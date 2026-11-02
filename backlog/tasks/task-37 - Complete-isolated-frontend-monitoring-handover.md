---
id: TASK-37
title: Complete isolated frontend monitoring handover
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-02 21:39'
updated_date: '2026-11-02 21:39'
labels: []
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure Mission Control monitoring covers the newly active isolated frontend organization as well as legacy/frontend and unchanged backend history, preserving metadata-only output and existing private diagnostics. Preserve pre-existing Mission Control working changes and publisher/deployment fences.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Default maintained monitoring reads both allowlisted organizations and distinguishes identical project slugs without emitting raw event data.
- [ ] #2 Pagination cannot cross an organization boundary, and unavailable organization coverage fails visibly rather than silently reporting success.
- [ ] #3 Offline regressions and a bounded live metadata-only check pass; canonical source and installed helper are synchronized while pre-existing work is preserved.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve existing Mission Control modifications and work from its current upstream in an isolated worktree.
2. Add explicit allowlisted multi-organization coverage, namespaced output and pagination guards with tests. Preserve existing diagnostics/sanitizers and no-event default.
3. Validate/merge through its forge, apply only the feature delta to the existing working source, install the verified helper and run one bounded metadata-only live check.
4. Keep all publisher/updater fences and other project work unchanged; report any supported-interface or authorization limitation rather than bypassing it.
<!-- SECTION:PLAN:END -->
