---
id: TASK-35
title: Cut over verified public images with guarded recovery
status: Done
assignee:
  - '@pi'
created_date: '2026-11-02 18:42'
updated_date: '2026-11-02 21:18'
labels: []
dependencies: []
references:
  - docs/operations/runtime-cutover-plan.md
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Deploy the already-published and pull-verified public-repository release without changing production identities or credentials. Owner approved the guarded runtime plan, including one image-only rollback if needed. Preparation is blocked at R2 storage/accounting authentication before any service pause, backup/restore or app change; recover that access before continuing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The reviewed exact digests, hydrated configuration, source revision, physical volumes, bind paths, credentials and rollback references are verified before changing services; unexpected drift stops the operation.
- [x] #2 A fresh encrypted snapshot of the existing database and an isolated verified restore succeed within reviewed storage budgets, without repository initialization, pruning, retention changes or plaintext disclosure.
- [x] #3 Only backend, backup and frontend are recreated to the approved digests; readiness, frontend responses, backup health and existing data ownership/paths pass while Caddy and Alloy identities and bindings remain unchanged.
- [x] #4 A failed service switch follows the preapproved one-shot image-only rollback or stops for operator recovery; no database restore or arbitrary repair occurs automatically.
- [x] #5 The existing Watchtower is explicitly paused and both publishers remain fenced at handoff; temporary tooling/plaintext is removed, retained state/history is preserved, and continuing CD is not falsely declared complete.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Obtain explicit approval of docs/operations/runtime-cutover-plan.md, including short service interruption, bounded backup/restore tooling, existing updater pause and one image-only rollback if needed. Until approval, keep work read-only.
2. Implement and validate only bounded operator tooling with synthetic data/dry-run configuration. Refresh identities, fences, storage, backup activity, exact digest access and secret-redacted configuration comparisons; stop on drift.
3. Create the absent clean public production checkout pinned to 4ef6b03 and persistent non-secret digest/rollback overrides. Keep old checkout and relative bind anchor, explicit project ignite-for-spotify, and all credentials/data/volumes/settings unchanged.
4. Stop existing Watchtower, coordinate the old backup daemon, and use no-init/no-prune tooling for one fresh encrypted snapshot plus exact-ID isolated restore/integrity proof. Enforce input/scratch/incremental-storage budgets and remove owned plaintext only. Resume old backups and stop if this phase fails.
5. Recreate only backend, then backup/frontend, using exact digests, no build/pull/dependency recreation and bounded health waits. Verify exact running identities, readiness/static responses, backup state and unchanged Caddy/Alloy/mounts.
6. On a failed switch, use only the preapproved old-image rollback once, with the same data/configuration. Never restore the database automatically; stop if rollback health fails.
7. Leave Watchtower and both publishers fenced. Record evidence and remaining CD/integration boundaries; do not treat digest-pinned runtime adoption as completion of continuing automatic CD.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Continue was treated as permission to prepare the concrete runtime plan, not as permission to mutate services.
- Read-only comparison found all 33 selected backend source/config files identical to deployed revision 5028436. Hydrated public Compose configuration passed digest/mount invariants, with no managed environment changes/removals for the three app services; Caddy/Alloy/Watchtower bind paths match when using the existing old docker directory as project-directory. Secret values stayed inside private production-side subprocesses.
- Existing Watchtower targets only the three app containers, polls every 30 seconds and enables cleanup. Upstream is archived. Plan pauses this existing instance; no upgrade, replacement or second updater is proposed.
- Existing backup wrapper can auto-initialize on repository-read failure and prune on Sundays, so it will not be used unmodified for the bounded cutover backup. No live backup/restore/service change has been performed.
- Current database is 71,483,392 bytes, owned 999/999 with mode 0600; free space was about 16.2 GB. New production checkout path is absent. Compose 5.1.3 supports the reviewed explicit project-directory/pull/wait controls.

Concrete plan written to docs/operations/runtime-cutover-plan.md. Proposed budgets: snapshot input <=256 MiB, scratch <=1 GiB with >=3 GiB free, additional R2 storage <=512 MiB (checks are not a hard billing cap). Execution and conditional image-only rollback are awaiting owner approval. No live backup/restore, new checkout creation, publisher activation or service change occurred.

Owner explicitly approved execution of the documented guarded cutover, bounded backup/restore drill, short interruption and at most one image-only rollback on failed health checks. Watchtower and both publishers must remain paused afterward. Implementing/testing bounded operator tooling before any service mutation.

- Owner-approved operator tooling passed six local tests, including a real synthetic WAL-mode snapshot/exact restore/cleanup, refusal to initialize a missing repository, storage-inventory parsing and image-only rollback of only changed services. The custom SigV4 request also matches an independent Botocore S3 signer with synthetic credentials.
- A launch-wrapper quoting issue was caught before any phase process started; corrected and generated remote code is now syntax-checked before transport.
- Prepared the new production checkout pinned to 4ef6b0380b2474be921fa46ae31b45ccab4782b8, with local Gmail author policy and push disabled. Created private non-secret candidate/rollback overrides and durable bounded operator records. No old checkout was changed.
- BLOCKED in prepare: existing backup-bucket ListObjects accounting returned HTTP 401 / Unauthorized using the same credentials as the running backup container. The trailing-slash equivalent also returned 401; an independently signed HEAD of the existing config object returned 401. No credential values were printed or persisted. Root cause is not yet established; credential revocation/expiry is not asserted as fact.
- A bounded read using the existing Restic client did not finish within 60 seconds. Its exact owned read-only/no-lock exec was identified and terminated; final readback found no remaining Restic probe process. The backup daemon itself was never stopped.
- No backup or switch phase started; no snapshot upload/restore/marker write, app recreation, Watchtower stop, rollback, credential change, initialization/pruning or IaC apply occurred. All six original container IDs/start times/images/projects/mounts are unchanged and applicable container health remains healthy. Both publishers remain fenced.
- Preserve the failed prepare report and new checkout/operator state. Do not blindly rerun prepare (paths now exist), relax storage accounting, borrow broader backup credentials or re-enable publishing. Need scoped backup-access diagnosis/recovery before revalidating the prepared environment and resuming the already-approved runtime plan.

TASK-36 is handling the separately approved same-scope backup-access recovery. Independent SDK and both hosts receive 401; bucket exists, but token-administration metadata access is denied to the existing operator credential. Waiting for a secure human dashboard handoff. Runtime cutover remains stopped before backup/service phases.

Scoped R2 recovery succeeded with the user-supplied bucket-only pair. Read-only revalidation passed on the known-owned pinned checkout and overrides, preserving all unrelated identities. Fresh encrypted snapshot/exact-ID restore passed pinned-client verification and SQLite integrity within budgets; only 4,808 additional remote bytes, owned tool/plaintext removed and fresh success marker set. Backend/frontend still unchanged; existing updater and backup daemon are paused for the approved service switch.

- Scoped credential recovery completed without broader permissions or changes to repository/encryption identity. Only backup credentials were refreshed on its original image, with the existing updater paused under the cutover approval. Canonical mount ordering fixed a verifier-only false drift; all mount attributes remain checked.
- Read-only resume revalidated the known-owned clean public checkout, exact overrides, updated backup identity and all untouched services; no clone/reset or blind retry of failed preparation.
- Approved backend-then-backup/frontend switch completed successfully at exact 4ef6b03 digests. No image rollback or live database restore was needed.
- Independent readback confirms all three app containers healthy at expected digest/source/configuration; public frontend HTTP 200, internal readiness successful, served frontend targets isolated GlitchTip project 8, running backup can read the same Restic repository, backend effective UID/GID 999/999, preserved data inode/ownership and mounts. Caddy/Alloy IDs/start times/images/binds unchanged.
- Fresh snapshot was 71,933,952 bytes; isolated restore verified and integrity checked; scratch peak 143,953,920 bytes, incremental remote storage 4,808 bytes. Owned plaintext/tooling and secure credential handoff file removed; no temporary containers remain.
- Existing Watchtower is stopped and both publishers remain fenced as approved. Active non-secret override: /home/scowalt/.local/state/ignite-cutover-4ef6b03/images.compose.json on production. Public checkout remains pinned to 4ef6b0380b2474be921fa46ae31b45ccab4782b8; old checkout retained as bind anchor/history.
- Updated local handoff/instruction docs to reflect actual runtime state and the intentional source-true/live-false publisher drift. Continuing CD, remaining integrations and wider migration are not complete.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed the guarded production cutover to the verified public-repository release.

- Restored scoped R2 access under the separate credential-recovery approval, preserving all non-target secrets and the existing repository/encryption password.
- Created a fresh encrypted snapshot, restored its exact ID in isolation with verification and SQLite integrity, stayed within all storage budgets, and removed owned plaintext/tooling.
- Recreated only backend, backup and frontend at the published immutable 4ef6b03 digests. Health/readiness, public frontend response, active frontend project-8 routing, backup access, effective backend UID/GID and persistent data/mount identity passed.
- Caddy/Alloy and retained source/history were preserved. No image rollback, database restore, schema migration, repository init/prune, credential-scope expansion, publication or DNS change was needed during the runtime switch.

Existing Watchtower and both publishers remain intentionally paused. Durable image/rollback overrides and private execution evidence are retained. Continuing CD and wider integration handover require their next separate plan; full migration is not claimed complete.
<!-- SECTION:FINAL_SUMMARY:END -->
