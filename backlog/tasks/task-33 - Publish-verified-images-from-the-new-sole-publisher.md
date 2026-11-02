---
id: TASK-33
title: Publish verified images from the new sole publisher
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-02 14:43'
updated_date: '2026-11-02 14:47'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Perform the owner-approved first-publication handover without changing running containers: validate the new source policy, fence the legacy publisher, publish inspected fresh images and isolated source maps, and verify pull access.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Protected source/IaC changes authorize the new publisher without weakening security, notice, source-map or environment gates.
- [ ] #2 The original Deploy workflow is disabled and drained before only the new publication flag is enabled; no unrelated settings or package permissions change.
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
<!-- SECTION:NOTES:END -->
