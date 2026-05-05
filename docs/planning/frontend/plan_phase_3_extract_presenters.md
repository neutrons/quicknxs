# Plan: Phase 3 - Extract Presenters And Application Commands

Reference: [research_mvp_architecture.md](../research_mvp_architecture.md),
Frontend Phase 3.
Identity reference: [session_identity_contract.md](../session_identity_contract.md).

## Goal

Reduce `MainHandler` from a large UI-and-application coordinator into a wiring layer
while presenters own user-action orchestration.

Presenters should:

- Receive typed user intent from the view.
- Mutate model/session/backend services.
- Build view models.
- Ask the view to render those models.
- Translate domain failures into UI messages.

Presenters should not:

- Import Qt widgets.
- Reach into `self.ui`.
- Know widget names.
- Use run number as row identity.
- Depend on Mantid workspace globals directly.

## Inputs From Earlier Phases

Phase 3 assumes:

- Phase 1 view models, `IMainView`, configuration adapters, and row builders exist.
- Phase 1A identity rules define how presenters compare entry ID, run number, file
  path, object identity, and reduced-file `DB_ID`.
- Phase 2 direct-beam and reduction table render methods block their own signals.
- Duplicate-run-number behavior has characterization tests.

## Presenter Slices

### `ReductionPresenter`

Owns direct-beam and reduction-list actions:

- Direct-beam table cell edits.
- Reduction table cell edits.
- Add/remove/clear direct beams.
- Add/remove/clear reduction runs.
- Active direct-beam row changes.
- Active reduction row changes.
- Stitch reflectivity.
- Strip overlap.
- Trim data to normalization.
- Reload selected reduction files when the operation is table/session specific.

This presenter should be extracted first because it contains the highest-risk identity
rules.

### `FilePresenter`

Owns file and active-run workflows:

- Open/load Nexus files.
- Active cross-section changes.
- File-list rendering and selection.
- Run overview rendering.
- DAS log rendering.
- Calculated data display.
- Panel visibility toggles.

File loading can still call existing `DataManager` methods during Phase 3. The goal
is to move orchestration out of Qt slots, not to split `DataManager` yet.

### `PlotPresenter`

Owns plot-trigger decisions:

- Projection refresh requests.
- Reflectivity/intensity plot refresh requests.
- Offspec recompute-on-change.
- GISANS recompute-on-change.
- Plot option reads through `ConfigViewModel`.

`PlotManager` should remain a renderer. `PlotPresenter` decides when a plot needs to
be refreshed.

### Optional `ConfigurationPresenter`

Only extract this if configuration event handling becomes a blocker during Phase 3.
The full replacement of legacy `Configuration` belongs to the frontend
configuration/job phase.

## Implementation Steps

### Step 1: Define User-Action Inputs

Create small dataclasses or typed method inputs for actions that currently arrive as
raw Qt objects.

Examples:

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

### Step 2: Add Thin View Forwarders

In `MainWindow`, convert selected Qt slots into thin forwarders:

1. Read the minimal widget information needed to construct the typed action.
2. Resolve row-to-entry mapping from the table render state.
3. Emit or call the presenter-facing action.

The forwarder may know table column numbers. The presenter should receive a typed
action and should not inspect widgets.

### Step 3: Extract `ReductionPresenter`

Move the direct-beam and reduction table edit logic first.

For each migrated method:

1. Copy existing behavior into a presenter method.
2. Replace widget reads with typed action input.
3. Replace widget writes with view model rendering.
4. Replace broad update cascades with a named render method such as
   `_render_after_direct_beam_edit()`.
5. Add a unit test with a fake view and mocked model/session service.
6. Keep the old handler method as a bridge until call sites move.

Direct-beam/data-run row identity rules:

- Use entry ID for row mutation.
- Use run number for matching/display.
- Use explicit direct-beam entry ID for pairings where available.

### Step 4: Extract Add/Remove/Clear Operations

Move table-list operations into `ReductionPresenter` after cell edits are stable.

Operations:

- `add_direct_beam`
- `remove_direct_beam`
- `clear_direct_beams`
- `add_reflectivity`
- `remove_reflectivity`
- `clear_reflectivity`

Each operation should end by rebuilding row models and rendering the affected tables.

### Step 5: Extract `FilePresenter`

Move active file and cross-section workflows:

- `open_file`
- `file_loaded`
- `active_cross_section_changed`
- `active_data_changed`
- `update_file_list`
- `update_overview_run_info_from_active_run`
- `update_calculated_data`
- `update_cross_section_info`
- `update_daslog`

The render result should use view models:

- `RunOverviewModel`
- file-list model
- DAS log model
- cross-section button model
- status/progress messages

### Step 6: Extract `PlotPresenter`

Move plot-trigger decisions after file and table presenters have stable render
methods.

Inputs should be current session state and `ConfigViewModel`, not widget reads.

### Step 7: Collapse `MainHandler`

After each slice is migrated:

- Remove migrated handler methods.
- Keep wiring and construction in a small coordinator if needed.
- Prefer explicit presenter construction over hidden signal cascades.
- Delete obsolete bridge methods once there are no call sites.

## Tests

Add tests at three levels:

- Presenter unit tests with fake views and fake model/session services.
- Qt integration tests for thin view forwarders and table entry ID mapping.
- Characterization tests for full workflows that were previously handled by
  `MainHandler`.

Required duplicate-run-number tests:

- A direct-beam table edit targets one direct-beam entry with a duplicated run number.
- A reduction table edit targets one data entry with a duplicated run number.
- A data entry remains paired with the intended direct-beam entry after table rerender.

## Acceptance Criteria

- Direct-beam and reduction table edit flows are owned by `ReductionPresenter`.
- Add/remove/clear table operations are owned by `ReductionPresenter`.
- File loading and active cross-section orchestration are owned by `FilePresenter`.
- Plot refresh decisions are owned by `PlotPresenter`.
- Migrated presenters have no Qt widget imports.
- `MainHandler` no longer contains the migrated orchestration logic.
- Existing UI workflows continue to pass.

## Relationship To Other Plans

- Phase 2 supplies the mutation/render pattern presenters should follow.
- Phase 4 replaces the `DataManager` facade behind the presenters with smaller
  services.
- The backend facade plan makes presenter calls to backend persistence/reduction go
  through a backend facade.
- The frontend configuration/job plan removes legacy configuration and improves
  job/error boundaries used by presenters.
