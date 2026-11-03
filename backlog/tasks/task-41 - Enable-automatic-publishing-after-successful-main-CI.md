---
id: TASK-41
title: Enable automatic publishing after successful main CI
status: Done
assignee:
  - '@pi'
created_date: '2026-11-03 13:38'
updated_date: '2026-11-03 14:11'
labels: []
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make merging a green protected PR the release decision by removing only the production-environment required-reviewer rule. The owner approved this change in the current thread; preserve the environment, main-only policy, all actual CI/image/signing/backup/health gates, scoped credentials, emergency publishing fence and sole updater.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The maintained public-source IaC and live production environment no longer require a manual reviewer while retaining main-only deployment and all other reviewed environment settings.
- [x] #2 Native branch protection, CI and image gates, scoped upload credentials, signing, the emergency publishing switch, recovery budgets and sole-updater behavior remain unchanged; legacy publishing and Watchtower stay inactive.
- [x] #3 A fresh reviewed full-root plan applies only the required-reviewer removal, preserves unrelated resources/state/settings, and has an empty follow-up plan.
- [x] #4 An exact-head successful main run publishes a signed release without approval, and the existing timer deploys it with fresh verified recovery, healthy exact images and preserved data/auxiliary identities.
- [x] #5 Policy regression tests, current operating documentation and task evidence describe automatic delivery and the remaining manual database/contract/operator boundaries.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Use the existing OpenTofu planned-resource test boundary: change the production policy expectation to no reviewers, observe it fail, then remove only the reviewer block and re-run all existing policy tests. No new test seam is introduced.
2. Update current operating docs; retain branch protection, production environment, main-only policy, least-privilege secrets/signing, all CI/image gates and runtime safeguards. Publish through a protected exact-head/Gmail PR. The owner already approved this plan and its tests/docs; no routine confirmation is needed.
3. At the merged exact main, inspect a fresh full-root live plan allowing only the reviewer-list removal with unchanged state/settings elsewhere. Confirm no unrelated pending publisher; apply the reviewed plan and require unchanged unrelated state plus an empty follow-up. Do not approve any production deployment manually.
4. Verify the resulting main release is signed/published without an approval event, then observe the existing timer deploy it. Independently check exact images, health, recovery evidence, database/bind/auxiliary identities and cleanup. Do not invoke a manual once deployment, upgrade the operator, or bypass any failed gate.
5. Record evidence and complete task/docs through protected source changes; do not leave temporary publishing holds. Stop on unexpected plan effects, CI/runtime incompatibility or unsafe recovery with precise evidence and the minimum next input.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Updated the existing planned-resource policy test first: it failed specifically because one reviewer was still configured (7 other checks passed). Removed only the four-line reviewers block; all eight native OpenTofu tests now pass, fmt/validate pass, and the runtime compatibility fingerprint is unchanged. Updated current runbooks and the historical design pointer to distinguish automatic publishing from the original migration approval gate. Credential-free script suite passed; native Docker/source-map fixtures remain covered by exact-head hosted CI. No workflow or runtime/operator source changed; no live policy change has occurred yet.

Protected PR #19 merged as 6be9e16d475726d7975a7644a74e3565b956bd57 after all exact-head validation/image/backup/infra checks passed, with explicit Gmail, expected head, tree equality and preserved native protections. Fresh full-root plan 3f40a5dde8c89d99ae1c23ae0b3f6e47c31d7a4960a226850d8438cfaf7aa6c5 changed only production.reviewers from the owner to empty; apply succeeded, follow-up plan was empty, unrelated state and all non-reviewer settings/inputs/secret metadata were unchanged. Publishing remained enabled; no timer/operator/runtime change was made.
GitHub canceled the already-waiting publisher in push run 41647626377 when its reviewer rule was deleted (native review event: Required reviewers protection rule deleted; runner ID 0 and no steps). This was not a failed image gate or a manual approval. Started one fresh full CI run 41648567265 at the identical main commit to validate the new policy; no production approval was given.

Fresh full CI run 41648567265 at 6be9e16d475726d7975a7644a74e3565b956bd57 passed every validation and actual source-map/security/notice/push/signature/pointer gate. GitHub review history is empty: no manual approval or bypass. The existing timer automatically deployed signed artifact sha256:8904c73c1d7e3524ac612f45d8924d99ff55fd44f24d0327e77ea6d1ce5df379, order [51,1], without a manual once invocation. Independent Docker image-ID/digest/revision/platform, health, data inode/UID/GID/mode, mount, auxiliary ID, operator/policy/unit hash and cleanup checks passed; public homepage HTTP 200. Fresh recovery snapshot 6bdf1020692a476c75e49d1bb221300f9dba5a37ff40986e10d151c6381e48ca restored exactly: 71,942,144 snapshot bytes, 143,974,400 scratch bytes and 541,668 additional remote bytes. No rollback, live DB restore, credential change or unrelated restart occurred. Completion records will use the normal protected main-push pipeline without a documentation publishing hold.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Enabled automatic production publishing after successful trusted-main CI by removing only the production environment required-reviewer block. The environment, main-only restriction, branch protections, scoped upload secret, signing, publishing stop switch and guarded updater remain intact. Merging a green PR is now the release decision, including Renovate auto-merges.

Validation:
- Existing policy regression test failed under the old reviewer rule, then all eight native OpenTofu tests passed; fmt/validate and the credential-free 97-test script suite passed (seven local-only fixture skips covered by hosted CI).
- Protected PR #19 passed actual CI/image/backup/infra checks and merged with exact-head/Gmail/tree/protection validation.
- Fresh full-root live plan changed only reviewers; apply and empty follow-up succeeded with other settings and unrelated state preserved.
- Full run 41648567265 published a signed release with zero approval events. The existing timer deployed it automatically; exact image health, fresh encrypted recovery/restore, data/mount/auxiliary identity, unchanged operator policy/units and cleanup were independently verified.

GitHub canceled the old waiting job when its reviewer rule was deleted, before it started a runner; the fresh full run verifies the new policy rather than approving that old job. Database/compatibility-contract changes and operator/infrastructure upgrades retain separate reviewed procedures. Legacy publishing and Watchtower remain inactive.
<!-- SECTION:FINAL_SUMMARY:END -->
