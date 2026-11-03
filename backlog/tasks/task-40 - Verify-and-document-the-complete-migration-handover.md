---
id: TASK-40
title: Verify and document the complete migration handover
status: To Do
assignee: []
created_date: '2026-11-03 01:08'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Close the remaining cross-system migration checks with explicit evidence rather than equating publication with complete operational handover.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The new release publisher and sole guarded updater are verified operational, with healthy exact production images and preserved backup/data/observability/protections.
- [ ] #2 A bounded synthetic event proves frontend source-map symbolication in the isolated target, without exposing real user events.
- [ ] #3 Supported BB project/source metadata reflects the new repository, or an evidenced external blocker is reported without unsupported internal mutation.
- [ ] #4 Maintained references, operating documentation and migration tasks reflect the verified final state; old repositories/checkouts/rollback material remain preserved.
<!-- AC:END -->
