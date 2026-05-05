# QuickNXS Architecture Documentation Overview

This overview maps the active planning documents in this folder.

## Source Of Truth

[research_mvp_architecture.md](research_mvp_architecture.md) is the top-level
architecture research document. It explains the current coupling, the target MVP
shape, the direct-beam/data-run identity rules, backend boundaries, and the
migration roadmap.

[session_identity_contract.md](session_identity_contract.md) is the active identity
contract for the roadmap. It defines when plans should compare by source run
number, file path, object identity, table/session entry ID, direct-beam entry ID,
and reduced-file `DB_ID`.

The active work is split into two roadmaps:

- The frontend roadmap covers QuickNXS UI, presenter, session, and adapter
  boundaries.
- The backend roadmap covers `mr_reduction` APIs, canonical file formats,
  calculation services, matching, stitching, and output generation.

The two roadmaps should proceed in parallel wherever their contracts allow it.

## Frontend Roadmap

| Frontend phase | Active plan | Purpose | Depends on |
|---|---|---|---|
| Phase 1: Stabilize identity and view contracts | [plan_introduce_view_interface.md](frontend/plan_introduce_view_interface.md) | Split into Phase 1A-1D: identity characterization, read-only view models, configuration inventory/adapters, and a narrow target `IMainView` without changing behavior. | Research document and identity contract |
| Phase 2: Replace shared reentrancy | [plan_phase_2_replace_shared_reentrancy.md](frontend/plan_phase_2_replace_shared_reentrancy.md) | Replace `auto_change_active` in direct-beam and reduction table paths with local signal blocking in render methods. | Frontend Phase 1 |
| Phase 3: Extract presenters | [plan_phase_3_extract_presenters.md](frontend/plan_phase_3_extract_presenters.md) | Move user-action orchestration from `MainHandler` into `ReductionPresenter`, `FilePresenter`, and `PlotPresenter`. | Frontend Phases 1-2 |
| Phase 4: Split `DataManager` | [plan_phase_4_split_data_manager.md](frontend/plan_phase_4_split_data_manager.md) | Split loaded-data cache, session entries, direct-beam repositories, reduction repositories, matching, and reduction execution behind focused services. | Frontend Phases 1-3 |
| Phase 5: Configuration, jobs, errors | [plan_phase_5_configuration_jobs_errors.md](frontend/plan_phase_5_configuration_jobs_errors.md) | Replace legacy `Configuration` with explicit option models and add job/progress/error/workspace boundaries. | Frontend Phases 1, 3, and 4; backend contracts where migrated paths use backend APIs |

## Backend Roadmap

| Backend phase | Active plan | Purpose | Depends on |
|---|---|---|---|
| Phase 1: API contracts and common models | [backend phase 1](backend/plan_mr_reduction_backend_parallel_phases.md#backend-phase-1-backend-api-contracts-and-common-models) | Define common backend request/result dataclasses, workspace helpers, and contract guidelines. | Research document |
| Phase 2: Backend facade and reduced-file I/O | [plan_phase_2_backend_facade_and_io.md](backend/plan_phase_2_backend_facade_and_io.md), [plan_reduced_data_file_io_backend_migration.md](backend/plan_reduced_data_file_io_backend_migration.md), [backend phase 2](backend/plan_mr_reduction_backend_parallel_phases.md#backend-phase-2-reduced-data-file-io) | Move backend facade and reduced-data-file work into `mr_reduction`: reduced-data-file parsing/writing, canonical output formatting, backend facade contracts, and entry-based direct-beam references. This phase does not switch QuickNXS call sites. | Backend Phase 1 where shared models are ready; can start independently with local models |
| Phase 3: Direct beam matching | [backend phase 3](backend/plan_mr_reduction_backend_parallel_phases.md#backend-phase-3-direct-beam-matching) | Provide backend matching APIs that preserve candidate identity when run numbers duplicate. | Backend Phase 1 helpful but not blocking |
| Phase 4: Specular reflectivity calculation | [backend phase 4](backend/plan_mr_reduction_backend_parallel_phases.md#backend-phase-4-specular-reflectivity-calculation) | Expose a backend specular reflectivity calculation API around existing reduction behavior. | Backend Phase 1 helpful but not blocking |
| Phase 5: Stitching, scaling, merging | [backend phase 5](backend/plan_mr_reduction_backend_parallel_phases.md#backend-phase-5-stitching-scaling-merging-and-normalize-to-unity) | Consolidate curve stitching, scale-factor, merge, and normalize-to-unity behavior in backend APIs. | Backend Phase 1 helpful but not blocking |
| Phase 6: Off-specular calculation | [backend phase 6](backend/plan_mr_reduction_backend_parallel_phases.md#backend-phase-6-off-specular-reflectivity-calculation) | Move off-specular numerical calculation and rebinning behind backend APIs. | Backend Phase 1 helpful but not blocking |
| Phase 7: GISANS calculation | [backend phase 7](backend/plan_mr_reduction_backend_parallel_phases.md#backend-phase-7-gisans-calculation) | Move GISANS numerical calculation, merging, and wavelength-band rebinning behind backend APIs. | Backend Phase 1 helpful but not blocking |
| Phase 8: Run metadata, ROI, and data type inspection | [backend phase 8](backend/plan_mr_reduction_backend_parallel_phases.md#backend-phase-8-run-metadata-roi-peak-finding-and-data-type-classification) | Make metadata extraction, ROI/peak selection, and `data_type` classification reusable backend services. | Can proceed independently; later feeds matching and reduction APIs |
| Phase 9: Raw NeXus loading and correction | [backend phase 9](backend/plan_mr_reduction_backend_parallel_phases.md#backend-phase-9-raw-nexus-loading-cross-section-splitting-and-dead-time-correction) | Provide backend APIs for event loading, cross-section splitting, and dead-time correction. | Can proceed independently around existing backend modules |
| Phase 10: Output and export artifacts | [backend phase 10](backend/plan_mr_reduction_backend_parallel_phases.md#backend-phase-10-output-and-export-artifacts) | Consolidate reduced `.dat`, ORSO, Nexus, script, catalog, and report output creation. | Coordinate with Backend Phase 2 for reduced `.dat` output |

## Future Integration Plans

These documents describe cross-roadmap adoption work that should happen after the
relevant frontend and backend contracts exist. They are not backend-phase acceptance
criteria.

- [frontend/plan_future_backend_reduced_file_io_integration.md](frontend/plan_future_backend_reduced_file_io_integration.md): switch QuickNXS save/load paths to backend reduced-file APIs through frontend adapters.

## Dependency Narrative

Frontend Phase 1 creates contracts without changing behavior. It is split into
smaller subphases so identity characterization lands first, followed by read-only
view models, configuration inventory/adapters, and the target view protocol.

Frontend Phases 2-4 can then clean up UI reentrancy, extract presenters, and move
session ownership out of `DataManager`. These phases should not wait for backend
implementation unless a specific migrated path needs a backend contract.

Backend phases can proceed at the same time because they add or consolidate
`mr_reduction` APIs and tests without requiring QuickNXS call-site changes. Backend
Phase 2 contains backend reduced-file I/O and backend-facade work only. QuickNXS
adoption of those APIs is tracked separately as a future frontend integration plan.

Frontend Phase 5 finishes frontend state cleanup by replacing legacy
`Configuration` usage and adding clear job, progress, error, and workspace
boundaries. It should consume backend contracts only where those contracts already
exist; it should not block unrelated frontend cleanup.

## Cross-Cutting Consistency Rules

Use these rules across all active plans:

- Run number is source-run identity, not mutable table-entry identity.
- Direct-beam and reduction/data table rows need stable entry IDs.
- Direct-beam/data-run pairing should use direct-beam entry identity, not direct-beam
  run number.
- Reduced-file `DB_ID` should be treated as a file-local direct-beam entry reference,
  not as a run-number alias.
- Use file path for loading/cache identity, not mutable session-entry identity.
- Use object identity only inside cache or adapter internals where object lifetime is
  the subject of the operation.
- View models and backend DTOs should be plain Python and Qt-free.
- Presenters should not import Qt widgets or Mantid workspace globals.
- QuickNXS owns GUI orchestration and live session reconstruction.
- `mr_reduction` owns reusable backend contracts, canonical reduced-file parsing,
  canonical reduced-file writing, and backend output formatting.
- Legacy `Configuration` remains behind adapters until the frontend configuration
  phase removes it from migrated paths.

## Active Document Set

These are the active documents covered by this overview:

- [research_mvp_architecture.md](research_mvp_architecture.md)
- [session_identity_contract.md](session_identity_contract.md)
- [analysis_refactoring_plan.md](analysis_refactoring_plan.md)
- [frontend/plan_introduce_view_interface.md](frontend/plan_introduce_view_interface.md)
- [frontend/plan_phase_2_replace_shared_reentrancy.md](frontend/plan_phase_2_replace_shared_reentrancy.md)
- [frontend/plan_phase_3_extract_presenters.md](frontend/plan_phase_3_extract_presenters.md)
- [frontend/plan_phase_4_split_data_manager.md](frontend/plan_phase_4_split_data_manager.md)
- [frontend/plan_phase_5_configuration_jobs_errors.md](frontend/plan_phase_5_configuration_jobs_errors.md)
- [frontend/plan_future_backend_reduced_file_io_integration.md](frontend/plan_future_backend_reduced_file_io_integration.md)
- [backend/plan_mr_reduction_backend_parallel_phases.md](backend/plan_mr_reduction_backend_parallel_phases.md)
- [backend/plan_phase_2_backend_facade_and_io.md](backend/plan_phase_2_backend_facade_and_io.md)
- [backend/plan_reduced_data_file_io_backend_migration.md](backend/plan_reduced_data_file_io_backend_migration.md)
