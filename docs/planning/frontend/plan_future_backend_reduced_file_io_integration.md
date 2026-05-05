# Future Integration Plan: QuickNXS Backend Reduced-File I/O Adoption

Reference: [overview.md](../overview.md),
[session_identity_contract.md](../session_identity_contract.md), and
[backend/plan_phase_2_backend_facade_and_io.md](../backend/plan_phase_2_backend_facade_and_io.md).

This is a future frontend integration plan. It is not part of Backend Phase 2
acceptance criteria and should not block backend parser/writer work.

## Goal

Switch QuickNXS reduced-data-file save/load paths to backend reduced-file APIs after
the frontend has enough identity and configuration adapter support to preserve
current behavior.

QuickNXS should remain responsible for:

- GUI orchestration.
- Loading raw Nexus files into current runtime objects.
- Applying parsed reduced-file entries to the live session.
- Updating tables, active selections, status/progress UI, and plots.
- Reporting missing files and recoverable warnings to the user.

The backend should own:

- Reduced-file parser.
- Reduced-file writer.
- Reduced-file validation.
- Compatibility rules.
- Canonical file-format DTOs.

## Dependencies

This integration should start only after:

- Frontend Phase 1A defines and tests session identity behavior.
- Frontend Phase 1C provides configuration field inventory and adapters.
- Backend Phase 2 provides backend reduced-file parser/writer/facade APIs.
- Backend reduced-file models represent direct-beam entries as entries, not as run
  number aliases.

Frontend Phase 4 session services are not strictly required, but they will simplify
the adapter. If integration happens before Phase 4, the adapter should be treated as
a bridge over the legacy `DataManager` shape.

## Adapter Module

Add a QuickNXS adapter module:

```text
src/quicknxs/interfaces/data_handling/reduced_file_adapter.py
```

Responsibilities:

- Convert `DataManager.peak_reduction_lists`, `direct_beam_list`, and
  `Configuration` state into backend reduced-file DTOs.
- Convert backend direct-beam entries into QuickNXS direct-beam load/apply inputs.
- Convert backend data-run entries into QuickNXS reduction load/apply inputs.
- Preserve exact direct-beam/data-run entry pairings.
- Convert backend option dictionaries into legacy `Configuration` values through
  the configuration adapter.
- Preserve QuickNXS-specific missing-file, cache, active-data, table-state,
  progress-reporting, and recalculation behavior.

The adapter must not make run number the identity of a mutable direct-beam or data
entry. Use the identity rules in
[session_identity_contract.md](../session_identity_contract.md).

## Implementation Steps

### Step 1: Add Adapter Tests

Add tests before changing save/load call sites.

Required coverage:

- One direct beam and one data run.
- Multiple data runs sharing one direct beam.
- Same source run number present in both direct-beam and data tables.
- Two direct-beam entries with the same source run number and different parameters.
- Additional peak sections.
- Slice values.
- Scaling error.
- Unknown columns/options preserved or reported.

### Step 2: Add Backend-To-QuickNXS Load Adapter

Convert backend parsed models into the current inputs used by
`DataManager.load_data_from_reduced_file()` or a small replacement application
service.

Rules:

- Preserve direct-beam entry identity through adapter-local IDs if Phase 4 session
  IDs do not exist yet.
- Treat source run number as metadata.
- Preserve file paths and path-resolution warnings.
- Keep missing-file dialogs and progress behavior in QuickNXS.

### Step 3: Add QuickNXS-To-Backend Save Adapter

Convert live QuickNXS session state into backend DTOs.

Rules:

- Serialize direct-beam entries as entries.
- Serialize data-run entries with direct-beam entry references.
- Preserve global options, run options, cross-section options, additional peaks,
  and combined reflectivity data.
- Keep GUI-only state out of backend DTOs unless it is already part of the saved
  reduction format.

### Step 4: Switch Save Path

Update the QuickNXS save path to build backend DTOs through the adapter and call the
backend writer.

Temporary wrappers in `quicknxs_io.py` may remain as internal transition shims while
call sites are migrated. No formal deprecation period is needed.

### Step 5: Switch Load Path

Update the QuickNXS load path to call the backend parser and apply the parsed model
through the adapter.

The load path should still:

- Load raw Nexus files through QuickNXS runtime code.
- Create or deep-copy `NexusData` objects where current behavior requires it.
- Restore tables and additional peaks.
- Restore run-specific and global options.
- Refresh plots and status UI as current behavior does.

### Step 6: Remove Duplicate QuickNXS Format Logic

After save/load paths and tests pass:

- Remove duplicate parser/writer implementation from `quicknxs_io.py`.
- Keep only adapter code and temporary wrappers with live call sites.
- Remove wrappers once internal callers use the adapter/backend APIs directly.

## Tests

Required tests:

- QuickNXS loads backend-parsed files.
- QuickNXS exports through the backend writer and reloads the result.
- Existing QuickNXS fixtures still load.
- Backend `mr_reduction` fixtures that previously failed now load.
- Additional peak tabs are restored.
- Direct-beam/data-run pairings are restored by entry identity.
- Run-specific parameters and global options are restored.
- Combined reflectivity data table remains present and readable.

## Acceptance Criteria

- QuickNXS save uses backend reduced-file writer through an adapter.
- QuickNXS load uses backend reduced-file parser through an adapter.
- Direct-beam/data-run pairings survive save/load when source run numbers duplicate.
- Legacy QuickNXS fixtures and backend fixtures are covered by tests.
- QuickNXS contains no independent reduced-file parser/writer logic beyond adapters
  and temporary internal wrappers.
