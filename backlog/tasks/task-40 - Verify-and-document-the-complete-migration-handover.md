---
id: TASK-40
title: Verify and document the complete migration handover
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-03 01:08'
updated_date: '2026-11-03 05:03'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Close the remaining cross-system migration checks with explicit evidence rather than equating publication with complete operational handover.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The new release publisher and sole guarded updater are verified operational, with healthy exact production images and preserved backup/data/observability/protections.
- [x] #2 A bounded synthetic event proves frontend source-map symbolication in the isolated target, without exposing real user events.
- [ ] #3 Supported BB project/source metadata reflects the new repository, or an evidenced external blocker is reported without unsupported internal mutation.
- [x] #4 Maintained references, operating documentation and migration tasks reflect the verified final state; old repositories/checkouts/rollback material remain preserved.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Independently verify final runtime/publisher/updater and backup protections after TASK-38 activation.
2. Perform a uniquely tagged synthetic frontend symbolication check, reading only that synthetic event and public release assets.
3. Recheck supported BB metadata controls and all maintained references; never patch internal BB state or duplicate its project.
4. Update runbooks/tasks through a protected source change and state any irreducible external blocker explicitly. Owner has preapproved these remaining migration checks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- End-to-end isolated frontend symbolication passed using only a labelled synthetic event: the actual served Home chunk debug ID mapped to ../../src/pages/Home.tsx, statsQuery, line 8/column 41. The first probe selected an unmapped generated HTML span; a second probe used a verified executable mapping. Both single-event synthetic issues were identity-checked and resolved; no real user events were read.
- Current supported BB project/source CLI still has no cached-remote setter; project update accepts only name. Actual source/origin/thread are correct, but the project cache remains an external metadata limitation. No unsupported DB/runtime edit or duplicate project was attempted.

Synthetic cleanup verification initially stopped because GlitchTip truncates the issue title before the event UUID. Rechecked exact event-ID-to-group binding, project 8, unique synthetic label and single-event count; both synthetic groups are now confirmed resolved. No real issue was modified.

Guarded CD is now verified end to end, including a real timer-driven deployment, exact healthy images, fresh verified recovery, preserved data/auxiliaries and final sole-publisher/updater activation. TASK-38 is Done. Remaining handover work is publishing the current runbooks/catalog and resolving or explicitly reporting supported BB metadata limitations; hosted bot coverage is tracked separately in TASK-39.

Application runbook/task handover PR #15 merged as ae7b00dd18cf32608a1958c09ad42f1cf14b1b71 with exact-head/Gmail/tree validation. Mission Control catalog PR #61 merged as 7db68781960ed72d9833ed40e011766e03d48a9e through green Woodpecker checks, with GitHub Actions still disabled. Applied only that catalog paragraph to the permanent Mission Control working file; unrelated dirty work and HEAD were preserved. Updating remaining design/implementation status pointers to distinguish completed live verification from historical preparation. BB cached remote remains the only unchecked criterion for this task; current API offers no supported setter.
<!-- SECTION:NOTES:END -->
