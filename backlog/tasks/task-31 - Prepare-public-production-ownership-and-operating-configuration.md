---
id: TASK-31
title: Prepare public production ownership and operating configuration
status: Done
assignee:
  - '@pi'
created_date: '2026-11-01 23:53'
updated_date: '2026-11-02 13:51'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Prepare the maintained public source and IaC for later controlled production adoption, preserving legacy resources, GlitchTip observability and release protections without live state or service changes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Separate public-repository and protected main-only production-environment definitions have an explicit adoption plan; legacy repository, DNS, backup resources and backend identity are preserved.
- [x] #2 Contributor, agent and operational instructions describe the current repository, owner authorship, least-privilege release inputs and retired Paseo dispatch without removing application GlitchTip integration.
- [x] #3 Pinned source-map tooling has verified no-finalization-compatible behavior and credential-free regression coverage; any necessary workflow change preserves release gates and PR isolation.
- [x] #4 Relevant local and protected-PR validation passes before merge with explicit scowalt@gmail.com author and expected head; no live state, credentials, publishing or production settings are changed.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inspect existing IaC, live public GitHub metadata (read-only) and pinned tool/provider contracts.
2. Add distinct public-repository/environment definitions and an adoption runbook, preserving all legacy resource addresses and the existing backend. Validate offline with mocked provider tests; no live backend initialization, credentials or apply.
3. Update agent/contributor/operations documentation for the approved public source, Gmail author policy, minimum release inputs and owner-retired Paseo dispatch.
4. Verify pinned sentry-cli behavior and test compatible source-map command construction without production calls. Make only necessary workflow changes.
5. Run source/comment/security/static/unit validation, open protected PR(s), inspect exact-head Actions and public artifacts, then merge with explicit authorEmail and expectedHeadOid. Keep publishing disabled.

Owner explicitly approved this source-only scope and protected validation/merge. Stop for live-state/credential access, destructive resource changes or broader application work.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Added a separate public-repository IaC root/state key, identity guards, owner-reviewed main-only environment and explicit false publication flag. Legacy resource addresses/backend/DNS/backups are unchanged; corrected only the unavailable OpenTofu minimum to tested 1.13.2. Four mocked plan tests pass without cloud credentials.
- Pinned GitHub provider cannot preserve app-bound status checks for this user-owned repo: REST protection requires an organization, GraphQL exposes context names only. Kept protections outside a weaker resource; added declarative policy and read-only drift guard with regression tests.
- Verified Sentry CLI 3.8.2 checksum/help/source. Its dedicated upload rejects --no-finalize but makes no release/finalize request. Actual binary and npm package pass the exact-workflow loopback protocol test, including real debug-ID/chunk upload. Production compatibility still requires first-release verification.
- Updated authority/secret/adoption instructions and marked Paseo dispatch historical without deleting controller source/state or removing GlitchTip observability. Added unprivileged infrastructure and source-map checks to CI; required backup aggregate fails closed on infrastructure validation.
- Static workflow assertions and comment-policy tests passed; no live backend access, state mutation, credentials, registry or production operations.

Final local validation also passed: 94 backend tests, 37 frontend tests plus lint/typecheck/build, 102 retained controller tests plus lint/types, 28 script tests (binary protocol case separately passed), 13 comment-policy tests, actionlint, shellcheck, full staged source/comment guards and redacted source scanning. Both IaC roots validate with backend disabled; legacy root reports only its existing vulnerability-alert attribute deprecation. No live provider calls or state access were used for validation.

- PR #2 merged as bf154b6c71da3d224ee69b1a1cdc578d44cf5848 with explicit Gmail author and expected head bf2fe98. PR CI 41366362465 and both comment-policy runs succeeded. Hosted protocol fixture actually ran; all three image artifact summaries passed and captured CI logs/reports had zero redacted secret-scan findings.
- Post-merge CI 41366835064 and comment-policy run 41366835040 succeeded. All ten validation jobs passed; publisher skipped. Main protection readback is unchanged; production environments/variables/secrets remain absent.
- Only source preparation is complete. Real IaC state adoption, minimum credentials/configuration, exclusive-publisher cutover, registry publication, runtime verification and remaining bot/open-work handover are unexecuted. BB cached remote remains a separate tool limitation.
- Final task completion metadata is local after merge, pending a later approved documentation commit.

After this source-only task, separately approved operations adopted the public state, created the protected environment with publishing false, and provisioned an isolated GlitchTip frontend target/credential in Doppler. Those later operations are distinct from this task’s original no-live-change implementation.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Prepared public-source infrastructure adoption and operating instructions without live changes.

Changes:
- Separate identity-guarded public-repository/state root, protected main-only production environment, pinned provider and disabled publishing definition. Preserved legacy resources/backend and corrected the unsupported OpenTofu minimum.
- Declarative protection policy with read-only drift guard preserves app-bound checks unsupported by the pinned provider for a user-owned repository.
- Credential-free test executes the actual pinned source-map client against a loopback fixture, verifying debug-ID/chunk upload without release finalization. Existing deploy commands remain unchanged.
- Updated current repository/author/minimum-secret guidance and marked owner-retired Paseo instructions historical while preserving GlitchTip reporting and old source/state.

Validation:
- Four mocked IaC plans; both roots validate backend-disabled. Application, script, protocol, lint/type, comment-policy, source/secret and workflow checks passed.
- PR #2 and post-merge CI passed with all image checks and publisher skipped. No branch-protection change.

No live backend/state operation, environment/credential provisioning, registry push or production mutation occurred. Operational adoption and cutover still require separate approvals.
<!-- SECTION:FINAL_SUMMARY:END -->
