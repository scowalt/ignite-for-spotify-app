---
id: TASK-38
title: Establish guarded coherent release deployment
status: Done
assignee:
  - '@pi'
created_date: '2026-11-02 22:00'
updated_date: '2026-11-03 04:43'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace the stopped archived Watchtower deployment path with one project-owned guarded updater driven by a coherent, verifiable release record from the protected GitHub publisher. Preserve production data/configuration and require pre-deployment backup/restore proof, exact image identity, bounded health checks and image-only rollback. Activation is covered by the owner’s approval to finish the remaining migration; preserve existing safety boundaries and private history.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A release becomes deployable only after all image gates/pushes and the protected trusted-main workflow succeed; its record binds the exact three digests and source identity without mutable-tag mixing.
- [x] #2 The sole updater verifies release authenticity/identity, refuses unexpected configuration or schema-contract changes, backs up and verifies recovery within budgets, and either deploys the exact set healthily or performs one bounded image-only rollback.
- [x] #3 Offline failure-path tests and controlled live deployment evidence cover coordination, cleanup, health, identity, rollback behavior, restart safety and no secret disclosure.
- [x] #4 Only the new reviewed publisher and updater are activated after validation; legacy publishing and Watchtower stay disabled, existing protections/scopes/data/binds are preserved, and active deployment state is durable and auditable.
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

- PR #10 merged through exact-head/Gmail controls as 2ee6cc66ffb936d6c63fdb22d9f3d56a8fb59bea. Main operator bundle passed actual production preflight with all container identities/start/running states unchanged; signer and user units were installed disabled, and the existing runtime baseline was verified and bootstrapped. No timer or publisher was enabled.
- Activation is blocked before any OpenTofu plan/apply: the existing mission-control/dev AWS state pair returns 401 on all three existing state objects. Independent Botocore HEAD also returns 401; server clock difference is under one second; the Cloudflare control API confirms the existing opentofu-state bucket still exists. No AWS_SESSION_TOKEN name is configured. A replacement S3 pair limited to this state bucket is needed; this is not the already-repaired application backup pair. Preserve all state/history and both publisher fences. Evidence is in guarded-cd-activation-evidence/state-*.json.

The secure state-backend credential request was cancelled by the user. No replacement pair was received or applied. Keep publisher activation paused; the installed updater remains disabled. Continue only independent source/dependency/integration work until existing state access is restored through a secure approved path.

- Shared state credentials were restored through the secure form: independent HEAD/GET succeeded on all three unchanged state objects, only mission-control/dev AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY changed, non-target values/sync boundaries were preserved, and the handoff file was verified then deleted. A fresh reviewed flag-only OpenTofu apply enabled one controlled publication.
- Controlled run 41565946062 passed all validation and actual app-image gates/pushes, but GHCR denied the metadata record push. It emitted an extra BuildKit attestation, outside the intended single-platform record contract. Publishing was fenced again automatically; timer and production remain unchanged. A narrow packaging fix is under protected review, without broader permissions or weaker Cosign checks.
- Author-policy review found that earlier branch commits inherited the isolated verification runner’s synthetic identity. Existing owner merges already used explicit Gmail controls. Future owner commits now explicitly use Scott Walters <scowalt@gmail.com>; published history is preserved rather than rewritten.

- Packaging correction merged as 883b869e3f512e97e368707dc2d8cc3ac118faf9. Controlled publication 41569719775 completed successfully with all app gates, the metadata artifact, Cosign signature verification and pointer promotion. No package permissions were broadened.
- VPS artifact and both signature checks succeeded. The remaining public workflow API lookup was rejected only because anonymous GitHub rate quota was exhausted (403, remaining 0, reset supplied). Publisher was fenced while timer stays disabled; production is unchanged. An idle-poll optimization is under protected review so already-verified unchanged releases do not consume workflow quota. New releases retain full CI verification and wait for reset; no broad token is copied to production.

- Controlled runtime deployment of signed release 883b869 completed successfully after the provider quota reset. Exact encrypted snapshot 4f22373e3d712512040bb8456bb858ea4079d40e19f8e39282f151277787b31e restored and passed integrity verification; 71,933,952 input bytes, 143,953,920 scratch bytes and 8,434 additional R2 bytes. No rollback used. Independent checks confirmed healthy exact images, preserved data ownership/inode/mounts and unchanged Caddy/Alloy/Watchtower identities; backup access and cleanup passed.
- Reviewed idle-poll fix merged as c3ee2e694a5b9078980056c4a58271c238fe6b4f. Operator bundle was upgraded with timer/service inactive and a matching old-version guard; ledger stayed byte-identical and prior bundle was retained. The new once command returned unchanged without repeating backup/deployment. Timer was then enabled as the sole updater; Watchtower stays stopped. Final publisher re-enable and an observed automatic deployment remain to finish AC4.

The automatic follow-up safely stopped before admission when anonymous GitHub API quota exhausted again; active release stayed healthy and no failed attempt/data mutation began. Timer and publisher were paused. Read-only differential verification proved the existing VPS registry credential has exactly read:packages scope and can authenticate the fixed public workflow endpoint (HTTP 200, quota available), so no new secret or permission is needed. The narrowly scoped reader-auth fix is in protected PR #14; automatic activation will resume only after validated operator upgrade.

- Read-only registry-auth correction merged as 7b1953e96a00f2dcc7ac2c4c40b27d1f6c1990cc and installed with an expected-old-version guard, inactive timer, unchanged ledger and retained old bundles. The existing GHCR credential has only read:packages and authenticates the fixed public workflow endpoint; no credential was added, copied to CI/state, rotated or broadened.
- Real timer-driven deployment of signed source c3ee2e6 completed from run 41574530594. All exact app images are healthy; independent checks confirm unchanged data inode/ownership/mounts and Caddy/Alloy identities, valid backup access, no owned plaintext/tooling and no rollback. Snapshot 3ac123f47bd369c328f2fc50ae76b2fa538a20d116a5fab69cd5f6efecdaa3b6 was exactly restored/verified: 71,933,952 input bytes, 143,958,016 scratch bytes, 8,438 additional remote bytes.
- Only the guarded timer is enabled; Watchtower remains stopped. A fresh flag-only OpenTofu apply restored the new publisher, preserved unrelated states/settings and produced a no-op follow-up plan. Legacy Deploy stays disabled. Continuous delivery is now independently demonstrated, not inferred from publication.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Established guarded continuous delivery from the public repository.

- Coherent immutable release records are signed with short-lived GitHub identity and accepted only with matching successful trusted-main workflow evidence.
- The sole VPS updater preserves the existing project/configuration/data/binds, proves fresh encrypted recovery, gates backend/dependent updates and records one-shot rollback/restart-safe state.
- Actual protected publication, VPS signature/access verification, a controlled deployment and a timer-driven follow-up passed. No production rollback or database restore was used.
- Offline/native fixture tests cover failure, cleanup, identity, locking, process death, replay and secret boundaries. Existing read-only registry auth avoids anonymous API quota without new credentials.
- Required CI, source-map/image/security/notice gates and exact-head/Gmail controls remain in force; legacy publishing and Watchtower remain inactive.
<!-- SECTION:FINAL_SUMMARY:END -->
