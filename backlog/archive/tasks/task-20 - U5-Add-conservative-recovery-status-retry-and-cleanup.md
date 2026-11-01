---
id: TASK-20
title: 'U5: Add conservative recovery status retry and cleanup'
status: To Do
assignee: []
created_date: '2026-07-22 21:10'
updated_date: '2026-07-23 22:07'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Recover clear jobs from their recorded Git/Paseo/GitHub state, block ambiguity, expose operator status and controls, and clean successful or explicitly abandoned jobs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Restart continues only clear recorded phases and blocks uncertain external outcomes
- [ ] #2 Pause, reconcile, retry, and abandon semantics are visible and never reuse stale CI or review
- [ ] #3 Successful and disposable-abandon cleanup archives agents and removes only exact worktree and branch resources
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Superseded by the simplified CI-only auto-merge plan on 2026-07-22.
<!-- SECTION:NOTES:END -->
