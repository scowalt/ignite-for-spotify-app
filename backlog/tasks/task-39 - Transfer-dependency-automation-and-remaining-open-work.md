---
id: TASK-39
title: Transfer dependency automation and remaining open work
status: Done
assignee:
  - '@pi'
created_date: '2026-11-03 01:08'
updated_date: '2026-11-03 13:03'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Finish the repository migration by moving maintained dependency automation and the reviewed legacy dependency work to clean public ancestry. Preserve private histories and deployment protections.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Legacy dependency PRs 276 and 236 are reviewed and transferred or explicitly superseded in the public repository with passing validation.
- [x] #2 Renovate is validated and active only on the maintained repository path, with intended grouping/approval policy and no revived legacy publisher.
- [x] #3 Remaining legacy open work and integration references are inventoried and dispositioned without deleting private history or uncommitted work.
- [x] #4 Comment-free source-tool version/commit tracking is functional, manual infrastructure-provider updates are preserved, and automerge honors the existing protected PR workflow.
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

Protected PR #12 merged as f28bb0eed16ff733c136b13825cef73f4aefb49c with exact-head Gmail controls, tree equality and successful required CI. Both legacy dependency updates are now in maintained main; bot configuration/extraction/provider policy is validated. Actual hosted Renovate coverage remains unproven because no new-repository bot issue/PR has yet appeared.

Legacy dependency PRs #276 and #236 were closed as superseded only after their public replacement merged and passed validation; branches/history were retained. Legacy dashboard #279 was closed as obsolete, with a handover comment. The verified legacy open-work inventory contained no other issues or PRs. New hosted Renovate run evidence remains the sole unfinished criterion for this task.

Correction to the legacy inventory classification: issue #279 was a Renovate configuration warning, not an ordinary dependency dashboard. Legacy config still had unsupported postUpdateOptions: bunInstall despite enabled=false. Opened a narrowly scoped private retirement PR removing only that invalid option while preserving enabled=false and the publisher fence; no private history was copied into public source. AC3 remains open until that cleanup is validated.

Legacy retirement PR #280 merged through exact-head/Gmail controls after all three required checks and comment policy passed. Its existing retired controller check fails at dependency installation and remains non-required; it was not activated or opportunistically repaired. Only the invalid bunInstall option was removed, enabled=false stayed intact, legacy publishing remained disabled, and private history/branches/checkouts were preserved.

Hosted verification completed on 2026-11-03. The owner provided the existing signed-in BB tab for the correct Mend repository. The latest October 31 DONE job actually reported disabled-by-config; requested one fresh scan through Actions > Run Renovate scan without changing installation/settings/permissions. Job d877cbee-0047-424e-a676-d99925459dd9 completed at 13:00:46 UTC with Renovate 44.204.0: result done, status onboarded, enabled true, onboarded true; 161 dependency entries; no warning/error-level log messages. Bot-authored Dependency Dashboard #17 independently confirms access, grouping/schedule/major approvals and Restic/Caddy extraction. No approvals or schedule overrides were selected. Legacy enabled=false and Deploy 218752864 disabled_manually rechecked. Both local Renovate policy tests passed. Updated dependency-handover.md; completion documentation awaits its protected source merge.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed dependency automation and open-work handover to the public repository.

- PR #12 transferred the reviewed PostHog/Trivy updates and repaired comment-free Restic/Caddy tracking while preserving protected PR merges, major approvals and manual infrastructure updates.
- Superseded legacy dependency PRs and corrected the disabled legacy configuration through private PR #280, retaining history and the old publisher fence.
- Verified the existing hosted Mend integration with successful enabled job d877cbee-0047-424e-a676-d99925459dd9 and bot-authored Dependency Dashboard #17. Documented why older DONE-but-disabled jobs were insufficient.

Validation: prior native Renovate strict validation/extraction, frontend validation and required PR CI; current two policy tests; actual hosted scan of 161 dependency entries with no warning/error-level log messages. The dashboard preserves major approvals and scheduled non-major grouping. No new credentials/permissions or production change.
<!-- SECTION:FINAL_SUMMARY:END -->
