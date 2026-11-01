---
id: TASK-28
title: Prepare clean MIT-licensed public repository candidate
status: Done
assignee:
  - '@pi'
created_date: '2026-11-01 00:14'
updated_date: '2026-11-01 00:35'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Prepare a local-only clean source snapshot for ignite-for-spotify-app, with MIT licensing, public-safe validation and disabled production publishing. Preserve the original private repository and existing production deployment; no remote or production changes in this task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Candidate excludes database sidecars, runtime state and inherited Git history, with a reproducible manifest and export guard.
- [x] #2 Original code has MIT licensing and third-party terms are inventoried with unresolved redistribution obligations explicitly documented.
- [x] #3 Hosted-runner CI validates the candidate without service secrets; production publishing is disabled by default and gated on trusted main and successful validation.
- [x] #4 Active repository identity and controller validation target ignite-for-spotify-app without weakening controller safety or changing existing image pull coordinates.
- [x] #5 Isolated verification results and all blockers are recorded; no remote, credential or production changes occur.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Export the approved baseline into an independent local candidate; exclude database sidecars and empty archive.
2. Add MIT and third-party documentation, export guard, and scoped repository identity changes.
3. Prepare hosted-runner CI and trusted-main publishing disabled by default, without changing production image identities.
4. Resolve dependencies in an isolated environment, run synthetic/fixture validation, and inspect dependency notices.
5. Self-review manifests/diffs and record tests and blocked publication/cutover gates.

Owner approved this local-only scope before implementation; remote creation/publication and production handover remain unapproved.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Prepared an independent local candidate from the approved baseline; excluded the two database sidecars and empty ZIP. Added MIT and a tested publication-artifact guard.
- CI uses hosted runners and frozen frontend dependencies. Publishing is reusable-only, requires successful validation for the same revision, trusted main and an explicit enable variable; no production secret bundle is inherited.
- Updated the controller exact-repository allowlist and added old/fork-repository rejection coverage.
- Backend: 94 tests pass on the exact CI SDK 10.0.401. Frontend: 37 tests plus lint/typecheck/build pass on Bun 1.4.2. Controller: 102 tests, ruff, strict pyright and fixture report pass. Comment policy: 13 tests and zero violations. Synthetic backup snapshot/restore image build passes.
- Exact package metadata and installed notices are recorded, with missing notice text and release-image license obligations explicitly left for review. No full image-redistribution clearance claimed.
- Full handover includes issues/PRs, contributor checkouts, BB/agent workspaces, Renovate/apps, controller, infra ownership, CI and the sole production publisher; old repository is history-only after coordinated cutover.
- No remote writes, credentials or production changes. Final export review and handover approval remain pending.

- Final local verification passed; source-only Gitleaks scan found zero matches. Known WAL/SHM blobs are absent from the independent candidate object store.
- New target is the sole intended home for development AND CI/CD; this local task does not mark the overall migration complete. Creation/push, final public visibility and production/integration handover still require separate approvals.
- Baseline files and upstream notice texts retain some pre-existing whitespace; working-tree diff checks and workflow syntax/safety assertions pass.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Prepared a clean-root, MIT-licensed local candidate for ignite-for-spotify-app without changing the original private repository or production.

Changes:
- Excluded database sidecars/empty archive; added source-artifact guard, ignore coverage, Docker context exclusions and third-party notice inventory.
- Prepared hosted-runner validation and disabled-by-default production publishing gated by exact trusted main, CI completion and environment protection. Preserved existing image identities.
- Retargeted controller configuration with regression coverage, and documented the full development/CI/CD handover rather than a permanent mirror.

Verification:
- 94 backend, 37 frontend, 102 controller, 13 comment-policy and 4 publication-guard tests passed.
- Frontend lint/typecheck/build, controller lint/format/typecheck/fixture report, actionlint, static workflow gates and synthetic container backup/restore passed.
- Source-only secret scanning found no matches.

Remaining gates:
- No GitHub creation/push/publication or production actions performed. Actual release-image redistribution/security obligations, GitHub protection/package/environment setup and full operational handover remain separately reviewed and approved.
<!-- SECTION:FINAL_SUMMARY:END -->
