---
id: TASK-38
title: Establish guarded coherent release deployment
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-02 22:00'
updated_date: '2026-11-03 01:47'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace the stopped archived Watchtower deployment path with one project-owned guarded updater driven by a coherent, verifiable release record from the protected GitHub publisher. Preserve production data/configuration and require pre-deployment backup/restore proof, exact image identity, bounded health checks and image-only rollback. Activation is covered by the owner’s approval to finish the remaining migration; preserve existing safety boundaries and private history.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A release becomes deployable only after all image gates/pushes and the protected trusted-main workflow succeed; its record binds the exact three digests and source identity without mutable-tag mixing.
- [ ] #2 The sole updater verifies release authenticity/identity, refuses unexpected configuration or schema-contract changes, backs up and verifies recovery within budgets, and either deploys the exact set healthily or performs one bounded image-only rollback.
- [ ] #3 Offline failure-path tests and controlled live deployment evidence cover coordination, cleanup, health, identity, rollback behavior, restart safety and no secret disclosure.
- [ ] #4 Only the new reviewed publisher and updater are activated after validation; legacy publishing and Watchtower stay disabled, existing protections/scopes/data/binds are preserved, and active deployment state is durable and auditable.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Define the signed immutable release-record contract and explicit deployment/schema compatibility fingerprint. Test the release-validation interface first: it catches malformed/mixed/untrusted/unfinished releases, not Docker or provider behavior.
2. Extend only the protected publisher to publish/sign the release record after all image gates and pushes; use short-lived GitHub OIDC rather than a new signing secret. Preserve owner environment review and read-only fork CI. Verify the actual pinned signing client and identity semantics.
3. Implement one project-owned VPS updater around the proven backup/restore/configuration/identity/health/one-shot rollback behavior. Test its deployment-transaction interface with external Docker/registry/API/storage adapters; add real synthetic backup and crypto/transport fixtures.
4. Keep installed deployment/schema contract changes manual, durable state locked/atomic, logs value-redacted and failed releases fenced. Never execute operator code fetched from an unverified release.
5. Publish and verify one controlled signed release, validate production access and dry-run behavior, then exercise a guarded deployment and enable only the single new updater/publisher. Preserve the stopped legacy updater and disabled old publisher.
6. Independently recheck healthy exact running digests, recovery proof, configuration/volume identity, no secret disclosure, and repeat/restart/failure safety. Source/protection review remains exact-head and Gmail-attributed.

Owner preapproved remaining migration work and routine implementation/validation; no extra per-step approval prompt is needed. Test interfaces are release validation and deployment transaction, with real provider/CLI compatibility verified separately before activation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Owner explicitly approved completion of remaining migration work. Proposed direction: immutable three-image release record published only after all pushes, authenticated provenance, and one VPS-owned guarded updater with existing tested backup/recovery/identity safeguards. Do not reactivate archived Watchtower, create parallel active updaters, bypass protected environment review, or silently accept schema/configuration changes. Architecture/details are being validated before code or activation.

- Designed one signed OCI release record binding all three immutable image references, source/run identity and a conservative runtime/schema compatibility fingerprint. Only the protected publisher receives short-lived OIDC signing permission; no static signing secret. Legacy updater/publisher fences remain untouched.
- Added vertical red/green tests and release validation/creation modules: strict bounded JSON, duplicate/unknown-field rejection, exact namespace/digests, fixed signer/issuer/source binding, exact successful trusted-main CI identity and manual contract-change gate. Added a CLI builder tested through a fake external Docker interface.
- Extended the still-disabled publisher to check current main, publish a scanned metadata-only release artifact after all app pushes, sign/verify with pinned Cosign v3.1.4, and promote one pointer only after verification. Native actionlint and workflow guard tests pass; real keyless registry compatibility is not yet claimed.
- Pinned Cosign binary checksum/help verified. Production has a functioning user-systemd manager with lingering enabled and Docker/buildx; no new updater or signer was installed there. Read-only actual buildx descriptor output matches the already-published backend receipt.
- Remaining before activation: real crypto/transport fixtures, VPS guarded transaction/state/restart/rollback module, controlled signed-release/live verification and one-updater activation. Keep this source work draft until those checks pass.

Signed-release preparation is in draft PR #10. Added tested decision rules for no-op active releases, stale/failed release fencing and interrupted-operation recovery priority; a rollback already started cannot be retried automatically. A trusted CI run still finishing is explicitly deferred rather than treated as a failed deployment attempt. Durable state, real verifier/transport adapters and the actual VPS transaction/updater remain unfinished; nothing new is activated.

Self-review tightened replay fencing: the highest attempted release order is separate from the active image order and must survive rollback. Added a red/green test showing an older signed release cannot become eligible merely because a newer deployment rolled back. This is still a pure decision module, not durable state or production transaction execution.

- Added the durable deployment-transaction interface with private bounded/schema-checked state, no-follow reads, flock, atomic writes plus file/directory fsync, retained attempt receipts, and a replay high-water mark preserved through rollback. Recovery is processed before any new candidate.
- Twenty transaction tests exercise real filesystem/locking and an actual killed child process, plus external runtime failure fixtures: partial/failed/interrupted rollback, cleanup retry without redeployment, preflight drift without overwriting unknown runtime, snapshot freshness/budgets, failed-release fencing, audit retention and malformed/symlink state refusal. Backend changes cannot begin while owned plaintext remains.
- Self-review added rejection of expired receipts after slow cleanup, distinct filesystem-vs-lock errors and a stop before exhausting failure-fence capacity. These tests prove transaction behavior, not live Docker/Restic/R2/Cosign compatibility. Runtime adapter, record transport and installer/timer are still pending; production and publisher fences unchanged.

- Ported the proven SQLite/Restic backup helper into maintained source and hardened restart cleanup: operation-specific ownership discovery, exact scratch-mount validation, idempotence and child-environment minimization. Four real, network-disabled rootless-Docker fixtures passed, including WAL snapshot/exact encrypted restore, missing-repository refusal and cleanup from a new operator instance. Added the same fixture gate after the backup-image build in hosted CI; no production storage was used.
- Added a pinned Cosign invocation adapter with exact immutable reference/issuer/workflow/repository/ref/source checks, binary checksum verification, redacted subprocess failures and filtered environment. Three external-executable protocol tests pass; actual protected keyless/registry compatibility remains pending. The ported R2 signer also matched the independent pinned Botocore signer with synthetic credentials and a mocked transport.
- Full local suite with real backup and pinned source-map fixtures: 77 tests passed, no skips. Actionlint, comment-policy (278 files), whitespace and secret checks passed. This remains draft source: authenticated artifact transport, full production runtime adapter and installer/timer are not yet complete or activated.

- Implemented the immutable record loader: authorize publisher before bounded pulls, resolve one digest, read a bounded Docker export in memory without running/extracting artifact code, verify exact source-bound signature and successful trusted workflow. Actual Docker archive export compatibility passes locally; hosted CI includes the fixture.
- Added the production Docker runtime adapter around the proven cutover: fixed project/bind anchors, credential-bearing configuration equality via private HMAC without stored values, physical-volume/data/account guards, explicit pull budgets, existing backup idleness/access/identity, known-good backup image, health-gated app-only switch and one image-only rollback. External Docker/Compose fixtures cover preserved settings, drift refusal and expected missing-container recovery.
- Added version-bound CLI bootstrap/status/check/once and a fail-closed disabled user-unit installer. Read-only check cannot trigger recovery. User units are not installed/enabled yet; confirmed production Doppler and system Python locations. Remaining before activation: exact-head CI/source review, real production no-service-change preflight, protected keyless signing trial and guarded deployment. TASK-39 and TASK-40 now track dependency/open-work and final cross-system checks.

Actual production no-service-change preflight exposed an optional Docker Config.Volumes template issue before mutation. Container identities/start times stayed unchanged. Added null-safe Volumes and Labels lookups, preserving required provenance checks, and actual Docker metadata compatibility coverage. Retained the failed attempt evidence; no image/service/credential or safety invariant was relaxed.
<!-- SECTION:NOTES:END -->
