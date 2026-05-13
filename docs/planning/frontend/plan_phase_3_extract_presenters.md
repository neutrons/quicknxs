# Plan: Phase 3 - Extract Presenters And Application Commands

Reference: [research_mvp_architecture.md](../research_mvp_architecture.md),
Frontend Phase 3.
Identity reference: [session_identity_contract.md](../session_identity_contract.md).

## Goal

Introduce one presenter per view and an event broker. Retire `MainHandler` as an
application coordinator by migrating its orchestration logic into focused
presenters.

After Phase 3:

- Each view class is paired with exactly one presenter that holds a direct
  reference to it.
- User actions flow from view callbacks into presenter handler methods.
- Model services publish typed domain events after state mutations.
- Presenters subscribe to domain events and call their own view's render methods
  on receipt.
- Presenters coordinate through the event broker; they do not hold direct
  references to each other.
- `MainHandler` is retired or reduced to a thin wiring layer with no orchestration
  logic.

Presenters should:

- Receive typed user intent from view callbacks.
- Mutate frontend model/session services and call backend adapters where
  appropriate.
- Translate domain failures into UI messages.

Presenters should not:

- Import Qt widgets.
- Reach into `self.ui`.
- Know widget names.
- Use run number as row identity.
- Depend on Mantid workspace globals directly.
- Publish domain events — that is the model service's responsibility.
- Hold references to other presenters.

Model services should:

- Publish a domain event after any state mutation that other components need to
  observe.
- Not import Qt.
- Not hold references to views or presenters.

Views should:

- Declare user-action hooks as callable attributes or Qt signal connection points.
- Declare render methods that accept typed view model payloads.
- Apply `blockSignals()` locally inside render methods.
- Not subscribe to or publish events on the event broker.

## Inputs From Earlier Phases

Phase 3 assumes:

- Phase 1 view models, focused view classes, configuration adapters, and row
  builders exist.
- Phase 1 view classes expose render methods and user-action hooks.
- Phase 1A identity rules define how presenters compare entry ID, run number, file
  path, object identity, and reduced-file `DB_ID`.
- Phase 2 direct-beam and reduction table render methods block their own signals.
- Duplicate-run-number behavior has characterization tests.

## Event Broker

### Design

The event broker is a plain Python object with no Qt dependency. It is
instantiated once in the composition root (`MainWindow` or application startup)
and passed to all presenters and model services at construction.

```python
class EventBroker:
    def subscribe(self, event_type: type, handler: Callable) -> None: ...
    def publish(self, event: object) -> None: ...
```

Dispatch is synchronous. When `publish` is called, all registered handlers for
that event type are called before `publish` returns.

### Reentrancy constraint

A subscriber must not cause the same event type to be published again during its
own handling of that event. Document this constraint on the broker; enforce it
mechanically in a later phase if needed.

### Initial event taxonomy

Events are plain Python dataclasses with no Qt dependency:

```python
@dataclass(frozen=True)
class RunLoadedEvent:
    run_number: int
    entry_id: EntryId

@dataclass(frozen=True)
class ActiveRunChangedEvent:
    entry_id: EntryId

@dataclass(frozen=True)
class FileListChangedEvent:
    pass

@dataclass(frozen=True)
class DirectBeamEntryUpdatedEvent:
    entry_id: EntryId

@dataclass(frozen=True)
class DirectBeamListChangedEvent:
    pass

@dataclass(frozen=True)
class ReductionListChangedEvent:
    pass

@dataclass(frozen=True)
class GlobalOptionsChangedEvent:
    pass

@dataclass(frozen=True)
class RunOptionsUpdatedEvent:
    entry_id: EntryId

@dataclass(frozen=True)
class ReductionResultReadyEvent:
    entry_id: EntryId

@dataclass(frozen=True)
class StitchingCompletedEvent:
    entry_ids: tuple[EntryId, ...]

@dataclass(frozen=True)
class IntensityDataReadyEvent:
    entry_id: EntryId
```

Extend the taxonomy as new event needs are discovered during migration. Keep each
event type focused on one state change.

## Presenter Slices

Extraction follows coupling risk (highest risk first).

### 1. `DirectBeamTablePresenter`

Owns direct-beam table actions:

- Direct-beam table cell edits.
- Add/remove/clear direct beams.
- Active direct-beam row selection changes.

Subscribes to: `DirectBeamEntryUpdatedEvent`, `DirectBeamListChangedEvent`,
`ActiveRunChangedEvent`.

This presenter is extracted first because it contains the highest-risk identity
rules.

### 2. `ReductionTablePresenter`

Owns reduction-table actions and reduction-list commands, even when the current UI
exposes a command from the main toolbar:

- Reduction table cell edits.
- Add/remove/clear data runs.
- Active reduction row selection changes.
- Stitch reflectivity and update scale factors for affected reduction entries.
- Strip overlap.
- Trim to normalization.
- Reload selected reduction files.

The main-window toolbar stitch button should be exposed as a user-action hook on
the reduction table/action view and handled by `ReductionTablePresenter`. It does
not need a separate toolbar presenter unless the toolbar later grows independent
state and workflows.

Subscribes to: `ReductionListChangedEvent`, `DirectBeamEntryUpdatedEvent`,
`ReductionResultReadyEvent`, `StitchingCompletedEvent`.

### 3. `RunOptionsPresenter`

Owns the per-run options form:

- Peak position, background, and scaling parameter edits for the active run.

Subscribes to: `ActiveRunChangedEvent`, `RunOptionsUpdatedEvent`.

### 4. `GlobalOptionsPresenter`

Owns the global options form:

- Global reduction settings.
- Normalization options.
- Dead-time correction toggle.
- Other configuration-wide form fields.

Subscribes to: `GlobalOptionsChangedEvent`.

### 5. `FileListPresenter`

Owns file and active-run workflows:

- Open/load Nexus files.
- File list rendering and active file selection.
- Active run changes triggered from the file list.

Subscribes to: `RunLoadedEvent`, `FileListChangedEvent`, `ActiveRunChangedEvent`.

### 6. `RunOverviewPresenter`

Owns the run overview panel:

- Detector image and overview rendering.
- Cross-section selector.
- DAS log table rendering.
- Calculated data display.
- Panel visibility toggles.

Subscribes to: `ActiveRunChangedEvent`, `RunLoadedEvent`.

### 7. `IntensityPlotPresenter`

Owns intensity plot trigger decisions:

- XY, X-TOF, and overview intensity plot refresh.
- Intensity plot option changes.

Subscribes to: `ActiveRunChangedEvent`, `IntensityDataReadyEvent`.

### 8. `ReflectivityPlotPresenter`

Owns reflectivity plot trigger decisions:

- Reflectivity and compare-plot refresh.
- Off-specular and GISANS recompute-on-change guards.
- Reflectivity plot option changes.

Subscribes to: `ReductionResultReadyEvent`, `ReductionListChangedEvent`,
`GlobalOptionsChangedEvent`, `StitchingCompletedEvent`.

## Implementation Steps

### Step 1: Introduce the event broker

Create `interfaces/event_broker.py` with the `EventBroker` class and the initial
event dataclasses. Add unit tests for subscription and synchronous dispatch.

During Phase 3, `DataManager` acts as the initial event publisher because the
dedicated model services (`DirectBeamRepository`, `ReductionRunRepository`, etc.)
do not exist until Phase 4. Mutation methods on `DataManager` should publish the
relevant domain events after each state change. Phase 4 transfers publishing
responsibility to each split service when it is extracted.

### Step 2: Decompose `MainWindow` into focused view classes

For each presenter slice:

1. Extract the relevant widgets, render methods, and user-action hooks into a
   dedicated view class (e.g., `DirectBeamTableView`).
2. Have `MainWindow` instantiate and host each view class.
3. Keep the extracted view class as a Qt widget child of `MainWindow`'s layout.

The extraction can be incremental: start with the tables (highest coupling), then
options views, then file and overview views, then plot views.

### Step 3: Define user-action inputs

Create small frozen dataclasses for actions that currently arrive as raw Qt
objects:

```python
@dataclass(frozen=True)
class TableCellEdit:
    entry_id: EntryId
    column: int
    value: object


@dataclass(frozen=True)
class ActiveEntryChange:
    entry_id: EntryId
```

Avoid passing `QTableWidgetItem`, row index, or widget objects into presenters.

### Step 4: Add view forwarders and user-action hooks

In each view class:

1. Connect Qt signals to internal handler methods.
2. The internal handler reads the minimum widget state needed.
3. It resolves row-to-entry mapping from the view's current render state.
4. It calls the registered presenter callback with a typed action.

Example:

```python
class DirectBeamTableView(QWidget):
    def __init__(self):
        super().__init__()
        self.on_cell_edited: Callable[[TableCellEdit], None] | None = None
        self._table.cellChanged.connect(self._on_cell_changed)

    def _on_cell_changed(self, row: int, col: int) -> None:
        entry_id = self._entry_ids[row]
        value = self._table.item(row, col).text()
        if self.on_cell_edited:
            self.on_cell_edited(TableCellEdit(entry_id, col, value))

    def render_rows(self, rows: list[DirectBeamRowViewModel]) -> None:
        with signals_blocked(self._table):
            # populate table from rows
            ...
```

### Step 5: Extract `DirectBeamTablePresenter`

For each migrated method:

1. Copy existing behavior into a presenter method.
2. Replace widget reads with typed action input from the view hook.
3. Call the model service to mutate state.
4. The model service publishes a domain event.
5. Register a broker subscription to receive the event and call
   `self._view.render_rows(rows)`.
6. Add a unit test with a fake view and a real or fake event broker.
7. Keep the old handler method as a bridge until call sites move.

Direct-beam/data-run row identity rules:

- Use entry ID for row mutation.
- Use run number for matching/display.
- Use explicit direct-beam entry ID for pairings where available.

### Step 6: Extract `ReductionTablePresenter`

Same pattern as Step 5. Register subscriptions on `ReductionListChangedEvent` and
`DirectBeamEntryUpdatedEvent`.

### Step 7: Extract `RunOptionsPresenter` and `GlobalOptionsPresenter`

Register subscriptions on `ActiveRunChangedEvent` and `GlobalOptionsChangedEvent`
respectively.

### Step 8: Extract `FileListPresenter` and `RunOverviewPresenter`

Move active file and cross-section workflows. These presenters can still call
existing `DataManager` methods during Phase 3. The goal is to move orchestration
out of Qt slots, not to split `DataManager` yet.

### Step 9: Extract `IntensityPlotPresenter` and `ReflectivityPlotPresenter`

Move plot-trigger decisions after file and table presenters have stable event
subscriptions.

Inputs should be current session state from model services, not widget reads.

### Step 10: Collapse `MainHandler`

After each slice is migrated:

- Remove migrated handler methods.
- Keep `MainHandler` as a thin wiring layer if needed for construction.
- Delete obsolete bridge methods once there are no call sites.
- Prefer explicit presenter construction over hidden signal cascades.

## Tests

Add tests at three levels:

- Event broker unit tests: subscription, synchronous dispatch, and reentrancy
  detection.
- Presenter unit tests with a fake view (plain object or
  `MagicMock(spec=ViewClass)`) and a real or fake event broker.
- Qt integration tests for view forwarder methods and table entry-ID mapping.
- Characterization tests for full workflows previously handled by `MainHandler`.

Required duplicate-run-number tests:

- A direct-beam table edit targets one direct-beam entry with a duplicated run
  number.
- A reduction table edit targets one data entry with a duplicated run number.
- A data entry remains paired with the intended direct-beam entry after table
  re-render.
- The toolbar stitch action is routed through `ReductionTablePresenter`, updates
  affected reduction-row view models, and triggers reflectivity plot refresh through
  `StitchingCompletedEvent`.

## Acceptance Criteria

- One presenter exists per view; each presenter holds a reference to its concrete
  view.
- The event broker is instantiated at the composition root and passed to all
  presenters and model services.
- Model services publish domain events after state mutations; presenters do not
  publish domain events.
- Presenters subscribe to domain events and re-render their views on receipt.
- Views do not subscribe to or publish events on the event broker.
- The stitch toolbar action is handled by `ReductionTablePresenter`, not a separate
  toolbar presenter.
- Migrated presenters have no Qt widget imports.
- `MainHandler` contains no orchestration logic for migrated paths.
- Existing UI workflows continue to pass.

## Relationship To Other Plans

- Phase 2 supplies the mutation/render pattern and `signals_blocked` context
  manager that view render methods should use.
- Phase 4 replaces the `DataManager` facade behind the presenters with smaller
  services that publish their own domain events.
- The backend facade plan makes presenter calls to backend persistence/reduction
  go through a backend facade.
- The frontend configuration/job plan removes legacy configuration and improves
  job/error boundaries used by presenters.
