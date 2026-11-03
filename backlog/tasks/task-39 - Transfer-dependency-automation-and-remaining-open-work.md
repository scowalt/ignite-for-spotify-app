---
id: TASK-39
title: Transfer dependency automation and remaining open work
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-03 01:08'
updated_date: '2026-11-03 02:50'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Finish the repository migration by moving maintained dependency automation and the reviewed legacy dependency work to clean public ancestry. Preserve private histories and deployment protections.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Legacy dependency PRs 276 and 236 are reviewed and transferred or explicitly superseded in the public repository with passing validation.
- [ ] #2 Renovate is validated and active only on the maintained repository path, with intended grouping/approval policy and no revived legacy publisher.
- [ ] #3 Remaining legacy open work and integration references are inventoried and dispositioned without deleting private history or uncommitted work.
- [ ] #4 Comment-free source-tool version/commit tracking is functional, manual infrastructure-provider updates are preserved, and automerge honors the existing protected PR workflow.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Review the two legacy dependency PRs and the maintained configuration without importing private history.
2. Transfer the exact applicable updates to clean public ancestry and validate lockfile, actual image/security/notice gates and bot policy.
3. Use a protected exact-head source PR; keep publishers/updater fenced while state-backend access is blocked.
4. Activate only the maintained Renovate source configuration after review; verify actual bot coverage or record the smallest external installation blocker. Preserve legacy work until its disposition is proven. Owner already approved remaining migration scope; no routine plan prompt needed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Transferred PostHog 1.434.15 with Bun and preserved the requested caret range plus existing security-fixed transitive dependencies. Updated the Trivy action digest while explicitly retaining the reviewed v0.72.0 scanner in all three publication scans.
- Repaired the comment-free Restic/Caddy source-pin extraction, derived the Caddy runtime version from its ARG, retained major approvals/manual infrastructure updates, and selected Renovate-managed protected PR automerge without changing native repository settings. Native Renovate 44.206.2 strict validation and credential-free extraction passed; actual regex extraction found both source pins.
- Legacy main already disables Renovate. Open inventory is exactly PRs 276/236 and dashboard issue 279; do not close them until replacement/bot evidence is verified. New-repository App access remains to be proven after the reviewed configuration reaches main.
- Frontend frozen install, 37 tests, lint (one existing warning), type check and build passed. Script tests/actionlint/comment checks passed; exact-head image gates remain required in CI.
<!-- SECTION:NOTES:END -->
