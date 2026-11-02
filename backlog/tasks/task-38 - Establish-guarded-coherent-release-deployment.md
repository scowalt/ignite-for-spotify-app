---
id: TASK-38
title: Establish guarded coherent release deployment
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-02 22:00'
updated_date: '2026-11-02 23:21'
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
<!-- SECTION:NOTES:END -->
