---
id: TASK-18
title: 'U3: Run local remediation and publish via controller'
status: To Do
assignee: []
created_date: '2026-07-22 21:10'
updated_date: '2026-07-23 22:07'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Launch a GitHub/GlitchTip-credential-free remediation agent in a fresh worktree, validate its local tested commit, then have the controller push and open one linked PR.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Agent produces a clean issue-related local commit from current origin/main without remote credentials
- [ ] #2 Controller blocks secrets, unrelated or guarded paths before publication and publishes the exact local SHA
- [ ] #3 Deterministic branch and PR marker recovery adopts one remote object or blocks ambiguity
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Superseded by the simplified CI-only auto-merge plan on 2026-07-22.
<!-- SECTION:NOTES:END -->
