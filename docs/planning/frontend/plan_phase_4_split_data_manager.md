# Plan: Phase 4 - Split `DataManager`

Reference: [research_mvp_architecture.md](../research_mvp_architecture.md),
Frontend Phase 4.
Identity reference: [session_identity_contract.md](../session_identity_contract.md).

## Goal

Split `DataManager` into focused services while keeping a temporary facade for
callers that have not migrated yet.

The split should make these responsibilities explicit:

- Loaded Nexus data cache.
- Active session state.
- Direct-beam entries.
- Data/reduction entries.
- Direct-beam matching.
- Reduction execution.
- Reload/project application helpers.

This phase is where row entry IDs should move from adapter/view-model support into
the real session model.

The split should follow the comparison rules in
[session_identity_contract.md](../session_identity_contract.md): run number is source
metadata, file path is loading/cache identity, object identity is an internal cache
concern, and mutable session operations use entry IDs.

## Current Problem

`DataManager` currently owns loaded files, active run state, direct-beam lists,
reduction lists, matching, reflectivity calculation, reload behavior, and parts of
save/load application. That makes it hard to reason about what operation owns a
state change.

The biggest current risk is identity:

- Run number is used for scientific matching and display.
- Mutable table/session entries need their own identity.
- Copied `NexusData` instances can represent the same source run with different
  role-specific parameters.

## Target Service Boundaries

### `LoadedDataCache`

Owns loaded Nexus objects and file/run lookup.

Responsibilities:

- Load or return cached raw Nexus files.
- Track file path, run number, and source metadata.
- Own cache eviction policy.
- Avoid role-specific reduction parameters.

### `ReductionSession`

Owns the active reduction session.

Responsibilities:

- Active loaded run.
- Active cross-section.
- Direct-beam entries.
- Reduction/data entries.
- Active table entry IDs.
- Direct-beam/data-run pairing by direct-beam entry ID.
- Additional peak/tab state if currently represented in `DataManager`.

### `DirectBeamRepository`

Owns direct-beam session entries.

Responsibilities:

- Add/remove/clear direct-beam entries.
- Assign stable direct-beam entry IDs.
- Return entries by entry ID.
- Keep run number as metadata, not identity.

### `ReductionRunRepository`

Owns data/reduction session entries.

Responsibilities:

- Add/remove/clear data entries.
- Assign stable reduction entry IDs.
- Track direct-beam entry pairing.
- Return entries by entry ID.

### `DirectBeamMatcher`

Owns matching rules.

Responsibilities:

- Match data entries to candidate direct-beam entries using run metadata and current
  QuickNXS behavior.
- Return an explicit direct-beam entry ID.
- Report no-match and ambiguous-match cases.

### `ReductionService`

Owns reduction execution orchestration.

Responsibilities:

- Build reduction inputs from session entries and options.
- Call current reflectivity calculation code.
- Return reduction results or typed failures.
- Avoid UI updates.

During this phase, `ReductionService` may still call existing QuickNXS reduction
methods internally. The boundary is the important change.

## Implementation Steps

### Step 1: Characterize Current `DataManager`

Inventory public methods and group them by target service:

- Loading/cache.
- Active state.
- Direct-beam list.
- Reduction list.
- Matching.
- Reflectivity calculation.
- Reload/save-load application.

Add tests around current behavior before moving methods with broad call graphs.

### Step 2: Add Session Entry Models

Add explicit entry models:

```python
@dataclass
class DirectBeamEntry:
    entry_id: EntryId
    run_number: str
    nexus_data: NexusData
    source_file: str = ""


@dataclass
class ReductionRunEntry:
    entry_id: EntryId
    run_number: str
    nexus_data: NexusData
    direct_beam_entry_id: EntryId | None = None
    source_file: str = ""
```

Keep these close to session/model code, not UI code.

### Step 3: Extract Repositories Behind The Facade

Create repository classes and let `DataManager` delegate to them.

Keep existing `DataManager` methods and attributes where needed, but implement new
logic through the repositories.

Rules:

- New code should prefer repositories.
- Old call sites may keep using `DataManager` temporarily.
- Do not expose internal repository lists as mutable public lists unless a caller is
  explicitly being migrated.

### Step 4: Extract `DirectBeamMatcher`

Move `_find_direct_beam()`, run-number normalization, and matching policy into a
dedicated matcher.

The matcher should return:

- matched direct-beam entry ID,
- matched cross-section data where current calculation needs it,
- no-match result,
- ambiguous result if multiple entries are valid.

Existing behavior can keep choosing the first match, but the result should make that
choice visible and testable.

### Step 5: Extract `LoadedDataCache`

Move cache ownership, cache lookup, and file identity logic out of the broad manager.

Tests should cover:

- repeated loads,
- cache eviction,
- source run metadata,
- file path normalization behavior currently expected by QuickNXS.

### Step 6: Extract `ReductionService`

Move reflectivity calculation orchestration behind a service.

The first implementation can delegate to current calculation methods. The service
interface should already use session entries and option models so later backend work
does not depend on `DataManager`.

### Step 7: Update Presenters To Prefer Services

After services exist, update presenters from Phase 3 to depend on the smaller
services where practical.

Keep `DataManager` as a facade until all direct callers are migrated.

### Step 8: Retire Facade Surface Incrementally

Mark internal facade methods as migrated in comments or documentation as call sites
move. Remove methods only when no internal callers remain.

## Tests

Add focused tests for:

- entry ID generation and lookup,
- duplicate run numbers in direct-beam entries,
- duplicate run numbers in data entries,
- direct-beam matching behavior,
- active entry selection,
- cache lookup and reload,
- reduction service request building.

Keep higher-level UI tests for add/remove/direct-beam workflows.

## Acceptance Criteria

- Direct-beam and data session entries have stable entry IDs.
- `DataManager` delegates direct-beam list operations to a repository.
- `DataManager` delegates reduction list operations to a repository.
- Direct-beam matching is isolated and tested.
- Loaded-data cache behavior is isolated and tested.
- Reduction execution has a service boundary.
- Existing presenters and UI workflows continue to pass.

## Relationship To Other Plans

- Phase 1 introduces entry IDs in view models.
- Phase 2 and Phase 3 use entry IDs at the UI/presenter boundary.
- Phase 4 makes entry IDs part of the real session model.
- The backend facade plan can build backend requests from session services instead
  of broad `DataManager` state.
- The frontend configuration/job plan can migrate configuration ownership onto
  session entries and option models.
