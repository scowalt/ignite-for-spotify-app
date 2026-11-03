---
id: TASK-41
title: Enable automatic publishing after successful main CI
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-03 13:38'
updated_date: '2026-11-03 13:42'
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
- [ ] #1 The maintained public-source IaC and live production environment no longer require a manual reviewer while retaining main-only deployment and all other reviewed environment settings.
- [ ] #2 Native branch protection, CI and image gates, scoped upload credentials, signing, the emergency publishing switch, recovery budgets and sole-updater behavior remain unchanged; legacy publishing and Watchtower stay inactive.
- [ ] #3 A fresh reviewed full-root plan applies only the required-reviewer removal, preserves unrelated resources/state/settings, and has an empty follow-up plan.
- [ ] #4 An exact-head successful main run publishes a signed release without approval, and the existing timer deploys it with fresh verified recovery, healthy exact images and preserved data/auxiliary identities.
- [ ] #5 Policy regression tests, current operating documentation and task evidence describe automatic delivery and the remaining manual database/contract/operator boundaries.
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
<!-- SECTION:NOTES:END -->
