# Session Identity Contract

Reference: [overview.md](overview.md) and
[analysis_refactoring_plan.md](analysis_refactoring_plan.md).

This contract defines how QuickNXS and backend-facing models should distinguish
physical run identity from mutable session-entry identity. It is a dependency for
frontend table work, direct-beam matching, reduced-data-file I/O, and backend API
design.

## Problem

The current application can have more than one `NexusData` instance for the same
source run number. That happens when a run is used in more than one role, or when a
run is copied so role-specific parameters such as peak position can differ.

Run number is therefore not enough to identify a mutable row in the direct-beam
table or data table. The application must treat source identity and session-entry
identity as separate concepts.

## Identity Types

### Source Run Number

`source_run_number` identifies the physical run from the experiment.

Use it for:

- Display labels.
- Source-run metadata.
- Scientific matching heuristics.
- Compatibility with existing reduced-file values.

Do not use it for:

- Mutable table row identity.
- Direct-beam/data-run pairing.
- Deciding which copied `NexusData` object should be edited.
- Persisting a reference to a specific direct-beam table entry.

### Source File

`source_file` identifies the path or locator used to load raw data.

Use it for:

- Raw Nexus loading.
- Cache lookup.
- File-path normalization.
- Missing-file diagnostics.

Do not use it for:

- Session-entry identity.
- Direct-beam/data-run pairing.
- Distinguishing copied entries that intentionally share the same source file.

### Loaded Data Identity

`loaded_data_id` identifies an object or cache entry that represents loaded raw data.
This may be implicit while the current `DataManager` still owns loaded `NexusData`
objects.

Use it for:

- Cache internals.
- Object lifetime tracking.
- Avoiding duplicate raw loads where the same loaded data can be reused safely.

Do not use it for:

- Mutable table row identity.
- Serialized reduced-file references.
- Direct-beam selection after the data has been copied for role-specific parameters.

### Reduction Entry ID

`reduction_entry_id` identifies one mutable data/reduction table entry in the active
session.

Use it for:

- Data/reduction table rendering.
- Data/reduction table edits.
- Active data row selection.
- Run-specific parameter ownership.
- References from presenters or session services to a data entry.

It must be unique within the active session. It is not a run number and should not be
derived in a way that makes duplicate run numbers collide.

### Direct-Beam Entry ID

`direct_beam_entry_id` identifies one mutable direct-beam table entry in the active
session.

Use it for:

- Direct-beam table rendering.
- Direct-beam table edits.
- Active direct-beam row selection.
- Pairing a data/reduction entry with a specific direct-beam entry.
- Direct-beam matching results.
- Reduced-file direct-beam references after parsing into the in-memory model.

It must be unique within the active session. Two direct-beam entries may have the
same source run number and different parameters.

### Peak Entry ID

`peak_entry_id` identifies an additional peak entry if additional peaks are modeled
as explicit session entries.

Use it for:

- Additional peak tables.
- Additional peak reduced-file sections.
- Entry-specific parameters for copied peak data.

If additional peaks remain represented by lists during an intermediate phase, tests
should still verify that copied entries do not rely on run number for mutable
identity.

### Reduced-File DB_ID

`DB_ID` is a serialized direct-beam entry reference in reduced data files.

Use it for:

- Mapping a serialized data-run row to a serialized direct-beam entry.
- Compatibility with existing files.

Do not use it as:

- A run-number alias.
- A global identifier outside the file being parsed or written.

On read, legacy files may require compatibility logic when `DB_ID` effectively maps
to a run number. The parsed backend model should immediately normalize that into an
explicit direct-beam entry reference.

## Comparison Rules

Use these comparison rules across active plans:

- Compare by `reduction_entry_id` for data table membership, data table edits, and
  data-row selection.
- Compare by `direct_beam_entry_id` for direct-beam table membership, direct-beam
  table edits, direct-beam pairing, and matching results.
- Compare by source run number only for physical metadata, display, grouping, and
  matching heuristics.
- Compare by source file only for loading and cache lookup.
- Compare by object identity only inside cache or adapter internals where the object
  lifetime is the subject of the operation.
- Compare by `DB_ID` only inside reduced-file parser/writer logic, and normalize it
  to a direct-beam entry reference in the parsed model.

## Backend API Rule

Backend APIs should accept caller-owned candidate or entry IDs when the caller needs
to preserve exact identity.

For example, direct-beam matching should accept candidate records such as:

```python
@dataclass(frozen=True)
class DirectBeamCandidate:
    candidate_id: str
    source_run_number: str
    options: dict[str, Any]
```

The result should return `candidate_id`, not just `source_run_number`.

## Reduced-File I/O Rule

Reduced-file models should serialize and parse direct-beam entries as entries:

- A direct-beam entry stores source run number as metadata.
- A data-run entry references the selected direct-beam entry by serialized entry
  reference or file-local `DB_ID`.
- The writer may choose a documented `DB_ID` indexing policy, but the mapping must
  be from data entry to direct-beam entry, not data run number to direct-beam run
  number.

## Required Characterization Tests

Plans that touch table identity, direct-beam matching, or reduced-file I/O should
include tests for:

- A data run added as a direct beam has independent role-specific parameters.
- A direct beam run added as a data run does not unintentionally share mutable
  parameters with its direct-beam table entry.
- Two direct-beam entries with the same source run number can be selected and edited
  distinctly.
- Direct-beam matching returns the selected direct-beam entry or candidate ID.
- Reduced-file save/load preserves direct-beam/data-run pairings when source run
  numbers duplicate.
- Programmatic table rendering does not mutate model/session state.
