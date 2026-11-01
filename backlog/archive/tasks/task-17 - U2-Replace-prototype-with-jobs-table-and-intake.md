---
id: TASK-17
title: 'U2: Replace prototype with jobs table and intake'
status: To Do
assignee: []
created_date: '2026-07-22 21:10'
updated_date: '2026-07-23 22:07'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace the committed multi-table lifecycle/action prototype with the single jobs-table baseline, eligibility, FIFO capacity, and persisted dispatch-gate design.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Prototype action/transition schema and tests are removed in favor of one jobs table with no data migration
- [ ] #2 Baseline, positive resolved observation, reactivation, and uniqueness rules prevent duplicate active jobs
- [ ] #3 Dispatch defaults false and FIFO capacity plus restore behavior remain visible and restart-safe
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Superseded by the simplified CI-only auto-merge plan on 2026-07-22.
<!-- SECTION:NOTES:END -->
