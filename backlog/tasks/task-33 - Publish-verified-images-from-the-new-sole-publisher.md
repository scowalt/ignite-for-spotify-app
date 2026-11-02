---
id: TASK-33
title: Publish verified images from the new sole publisher
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-02 14:43'
updated_date: '2026-11-02 15:34'
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
1. Prepare minimal source/IaC enablement with fail-closed source-map upload, consistent verification tooling and updated publication-versus-deployment guidance. Validate locally and through a protected PR; merge with explicit Gmail author/expected head.
2. Wait for post-merge validation to finish with publisher skipped; capture production/rollback metadata and verify protection/input invariants.
3. Disable original workflow 218752864 and verify all legacy release runs drained. Apply only the new publish-flag change via reviewed private IaC plan.
4. Dispatch one CI run on exact reviewed main; verify all validation jobs and head before approving its production environment through the normal reviewer API. Preserve every security/notice gate.
5. Verify source-map upload and fresh-image publication, record immutable digests, check production pull access/UID metadata, and prove containers/mounts unchanged.
6. If a release gate, identity or access check fails, fence the new publisher and stop with evidence. No service deployment, volume/database/backup/DNS changes, legacy package grant or bot activation.

Owner explicitly approved first publication only, including old-publisher fencing, scoped new enablement, isolated source-map upload and fresh image pushes/pull verification.
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
<!-- SECTION:NOTES:END -->
