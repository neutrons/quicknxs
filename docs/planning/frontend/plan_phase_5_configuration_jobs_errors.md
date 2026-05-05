# Plan: Frontend Configuration, Jobs, And Error Boundaries

Reference: [overview.md](../overview.md), Frontend Roadmap Phase 5.
Identity reference: [session_identity_contract.md](../session_identity_contract.md).

## Goal

Finish separating UI, domain, persistence, and backend state by replacing the legacy
`Configuration` hub with explicit option models and by adding clear job, progress,
error, and workspace boundaries.

This frontend phase completes work that begins earlier:

- Phase 1 classifies configuration fields and adds adapters.
- Phase 3 moves UI orchestration into presenters.
- Phase 4 gives session entries a real home.
- Backend phases provide persistence and backend contracts behind `mr_reduction`
  APIs; QuickNXS adoption happens through frontend adapters when those contracts are
  ready.

## Configuration Target

Replace the mixed legacy object with explicit models:

- `GlobalReductionOptions`
- `LoadingOptions`
- `RunReductionParameters`
- `DirectBeamParameters`
- `PeakFinderOptions`
- `AngleOverrideOptions`
- `PlotViewPreferences`
- `OffspecOptions`
- `GisansOptions`
- `ExportOptions`
- `ReducedDataFile` persistence models from the backend facade and I/O phase

These models should be plain Python dataclasses or typed backend DTOs. They should
not import Qt.

## Job, Error, And Workspace Targets

Add:

- `ProgressSink` interface for progress reporting.
- `JobRunner` or equivalent for long-running loading/reduction/export work.
- Typed domain errors for file parsing, invalid options, missing direct beam,
  workspace failure, reduction failure, and export failure.
- `WorkspaceHandle` or workspace service to localize Mantid ADS interaction.
- Optional model notifications after presenters and session services are stable.

## Implementation Steps

### Step 1: Finalize Configuration Field Inventory

Use the Phase 1 field inventory and adapter tests.

For each legacy field, decide:

- target option model,
- default value source,
- whether it is global or entry-specific,
- whether it belongs in persistence,
- whether it is UI-only,
- whether it should remain as compatibility-only during migration.

Add tests that fail if a current legacy field is unclassified.

### Step 2: Add Explicit Option Models

Create the option dataclasses in appropriate model/backend modules.

Rules:

- Keep UI preferences out of backend reduction requests.
- Keep persistence compatibility fields in persistence models.
- Keep run-specific parameters on session entries.
- Keep direct-beam-specific parameters on direct-beam entries.
- Avoid class-level mutable state.

### Step 3: Replace Class-Level Global Configuration

Migrate global `Configuration` class attributes to a session-level
`GlobalReductionOptions` object.

Update:

- configuration event handling,
- presenters that read global options,
- reduction request builders,
- save/load adapters,
- tests that call `Configuration.setup_default_values()`.

Keep a legacy adapter only as long as old call sites remain.

### Step 4: Replace Run-Specific Configuration Usage

Move per-run fields from `CrossSectionData.configuration` or copied
`Configuration` instances into session entry parameter objects.

Migration order:

1. Direct-beam entry parameters.
2. Reduction/data entry parameters.
3. Cross-section display preferences.
4. Offspec/GISANS options.

During transition, provide read/write adapters so current calculation code still
receives a legacy `Configuration` where needed.

### Step 5: Update Backend And Persistence Adapters

Replace dictionary or legacy-configuration adapters with explicit option models where
the backend contract is stable.

Tests should verify:

- saved files preserve all supported options,
- loaded files reconstruct the same session option models,
- unknown fields remain preserved or produce clear compatibility warnings.

### Step 6: Add Domain Error Types

Introduce typed errors/results for:

- reduced-file parse errors,
- unsupported schema version,
- missing Nexus file,
- invalid configuration/options,
- missing direct beam,
- ambiguous direct beam,
- Mantid workspace failure,
- reduction failure,
- export failure.

Presenters should translate these into user-facing messages. Backend and model
services should not import UI code to report them.

### Step 7: Add Progress And Job Boundaries

Introduce a progress interface:

```python
class ProgressSink(Protocol):
    def set_fraction(self, value: float) -> None:
        ...

    def set_message(self, message: str) -> None:
        ...
```

Use it for:

- file loading,
- reload all files,
- reduced-file load/save,
- reduction,
- export.

If background execution is added, use a `JobRunner` abstraction so presenters do not
depend directly on thread or Qt worker implementation details.

### Step 8: Localize Mantid Workspace Access

Add a workspace service around Mantid ADS operations.

Responsibilities:

- create/load workspace,
- return workspace handles,
- cleanup temporary workspaces,
- resolve workspace names,
- isolate tests from global workspace state.

Do not attempt to remove all Mantid global usage in one patch. Start at service
boundaries used by file loading and reduction.

### Step 9: Consider Model Notifications

After presenters and services are stable, add lightweight notifications for session
state changes if they reduce manual render calls.

Notifications should describe domain changes, not widget events:

- direct-beam entry changed,
- reduction entry changed,
- active cross-section changed,
- reduction result updated,
- file load completed.

## Tests

Required tests:

- every legacy `Configuration` field is classified,
- legacy configuration round-trips through new option models during transition,
- global options no longer leak through class attributes in migrated paths,
- per-run parameter changes affect only the intended entry,
- domain errors are returned without UI imports,
- presenters translate domain errors into status/message models,
- progress updates can be tested with a fake `ProgressSink`,
- workspace service tests clean up Mantid state.

## Acceptance Criteria

- New option models replace legacy `Configuration` in migrated presenter/service
  paths.
- Legacy `Configuration` remains only behind adapters or compatibility code.
- Backend requests use explicit option models or DTOs.
- Reduced-file persistence uses backend persistence models, not live runtime objects.
- Long-running operations report progress through a boundary.
- Domain failures have typed results or exceptions that do not depend on UI code.
- Mantid ADS access is localized behind service boundaries for migrated paths.

## Relationship To Other Plans

- Phase 1 starts configuration classification and adapter coverage.
- Phase 3 presenters provide the place where option models enter user workflows.
- Phase 4 session entries provide ownership for run-specific and direct-beam-specific
  parameters.
- Backend facade and I/O persistence models provide the backend file-format
  representation.
