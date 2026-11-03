---
id: TASK-45
title: Patch the production .NET runtime for the Brotli decoder advisory
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-03 21:03'
updated_date: '2026-11-03 21:09'
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
- [ ] #2 The unchanged exact image security/notice gate passes and protected exact-head CI succeeds without vulnerability ignores, waivers or disabled checks.
- [ ] #3 Owner merge uses explicit expectedHeadOid and scowalt@gmail.com with tree/protection verification; successful main CI publishes a signed coherent release through the existing automatic production environment.
- [ ] #4 The existing timer deploys the verified release without a manual once command or updater upgrade, with fresh encrypted backup/restore proof, healthy exact images and preserved data/mount/auxiliary/operator identities.
- [ ] #5 Evidence records the advisory, version readback and operational outcome; database migration activation and unrelated services remain untouched, with no unresolved publication hold.
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
<!-- SECTION:NOTES:END -->
