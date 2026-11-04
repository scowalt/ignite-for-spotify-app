---
id: TASK-45
title: Patch the production .NET runtime for the Brotli decoder advisory
status: Done
assignee:
  - '@pi'
created_date: '2026-11-03 21:03'
updated_date: '2026-11-03 21:38'
labels:
  - security
  - deployment
dependencies: []
references:
  - 'https://github.com/advisories/GHSA-p3jp-9v83-76w9'
  - docker/Dockerfile.backend
documentation:
  - docs/operations/guarded-continuous-delivery.md
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ship the separately owner-approved narrow runtime-image fix for GHSA-p3jp-9v83-76w9. Production image metadata shows .NET 10.0.13; 10.0.14 fixes the newly published high-severity Brotli decoder finding. Use the maintained protected, signed image-only CD path. Do not merge the database-CD drafts or alter schema, operator, credentials, infrastructure, CI policy or backup retention/budgets.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Only the final backend runtime pin and necessary task evidence change; the runtime uses 10.0.14 and the existing application/deployment compatibility contract remains unchanged.
- [x] #2 The unchanged exact image security/notice gate passes and protected exact-head CI succeeds without vulnerability ignores, waivers or disabled checks.
- [x] #3 Owner merge uses explicit expectedHeadOid and scowalt@gmail.com with tree/protection verification; successful main CI publishes a signed coherent release through the existing automatic production environment.
- [x] #4 The existing timer deploys the verified release without a manual once command or updater upgrade, with fresh encrypted backup/restore proof, healthy exact images and preserved data/mount/auxiliary/operator identities.
- [x] #5 Evidence records the advisory, version readback and operational outcome; database migration activation and unrelated services remain untouched, with no unresolved publication hold.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Change only the final backend ASP.NET runtime tag from 10.0.13 to 10.0.14 on an isolated branch based on current main; preserve the database-CD branches and all operating contracts.
2. Run relevant checks and the unchanged security/notice gates; require actual protected PR CI on the exact head. No advisory suppression or gate weakening.
3. Capture a fresh read-only runtime baseline and native GitHub settings. Merge only the exact tested head with explicit owner email and tree/protection equality; do not introduce a publication hold.
4. Observe automatic successful main publication/signing, then the existing timer deployment. Independently verify actual runtime 10.0.14, exact image health, fresh bounded backup/restore, preserved data/mount/auxiliary/operator/policy/unit identities and no unfinished transaction.
5. Record final task/evidence through protected source changes, preserve old recovery material, and return to the unmerged database-CD integration. If any check fails, stop rather than bypass gates or perform an unapproved database/operator operation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Owner explicitly selected Deploy runtime patch first. Existing main is 8ecfddda374820a769fb1852997ca18988329399. This is separate approval for the maintained image-only CD transaction, not database migration activation. Private reproduction found GHSA-p3jp-9v83-76w9 in Microsoft.NETCore.App.Runtime.linux-x64 10.0.13; a 10.0.14 development candidate passed the identical full image gate. Production runtime version was confirmed via filtered image metadata only. Exact source branch is fix/net-runtime-10-0-14; database drafts #21/#22 stay unmerged.

Isolated main-based candidate changes only the final runtime tag. Exact-source backend image build passed the unchanged full secret/vulnerability/SBOM/notice gate; release guard suite ran 24 tests, OK (one existing local native fixture skipped). Compatibility fingerprint remains 417fe8060e7156e73c308c2148e0d282f9cadbbaaf952e7b0097744a31666d5f. Fresh read-only production baseline: source 8ecfddd, runtime 10.0.13, healthy exact images, no transaction/failed digests, sole timer active, preserved data/mount/unit/operator evidence captured privately. No production mutation or manual deployment command yet.

PR #23 exact head e0c80c1c6d50c13d32347a3e28343b1e2df501a9 passed CI 41719264179 and comment checks. Fresh native branch/environment/workflow-permission checks passed; no other main publisher was active. Merged with explicit authorEmail and expectedHeadOid as 5d0f565a3eff1a35c10979e24665ecf19e284722, with tree equality and unchanged protections/settings verified. No publication fence or manual approval was introduced. Main push CI 41720036462 is now validating/publishing automatically; comment CI 41720036202 passed. Existing timer rollout remains to be observed.

Main push CI 41720036462 completed successfully at 5d0f565a3eff1a35c10979e24665ecf19e284722, order [58,1], with all real source-map/security/notice/image/signature/pointer gates successful and empty approval history. No manual workflow dispatch, deployment approval or once invocation occurred. Timer tick at 21:27:43 UTC deferred while CI was finishing; next existing tick is scheduled at 21:33:17 UTC. Awaiting automatic runtime/recovery verification.

Existing timer automatically deployed source 5d0f565a3eff1a35c10979e24665ecf19e284722 from successful main run 41720036462, order [58,1], signed record sha256:2afe35a4146d28dc67797cbba0ed4bafd1f18be30fa4c46f949a0243720baed1. Independent readback verified runtime 10.0.14, exact healthy images, preserved database inode/UID/GID/mode and mounts, unchanged auxiliary identities/operator/policy/units, empty failed-digest set and no unfinished transaction. Public homepage returned HTTP 200.
Fresh recovery snapshot 7cd663f55ddfaf4bc5fd16bf57f939ea9982e07fb6e429f83ac158657c149cbd restored exactly within budget: 71,942,144 input bytes, 143,970,304 scratch bytes and 4,811 additional remote bytes. No rollback, manual once command, live restore, credential change or unrelated restart occurred. Metadata-only post-check confirms unchanged schema definitions/column-index metadata and schema_version 22. Completion bookkeeping will join the existing development review rather than trigger an unnecessary documentation-only production rollout.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Patched the backend runtime from .NET 10.0.13 to 10.0.14 for GHSA-p3jp-9v83-76w9, without schema, updater, configuration, credential or CI-policy changes.

Verification:
- Exact local image passed the unchanged security and notice gates.
- PR #23 exact head e0c80c1 passed CI 41719264179; explicit Gmail/expected-head merge 5d0f565 preserved tree and native protections.
- Main CI 41720036462 passed all actual publication/signature gates with no approval event.
- The existing timer deployed the coherent signed image set automatically; actual runtime 10.0.14 and healthy exact images independently verified. Fresh encrypted backup restored within all existing budgets; no rollback was needed.
- Data/schema/mount/auxiliary/operator/policy/unit identities remained intact; public HTTP 200.

Database-CD drafts remain unmerged and unactivated. No new publication hold or pending security rollout remains.
<!-- SECTION:FINAL_SUMMARY:END -->
