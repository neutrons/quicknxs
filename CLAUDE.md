# quicknxsv2 (neutrons/quicknxs) — Agent Instructions

## Project identity
This is the **upstream institutional project** (`neutrons/quicknxs`) for the
Magnetism Reflectometer data reduction GUI at ORNL/SNS.  It is distinct from
`quicknxsv1` (`bvacaliuc/quicknxs`), which is a fork.  Changes here follow
SNS/ORNL data-reduction conventions and require `mr_reduction` / `mantid`
compatibility.

## Layout and tools
- **`src/` layout** — package lives at `src/quicknxs/`; tests under `test/`
- **Build tool:** `pixi` (no Makefile); use `pixi run <task>` for all operations
- **Key pixi tasks:** `test`, `conda-build`, `audit-deps`, `build-docs`
- **Versioning:** Git-tag-based via `versioningit` (hatchling backend)
- **Platform:** linux-64 only

## Branching model
- **`next`** — integration branch; all PRs target `next`
- **`qa`** — staging; promoted from `next`
- **`main`** — stable release; promoted from `qa`
- Never commit directly to `next`, `qa`, or `main`

## Branch naming conventions
- `EWM{number}_{description}` — work items tracked in the SNS work management system
- `bugfix_{description}` or `fix_{description}` — bug fixes
- `{user}/{description}` — personal/agentic branches (see Agent workflow below)
- `dependabot/**`, `pre-commit-ci-*` — automated dependency/tooling branches

## CI/CD (`.github/workflows/test_and_deploy.yml`)
- **Triggers:** push to `next`/`qa`/`main`, pull requests, `v*` tags, manual dispatch
- **`tests` job:** pytest with coverage → Codecov upload
- **`build` job:** conda package build → conda-verify
- **`publish` job:** on `v*` tags only — uploads to Anaconda (label `rc` or `main`)
- **`deploy-dev` job:** on push to `next` only — triggers GitLab CI dev deployment
  ⚠️  Merges to `next` automatically trigger a dev environment deployment.
- **Lockfile updates:** monthly via `update-lockfile.yml`, targets `next`

## Required secrets
- `CODECOV_TOKEN` — coverage uploads
- `ANACONDA_TOKEN` — conda package publishing (release only)
- `GITLAB_DEPLOY_TOKEN` — dev deployment trigger (on `next` pushes)

## Pre-commit hooks
Pre-commit runs ruff (lint + format) automatically; CI (`pre-commit.ci`) will
push auto-fixes to PRs.  The `pixi-lock-check` hook runs at pre-push stage.
Do not bypass pre-commit; it is enforced in CI.

## Test data
Integration tests use `git-lfs`; the `test/data` submodule must be initialised.
Unit and UI tests do not require LFS.

## Agent workflow for this repository
This is an institutional repo with controlled write access.  Claude operates
under the following constraints:

**Read-only via `origin`:**
```bash
git fetch origin        # OK
git log origin/next     # OK
git push origin ...     # NOT permitted
```

**Branch creation and push is performed by the human contributor.**
The agreed convention is `{user}/{feature-description}` for agentic branches.

**Draft PR creation via PAT:**
After the human has pushed a `{user}/` branch, Claude may use the PAT
(extracted from the `upstream` remote URL) to open a **draft PR** targeting
`next` via the GitHub REST API:
```
POST https://api.github.com/repos/neutrons/quicknxs/pulls
{ "draft": true, "head": "{user}/{feature}", "base": "next", ... }
```

**Claude's session workflow:**
1. Prepare all changes for a logical task on the local `{user}/agentic-knowledge`
   branch (or a task-specific branch agreed with the user).
2. Commit locally with descriptive messages.
3. Ask the user to push: `git push origin {user}/{feature-description}`.
4. Once confirmed, create a draft PR via the PAT.
5. The user reviews and promotes the PR from draft to ready when satisfied.

**Do not** open non-draft PRs, merge PRs, or modify branch protection settings
on this repository without explicit instruction.

## GitHub Actions gotchas (cross-project lessons)
- `GITHUB_TOKEN` pushes are silenced by GitHub's anti-loop protection; any
  workflow creating a branch that needs CI to run on it must use a PAT instead
- `workflow_dispatch` check runs do **not** satisfy PR branch protection —
  only `push`/`pull_request` event check runs count
- Enable `delete_branch_on_merge` to avoid stale branch accumulation:
  `PATCH /repos/neutrons/quicknxs {"delete_branch_on_merge": true}`
