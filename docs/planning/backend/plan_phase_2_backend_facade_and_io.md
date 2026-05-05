# Plan: Backend Phase 2 - Backend Facade And Reduced-File I/O

Reference: [overview.md](../overview.md), Backend Roadmap Phase 2.
Identity reference: [session_identity_contract.md](../session_identity_contract.md).

## Goal

Make `mr_reduction` the owner of reusable reduced-data-file parsing, writing,
validation, compatibility handling, and backend facade contracts.

This backend phase produces APIs that QuickNXS can call later. It does not switch
QuickNXS save/load call sites, does not add QuickNXS adapters, and does not remove
QuickNXS parser/writer code. Those steps belong to the future frontend integration
plan: [plan_future_backend_reduced_file_io_integration.md](../frontend/plan_future_backend_reduced_file_io_integration.md).

## Related Documents

This backend phase coordinates with:

- [plan_reduced_data_file_io_backend_migration.md](plan_reduced_data_file_io_backend_migration.md)
- [plan_mr_reduction_backend_parallel_phases.md](plan_mr_reduction_backend_parallel_phases.md)
- [session_identity_contract.md](../session_identity_contract.md)

## Backend Boundary

Add a backend facade that exposes stable operations such as:

```python
class ReductionBackend:
    def read_reduced_data_file(self, path: Path) -> ReducedDataFile:
        ...

    def write_reduced_data_file(self, path: Path, model: ReducedDataFile) -> None:
        ...
```

The reduced-file parser, writer, and model should live in `mr_reduction`.

This phase should not delegate backend behavior to QuickNXS code and should not
import QuickNXS UI classes, `DataManager`, `Configuration`, `NexusData`, or
`CrossSectionData`.

## Ownership Rules

Backend owns:

- Reduced-file schema and versions.
- Reduced-file parser.
- Reduced-file writer.
- Reduced-file validation.
- Compatibility parsing for QuickNXS and `mr_reduction` producers.
- Canonical reflectivity output formatting.
- Backend DTOs and validation.
- File-local direct-beam entry references such as `DB_ID`.

QuickNXS owns later, outside this backend phase:

- Loading raw Nexus files into current runtime objects.
- Applying parsed reduced-file models to live session entries.
- Updating UI state, selections, progress, and plots.
- Reporting missing files or recoverable load warnings to the user.
- Adapting legacy `Configuration` and `DataManager` state to backend DTOs.

## Identity Requirements

Backend reduced-file models must follow
[session_identity_contract.md](../session_identity_contract.md):

- Source run number is metadata, not mutable entry identity.
- Direct-beam entries are represented as entries.
- Data-run entries reference direct-beam entries, not direct-beam run numbers.
- `DB_ID` is a serialized direct-beam entry reference local to a file.
- Legacy files may be parsed with compatibility rules, but the parsed in-memory model
  should normalize direct-beam references to explicit entry references.

## Proposed Backend Models

Suggested models:

```python
@dataclass(frozen=True)
class ReducedFileMetadata:
    schema_version: str
    created_by: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class ReducedSourceRun:
    run_number: str
    file_path: str = ""
    cross_section: str = ""
    slice_number: int | None = None


@dataclass(frozen=True)
class ReducedDirectBeamEntry:
    entry_id: str
    source: ReducedSourceRun
    options: dict[str, Any]


@dataclass(frozen=True)
class ReducedDataRunEntry:
    entry_id: str
    source: ReducedSourceRun
    direct_beam_entry_id: str | None
    options: dict[str, Any]


@dataclass(frozen=True)
class ReducedReflectivityCurve:
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True)
class ReducedDataFile:
    metadata: ReducedFileMetadata
    global_options: dict[str, Any]
    direct_beam_runs: tuple[ReducedDirectBeamEntry, ...]
    data_runs: tuple[ReducedDataRunEntry, ...]
    combined_reflectivity: tuple[ReducedReflectivityCurve, ...]
    unknown_sections: dict[str, Any] = field(default_factory=dict)
```

DTO rules:

- Do not import QuickNXS classes.
- Preserve unknown columns and sections where feasible.
- Represent direct-beam/data-run pairings by entry ID.
- Keep run number as source metadata.
- Keep GUI-only state out of backend models unless it is already part of the saved
  reduction format.

## Implementation Steps

### Step 1: Confirm Backend DTOs And Golden Tests

Create backend fixtures and tests that compare parsed models first. Use byte-for-byte
output tests only where exact text compatibility is required.

Required fixtures:

- QuickNXS reduced file with one direct beam and one data run.
- QuickNXS reduced file with multiple data runs.
- File with additional peak sections.
- File with summed runs.
- File with slice values.
- File with scaling error.
- File with duplicate source run numbers in distinct entries.
- Existing `mr_reduction` output that QuickNXS currently cannot load.

### Step 2: Implement Backend Parser

Move parsing responsibilities to `mr_reduction`:

- Header parsing.
- Section detection.
- Direct-beam table parsing.
- Data-run table parsing.
- Additional peak section parsing.
- Global options parsing.
- Data block parsing or preservation.
- `DB_ID` compatibility.
- Unknown column preservation.

Parser requirements:

- Accept QuickNXS and `mr_reduction` producer headers.
- Normalize legacy `DB_ID` variants.
- Return direct-beam entry records and data-run direct-beam entry references.
- Preserve parse warnings instead of reporting through UI.
- Avoid QuickNXS imports.

### Step 3: Implement Backend Writer

Implement a writer that emits the canonical QuickNXS-loadable format from backend
DTOs.

Writer requirements:

- Preserve direct-beam and data-run sections.
- Preserve additional peak sections.
- Preserve global options.
- Preserve slice information.
- Preserve scaling error.
- Preserve combined reflectivity data.
- Write documented direct-beam/data-run pairings by direct-beam entry reference.
- Use one documented `DB_ID` indexing policy for new files.
- Preserve or explicitly report unknown values.

### Step 4: Add Backend Facade

Expose parser/writer through backend facade functions or a small facade class.

The facade should:

- Accept paths and backend DTOs.
- Return backend DTOs and backend messages.
- Avoid Qt, QuickNXS runtime objects, and UI callbacks.
- Be usable from scripts, autoreduction, and future QuickNXS adapters.

### Step 5: Switch `mr_reduction` Output

Update `mr_reduction.reflectivity_output.write_reflectivity()` to build the canonical
backend model and write through the shared writer where practical.

Keep existing backend public entry points where they are still the natural API for
autoreduction or scripts.

## Tests

Required backend tests:

- Parser tests for QuickNXS-produced files.
- Parser tests for `mr_reduction`-produced files.
- Writer tests for canonical output.
- Round-trip tests preserving duplicate source run numbers in distinct entries.
- Round-trip tests preserving exact direct-beam/data-run pairings.
- Tests proving `DB_ID` maps to direct-beam entries, not run numbers.
- Tests preserving unknown columns and sections where feasible.

Tests that switch QuickNXS save/load belong to the future frontend integration plan,
not this backend phase.

## Acceptance Criteria

- Backend parser can read supported QuickNXS and `mr_reduction` files.
- Backend writer emits the documented canonical reduced-file format.
- Backend models can represent duplicate source run numbers in distinct direct-beam
  and data-run entries.
- Direct-beam/data-run pairings survive backend parse/write round trips when source
  run numbers duplicate.
- `mr_reduction` output uses or can be represented by the canonical backend writer.
- Backend code has no QuickNXS imports.
- No QuickNXS save/load call sites are modified as part of this backend phase.

## Out-Of-Phase Follow-Up

QuickNXS adoption is tracked in
[plan_future_backend_reduced_file_io_integration.md](../frontend/plan_future_backend_reduced_file_io_integration.md).

That future work includes:

- QuickNXS adapter module.
- QuickNXS save path switch.
- QuickNXS load path switch.
- Removal of duplicated QuickNXS parser/writer logic after internal call sites are
  migrated.

## Relationship To Other Plans

- Frontend Phase 1 supplies the identity contract and configuration inventory needed
  by future QuickNXS adapters.
- Frontend Phase 4 supplies session services and entry IDs that make backend model
  creation less dependent on broad `DataManager` state.
- Backend Phase 3 uses the same candidate/entry identity rules for direct-beam
  matching.
