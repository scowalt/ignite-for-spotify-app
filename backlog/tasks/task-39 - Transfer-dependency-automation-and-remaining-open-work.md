---
id: TASK-39
title: Transfer dependency automation and remaining open work
status: To Do
assignee: []
created_date: '2026-11-03 01:08'
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
<!-- AC:END -->
