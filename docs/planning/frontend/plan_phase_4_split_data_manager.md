# Plan: Phase 4 - Split `DataManager`

Reference: [research_mvp_architecture.md](../research_mvp_architecture.md),
Frontend Phase 4.
Identity reference: [session_identity_contract.md](../session_identity_contract.md).

## Goal

Split `DataManager` into a Qt-free frontend model layer while keeping a temporary
facade for callers that have not migrated yet.

In this phase, "model layer" means both passive state models and services that
mutate or query those models. The split should not imply that every extracted
object is a passive domain model.

The split should make these responsibilities explicit:

- Loaded Nexus data cache.
- Active session state.
- Direct-beam entries.
- Data/reduction entries.
- Direct-beam matching.
- Reduction execution.
- Stitching and scale-factor updates.
- Reduction results.
- Run-specific and direct-beam-specific option ownership.
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

There is also a vocabulary risk: the current roadmap uses "model" for state
objects such as `ReductionSession`, but also for services such as direct-beam
matching and reduction orchestration. This phase should make that distinction
explicit.

## Event Publishing Responsibility

Each service extracted in this phase takes over domain event publishing from
`DataManager` for the operations it owns. The event broker and initial event
taxonomy are introduced in Phase 3, where `DataManager` acts as the temporary
publisher. When a service is split out, its mutation methods should publish the
relevant events so that presenters and other subscribers receive notifications
without any change to their subscription code.

## Target Model Layer Boundaries

### Runtime State Models

These are the passive or mostly passive objects that represent live QuickNXS
runtime state. They should not import Qt or render UI:

- `ReductionSession`: active loaded run, active cross-section, selected
  direct-beam/reduction entry IDs, table-tab/peak state, session entries, pairings,
  run options, direct-beam parameters, and result state.
- `DirectBeamEntry`: a role-specific direct-beam row keyed by a stable entry ID.
- `ReductionRunEntry`: a role-specific reduction/data row keyed by a stable entry
  ID and paired by direct-beam entry ID.
- Option objects referenced by entries or session state. Phase 5 completes the
  option split, but Phase 4 should avoid adding new behavior that assumes legacy
  `Configuration` is the long-term owner.
- Stitching output should be represented as scale-factor and scale-error values on
  the affected `ReductionRunEntry.parameters`, not as a separate long-lived
  stitching model.
- Result state needed to rebuild view models without asking plots or widgets for
  current application state.

### Session State Services

These services own state mutation and lookup around the runtime state models.

#### `LoadedDataCache`

Owns loaded Nexus objects and file/run lookup.

Responsibilities:

- Load or return cached raw Nexus files.
- Track file path, run number, and source metadata.
- Own cache eviction policy.
- Avoid role-specific reduction parameters.

Publishes: `RunLoadedEvent` when a new file is loaded; `FileListChangedEvent`
when the cache contents change.

#### `DirectBeamRepository`

Owns direct-beam session entries.

Responsibilities:

- Add/remove/clear direct-beam entries.
- Assign stable direct-beam entry IDs.
- Return entries by entry ID.
- Keep run number as metadata, not identity.

Publishes: `DirectBeamListChangedEvent` when entries are added or removed;
`DirectBeamEntryUpdatedEvent(entry_id)` when a single entry's parameters change.

#### `ReductionRunRepository`

Owns data/reduction session entries.

Responsibilities:

- Add/remove/clear data entries.
- Assign stable reduction entry IDs.
- Track direct-beam entry pairing.
- Apply scale-factor and scale-error updates to entries after stitching.
- Return entries by entry ID.

Publishes: `ReductionListChangedEvent` when entries are added, removed, or
reordered; `RunOptionsUpdatedEvent(entry_id)` when a single entry's parameters
change.

### Domain/Application Services

These services coordinate domain workflows around the runtime state models. They
are part of the frontend model layer during migration, but they are not passive
models and should not duplicate backend-owned scientific or file-format behavior
after backend APIs exist.

#### `DirectBeamMatcher`

Owns current QuickNXS matching policy while that policy still lives in the
frontend.

Responsibilities:

- Match data entries to candidate direct-beam entries using run metadata and current
  QuickNXS behavior.
- Return an explicit match result: matched direct-beam entry ID, candidate IDs,
  no-match, or ambiguous-match.
- Return any matched cross-section/runtime object needed by current calculation
  code during migration.

It should not own direct-beam entries or mutate the direct-beam list. Those
responsibilities belong to `ReductionSession` and `DirectBeamRepository`.

After backend direct-beam matching is available, keep `DirectBeamMatcher` only as a
thin adapter that maps session entries to backend DTOs and applies the backend
result to session pairing. If no frontend policy remains, this adapter can be
folded into the service that builds reduction requests.

#### `ReductionService`

Owns reduction execution orchestration.

Responsibilities:

- Build reduction inputs from `ReductionSession` entries and option models.
- Call current reflectivity calculation code until backend reduction APIs are
  adopted.
- Delegate to backend specular/offspec/GISANS APIs once those contracts exist.
- Store or return reduction results without asking plot widgets for state.
- Return typed failures for invalid options, missing direct beam, ambiguous direct
  beam, workspace failure, or calculation failure.
- Avoid UI updates.

Publishes: `ReductionResultReadyEvent(entry_id)` when a reduction result is
available for a given entry.

`ReductionService` should not own the direct-beam list, reduction list, active
selection, or user-facing error wording. Those belong to session state services and
presenters respectively.

#### `StitchingService`

Owns stitching orchestration for the active reduction list. This is a command/use
case service, not a long-lived state model.

Responsibilities:

- Build a stitching request from the ordered reduction entries, active
  cross-section, and project-owned reduction options.
- Call current QuickNXS `data_manipulation.stitch_reflectivity()` until Backend
  Phase 5 stitching APIs are adopted.
- Delegate to backend stitching/scaling APIs once those contracts exist.
- Return explicit scale-factor and scale-error updates keyed by reduction entry ID.
- Apply those updates through `ReductionRunRepository` or `ReductionSession`, so
  the repository remains the owner of reduction entry state.
- Return typed failures for insufficient runs, invalid options, missing
  reflectivity data, backend failure, or normalize-to-unity cutoff failure.
- Avoid UI updates.

Publishes: `StitchingCompletedEvent(entry_ids)` after scale factors are updated,
plus `RunOptionsUpdatedEvent(entry_id)` if row-level option subscribers need
per-entry updates.

`StitchingService` should not own the reduction list, decide which widgets to
refresh, or store its own duplicate copy of scale factors. Its persisted effect is
the updated scale factor/error on each affected reduction entry.

## Implementation Steps

### Step 1: Characterize Current `DataManager`

Inventory public methods and group them by target service:

- Loading/cache.
- Active session state.
- Direct-beam list.
- Reduction list.
- Matching.
- Reflectivity calculation.
- Stitching and scale-factor updates.
- Result storage and merged reflectivity state.
- Run-specific and direct-beam-specific configuration ownership.
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
    parameters: DirectBeamParameters
    source_file: str = ""


@dataclass
class ReductionRunEntry:
    entry_id: EntryId
    run_number: str
    nexus_data: NexusData
    parameters: RunReductionParameters
    direct_beam_entry_id: EntryId | None = None
    result: ReductionResult | None = None
    source_file: str = ""
```

Keep these close to session/model code, not UI code. If the Phase 5 option classes
do not exist yet, introduce minimal placeholders or adapters with the same
ownership shape rather than adding new direct dependencies on legacy
`Configuration`.

### Step 3: Add `ReductionSession` And Repositories Behind The Facade

Create `ReductionSession` as the runtime owner of active selection, entry
collections, pairings, and result state. Create repository classes for collection
mutation and let `DataManager` delegate to them.

Keep existing `DataManager` methods and attributes where needed, but implement new
logic through the repositories.

Rules:

- New code should prefer repositories.
- Old call sites may keep using `DataManager` temporarily.
- Do not expose internal repository lists as mutable public lists unless a caller is
  explicitly being migrated.
- Repository methods should identify entries by `EntryId`, not run number.
- When a repository method is extracted, move the corresponding event publishing
  call from `DataManager` into the repository. Presenters subscribe to the same
  event types throughout; only the publisher changes.

### Step 4: Extract `DirectBeamMatcher`

Move `_find_direct_beam()`, run-number normalization, and matching policy into a
narrow matcher service.

The matcher should return:

- matched direct-beam entry ID,
- matched cross-section data where current calculation needs it,
- no-match result,
- ambiguous result if multiple entries are valid.

Existing behavior can keep choosing the first match, but the result should make that
choice visible and testable.

Do not move direct-beam list ownership into this service. When backend matching is
ready, change this service into a backend adapter instead of preserving duplicate
matching rules in QuickNXS.

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

The service should accept entry IDs or explicit entry objects plus option models,
return typed results/failures, and update session result state through the session
or repository boundary.

### Step 7: Extract `StitchingService`

Move `DataManager.stitch_data_sets()` and the current toolbar-triggered stitching
workflow behind a stitching service.

The first implementation can delegate to current QuickNXS stitching code. The
service interface should already use ordered reduction entry IDs and stitching
option models so Backend Phase 5 can replace the calculation without changing the
presenter contract.

The service should apply returned scale-factor and scale-error updates through the
reduction-run repository. It should not expose a mutable stitching model or mutate
widgets directly.

### Step 8: Update Presenters To Prefer Services

After services exist, update presenters from Phase 3 to depend on the smaller
services where practical.

Keep `DataManager` as a facade until all direct callers are migrated.

### Step 9: Retire Facade Surface Incrementally

Mark internal facade methods as migrated in comments or documentation as call sites
move. Remove methods only when no internal callers remain.

## Tests

Add focused tests for:

- entry ID generation and lookup,
- duplicate run numbers in direct-beam entries,
- duplicate run numbers in data entries,
- direct-beam matching behavior, including matched, no-match, and ambiguous
  results,
- stitching behavior, including scale-factor/error updates by entry ID,
- active entry selection,
- cache lookup and reload,
- reduction service request building from session entries and option models,
- stitching request building from ordered entries and project-owned reduction
  options,
- result state updates without reading plot/widget state,
- legacy `Configuration` adapter behavior where entry parameters still bridge to
  current calculation code.

Keep higher-level UI tests for add/remove/direct-beam workflows.

## Acceptance Criteria

- Direct-beam and data session entries have stable entry IDs.
- `ReductionSession` owns active selection, entry collections, pairings, and result
  state.
- `DataManager` delegates direct-beam list operations to a repository.
- `DataManager` delegates reduction list operations to a repository.
- Direct-beam matching is isolated and tested.
- `DirectBeamMatcher` is a narrow matcher/backend-adapter boundary, not the owner
  of direct-beam entries.
- Loaded-data cache behavior is isolated and tested.
- Reduction execution has an orchestration service boundary that uses session
  entries and option models.
- Stitching has an orchestration service boundary that writes scale-factor/error
  updates through `ReductionRunRepository` or `ReductionSession`.
- Existing presenters and UI workflows continue to pass.

## Relationship To Other Plans

- Phase 1 introduces entry IDs in view models.
- Phase 2 and Phase 3 use entry IDs at the UI/presenter boundary.
- Phase 4 makes entry IDs part of the real session model.
- The backend facade plan can build backend requests from session services instead
  of broad `DataManager` state.
- Backend Phase 5 can replace the stitching calculation behind `StitchingService`
  without changing presenter ownership or reduction-entry scale-factor ownership.
- The frontend configuration/job plan can migrate configuration ownership onto
  session entries and option models.
