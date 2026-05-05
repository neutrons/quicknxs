# Plan: Parallel Backend Phases In `mr_reduction`

This plan defines backend-only phases that can proceed in parallel with the
QuickNXS architecture plan. The source code for this work lives in
`../MagnetismReflectometer`, primarily under `src/mr_reduction`.

The intent is to make `mr_reduction` the stable backend home for reduction,
calculation, matching, stitching, export, and file-format responsibilities that
QuickNXS can eventually call. This plan does not require QuickNXS to call those APIs
yet.

## Scope

In scope:

- Backend APIs in `mr_reduction`.
- Backend data models, request/result objects, and validation.
- Backend tests using `../MagnetismReflectometer/tests`.
- Consolidating duplicate behavior where similar logic exists in QuickNXS and
  `mr_reduction`.
- Adding compatibility fixtures or golden tests that describe current QuickNXS
  behavior without importing QuickNXS UI/runtime objects.

Out of scope:

- Changes in QuickNXS to call the backend APIs.
- QuickNXS UI, presenter, `DataManager`, or table-state changes.
- Moving QuickNXS `NexusData`, `CrossSectionData`, or `Configuration` into the
  backend.
- Backend imports from QuickNXS.

## Compatibility With The Existing Plan

This plan runs beside the active QuickNXS plan in
[overview.md](../overview.md). It is compatible because each phase produces backend
contracts that QuickNXS can adopt later through adapters.

The QuickNXS-side architecture plan remains responsible for:

- view/presenter changes,
- session entry identity,
- QuickNXS adapters,
- GUI state reconstruction,
- deciding when QuickNXS starts calling backend APIs.

This backend plan is responsible for:

- defining backend contracts,
- implementing backend calculation/file-format behavior,
- testing backend behavior independently,
- avoiding QuickNXS runtime dependencies.

All backend phases that represent direct-beam/data-run pairing, candidate matching,
or reduced-file references should follow the identity rules in
[session_identity_contract.md](../session_identity_contract.md).

## Existing Backend Starting Points

Current `mr_reduction` modules already cover part of the target backend:

- `mr_reduction.mr_reduction.ReductionProcess`: autoreduction orchestration and
  `MagnetismReflectometryReduction` invocation.
- `mr_reduction.reflectivity_output`: current autoreduction `.dat` writer.
- `mr_reduction.reflectivity_merge`: current matching, scaling, stitching, and
  combined-output behavior for autoreduced curves.
- `mr_reduction.mr_direct_beam_finder`: direct-beam discovery from run metadata.
- `mr_reduction.data_info`: data type classification, ROI extraction, and peak data.
- `mr_reduction.filter_events`: raw NeXus event splitting into cross-sections.
- `mr_reduction.dead_time_correction`: dead-time correction logic.
- `mr_reduction.io_orso`: ORSO output.
- `mr_reduction.beam_options`: current direct/reflected beam option models used by
  output writing.

The phases below should reuse and evolve these modules rather than create
parallel implementations.

## Shared Backend Contract Guidelines

All phases should follow these rules:

- No imports from `quicknxs`.
- No Qt dependencies.
- Public APIs accept plain dataclasses, paths, primitive values, NumPy arrays, or
  Mantid workspace handles where Mantid is inherently required.
- Public APIs return explicit result objects, not UI messages.
- Run number is source-run identity; it is not sufficient for mutable QuickNXS table
  entry identity.
- Caller-owned entry or candidate IDs should be accepted whenever a backend API must
  return the exact selected object from a caller-provided list.
- File-local reduced-file IDs such as `DB_ID` should identify direct-beam entries,
  not run numbers.
- Preserve physical units in field names or docstrings.
- Keep Mantid ADS workspace names contained behind helper objects where practical.
- Add golden/characterization tests before changing behavior that already exists in
  QuickNXS or `mr_reduction`.

## Backend Phase 1: Backend API Contracts And Common Models

This is the only coordination phase. It should be small and can be done before
or alongside the functional phases. It is not a hard blocker: a functional phase
may define local request/result models first and converge on the shared models
later.

### Goal

Define common backend request/result dataclasses so each functional phase can
expose APIs that fit together.

### Proposed Modules

- `src/mr_reduction/api.py`
- `src/mr_reduction/models.py`
- `src/mr_reduction/results.py`
- `src/mr_reduction/workspaces.py`

### Candidate Models

```python
from typing import Any, NewType


BackendEntryId = NewType("BackendEntryId", str)
BackendCandidateId = NewType("BackendCandidateId", str)


@dataclass(frozen=True)
class SourceRun:
    run_number: str
    file_path: str = ""
    cross_section: str = ""
    peak_number: int | None = None
    slice_number: int | None = None


@dataclass(frozen=True)
class RoiRange:
    minimum: int
    maximum: int


@dataclass(frozen=True)
class ReductionOptions:
    q_min: float = 0.001
    q_step: float = -0.02
    use_sangle: bool = True
    constant_q_binning: bool = False
    subtract_background: bool = True


@dataclass(frozen=True)
class Curve1D:
    q: np.ndarray
    r: np.ndarray
    dr: np.ndarray
    dq: np.ndarray | None = None
    theta: np.ndarray | None = None


@dataclass(frozen=True)
class BackendMessage:
    level: str
    text: str
    code: str = ""


@dataclass(frozen=True)
class DirectBeamReference:
    entry_id: BackendEntryId
    source: SourceRun


@dataclass(frozen=True)
class DirectBeamCandidate:
    candidate_id: BackendCandidateId
    source: SourceRun
    options: dict[str, Any]
```

### Acceptance Criteria

- Common models import without Mantid where possible.
- Mantid-specific types are isolated in a small workspace module.
- Functional phases can depend on these models without importing each other
  unnecessarily.
- Shared models distinguish source run metadata from caller-owned entry or candidate
  identity.

## Backend Phase 2: Reduced Data File I/O

### Goal

Make `mr_reduction` own canonical reduced-data-file parsing and writing.

### Existing Starting Points

- `mr_reduction.reflectivity_output`
- `mr_reduction.reflectivity_merge.write_reflectivity_cross_section`
- QuickNXS current behavior documented in
  [plan_reduced_data_file_io_backend_migration.md](plan_reduced_data_file_io_backend_migration.md)

### Proposed Backend API

```python
def read_reduced_data_file(path: str | Path) -> ReducedDataFile:
    ...


def write_reduced_data_file(path: str | Path, model: ReducedDataFile) -> None:
    ...
```

### Work

- Add backend `ReducedDataFile` models.
- Parse QuickNXS-produced and `mr_reduction`-produced files.
- Write the canonical QuickNXS-loadable format.
- Preserve direct-beam entries, data-run entries, global options, additional peak
  sections, and combined reflectivity curves.
- Preserve duplicate run numbers in distinct roles.
- Represent direct-beam/data-run pairings by direct-beam entry reference, not by run
  number.
- Treat `DB_ID` as a file-local direct-beam entry reference.
- Preserve unknown columns and sections where feasible.

### Tests

- Golden parser tests for existing QuickNXS-style fixtures.
- Golden parser tests for current `mr_reduction` output.
- Writer tests for canonical sections.
- Round-trip tests for duplicate run numbers and direct-beam pairings.
- Tests proving `DB_ID` does not collapse duplicate direct-beam run numbers.

## Backend Phase 3: Direct Beam Matching

### Goal

Provide a backend matching service that can be used by autoreduction and eventually
QuickNXS.

### Existing Starting Points

- `mr_reduction.mr_direct_beam_finder.DirectBeamFinder`
- `mr_reduction.data_info.DataType`
- QuickNXS `DataManager._find_direct_beam()` behavior, which currently uses
  configured run numbers and direct-beam lists.

### Proposed Backend API

```python
def match_direct_beam(request: DirectBeamMatchRequest) -> DirectBeamMatchResult:
    ...
```

The request should support two modes:

- Metadata search mode: search directories/databases for a matching direct beam.
- Candidate-list mode: choose from direct-beam candidates supplied by a caller.

Candidate-list mode is important for future QuickNXS use because QuickNXS may have
multiple direct-beam entries with the same source run number but different role-
specific parameters.

### Work

- Extract matching criteria from `DirectBeamFinder` into a testable matching service.
- Represent wavelength, slit gaps, run number, data type, and tolerance explicitly.
- Return no-match and ambiguous-match results instead of only `None` or a run number.
- Preserve existing autoreduction behavior as a wrapper over the new service.
- Require candidate IDs in candidate-list request/result models so a future GUI
  adapter can preserve exact entry identity.

### Tests

- Match by wavelength and slit gaps.
- Match with `skip_slits`.
- Match with and without later runs.
- No-match result.
- Ambiguous candidate-list result.
- Candidate-list result preserves candidate ID even when run numbers duplicate.

## Backend Phase 4: Specular Reflectivity Calculation

### Goal

Expose a backend specular reflectivity API that covers the current
`MagnetismReflectometryReduction` invocation and can eventually replace QuickNXS
frontend calculation logic.

### Existing Starting Points

- `mr_reduction.mr_reduction.ReductionProcess.reduce_workspace_group`
- QuickNXS `CrossSectionData.reflectivity()` and
  `CrossSectionData.calculate_reflectivity()`

### Proposed Backend API

```python
def calculate_reflectivity(request: ReflectivityCalculationRequest) -> ReflectivityCalculationResult:
    ...
```

### Work

- Define request models for data workspace, optional direct-beam workspace, ROI
  ranges, background ranges, low-resolution ranges, TOF range, q-step, constant-Q
  binning, scaling, cut points, and angle options.
- Extract common `MagnetismReflectometryReduction` call construction from
  `ReductionProcess`.
- Preserve output workspace and numerical curve data.
- Return `Curve1D` data plus backend metadata and messages.
- Keep existing `ReductionProcess` behavior by delegating to the new service where
  practical.

### Tests

- Existing autoreduction integration tests still pass.
- Backend API can reduce a known fixture.
- Direct-beam normalization on/off.
- ROI/background/low-resolution options are reflected in the Mantid call.
- Cut/scaling options preserve current numerical behavior.

## Backend Phase 5: Stitching, Scaling, Merging, And Normalize-To-Unity

### Goal

Consolidate stitching and curve-combination behavior in the backend.

### Existing Starting Points

- `mr_reduction.reflectivity_merge`
- QuickNXS `data_manipulation.stitch_reflectivity`
- QuickNXS `data_manipulation.merge_reflectivity`
- QuickNXS normalize-to-unity behavior during stitching

### Proposed Backend API

```python
def compute_stitching(request: StitchingRequest) -> StitchingResult:
    ...


def merge_reflectivity_curves(request: MergeCurvesRequest) -> MergeCurvesResult:
    ...


def normalize_to_unity(curve: Curve1D, q_cutoff: float) -> NormalizedCurve:
    ...
```

### Work

- Define curve DTOs independent of QuickNXS `CrossSectionData`.
- Support Mantid `Stitch1D` behavior and polynomial fit scaling behavior.
- Preserve scale factor and scale error outputs.
- Support global stitching across cross-sections where current behavior requires it.
- Represent overlap trimming decisions explicitly.
- Preserve existing autoreduction combined-curve behavior.

### Tests

- Known two-curve scale factor.
- Polynomial stitching scale factor.
- Scale error preservation.
- Normalize-to-unity success and no-data-below-cutoff failure.
- Multi-cross-section/global stitching behavior.
- Compatibility with existing `reflectivity_merge` integration tests.

## Backend Phase 6: Off-Specular Reflectivity Calculation

### Goal

Move off-specular calculation and rebinning algorithms into backend APIs.

### Existing Starting Points

- QuickNXS `quicknxs.interfaces.data_handling.off_specular`
- Backend has no equivalent full API today.

### Proposed Backend API

```python
def calculate_offspecular(request: OffspecCalculationRequest) -> OffspecCalculationResult:
    ...


def rebin_offspecular(request: OffspecRebinRequest) -> OffspecRebinResult:
    ...
```

### Work

- Define input models for processed detector data, TOF edges, geometry, direct pixel,
  peak ROI, low-resolution ROI, background, proton charge, scaling, and optional
  direct-beam normalization data.
- Port reciprocal-space calculations for `Qx`, `Qz`, `ki_z`, `kf_z`, and
  `ki_z - kf_z`.
- Port background subtraction and direct-beam normalization behavior.
- Port weighted and unweighted 2D binning.
- Preserve current axis modes: `Qx` vs `Qz`, `ki_z` vs `kf_z`,
  and `ki_z - kf_z` vs `Qz`.
- Return numerical grids and metadata, not plot objects.

### Tests

- Small synthetic detector arrays with known geometry.
- Direct-beam normalization with nonzero and zero normalization bins.
- Weighted and unweighted rebinning.
- Axis-mode coverage.
- Regression tests from existing QuickNXS fixtures if suitable data can be copied or
  generated in backend tests.

## Backend Phase 7: GISANS Calculation

### Goal

Move GISANS calculation, merge, and wavelength-band rebinning into backend APIs.

### Existing Starting Points

- QuickNXS `quicknxs.interfaces.data_handling.gisans`
- Backend has no equivalent full API today.

### Proposed Backend API

```python
def calculate_gisans(request: GisansCalculationRequest) -> GisansCalculationResult:
    ...


def rebin_gisans(request: GisansRebinRequest) -> GisansRebinResult:
    ...
```

### Work

- Define input models for detector data, TOF edges, geometry, direct pixel, peak
  position, low-resolution position, cut points, proton charge, scaling, and optional
  direct-beam normalization data.
- Port `Qy`, `Qz`, `p_f`, wavelength, intensity, and uncertainty calculations.
- Preserve current QuickNXS compatibility behavior where it uses the full detector
  area for GISANS.
- Port wavelength-band merging and optional `p_f` vertical-axis behavior.
- Avoid multiprocessing in the core API unless it is behind an explicit option.

### Tests

- Small synthetic detector arrays with known geometry.
- Direct-beam normalization.
- Wavelength filtering.
- `Qz` and `p_f` axis modes.
- Multi-band rebinning.

## Backend Phase 8: Run Metadata, ROI, Peak Finding, And Data Type Classification

### Goal

Make backend metadata extraction and ROI/peak selection the canonical implementation.

### Existing Starting Points

- `mr_reduction.data_info`
- `mr_reduction.inspect_data`
- `mr_reduction.peak_finding`
- QuickNXS metadata and instrument helpers in `data_handling.instrument` and
  `NexusMetaData`

### Proposed Backend API

```python
def inspect_reflectometry_run(request: RunInspectionRequest) -> RunInspectionResult:
    ...
```

### Work

- Expose data type classification from metadata variable `data_type`.
- Return direct-beam/reflected-beam/unknown as backend enum values.
- Return peak ROI, background ROI, low-resolution ROI, TOF range, direct pixel,
  angles, wavelength range, slit metadata, and cross-section labels.
- Preserve forced ROI and update-peak-range options.
- Keep Mantid workspace inspection separate from file/session adapters.

### Tests

- Direct beam, reflected beam, and missing `data_type` behavior.
- Low event count classification.
- Forced ROI behavior.
- Metadata ROI behavior.
- Cross-section label mapping.

## Backend Phase 9: Raw NeXus Loading, Cross-Section Splitting, And Dead-Time Correction

### Goal

Provide backend APIs for raw event loading/splitting and correction steps that are
scientific reduction concerns rather than GUI concerns.

### Existing Starting Points

- `mr_reduction.filter_events.split_events`
- `mr_reduction.dead_time_correction`
- QuickNXS raw loading and correction paths in `NexusData` and `Instrument`

### Proposed Backend API

```python
def load_reflectometry_run(request: LoadRunRequest) -> LoadRunResult:
    ...


def split_cross_sections(request: SplitCrossSectionsRequest) -> SplitCrossSectionsResult:
    ...


def apply_dead_time_correction(request: DeadTimeCorrectionRequest) -> DeadTimeCorrectionResult:
    ...
```

### Work

- Standardize file path and workspace naming behavior.
- Expose cross-section splitting independent of autoreduction scripts.
- Preserve slow-flipper and polarization-log options.
- Standardize event-count filtering.
- Expose dead-time correction options and results.

### Tests

- Existing `filter_events` tests.
- Existing dead-time correction tests.
- Loading/splitting known fixtures.
- Workspace cleanup behavior.

## Backend Phase 10: Output And Export Artifacts

### Goal

Consolidate output artifact creation in the backend.

### Existing Starting Points

- `mr_reduction.reflectivity_output`
- `mr_reduction.io_orso`
- `mr_reduction.script_output`
- `mr_reduction.web_report`
- `mr_reduction.reflectivity_merge.combined_catalog_info`
- QuickNXS output/export paths listed below.

### Existing QuickNXS Logic To Consolidate

The following QuickNXS functions contain backend-candidate output logic. They should
be used as characterization targets when designing Phase 10 APIs. The Qt dialogs and
live `DataManager` orchestration should stay in QuickNXS adapters, but the artifact
model construction, format-specific serialization, and reusable packaging rules
belong in backend APIs.

#### Main export workflow

- `quicknxs.interfaces.data_handling.processing_workflow.ProcessingWorkflow.execute`
  currently loops over peak reduction lists, chooses which artifact groups to write
  from output options, triggers specular/offspec/GISANS export methods, tracks
  exported files, and optionally sends results by email. Backend Phase 10 should
  replace this with a backend output request/result API. QuickNXS should still own
  progress UI and session-to-request adaptation.
- `quicknxs.interfaces.data_handling.processing_workflow.ProcessingWorkflow.get_file_name`
  applies the output filename template using instrument name, run numbers, peak
  number, artifact type, polarization state, and extension. This naming policy should
  move to a backend output-name helper that accepts explicit metadata instead of
  reading `DataManager`.

#### Specular reflectivity outputs

- `ProcessingWorkflow.specular_reflectivity` gathers combined reflectivity output and
  writes QuickNXS `.dat`, ORSO, NumPy `.npz`, Matlab `.mat`, and Mantid script
  outputs. Backend Phase 10 should provide equivalent writers over backend result
  models. The specular calculation itself belongs to Backend Phase 4, and
  stitching/merged curve construction belongs to Backend Phase 5.
- `ProcessingWorkflow.get_output_data` converts scaled reflectivity workspaces into
  output arrays, sorts by `Qz`, carries `dQz` and `theta`, and computes spin
  asymmetry output when requested. The backend output API should consume a typed
  curve model with these fields; any remaining curve assembly that is not purely
  display-specific should be moved to Backend Phase 5 or Phase 10.
- `ProcessingWorkflow.write_quicknxs` writes one QuickNXS-style `.dat` file per
  output state by combining output arrays with `quicknxs_io` header/data writers.
  The reduced `.dat` writer is primarily Backend Phase 2 work, but Phase 10 should
  call the same backend writer when producing output artifacts.
- `quicknxs.interfaces.data_handling.quicknxs_io.write_reflectivity_header`,
  `quicknxs.interfaces.data_handling.quicknxs_io._get_cross_section_config_values`,
  and `quicknxs.interfaces.data_handling.quicknxs_io.write_reflectivity_data`
  contain the current reduced `.dat` header, section, option, and numerical data
  serialization logic. Backend Phase 2 owns the parser/writer migration; Backend
  Phase 10 should reuse that backend writer for artifact generation.
- `ProcessingWorkflow.write_orso` saves individual and combined ORSO files. It also
  creates combined Mantid workspaces from output arrays and copies logs from the
  first workspace. This logic should move behind backend ORSO/output APIs that accept
  backend curve and metadata models rather than QuickNXS `DataManager` state.
- `quicknxs.interfaces.data_handling.data_manipulation.generate_short_script` and
  `quicknxs.interfaces.data_handling.data_manipulation.generate_script` produce
  Mantid Python script output from reflectivity workspaces and crop/scale settings.
  This should converge with `mr_reduction.script_output`.

#### Off-specular and GISANS output artifacts

- `ProcessingWorkflow.offspec` coordinates raw, smoothed, binned, and slice
  off-specular artifact writing. The numerical off-specular calculation and rebinning
  belong to Backend Phase 6; Phase 10 should own serialization of the resulting
  backend models into output artifacts.
- `ProcessingWorkflow.get_offspec_data` converts per-run off-specular results into
  output dictionaries with `Qx`, `Qz`, `ki_z`, `kf_z`, `ki_z-kf_z`, intensity, and
  uncertainty columns.
- `ProcessingWorkflow.get_rebinned_offspec_data` builds binned off-specular output
  tables and slice output tables from `off_specular.rebin_extract`.
- `ProcessingWorkflow.smooth_offspec` builds smoothed off-specular output grids and
  slice tables. The smoothing calculation itself should align with Backend Phase 6;
  the output model/serialization should align with Phase 10.
- `ProcessingWorkflow.get_slice_output_data` formats off-specular slice tables and
  labels.
- `ProcessingWorkflow.gisans` coordinates GISANS export and GISANS slice export.
  The numerical GISANS calculation and rebinning belong to Backend Phase 7; Phase 10
  should own serialization of the resulting backend models.
- `ProcessingWorkflow.get_gisans_data` builds wavelength-band GISANS output grids,
  cross-section labels, and slice inputs.
- `ProcessingWorkflow.get_gisans_slice_output_data` formats GISANS slice tables and
  labels.

#### Raw/diagnostic and delivery outputs

- `quicknxs.interfaces.event_handlers.main_handler.MainHandler.save_run_data` writes
  one raw ROI TOF-counts table per cross-section using
  `CrossSectionData.get_tof_counts_table()`. The file dialog, basename prompt, and
  overwrite confirmation should remain in QuickNXS, but the table model and ASCII
  writer are candidates for backend diagnostic-output helpers if Phase 10 includes
  raw/diagnostic exports.
- `quicknxs.interfaces.data_handling.data_set.CrossSectionData.get_tof_counts_table`
  constructs the raw ROI TOF-counts table with wavelength, proton-charge-normalized
  counts, errors, raw counts, and ROI size. This computation may fit Backend Phase 8
  or Phase 9 if raw diagnostic exports become backend-owned; Phase 10 would then
  serialize the resulting table.
- `ProcessingWorkflow._email_replace` and `ProcessingWorkflow.send_email` package
  exported files, optionally zip them, and send them through SMTP. If result delivery
  remains supported, backend code can own reusable packaging helpers, but user
  preferences, SMTP configuration, and UI error reporting should remain outside the
  core scientific output API.

#### UI-only or lower-priority export helpers

- `quicknxs.interfaces.main_window.MainWindow.reduceDatasets` collects options from
  Qt dialogs and launches `ProcessingWorkflow`. It should remain a QuickNXS
  orchestration/adaptation path.
- `quicknxs.interfaces.reduction_dialog.ReductionDialog.get_options` and
  `ReductionDialog.save_settings` are UI option collection and persistence. They
  should remain in QuickNXS, with adapters mapping their output to backend request
  models.
- `quicknxs.ui.mplwidget.NavigationToolbar.save_figure` and
  `NavigationToolbar.save_data`, plus helpers `_save_dat`, `_save_npz`, and
  `_save_pkl`, are generic plot-toolbar exports from rendered Matplotlib state.
  These should not be an early Phase 10 target unless the backend explicitly takes
  ownership of plot-data export formats. Scientific result artifacts should use
  backend result models instead of extracting data back out of plotted figures.

### Proposed Backend API

```python
def write_reduction_outputs(request: ReductionOutputRequest) -> ReductionOutputResult:
    ...
```

### Work

- Keep output generation independent of QuickNXS UI state.
- Support reduced `.dat`, ORSO, Nexus, partial script, combined catalog JSON, and
  report assets where appropriate.
- Ensure output APIs accept backend result models rather than broad process objects.
- Move output naming/template expansion to a backend helper that accepts explicit
  run, peak, instrument, artifact, state, and extension metadata.
- Reuse the Backend Phase 2 reduced-file writer for QuickNXS-style `.dat` output
  instead of creating another writer.
- Move ORSO, NumPy, Matlab, Mantid script, offspec/GISANS table, and slice
  serialization behind backend APIs where those formats remain supported.
- Keep Qt dialogs, QSettings, progress UI, overwrite prompts, and live session
  reconstruction in QuickNXS adapters.
- Coordinate with Backend Phase 5 for specular/stitch/asymmetry curve models,
  Backend Phase 6 for off-specular result models, and Backend Phase 7 for GISANS
  result models.
- Keep existing public autoreduction outputs stable.

### Tests

- Existing ORSO tests.
- Existing reflectivity output tests.
- Script output tests.
- Report output tests where they do not require live web services.
- Golden files for reduced `.dat` sections.
- Characterization tests for current `ProcessingWorkflow` artifact names and file
  contents before replacing the QuickNXS implementation.
- Golden tests for specular `.dat`, ORSO, NumPy, Matlab, Mantid script, offspec,
  offspec slice, GISANS, and GISANS slice outputs where those formats remain in
  scope.
- Tests that backend output APIs do not import QuickNXS `DataManager`, `NexusData`,
  `CrossSectionData`, `Configuration`, or Qt widgets.

## Suggested Parallelization

The phases can proceed independently with limited coordination:

- Backend Phase 1 is useful to start early, but it is not required before the
  functional phases begin.
- Backend Phase 2 can proceed using its own file models and later align with common
  models from Backend Phase 1.
- Backend Phase 3 can proceed independently because direct-beam matching already has a
  backend starting point.
- Backend Phase 4 can proceed independently because reflectivity calculation already
  exists in `ReductionProcess`.
- Backend Phase 5 can proceed independently using curve DTOs and current merge tests.
- Backend Phases 6 and 7 can proceed independently from each other if they share only
  geometry/value DTOs.
- Backend Phase 8 can proceed independently and later feed Backend Phases 3 and 4.
- Backend Phase 9 can proceed independently around loading/splitting/correction APIs.
- Backend Phase 10 should coordinate with Backend Phase 2 for reduced `.dat` output, but can
  independently cover ORSO, Nexus, scripts, and reports.

## Backend Definition Of Done

For each phase:

- Public backend API exists in `mr_reduction`.
- API has request/result models and docstrings.
- Tests pass in `../MagnetismReflectometer`.
- Existing autoreduction behavior is preserved or intentionally changed with golden
  tests.
- No QuickNXS imports are added.
- No QuickNXS call sites are modified.
- The API is usable by a future QuickNXS adapter without requiring Qt, `DataManager`,
  `NexusData`, `CrossSectionData`, or QuickNXS `Configuration`.

## Relationship To Future QuickNXS Adoption

QuickNXS can adopt these APIs later through adapters created in the existing
architecture plan. Until then, backend work should be validated entirely from
`../MagnetismReflectometer` tests and fixtures.

Future QuickNXS adapter work should map:

- QuickNXS session entries to backend source/candidate IDs.
- QuickNXS configuration adapters to backend option models.
- QuickNXS loaded data objects to backend workspace or array inputs.
- Backend results to QuickNXS view models and session state.
