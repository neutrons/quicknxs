# Original Prompt

Users can save the current data reduction (data runs, direct beam runs, run-specific and global configuration parameters and the combined reflectivity curve table) in a so called reduced data file. Currently, the logic is duplicated in the backend mr_reduction, but the formats have diverged and currently a file output from mr_reduction cannot be loaded in QuickNXS. Rather than updating the mr_reduction logic to match the QuickNXS logic, we would like to move the QuickNXS logic to the backend. Please confirm whether file I/O should be a backend concern, and if so, please create a plan in a file plan_reduced_data_file_io_backend_migration.md for how to make that migration. Please also reason about whether the file loading should be part of the backend as well and include that in the plan if appropriate. The logic in the frontend is in src/quicknxs/interfaces/data_handling/quicknxs_io.py and the logic in the backend is in src/mr_reduction/reflectivity_output.py.

# Reduced Data File I/O Backend Migration Plan

## Recommendation

Reduced data file I/O should be a backend concern. The reduced file format is a data reduction interchange contract: it records run identity, direct beam pairing, per-run reduction parameters, global options, additional peak tables, and the exported reflectivity data table. That contract should be implemented once in `mr_reduction` and shared by QuickNXS, autoreduction, scripts, and tests.

QuickNXS should still own GUI orchestration and `DataManager` state mutation. In particular, QuickNXS should keep responsibility for turning parsed reduced-file entries into loaded `NexusData` instances, updating progress/status UI, selecting active rows, and refreshing plots. The backend should own parsing, validation, compatibility rules, and writing the on-disk format.

File loading should be split into two layers:

- Backend-owned: parse a reduced data file into a neutral model and serialize that model back to disk.
- Frontend-owned: load raw Nexus files into QuickNXS `NexusData` objects and apply the parsed model to direct beam and reduction tables.

This avoids making `mr_reduction` depend on QuickNXS GUI classes while still eliminating duplicated and divergent file format logic.

The backend implementation should follow
[session_identity_contract.md](../session_identity_contract.md). In particular,
source run number is metadata, not mutable entry identity. Reduced-file `DB_ID`
values should be treated as file-local direct-beam entry references, not as aliases
for direct-beam run numbers.

## Current State

QuickNXS currently owns the most complete format implementation in `src/quicknxs/interfaces/data_handling/quicknxs_io.py`.

It handles:

- Header metadata: QuickNXS, `mr_reduction`, Mantid versions, date, type, input run indices, extracted states.
- Direct beam runs in `[Direct Beam Runs]`.
- Data runs in `[Data Runs]`.
- Additional peak-specific sections such as `[Peak 1 Runs]`, `[Peak 2 Runs]`.
- Global options in `[Global Options]`.
- Numerical reflectivity data in `[Data]`.
- QuickNXS-specific label mapping between `Configuration` attributes and reduced-file column labels.
- Slice values.
- Summed runs and `+`-joined file paths.
- Legacy path normalization from histo/event Nexus names to `.nxs.h5`.
- Both old 1-based and newer 0-based `DB_ID` indexing.

`mr_reduction` currently writes related output in `src/mr_reduction/reflectivity_output.py`, assisted by `src/mr_reduction/beam_options.py`.

It currently:

- Writes from Mantid workspaces rather than an application state model.
- Writes `[Direct Beam Runs]`, `[Data Runs]`, `[Global Options]`, `[Sequence]`, and `[Data]`.
- Uses backend dataclasses `DirectBeamOptions` and `ReflectedBeamOptions`.
- Does not cover the full QuickNXS saved-reduction state, especially additional peak tables, full global/run-specific option coverage, slice values, and the exact QuickNXS reader expectations.
- Produces files that QuickNXS may reject because `quicknxs_io.read_reduced_file()` currently requires the first line to start with `# Datafile created by QuickNXS`.

## Target Architecture

Add a backend reduced-file module, for example:

```text
mr_reduction/reduced_data_file.py
```

The module should expose a neutral data model that does not import QuickNXS:

```text
ReducedDataFile
ReducedFileMetadata
ReducedRunEntry
ReducedDirectBeamEntry
ReducedDataRunEntry
ReducedPeakSection
ReducedGlobalOptions
ReducedDataBlock
ReducedFileParseResult
```

The model should store configuration as plain dictionaries of string keys to typed values. QuickNXS can adapt those dictionaries to and from `Configuration`; `mr_reduction` can adapt them to and from backend workspace logs or backend option dataclasses.

Direct-beam and data-run entries should have explicit file/model entry IDs. Run
number should remain on each entry's source metadata. Data-run entries should
reference direct-beam entries by entry ID or normalized file-local `DB_ID`.

Suggested backend APIs:

```python
read_reduced_data_file(path: str | Path) -> ReducedFileParseResult
write_reduced_data_file(model: ReducedDataFile, path: str | Path) -> None
write_reflectivity_data(path: str | Path, data, columns, *, as_5col: bool = True) -> None
```

Add explicit adapter functions rather than embedding frontend or workspace knowledge in the core parser:

```python
model_from_reflectivity_workspaces(...)
model_from_quicknxs_export_state(...)  # lives in QuickNXS, not backend
quicknxs_entries_from_model(...)       # lives in QuickNXS, not backend
```

The backend parser should accept both producer headers:

- `# Datafile created by QuickNXS ...`
- `# Datafile created by mr_reduction ...`

The writer should emit the canonical QuickNXS-loadable format. The compatibility target should be "files written by either QuickNXS or `mr_reduction` can be loaded by QuickNXS."

## Migration Steps

### 1. Freeze the Format With Golden Tests

Before moving code, add characterization tests using representative files.

In QuickNXS:

- Existing QuickNXS saved reduction with one direct beam and one data run.
- File with multiple data runs.
- File with additional peak sections.
- File with summed runs using `+`.
- File with slice values.
- File with `scale_err`.
- Current `mr_reduction` autoreduce `.dat` output that QuickNXS cannot currently load.

In `mr_reduction`:

- Existing `tests/unit/mr_reduction/test_reflectivity_output.py` expected autoreduce output.
- A QuickNXS-format fixture that includes the sections `mr_reduction` does not currently produce.

The first tests can assert parsed models rather than byte-identical output. Byte-identical tests are useful for numerical `[Data]` output, but model comparison is better for headers because column order and spacing can be normalized.

### 2. Introduce the Backend Model and Parser

Create the backend reduced-file model in `mr_reduction`.

Move or reimplement these frontend responsibilities in backend form:

- Section detection.
- Header metadata parsing.
- Table parsing for direct beam and data run sections.
- Additional peak section parsing.
- Global option parsing.
- `[Data]` block parsing or preservation.
- `DB_ID` indexing normalization.
- Summed-run path reconstruction.
- Relative path resolution.
- Legacy histo/event `.nxs.h5` path normalization.

Do not import `quicknxs.interfaces.configuration.Configuration` in the backend. Instead, return option dictionaries using file labels as parsed plus normalized canonical keys where useful.

Keep QuickNXS label compatibility in backend constants, but avoid naming them as QuickNXS-only if they define the shared file format:

```python
CONFIG_LABELS = {...}
LABEL_TO_CONFIG = {...}
```

If some labels are truly frontend-only, keep those mappings in a QuickNXS adapter.

### 3. Introduce the Backend Writer

Move the canonical table-building and data-writing behavior from `quicknxs_io.py` into `mr_reduction`.

Backend writer requirements:

- Preserve QuickNXS-loadable section names.
- Preserve direct beam, data run, and peak section semantics.
- Preserve slice columns.
- Preserve `scale_err` when available.
- Preserve current data table behavior for 4-column and 5-column specular output.
- Preserve off-specular/GISANS option keys when requested.
- Use one documented `DB_ID` indexing policy in newly written files. The mapping
  must be from data-run entry to direct-beam entry, not from data-run run number to
  direct-beam run number. Prefer 0-based only if QuickNXS and backend tests
  explicitly cover legacy 1-based input. Otherwise prefer 1-based if that is already
  the backend/autoreduction convention. The important point is to document and test
  both read paths.

Update `mr_reduction.reflectivity_output.write_reflectivity()` to build a `ReducedDataFile` model and call the shared writer. Keep `write_reflectivity()` as the public autoreduction API to avoid breaking callers.

### 4. Future Integration Track: Add QuickNXS Adapters

This step is future frontend integration work, not Backend Phase 2 acceptance
criteria. In QuickNXS, replace direct format construction/parsing with adapters
around the backend model.

Suggested adapter module:

```text
src/quicknxs/interfaces/data_handling/reduced_file_adapter.py
```

Adapter responsibilities:

- Convert `DataManager.peak_reduction_lists`, `direct_beam_list`, and `Configuration` state into `ReducedDataFile`.
- Convert parsed backend `ReducedDataFile` into the tuple/list structures currently consumed by `DataManager.load_direct_beam_and_data_files()`:
  - `db_files`
  - `data_files`
  - `additional_peaks`
  - `has_scaling_error`
- Apply file-format options to QuickNXS `Configuration` objects.
- Preserve QuickNXS-specific behavior for cache, active data, table state, progress reporting, and recalculation.

QuickNXS does not have downstream dependencies that import `quicknxs_io.py` as a public API. The existing functions can therefore be kept temporarily as internal transition shims while call sites are migrated, but there is no need for formal deprecation warnings or a release-cycle compatibility period.

Temporary wrapper shape:

```python
def read_reduced_file(...):
    model = mr_reduction.reduced_data_file.read_reduced_data_file(...)
    return reduced_file_adapter.to_data_manager_load_lists(model, ...)

def write_reflectivity_header(...):
    model = reduced_file_adapter.from_data_manager_state(...)
    mr_reduction.reduced_data_file.write_reduced_data_file(model, ...)
```

After internal QuickNXS call sites are migrated to the adapter/backend APIs, remove the temporary wrappers and any duplicated parser/writer implementation.

### 5. Decide the Loading Boundary

Move reduced-file parsing to the backend, but keep QuickNXS raw Nexus loading in QuickNXS.

The backend should not construct `NexusData` because that would couple `mr_reduction` to QuickNXS GUI/data-manager classes. Instead, backend loading should mean:

- Read the reduced file.
- Validate the format.
- Resolve file paths.
- Return a structured "reduction recipe."

QuickNXS loading should continue to mean:

- Iterate parsed direct beam and data run entries.
- Load raw Nexus files.
- Create or deep-copy `NexusData` instances as needed.
- Add entries to the direct beam and reduction tables.
- Recalculate reflectivity if required.
- Restore UI state.

For backend-only workflows, `mr_reduction` may add a separate optional helper later:

```python
load_reduced_data_workspaces(model: ReducedDataFile, ...)
```

That helper should return Mantid workspaces or backend-native reduction objects, not QuickNXS `NexusData`.

### 6. Future Integration Track: Update Call Sites

This step is future frontend integration work except for the backend
`mr_reduction.reflectivity_output.py` update.

QuickNXS call sites to update:

- `src/quicknxs/interfaces/data_handling/processing_workflow.py`
  - Replace direct `quicknxs_io.write_reflectivity_header()` and `write_reflectivity_data()` internals with backend-backed wrappers or direct backend calls.
- `src/quicknxs/interfaces/data_manager.py`
  - Keep `load_data_from_reduced_file()` orchestration.
  - Replace `quicknxs_io.read_reduced_file()` internals with backend parser plus QuickNXS adapter.
- Tests under `test/unit/quicknxs/interfaces/data_handling/test_quicknxs_io.py` should migrate to adapter tests and backend parser compatibility tests.

Backend call sites to update as part of backend implementation:

- `src/mr_reduction/reflectivity_output.py`
  - Keep public `write_reflectivity()` but make it use the shared writer.
- `src/mr_reduction/beam_options.py`
  - Either keep as workspace-to-model adapter support or fold into the new module if the dataclasses become redundant.
- `tests/unit/mr_reduction/test_reflectivity_output.py`
  - Add tests that the backend output parses through the new backend parser.

### 7. Compatibility and Validation Rules

The backend parser should enforce only file-format requirements, not UI requirements.

Required validations:

- Required columns exist in `[Direct Beam Runs]` and `[Data Runs]`.
- `DB_ID` values can be mapped to known direct-beam entries.
- Run number and file fields are parseable.
- Additional peak section names are parseable.
- Data block columns are recognized or preserved.

Warnings rather than hard failures:

- Unknown option columns.
- Unknown global options.
- Missing optional `slice`.
- Missing `scale_err`.
- Missing `[Sequence]`.
- Producer header from older `mr_reduction`.

Hard failure:

- File is not a recognized reduced data file.
- Data run sections cannot be parsed enough to identify files and run numbers.

### 8. Test Matrix

Backend tests:

- Parse current QuickNXS saved file.
- Parse current `mr_reduction` autoreduce file.
- Write model, read it back, compare normalized model.
- Round-trip direct beam/data run tables with additional peak sections.
- Parse legacy 1-based `DB_ID`.
- Parse current/new 0-based `DB_ID`, if retained.
- Preserve two direct-beam entries with the same run number as distinct entries.
- Preserve data-run to direct-beam entry references when run numbers duplicate.
- Preserve summed runs and slices.
- Write data blocks in 4-column and 5-column forms.

QuickNXS tests:

- `DataManager.load_data_from_reduced_file()` loads a backend-written file.
- QuickNXS exports a file through backend writer and reloads it.
- Existing QuickNXS fixtures still load.
- Backend `mr_reduction` fixture that currently fails now loads.
- Additional peak tabs are restored.
- Direct beam pairings are restored.
- Run-specific parameters and global options are restored.
- Combined reflectivity data table remains present and readable.

Integration test:

- Run `mr_reduction` autoreduction to write `.dat`.
- Load that file in QuickNXS.
- Confirm expected direct beam table, data table, parameters, and reflectivity curve.

### 9. Rollout Plan

Backend implementation:

- Add backend parser/writer and tests.
- Leave QuickNXS behavior unchanged.

Future QuickNXS adoption:

- Add QuickNXS adapter wrappers using backend parser/writer.
- Keep `quicknxs_io.py` functions only as temporary internal transition shims where useful.
- Add compatibility tests proving existing QuickNXS files and backend files load.

Backend output convergence:

- Update `mr_reduction.reflectivity_output.write_reflectivity()` to emit the canonical backend format.
- Ensure newly generated `mr_reduction` output parses through the backend parser.
- Ensure QuickNXS can load newly generated `mr_reduction` output during the future
  frontend integration track.

Frontend cleanup:

- Remove direct format logic in `quicknxs_io.py`.
- Remove temporary QuickNXS wrappers once internal call sites and tests use the adapter/backend APIs. No formal deprecation period is needed because QuickNXS has no downstream dependencies.

## Risks and Mitigations

- Risk: Backend accidentally imports QuickNXS and creates a circular package dependency.
  - Mitigation: Backend model stores plain dataclasses and dictionaries; QuickNXS-specific conversion lives in QuickNXS.

- Risk: Existing autoreduction consumers depend on exact whitespace or old columns.
  - Mitigation: Keep `write_reflectivity()` public API and add golden output tests. Prefer parser-equivalent output, but preserve exact output where external scripts require it.

- Risk: `DB_ID` indexing remains ambiguous.
  - Mitigation: Normalize on read, document the writer policy, and test both legacy variants.

- Risk: Path conversion logic is instrument/site-specific.
  - Mitigation: Keep path normalization configurable and separately tested. Do not hide failures; surface unresolved files in parse warnings.

- Risk: Configuration attributes evolve in QuickNXS.
  - Mitigation: Use unknown-column preservation in backend and QuickNXS adapter tests that check all known `Configuration` fields expected in saved reductions.

## Backend Definition of Done

Backend implementation is done when:

- `mr_reduction` contains the canonical reduced data file parser and writer.
- Backend models represent direct-beam entries and data-run entries with explicit
  entry references.
- Backend parser/writer tests cover duplicate run numbers, direct beam pairing,
  additional peaks, slices, summed runs, global options, run-specific options, and
  data tables.
- Files written by `mr_reduction` can be parsed by the backend parser.
- Existing backend autoreduction output tests pass or are intentionally updated with
  compatibility coverage.
- No backend code imports QuickNXS runtime objects.
- No QuickNXS save/load call sites are modified as part of the backend phase.

## Future Frontend Integration Definition of Done

The later QuickNXS adoption work is done when:

- QuickNXS no longer contains independent reduced-file parsing/serialization logic beyond adapters.
- Files written by QuickNXS can be loaded by QuickNXS.
- Files written by `mr_reduction` can be loaded by QuickNXS.
- Additional peaks, slices, summed runs, direct beam pairing, global options, run-specific options, and data tables are covered by tests.
