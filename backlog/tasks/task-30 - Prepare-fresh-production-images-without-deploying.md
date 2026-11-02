---
id: TASK-30
title: Prepare fresh production images without deploying
status: Done
assignee:
  - '@pi'
created_date: '2026-11-01 13:33'
updated_date: '2026-11-02 00:13'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Prepare the public repository for a safe image-namespace cutover without granting access to legacy package history or changing production. Preserve the existing Compose project and data/backup identities; validate the actual release images and document unresolved release gates.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Publishing and production Compose target ignite-for-spotify-app images, while the existing ignite-for-spotify Compose project and data/backup volumes remain explicit and unchanged.
- [x] #2 All three release images have repeatable non-publishing build/security verification with no production secrets, registry pushes or weakened security checks.
- [x] #3 Shipped dependency notices and source/license coverage are reviewed for the actual image components; unresolved obligations are clearly recorded rather than waived.
- [x] #4 The first-release and rollback runbook preserves existing data, backup and proxy bindings, identifies component-version differences, and requires separate production approval.
- [x] #5 Approved supported runtime and Go-library security updates remove the candidate images’ fixable HIGH/CRITICAL findings without weakening checks or changing application features.
- [x] #6 Relevant local and GitHub validation passes before merge; publisher/Renovate remain disabled, protections unchanged, and future owner commits/merges use scowalt@gmail.com while previously approved me@scowalt.com history is preserved.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Apply the owner-approved fresh-image namespace and explicit existing Compose project; add tests for image/volume/backup invariants.
2. Retarget isolated verification helpers to this public checkout and build/scan final images without pushes or production access.
3. Apply the approved security extension: .NET runtime 10.0.13/SDK 10.0.402, Go 1.27.3, documented fixed Go modules and compatible transitives. Preserve Caddy/restic application versions where compatible; stop for incompatible application or major-runtime changes.
4. Add repeatable non-publishing verification and review shipped dependency notices/source coverage, recording unresolved obligations honestly.
5. Update the unexecuted cutover/rollback runbook, preserving data/backup/proxy identities and private evidence.
6. Validate locally and through protected PR(s); merge only after relevant validation passes using explicit authorEmail and expectedHeadOid.

Owner approved this scope and its security-update extension. No registry writes, live settings/credential/service changes, old-repo changes, BB retargeting or automation enablement.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Implemented fresh image coordinates locally, explicit existing Compose project name, frontend digest override, and a value-free Compose invariant validator. Six configuration/rollback tests pass, including rejection of a changed volume namespace or missing require-existing policy.
- Retargeted isolated test helpers to the public checkout. Built final backend/backup/frontend images locally with no cache and no registry pushes, using the pinned action scanner version (Trivy 0.72.0).
- All three builds succeed and secret scans report zero findings, but every image fails the existing fixable HIGH/CRITICAL vulnerability gate. Broader runtime/Go dependency updates are needed; stopped before applying them, as required by the approved scope.
- Produced private image identity, vulnerability, secret, license and CycloneDX inventories. License metadata coverage is incomplete and is not redistribution clearance. No gate was weakened; no PR/merge, package write or production change occurred in this phase.
- Stable fixed runtime image tags and proposed Go module versions are available from primary registries. Awaiting owner approval for the concrete security-update scope before continuing.

Owner approved the documented security-update extension. Continuing locally with supported runtime/library fixes, image rebuilding/scanning, notice review and protected preparation PRs; no production or registry operations.

- Applied supported .NET 10.0.13/SDK 10.0.402 and Go 1.27.3 updates. x/net 0.60.0 requires compatible x/crypto 0.57.0 and x/text 0.42.0; retained the existing Caddy/restic application versions.
- Supplemental production-JavaScript lock scanning found vulnerabilities hidden by bundling. Updated DOMPurify to 3.4.17 and Solid to its compatible 1.9.16 patch, resolving seroval/seroval-plugins to 1.6.12 within the new declared range; no application source logic changed.
- Rebuilt final images and verified zero fixable HIGH/CRITICAL and zero secret findings for all three. Frontend production lock scan is clean. Updated backup snapshot/restore test passed.
- Added compiled-Go and published-.NET notice collectors, browser dependency notices, source references and a documented SPDX MIT supplement for tr46’s upstream declaration. Mechanical notice-file coverage passes for 50 .NET, 80 backup Go, 157 frontend Go and 65 frontend dependency components; this is not a blanket legal opinion.
- Added unprivileged, non-publishing verification; the existing required backup check aggregates backup tests and image checks and fails closed. No protection setting or controller-required status changed.
- Local validation: 94 backend, 37 frontend, 102 controller, 13 comment-policy and 22 publication/notice/configuration tests passed, plus formatting, type checking, actionlint, shellcheck and workflow safety assertions.
- New first-release/rollback documentation preserves project/volume/bind identities and requires separate production authorization. Copied upstream license text retains its original whitespace; only the generated notice text is exempted from whitespace lint.
- All preparation remains local pending protected-PR validation; no registry writes, live changes or automation enablement.

Owner changed preferred authorship to scowalt@gmail.com, matching the existing GitHub-generated test-merge address. No account change/history rewrite is needed; the earlier me@scowalt.com commits remain approved history. All PR validation passed. Repository remains private pending explicit republication approval.

- PR #1 passed all GitHub validation and was merged as 811c5dbbe8cd52103d7c91bdb85e679a926ae5a4 using explicit authorEmail=scowalt@gmail.com, matching the owner’s updated preference.
- Both post-merge workflows passed; all three image jobs and the required backup aggregate passed; publisher skipped. Branch-protection settings unchanged and no production secrets/variables/environments configured.
- Repository remains private pending republication approval. This task completes preparation only, not registry publication, operational cutover, controller/BB migration or automation activation.
- Completion metadata is recorded locally after the authorized merge and awaits a later approved documentation commit.

Subsequent owner-approved republication and development checkout move are complete. Production still uses legacy images. The BB default source and this thread use the new public checkout; BB cached remote metadata remains a documented tool limitation. Paseo dispatch is excluded by owner decision; GlitchTip error reporting is retained.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Prepared fresh-image cutover without deploying or granting access to legacy packages.

Changes:
- New image coordinates and explicit existing Compose project; guarded digest-pinned cutover/rollback configuration.
- Supported runtime/library security updates and compatible frontend transitive fixes, retaining existing application/runtime families.
- Non-publishing image checks, bundled notices/source references, filtered verification artifacts, and first-release/rollback documentation.

Verification:
- All three candidate images and frontend production-lock checks pass the existing fixable HIGH/CRITICAL and secret policies.
- Unit/fixture/configuration/notice tests, backup snapshot/restore and static checks passed locally and in GitHub Actions.
- PR #1 merged; post-merge CI is green with publisher skipped and protections unchanged.

No registry push, secret/package-permission change, production operation or automation activation occurred. Full migration remains pending the separately approved operational handover.
<!-- SECTION:FINAL_SUMMARY:END -->
