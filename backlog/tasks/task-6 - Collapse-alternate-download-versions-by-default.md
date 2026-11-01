---
id: TASK-6
title: Collapse alternate download versions by default
status: Done
assignee:
  - '@codex'
created_date: '2026-07-22 18:33'
updated_date: '2026-08-09 15:43'
labels:
  - frontend
  - ux
  - matching
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Tracks with several download matches make the results list excessively long. Keep alternate versions compact until the user asks to inspect them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A result with multiple download versions initially shows a compact summary instead of every version
- [x] #2 Users can expand and collapse all available versions for an individual result
- [x] #3 The collapsed state does not hide the track’s match status or primary action
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per-result expanded state. Multi-match results now show only the first downloadable match by default, retain the total match count and primary Download action, and expose an accessible toggle for alternate versions. Expansion state resets for each new search.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Collapsed alternate match versions by default in Match My Music and added independent, accessible expand/collapse controls for each result. Verified with frontend typecheck, lint, production build, and git diff checks.
<!-- SECTION:FINAL_SUMMARY:END -->
