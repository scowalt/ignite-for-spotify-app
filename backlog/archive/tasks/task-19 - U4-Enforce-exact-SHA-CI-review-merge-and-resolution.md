---
id: TASK-19
title: 'U4: Enforce exact-SHA CI review merge and resolution'
status: To Do
assignee: []
created_date: '2026-07-22 21:10'
updated_date: '2026-07-23 22:07'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Require live repository gates and native independent Paseo review for one candidate SHA, then controller squash-merge and conditionally resolve GlitchTip.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All live required gates and independent structured review approve the exact unchanged PR SHA
- [ ] #2 Expected-head squash and recovered merge evidence prove the merged head before resolution
- [ ] #3 Post-merge activity or ambiguous merge/resolution state blocks safely without automatic retry
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Superseded by the simplified CI-only auto-merge plan on 2026-07-22.
<!-- SECTION:NOTES:END -->
