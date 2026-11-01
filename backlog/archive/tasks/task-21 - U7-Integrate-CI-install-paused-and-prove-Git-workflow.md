---
id: TASK-21
title: 'U7: Integrate CI install paused and prove Git workflow'
status: To Do
assignee: []
created_date: '2026-07-22 21:10'
updated_date: '2026-07-23 22:07'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add non-required controller CI, install the service with persisted dispatch disabled, baseline, and prove synthetic commit-to-draft-PR-to-CI-to-review-to-abandon-cleanup before legacy deletion.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Controller is tested in non-required CI and installed with a restart-safe disabled dispatch gate
- [ ] #2 Synthetic Git/Paseo workflow reaches exact-SHA approved state and cleans up without merge or GlitchTip mutation
- [ ] #3 Failed preflight, baseline, credentials, state, or proof prevents manual cutover
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Superseded by the simplified CI-only auto-merge plan on 2026-07-22.
<!-- SECTION:NOTES:END -->
