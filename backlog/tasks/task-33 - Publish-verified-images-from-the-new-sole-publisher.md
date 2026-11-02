---
id: TASK-33
title: Publish verified images from the new sole publisher
status: Done
assignee:
  - '@pi'
created_date: '2026-11-02 14:43'
updated_date: '2026-11-02 18:08'
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
- [x] #3 One exact-head approved workflow publishes the three fully verified fresh-namespace images and isolated frontend source maps, with evidence of successful gates and immutable digests.
- [x] #4 Existing production credentials can pull the exact candidate digests while existing running containers, mounts, database/backups and settings remain unchanged; failures fence publication and stop.
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

- PR #8 merged as 4ef6b0380b2474be921fa46ae31b45ccab4782b8 from tested head cf4aa68d47ff63b074e2dc238cd722b4bfb57d9d with explicit Gmail author/expected head. PR CI 41490530773 and main CI 41491186774 passed; publisher skipped before activation.
- Fresh reviewed IaC plan contained only publication false-to-true plus the recorded emergency flag drift. Applied successfully; follow-up plan empty and unrelated states/protections unchanged. Old publisher remained disabled/drained.
- Sole approved retry 41491892742 passed all validation, normal environment approval, actual source-map upload and every image/security/notice gate before any push. All three images published with immutable digests. GlitchTip accepted artifact bundle b9c76104-aeca-595c-ab48-8f8a7425dd37 (18 files); client reported processing pending, not proven symbolication.
- Production manifest/pull access succeeded for backend and backup. Backend source/revision/digest/platform metadata matched. Verification then stopped because the private combined Docker inspection template failed on backup’s legitimately omitted User field. Read-only diagnosis reproduced the template error and showed the null-safe form succeeds, with backup digest/source/revision/platform all matching. This is a verifier defect, not demonstrated registry-access or image-provenance failure.
- Per the approved failure rule, immediately fenced new publication false; old Deploy remains disabled. No further pulls or container operations after the stop. Frontend pull and backend effective UID/GID checks remain incomplete. No candidate container was started or created. Existing production container IDs/start times/images/projects/mounts still match the pre-attempt baseline.
- Published candidate references: backend sha256:51beddd2ed0cfba81f04cd43fbfaa7b0888744a84457a01b444727badedb4800; backup sha256:ab1fdcbd8751b38be2de98af5df2a81fe5ead611c3af900df07ad56e119ece87; frontend sha256:7b5552579ffa93b582de5633aca57ed4d06dda8f664f43059e0adcd1814142d1. No rebuild or republish is indicated by the inspector failure.
- HOLD: both publishers fenced; source desired true now differs from live false again. Do not apply or re-enable automatically. Proposed next scope is only null-safe verifier repair and completion of existing-digest pull/UID checks, with no new publication, credential changes or running-container cutover.

- Owner approved only correcting the private verifier and finishing checks on the already-published digests, with both publishers fenced and no new publication/deployment.
- Preserved the faulty helper and changed only the optional User-field lookup in a new helper. The actual combined-template failure/red evidence and null-safe green evidence were retained; syntax and exact single-field change were checked.
- All three immutable candidate digests are now manifest-readable and pullable with existing production Docker credentials. Each image matches release 4ef6b0380b2474be921fa46ae31b45ccab4782b8, the new public source repository and linux/amd64.
- An owned network-disabled, read-only, unstarted backend inspection container exposed only image account metadata. UID/GID 999/999 matched fresh metadata for the existing data directory and database. The inspection object was removed; independent readback found none remaining. No candidate was started and no application data was mounted or read.
- Final before/after comparisons confirm all production container IDs/start times/image references/projects/physical mounts unchanged and applicable health checks healthy. New publisher remains false, old Deploy disabled_manually. No rebuild/push/upload, credential change, live IaC apply or service deployment occurred during this verification completion.
- Publication and pull verification are complete. Runtime cutover, publisher reactivation/Watchtower behavior and the wider operational migration remain separate work. Source desires true while live publishing is intentionally false; do not apply/unfence implicitly.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Published and verified the first release from the new public repository, without deploying it.

- Protected exact-head release 41491892742 at 4ef6b03 passed all validation/security/notice gates before pushing backend, backup and frontend images. GlitchTip accepted the isolated frontend artifact bundle; full server-side processing/symbolication is not claimed.
- Verified all three immutable registry digests through the existing production Docker client, including source/revision/platform identity. Backend UID/GID 999/999 matches current database/data-directory ownership.
- Corrected a private verifier-only optional User-field defect; no image rebuild, credential scope change or gate waiver was necessary. The owned unstarted inspection container was removed.

Validation: protected PR/post-merge/release Actions jobs, real credentialed upload and published digest receipts, production manifest/pulls, image account metadata, fresh ownership metadata and unchanged healthy running-container/mount readbacks.

Both publishers remain intentionally fenced per the final approval. Existing production continues on legacy images. Runtime cutover, continuing CD/updater decisions and remaining integration migration require separate approval.
<!-- SECTION:FINAL_SUMMARY:END -->
