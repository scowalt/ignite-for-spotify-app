---
id: TASK-33
title: Publish verified images from the new sole publisher
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-02 14:43'
updated_date: '2026-11-02 17:18'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Perform the owner-approved first-publication handover without changing running containers: validate the new source policy, fence the legacy publisher, publish inspected fresh images and isolated source maps, and verify pull access.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Protected source/IaC changes authorize the new publisher without weakening security, notice, source-map or environment gates.
- [x] #2 The original Deploy workflow is disabled and drained before only the new publication flag is enabled; no unrelated settings or package permissions change.
- [ ] #3 One exact-head approved workflow publishes the three fully verified fresh-namespace images and isolated frontend source maps, with evidence of successful gates and immutable digests.
- [ ] #4 Existing production credentials can pull the exact candidate digests while existing running containers, mounts, database/backups and settings remain unchanged; failures fence publication and stop.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Carry the known TASK-33/TASK-34 notes in a protected source PR changing only publication policy to true and corresponding tests/docs. Preserve the verified named-secret contract and every release gate. Keep live publishing false through PR and post-merge validation.
2. Refresh production identity/health/storage/rollback metadata and recheck exact main/environment/input invariants. Verify old workflow 218752864 is already disabled and has no active runs; never re-enable it.
3. Review a fresh private IaC plan: only false-to-true publication-variable update, with only the known emergency flag drift allowed. Apply it and verify no-op follow-up and unchanged protections/unrelated state.
4. Dispatch exactly one fresh CI run on the validated main head. Verify all validation jobs and identity before normal required-owner environment approval.
5. Verify real isolated source-map upload, all three actual release-image security/notice gates before pushes, immutable published digests, existing production pull access and image UID metadata. Prove running containers/mounts unchanged.
6. Any failed release gate, upload, identity or access check fences the new publisher and stops. Leave old publisher fenced. No rerun, scope broadening, service/database/backup/DNS changes or bots. Publication is not runtime cutover.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Prepared the reviewed publisher desired-state change to true, while the live flag remains false. Source-map upload is now fail-closed before image pushes, matching the approved stop-on-failure rule. Existing pinned Trivy action already defaults to v0.72.0, matching verification; no tool/dependency change was necessary. Mocked IaC, source-map protocol/routing, script and static checks passed. Operational fencing/enablement has not yet occurred.

- PR #4 merged as ab2df41e34604d3a4afa5eed51a87bcf2609c5e2 with explicit Gmail author/expected head. PR CI 41465766517 and post-merge CI 41467150074 passed all validation jobs with publication skipped.
- Original Deploy workflow 218752864 was disabled and all runs drained before applying the sole new flag change to true; a follow-up plan was empty.
- Exact-head workflow_dispatch run 41469762051 passed all ten validation jobs and received normal owner-required environment approval (no bypass).
- BLOCKED: source-map upload returned HTTP 401. The captured release-step environment shows SENTRY_AUTH_TOKEN empty, although the expected environment secret metadata is present. This identifies a secret-availability boundary, not a demonstrated scope failure. No replacement credential or broader scope was attempted.
- Fail-closed behavior stopped before registry login or any image build/push. New publication flag was immediately fenced false; old Deploy remains disabled_manually. Do not apply the current true desired-state policy or retry publication until reviewed recovery is approved.
- Production container IDs/start times/images/projects/mounts match the pre-release baseline. Pull checks are unperformed because no candidate images were published. Preserve the failed run and value-redacted evidence; source-map secret-path diagnosis requires a protected presence-only probe, with no values/uploads/publication.

- TASK-34 completed the approved narrow recovery through PRs #5/#6/#7. Main is now b278db534b91e54a09362f42a0d88f412432a0c5. Protected comparisons verified that explicit single-name forwarding restores the environment-secret value in a reusable job; no credential changes or broader scope were needed.
- Required secret contract and early empty-value guard are merged and green. Both publishers remain fenced, and source policy now also desires false. Publication is still incomplete: a separately approved exact-head retry must prove real upload, image publication/digests and production pull access. No runtime cutover is authorized.

- Owner explicitly approved one publication retry after TASK-34 recovery: reviewed flag enablement, one exact-head release with normal environment approval, real source-map/image/digest/pull checks, no running-container change or credential-scope expansion. Old publisher must stay fenced. Any release/access failure fences the new publisher and stops this attempt.
<!-- SECTION:NOTES:END -->
