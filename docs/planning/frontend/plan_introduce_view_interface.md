# Plan: Frontend Phase 1 - Stabilize Identity And View Contracts

**Part of the QuickNXS architecture migration.**
Reference: [research_mvp_architecture.md](../research_mvp_architecture.md),
"Split Migration Roadmap", Frontend Phase 1.
Identity reference: [session_identity_contract.md](../session_identity_contract.md).

Phase 1 is not a presenter extraction and not a backend adoption phase. It is a
contract-stabilization phase that prepares QuickNXS for the later table,
presenter, `DataManager`, backend I/O, and configuration splits while preserving
current behavior.

## Recommendation Reflected In This Version

Phase 1 is split into four subphases:

- **Phase 1A: Identity And Characterization**
- **Phase 1B: Read-Only View Models**
- **Phase 1C: Configuration Inventory**
- **Phase 1D: View Interface Preparation**

The work from the earlier Phase 1 plan is still valuable, but it should not land as
one large prerequisite patch. Phase 1A is the required first slice. The later
subphases can land incrementally as soon as their inputs are ready.

Backend reduced-file DTOs and parser/writer work are no longer Phase 1 acceptance
criteria. They belong to the backend roadmap. QuickNXS adoption of backend
reduced-file I/O is tracked as a future frontend integration plan after the identity
and configuration adapter work is stable enough.

## Goal

Make the implicit frontend contracts in the current application explicit without
changing live workflows.

Phase 1 should produce:

1. A documented identity model for source runs, loaded objects, reduction entries,
   direct-beam entries, additional peaks, and reduced-file `DB_ID` values.
2. Characterization tests that lock down current duplicate-run and copied-object
   behavior.
3. Plain Python row view models for the main table surfaces.
4. Read-only builders/adapters that can create view models from the current
   `DataManager`, `NexusData`, `CrossSectionData`, and `Configuration` objects.
5. A configuration field inventory and adapter sketch that preserve all current
   values while classifying them by future owner.
6. A narrow target `IMainView` protocol and fake view for future presenter tests.

The important constraint is that Phase 1 should avoid changing behavior. It should
add contracts, adapters, and tests around existing behavior so later phases can move
logic with confidence.

## Non-Goals

Do not do these in Phase 1:

- Do not extract `ReductionPresenter`, `FilePresenter`, or `PlotPresenter`.
- Do not replace `auto_change_active`.
- Do not change Qt signal names or user-action flow.
- Do not make table edits use entry IDs yet.
- Do not replace `Configuration` as the live runtime object.
- Do not split `DataManager`.
- Do not move save/load behavior to the backend.
- Do not add QuickNXS call sites for backend reduced-file I/O.
- Do not rewrite plotting, offspec, GISANS, or Mantid workspace handling.

Phase 1 can add target models and adapters, but the existing UI and reduction paths
should continue to run through the current classes.

## Phase 1A: Identity And Characterization

### Purpose

Define the identity rules before any table, presenter, I/O, or matching refactor
depends on them.

### Work

- Adopt [session_identity_contract.md](../session_identity_contract.md) as the
  source of truth for frontend identity decisions.
- Inventory current identity comparisons in `DataManager`, `MainHandler`,
  `quicknxs_io.py`, and direct-beam matching paths.
- Document which current comparisons are object identity, run-number identity,
  row-index identity, file-path identity, or reduced-file `DB_ID` identity.
- Add characterization tests for the current behavior before changing live mutation
  paths.

### Required Tests

- A data run added as a direct beam gets independent role-specific parameters from
  the data-run entry.
- A direct beam run added as a data run does not unintentionally share mutable
  role-specific parameters with its direct-beam entry.
- Two different `NexusData` objects with the same source run number are treated as
  different mutable entries in characterization tests.
- A copied `NexusData` object can have different row parameters from the source
  object.
- Existing direct-beam/data-run add and remove workflows still pass.
- Existing reduced-file parser tests still pass.

### Acceptance Criteria

- The identity contract is linked from the roadmap.
- The current comparison modes are documented in tests or comments.
- Duplicate-run-number characterization tests exist and pass.
- No live behavior is intentionally changed.

## Phase 1B: Read-Only View Models

### Purpose

Add plain Python snapshots for table and overview state so later phases can render
from explicit data rather than from broad live objects.

### Proposed File: `src/quicknxs/interfaces/view_models.py`

Add Qt-free dataclasses for the view boundary.

Suggested contents:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import NewType


EntryId = NewType("EntryId", str)


@dataclass(frozen=True)
class SourceRunViewModel:
    run_number: str
    file_path: str = ""
    cross_section: str = ""
    slice_number: int | None = None


@dataclass(frozen=True)
class RunOverviewModel:
    run_number: str = ""
    file_path: str = ""
    experiment: str = ""
    instrument: str = ""
    detector_angle: float | None = None
    sample_angle: float | None = None
    wavelength: float | None = None
    cross_section_labels: tuple[str, ...] = ()
    active_cross_section: str = ""
    matched_direct_beam: str = ""
    metadata_peak_roi: tuple[int, int] | None = None
    metadata_background_roi: tuple[int, int] | None = None


@dataclass(frozen=True)
class ReductionRowModel:
    entry_id: EntryId
    source: SourceRunViewModel
    is_active: bool = False
    direct_beam_entry_id: EntryId | None = None
    direct_beam_run_number: str = ""
    peak_position: float = 0.0
    peak_width: float = 0.0
    low_res_position: float = 0.0
    low_res_width: float = 0.0
    background_position: float = 0.0
    background_width: float = 0.0
    scaling_factor: float = 1.0
    scaling_error: float = 0.0
    subtract_background: bool = True
    cut_first: int = 0
    cut_last: int = 0
    binning_type: int = 0
    binning_q_step: float | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DirectBeamRowModel:
    entry_id: EntryId
    source: SourceRunViewModel
    is_active: bool = False
    peak_position: float = 0.0
    peak_width: float = 0.0
    low_res_position: float = 0.0
    low_res_width: float = 0.0
    background_position: float = 0.0
    background_width: float = 0.0
    direct_pixel: float | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class StatusMessageModel:
    message: str
    is_error: bool = False
    details: str = ""
```

Rules:

- Keep models immutable snapshots.
- Keep `EntryId` opaque. Do not expose assumptions such as row index, object ID, or
  run number in its public meaning.
- Keep models Qt-free and Mantid-free.
- Treat run number as source metadata only.

### Proposed File: `src/quicknxs/interfaces/view_model_builders.py`

Add read-only builders that convert current runtime state into view models.

Suggested functions:

```python
def build_direct_beam_row_models(data_manager: DataManager) -> tuple[DirectBeamRowModel, ...]:
    ...


def build_reduction_row_models(data_manager: DataManager) -> tuple[ReductionRowModel, ...]:
    ...


def build_run_overview_model(data_manager: DataManager) -> RunOverviewModel:
    ...
```

Entry ID guidance:

- Generate IDs from a small session-lifetime registry or adapter-local mapping, not
  from run number.
- Keep IDs stable for the lifetime of the current session where possible.
- Do not persist these IDs to reduced data files in Phase 1.
- Do not make the registry a new source of application truth. It is a bridge until
  Phase 4 moves entry IDs into the real session model.

Optional bridge:

```python
class SessionEntryIdRegistry:
    def direct_beam_id_for(self, nexus_data: NexusData) -> EntryId:
        ...

    def reduction_id_for(self, nexus_data: NexusData) -> EntryId:
        ...
```

### Required Tests

- `view_models.py` imports without Qt.
- Direct-beam and reduction row models include opaque entry IDs.
- Direct-beam list builds one `DirectBeamRowModel` per current direct-beam entry.
- Reduction list builds one `ReductionRowModel` per current data entry.
- Duplicate run numbers produce distinct row entry IDs for distinct entries.
- A data row linked to a direct beam records both display run number and exact
  direct-beam entry ID when that mapping is available.

### Acceptance Criteria

- View models and builders exist.
- Existing UI rendering still uses current paths unless a method can delegate
  without behavior changes.
- Entry IDs exist in snapshots but do not yet drive live table edits.

## Phase 1C: Configuration Inventory

### Purpose

Classify the legacy `Configuration` surface before backend adapters, reduced-file
adapters, or option models depend on it.

### Work

Create a field inventory from:

- `src/quicknxs/interfaces/configuration.py`
- `src/quicknxs/interfaces/event_handlers/main_handler.py`
- `src/quicknxs/interfaces/event_handlers/configuration_handler.py`
- `src/quicknxs/interfaces/data_handling/quicknxs_io.py`
- plotting/offspec/GISANS callers that read `configuration.*`

Record each field's current storage location:

- `Configuration` class attribute
- `Configuration` instance attribute
- computed property
- reduced-file label
- UI-only value

Record each field's target category:

- global reduction option
- loading option
- run reduction option
- direct-beam option
- peak-finder option
- angle override
- plot/view preference
- offspec option
- GISANS option
- persistence compatibility value

### Proposed File: `src/quicknxs/interfaces/config_view_model.py`

Add Qt-free models for configuration UI state and field classification.

Suggested structure:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GlobalReductionOptionsViewModel:
    sample_size: float
    wl_bandwidth: float
    binning_type_global: int
    binning_q_step_global: float
    normalize_to_unity: bool
    total_reflectivity_q_cutoff: float
    global_stitching: bool
    polynomial_stitching: bool
    polynomial_stitching_degree: int
    polynomial_stitching_points: int
    lock_direct_beam_y: bool


@dataclass(frozen=True)
class LoadingOptionsViewModel:
    tof_bins: int
    tof_range: tuple[float, float] | None
    tof_bin_type: int
    count_threshold: float
    nbr_events_min: int
    apply_deadtime: bool
    paralyzable_deadtime: bool
    deadtime_value: float
    deadtime_tof_step: int


@dataclass(frozen=True)
class RunReductionOptionsViewModel:
    peak_position: float
    peak_width: float
    low_res_position: float
    low_res_width: float
    background_position: float
    background_width: float
    subtract_background: bool
    scaling_factor: float
    scaling_error: float
    cut_first_n_points: int
    cut_last_n_points: int
    binning_type_run: int
    binning_q_step_run: float
    match_direct_beam: bool
    direct_beam_entry_id: str | None
    direct_beam_run_number: str | None


@dataclass(frozen=True)
class PeakFinderOptionsViewModel:
    use_roi: bool
    update_peak_range: bool
    use_peak_finder: bool
    use_low_res_finder: bool
    use_tight_bck: bool
    bck_offset: int
    use_metadata_bck_roi: bool


@dataclass(frozen=True)
class AngleOverrideOptionsViewModel:
    set_direct_pixel: bool
    direct_pixel_overwrite: float
    set_direct_angle_offset: bool
    direct_angle_offset_overwrite: float
    use_dangle: bool


@dataclass(frozen=True)
class PlotViewPreferencesViewModel:
    normalize_x_tof: bool
    x_wl_map: bool
    angle_map: bool
    log_1d: bool
    log_2d: bool


@dataclass(frozen=True)
class OffspecOptionsViewModel:
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GisansOptionsViewModel:
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConfigViewModel:
    global_reduction: GlobalReductionOptionsViewModel
    loading: LoadingOptionsViewModel
    run_reduction: RunReductionOptionsViewModel
    peak_finder: PeakFinderOptionsViewModel
    angle_overrides: AngleOverrideOptionsViewModel
    plot_preferences: PlotViewPreferencesViewModel
    offspec: OffspecOptionsViewModel
    gisans: GisansOptionsViewModel
    unknown_values: dict[str, Any] = field(default_factory=dict)
```

It is acceptable to start offspec/GISANS as grouped dictionaries with tests that
verify all current fields are captured.

### Proposed File: `src/quicknxs/interfaces/configuration_adapter.py`

Add adapters between the current `Configuration` object and `ConfigViewModel`.

Required functions:

```python
def config_view_model_from_configuration(configuration: Configuration) -> ConfigViewModel:
    ...


def apply_config_view_model_to_configuration(
    view_model: ConfigViewModel,
    configuration: Configuration | None = None,
) -> Configuration:
    ...
```

Rules:

- Preserve current class-level `Configuration` values where QuickNXS expects
  class-level behavior.
- Preserve instance-level values on the returned `Configuration`.
- Represent direct-beam pairing with `direct_beam_entry_id` where available and
  source run number only as display/compatibility metadata.
- Do not change live widget behavior in Phase 1.
- Add tests that enumerate expected fields and fail when a field is dropped.

### Required Tests

- `Configuration()` -> `ConfigViewModel` -> `Configuration()` preserves all known
  instance values.
- Current class-level global options are captured and reapplied.
- Offspec/GISANS fields are captured, even if grouped as dictionaries.
- Unknown or future fields are either preserved in `unknown_values` or explicitly
  listed as unsupported with a test explaining why.

### Acceptance Criteria

- Configuration field ownership is documented.
- Configuration adapters preserve current values in tests.
- Live runtime code still uses legacy `Configuration`.

## Phase 1D: View Interface Preparation

### Purpose

Prepare the narrow view boundary future presenters will use without pretending the
current handlers already satisfy that boundary.

### Design Principles

- Define `IMainView` as the target interface for future presenters.
- Add narrowly scoped display/read methods to `MainWindow` where they can delegate
  to existing behavior without changing it.
- Use fake views only for new presenter/view-model tests, not as drop-in
  replacements for current handlers.
- Do not annotate existing handlers as protocol consumers until their dependencies
  have actually been reduced.

### Proposed File: `src/quicknxs/interfaces/view_protocol.py`

Add the target view protocol. Keep it small and truthful.

Suggested contents:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from quicknxs.interfaces.config_view_model import ConfigViewModel
from quicknxs.interfaces.view_models import (
    DirectBeamRowModel,
    ReductionRowModel,
    RunOverviewModel,
    StatusMessageModel,
)


@runtime_checkable
class IMainView(Protocol):
    def show_run_overview(self, data: RunOverviewModel) -> None:
        ...

    def show_reduction_rows(self, rows: tuple[ReductionRowModel, ...]) -> None:
        ...

    def show_direct_beam_rows(self, rows: tuple[DirectBeamRowModel, ...]) -> None:
        ...

    def show_status_message(self, message: StatusMessageModel) -> None:
        ...

    def show_progress(self, value: float) -> None:
        ...

    def refresh_projection_plots(self) -> None:
        ...

    def refresh_reflectivity_plot(self) -> None:
        ...

    def get_config_view_model(self) -> ConfigViewModel:
        ...

    def set_config_view_model(self, view_model: ConfigViewModel) -> None:
        ...
```

Do not try to model Qt signals in the protocol. User-action signal typing belongs
with presenter extraction after the event surface is reduced.

### Proposed File: `test/unit/quicknxs/interfaces/fakes.py`

Add test fakes under `test/`, not `src/`.

Suggested fake:

```python
class FakeMainView:
    def __init__(self):
        self.run_overview: RunOverviewModel | None = None
        self.reduction_rows: tuple[ReductionRowModel, ...] = ()
        self.direct_beam_rows: tuple[DirectBeamRowModel, ...] = ()
        self.status_messages: list[StatusMessageModel] = []
        self.progress_values: list[float] = []
        self.projection_refresh_count = 0
        self.reflectivity_refresh_count = 0
        self.config_view_model: ConfigViewModel | None = None
```

### Optional `MainWindow` Methods

Add thin methods to `MainWindow` only where they can delegate to current behavior.

Suggested methods:

```python
def show_run_overview(self, data: RunOverviewModel) -> None:
    self.file_handler.update_overview_run_info_from_active_run()


def show_reduction_rows(self, rows: tuple[ReductionRowModel, ...]) -> None:
    self.file_handler.update_tables()


def show_direct_beam_rows(self, rows: tuple[DirectBeamRowModel, ...]) -> None:
    self.file_handler.update_tables()


def show_status_message(self, message: StatusMessageModel) -> None:
    self.file_handler.report_message(message.message, pop_up=message.is_error)


def show_progress(self, value: float) -> None:
    self.ui.progressBar.setValue(int(value * 100))


def refresh_projection_plots(self) -> None:
    self.initiate_projection_plot.emit(False)


def refresh_reflectivity_plot(self) -> None:
    self.initiate_reflectivity_or_intensity_plot.emit()
```

For `get_config_view_model()` and `set_config_view_model()`, either implement them
by calling the new configuration adapter plus existing widget mapping, or defer them
until `ConfigViewModel` coverage is complete. Do not add stub methods that silently
return incomplete data.

### Required Tests

- `view_protocol.py` imports without Qt.
- A small `FakeMainView` satisfies `IMainView` at runtime.
- The protocol does not import `MainWindow`, `MainHandler`, `DataManager`, or
  Mantid.
- `MainWindow` has target methods only where they are implemented truthfully.

### Acceptance Criteria

- A target view protocol exists.
- Fake view tests can be used by future presenters.
- Current handlers are not falsely typed against the protocol.

## Recommended Verification

Run focused tests for each subphase. Suggested commands:

```bash
pixi run ruff check src test
pixi run pytest test/unit/quicknxs/interfaces/test_configuration.py
pixi run pytest test/unit/quicknxs/interfaces/test_data_manager_direct_beam_mock.py
pixi run pytest test/unit/quicknxs/interfaces/data_handling/test_quicknxs_io.py
pixi run pytest test/ui/test_add_non_direct_beam.py test/ui/test_direct_beam_table.py
```

Run broader tests if a patch touches shared fixtures, `MainWindow`, or
`quicknxs_io.py`.

## Phase 1 Completion Definition

Phase 1 is complete when the target contracts exist, have tests, and describe the
current behavior accurately, but the running application still behaves as it did
before the phase started.

Completion requires:

- Phase 1A identity tests and contract adoption.
- Phase 1B read-only row models and builders.
- Phase 1C configuration inventory and adapter tests.
- Phase 1D target view protocol and fake view.

The end state should make later refactors smaller:

- Table identity no longer has to be invented during the reentrancy refactor.
- Presenters have view models and a view protocol ready to consume.
- Configuration splitting can proceed from a tested field inventory.
- Backend I/O adoption can use frontend adapters that already understand session
  entry identity.

## Risks And Mitigations

### Risk: Entry IDs Become A Second Source Of Truth

Mitigation: keep Phase 1 entry IDs in view models/builders only. The live session
state remains in `DataManager` until Phase 4.

### Risk: The New View Interface Lies About Current Dependencies

Mitigation: keep `IMainView` as a target protocol for new presenter work. Do not
pretend `MainHandler` only needs that surface until the handler is actually split.

### Risk: Configuration Field Coverage Is Incomplete

Mitigation: add tests that compare known class attributes, instance attributes, and
reduced-file labels against the adapter inventory.

### Risk: Too Much Work Lands In One Patch

Mitigation: land Phase 1 as the four subphases above. Phase 1A is mandatory first;
1B-1D can then proceed in small patches.

## Relationship To Later Phases

| Later phase | How it uses Phase 1 work |
|---|---|
| Phase 2: Replace shared reentrancy | Uses identity rules, row view models, and display methods so `blockSignals()` can be localized. |
| Phase 3: Extract presenters | Presenters consume `IMainView`, build view models, and can be tested with `FakeMainView`. |
| Phase 4: Split `DataManager` | Replaces adapter-local entry IDs with session-owned entry IDs and dedicated repositories. |
| Phase 5: Configuration, jobs, errors | Replaces legacy `Configuration` usage with the option groups introduced by `ConfigViewModel` and adapters. |
| Backend reduced-file I/O | Uses the same identity contract and later frontend adapters, but backend DTO/parser/writer work is tracked in the backend roadmap. |
