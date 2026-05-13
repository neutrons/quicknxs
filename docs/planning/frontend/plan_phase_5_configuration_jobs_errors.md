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

Replace the mixed legacy object with explicit frontend model-layer option models:

- `ReductionOptions`
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

These models are not view models. They represent application/domain options that
presenters and services can pass without reading widgets or mutating
`Configuration` class attributes. They should be plain Python dataclasses and must
not import Qt.

Ownership should be explicit:

- `ReductionOptions`: project-level defaults and global reduction controls,
  including normalization, stitching, dead-time, ROI/peak-finder defaults, and
  other settings that intentionally affect multiple entries. This model is owned by
  `QuickNXSProject`.
- `LoadingOptions`: file loading, correction, event filtering, and reload behavior
  that is independent of a specific table row.
- `RunReductionParameters`: per-data-entry peak, background, scaling, angle,
  direct-beam reference, and calculation options that should not leak to other rows.
- `DirectBeamParameters`: per-direct-beam-entry parameters such as peak/ROI values
  used when the entry acts as a direct beam.
- `PlotViewPreferences`: display-only plot and cross-section preferences. These are
  frontend model-layer state, but they should not enter backend reduction requests.
- `OffspecOptions`, `GisansOptions`, and `ExportOptions`: workflow-specific options
  used by the corresponding services.
- `ReducedDataFile`: backend-owned persistence DTOs used at the save/load boundary,
  not the live runtime session model.

Typed backend DTOs may replace or mirror these frontend option models only where
the backend contract is stable. Until then, keep adapters explicit so unstable
backend shapes do not leak into presenters or runtime session state.

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

Create the option dataclasses in frontend model/session modules unless a stable
backend DTO already exists and can be used directly without importing QuickNXS UI
or runtime objects.

Rules:

- Keep UI preferences out of backend reduction requests.
- Keep persistence compatibility fields in persistence models.
- Keep run-specific parameters on session entries.
- Keep direct-beam-specific parameters on direct-beam entries.
- Keep stitching controls on project-owned `ReductionOptions`, while keeping the
  resulting scale factor and scale error on each affected run entry.
- Keep global reduction options on the active `QuickNXSProject`, not on
  `Configuration` class attributes.
- Avoid class-level mutable state.

### Step 3: Replace Class-Level Global Configuration

Migrate global `Configuration` class attributes to a project-level
`ReductionOptions` object owned by the current `QuickNXSProject` and passed to
model services.

Update:

- configuration event handling,
- presenters that read project-level reduction options,
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

Adapters should be one-way at service boundaries where possible: presenters and
session services should work with option models, and only the compatibility call
into legacy calculation code should construct or update `Configuration`.

### Step 5: Update Backend And Persistence Adapters

Replace dictionary or legacy-configuration adapters with explicit option models where
the backend contract is stable.

Tests should verify:

- saved files preserve all supported options,
- loaded files reconstruct the same session option models,
- unknown fields remain preserved or produce clear compatibility warnings.

If backend DTOs do not yet cover a frontend option group, keep the frontend option
model and adapter in QuickNXS rather than extending backend contracts from the UI
side.

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

## Tests

Required tests:

- every legacy `Configuration` field is classified,
- legacy configuration round-trips through new option models during transition,
- project-level reduction options no longer leak through class attributes in
  migrated paths,
- per-run parameter changes affect only the intended entry,
- direct-beam parameter changes affect only the intended direct-beam entry,
- stitching control changes are read from project-owned `ReductionOptions`, and
  stitching results update only affected reduction entries,
- plot preferences do not enter backend reduction request DTOs,
- backend DTO adapters round-trip stable option fields without requiring Qt,
- domain errors are returned without UI imports,
- presenters translate domain errors into status/message models,
- progress updates can be tested with a fake `ProgressSink`,
- workspace service tests clean up Mantid state.

## Acceptance Criteria

- New option models replace legacy `Configuration` in migrated presenter/service
  paths.
- Legacy `Configuration` remains only behind adapters or compatibility code.
- Backend requests use explicit option models or stable backend DTOs.
- `QuickNXSProject` owns project-level `ReductionOptions`.
- Run-specific and direct-beam-specific parameters live on their corresponding
  session entries.
- Stitching controls are part of `ReductionOptions`, and scale-factor/error outputs
  are stored on reduction entries.
- Plot preferences remain frontend-only unless they are intentionally persisted.
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
- Backend calculation contracts can replace frontend option models only when their
  DTOs are stable and still preserve the frontend/runtime ownership boundaries.
- Backend Phase 5 stitching APIs should receive explicit reduction options and
  return scale-factor/error results that QuickNXS applies to reduction entries.
