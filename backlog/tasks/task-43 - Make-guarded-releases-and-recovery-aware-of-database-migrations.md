---
id: TASK-43
title: Make guarded releases and recovery aware of database migrations
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-03 15:51'
updated_date: '2026-11-03 20:23'
labels:
  - deployment
  - database
dependencies:
  - TASK-42
references:
  - scripts/release_record.py
  - scripts/deployment_transaction.py
  - scripts/deployment_runtime.py
documentation:
  - docs/plans/database-migration-delivery.md
  - docs/operations/database-migrations.md
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Integrate the journaled SQLite foundation into the signed-release and guarded-updater protocol so eligible database migrations can accompany normal green main releases without recurring production approvals. Preserve the current image-only path until a separately reviewed activation; do not remove contract checks without replacement evidence.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Signed release metadata binds the exact backend image and immutable migration catalogue to a versioned migration protocol; compatible catalogue additions no longer require manually repinning the entire startup-file fingerprint, while unrelated operating-contract changes remain guarded.
- [ ] #2 Migration releases serialize deployment, prepare before downtime, quiesce the old backend and all its HTTP/background writers, verify a fresh encrypted backup and isolated restore of the stopped state, then migrate before requests or background jobs are accepted.
- [ ] #3 Durable recovery distinguishes unchanged or rolled-back migration history from committed or uncertain schema changes; prior-image rollback is permitted only with verified compatibility, and incompatible/unknown states stop safely rather than restoring live data, repeating migrations blindly or launching an incompatible old image.
- [ ] #4 The first automatic policy supports reviewed backward-compatible bounded migrations; destructive changes, unbounded backfills, provider-managed Hangfire schema changes and operator/infrastructure changes are not implicitly authorized. A declaration alone is not treated as proof of compatibility.
- [ ] #5 Real SQLite/container and process-kill fixtures verify migration failure, commit-before-health-failure, restart/concurrency, backup budgets/cleanup and preservation of data/mount/auxiliary identities; existing signing, CI, replay/failure fences and secret boundaries remain enforced.
- [ ] #6 Production remains on the existing reviewed path until an explicit adoption/upgrade procedure is approved; no automatic operator upgrade, ledger reset, database initialization, restoration, pruning or credential change is introduced.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Extend the migration interface with read-only readiness validation and a restricted automatic-expansion policy. Verify existing schema and data preservation, reject destructive or unbounded/non-eligible operations, and add regression fixtures before integrating deployment. Keep arbitrary data/backfill migrations outside automatic scope.
2. Add a bounded credential-free migration CLI inside the backend image: describe the embedded catalogue, inspect schema/history, perform explicitly authorized baseline adoption, and apply eligible pending migrations without HTTP, Hangfire workers, network access or runtime service credentials. Production application startup must validate complete history before accepting requests/jobs, not independently execute unbacked pending migrations.
3. Version the signed release metadata to bind exact catalogue identifiers/checksums and migration protocol to the immutable backend image. Preserve strict source/signature/completed-CI checks and a bounded legacy-reader path; catalogue additions must not require changing the installed operating contract. Keep infrastructure/engine/runtime assumptions guarded.
4. Extend the durable transaction/runtime adapters: detect pending/adoption work before mutation; journal quiescing intent, stop all owned backend writers and backup daemon, reject unknown volume writers, then obtain fresh bounded encrypted backup/isolated restore. Run the verified migration CLI under bounded private Docker execution before application startup.
5. On interruption/failure, compare durable schema/history against the recorded before/expected states. Preserve the existing one-image-rollback path only when database compatibility is proven; committed or uncertain schema changes must never launch an incompatible prior artifact or restore live data. Provide an explicit fail-closed/manual-recovery or verified candidate-resume path, without endless retries.
6. Exercise real SQLite/container/process-kill fixtures, startup readiness ordering, partial/failed migration and commit-before-health failure, backup budgets/cleanup, no-op/legacy image-only behavior and all existing trust/runtime invariants. Preserve public/fork CI secret isolation and separate Hangfire ownership.
7. Keep integration on an unmerged reviewed branch while it changes the deployment contract. No production schema reads, service changes, updater upgrade, state edits or publication hold. Prepare the exact activation prerequisites and fail-closed baseline preflight for separate owner approval after offline verification.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Owner already approved the staged development scope, including migration-interface and real SQLite/container/process recovery seams. Foundation code head 96c1852 passed hosted CI; draft PR #21 remains unmerged. Integration branch feat/migration-aware-delivery starts from foundation completion commit 0c58370. No live operations are authorized. Retain strict history semantics: an older artifact missing a committed migration cannot be treated as rollback-compatible merely because its code might accept the new columns. Automatic first scope should favor structural expansion (new tables, safe indexes, nullable columns) rather than claiming arbitrary SQL semantic safety.

Implemented first offline slices: read-only requireReady checks exact complete catalogue/history and the immutable expected schema without executing pending SQL. Added AutomaticUpgrade with an exact reviewed-before schema/history and an explicit database budget (at most the existing 256 MiB ceiling).
Native authorization plus transactional before/after schema checks restrict expansion: preserve old object/root identities and columns, reject data rewrites, removals/renames, new triggers/views/virtual tables and complex/unique/partial indexes; allow simple nullable columns, ordinary nonunique indexes and new tables. Existing row values are compared using per-operation in-memory HMACs, with random key erased after use and no row values/hashes exported. A native max_page_count fixture proves over-budget index creation rolls back the whole batch and does not leave that lower limit on a new connection; this is not a WAL/temp/filesystem quota.
Current Infrastructure suite: 83 passed, including 21 new delivery-policy cases and all 43 foundation migration cases. Source-backed SQLite documentation confirms the database-file page limit/SQLITE_FULL behavior; runtime container/WAL/temp and wall-clock safeguards are still required in the integration. Foundation final metadata head 0c58370 also passed hosted CI 41681447547 and comment runs 41681446997/41681435330. Draft PR #21 stays unmerged. No live operations.

Added strict delivery metadata and deterministic source/schema descriptors, with independent canonical-hash fixture and malformed/tampered-input tests. Source manifest distinguishes baseline, automatic-schema and manual entries; declaration alone cannot bypass native expansion enforcement. Runtime metadata contains no SQL or row values. Added 16 MiB total catalogue bound in addition to per-script/count caps.
Added a separate credential-free migration executable and real process tests for build/describe/inspect, verified apply with target checked before commit, stale retry refusal, pending-manual refusal, baseline-only adoption and explicit native SQLite settlement. A 6 MB spill/kill fixture leaves a hot rollback journal: read-only inspection refuses it; only the named settle operation recovers readable prior history without executing pending SQL. No production startup, Docker packaging, publisher or Python updater wiring yet.
All 181 backend tests pass with zero skips (Infrastructure 106); new code adds no compiler warnings. Fantomas passes and full comment policy checks 316 files with zero violations. The current backup helper was confirmed to back up only ignite.db, not Hangfire; keep that scope explicit. Remaining work is packaging/startup, signed-record/controller integration, real container/recovery fixtures and a separately approved activation transition.

Prepared-command commit 4ffce8768d197e6fac965d776b2f9aa199aaace6 is published in draft PR #22, unmerged. Its initial foundation-branch base only triggered comment checks because CI filters PR bases to main. Retargeted this owned draft to main (still includes foundation #21) so the next source push gets the real CI gates; no workflow/protection/publishing policy was changed.
Python protocol work now has observed red/green tests for bounded nonblocking stdin, strict descriptor/history/source binding, resolved Hangfire package-content identity, v2 signed-record validation/creation, split host-configuration versus application-protocol fingerprints, and unstarted immutable-image metadata extraction. V2 validation requires explicit policy opt-in, and the legacy transaction driver explicitly rejects migration-bearing releases rather than silently using image-only rollback. Publisher CLI supports an explicit migration flag, not yet wired into the workflow. All 116 script tests pass (seven existing native-fixture skips locally). Container writer lifecycle and migration-aware durable state are still unfinished; no activation or production access.

Current Python protocol/plumbing verification: 116 tests run, OK, with seven existing native fixtures skipped locally (109 executed successfully); 321 files pass comment policy. Native .NET migration commands and policy suite remain at 181 passing backend tests. The protocol can now create/validate source-bound v2 records and copy image metadata without starting containers, but the workflow/default transport and transaction driver do not activate migrations. Exact production legacy schema is still unknown; source-derived EF schema is not a substitute for an approved metadata-only inventory.
<!-- SECTION:NOTES:END -->
