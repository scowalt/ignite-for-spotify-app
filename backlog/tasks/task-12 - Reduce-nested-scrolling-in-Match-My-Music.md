---
id: TASK-12
title: Reduce nested scrolling in Match My Music
status: Done
assignee:
  - '@scowalt'
created_date: '2026-07-22 18:33'
updated_date: '2026-08-16 17:00'
labels:
  - frontend
  - ux
  - responsive
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Separate scroll areas make Match My Music awkward to navigate, especially on large screens. Prefer a coherent page-level scroll and align any necessary scrollbar styling with the site theme.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The normal desktop Match My Music flow does not require users to manage competing nested vertical scroll areas
- [x] #2 Playlist and result content remains reachable on smaller viewports and with keyboard navigation
- [x] #3 Any scroll area that remains necessary uses scrollbar styling consistent with the site color scheme where the browser supports it
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Remove desktop results/sidebar scroll ownership so the document is the only md+ vertical scroller.
2. Rebuild the mobile Drawer on Kobalte Dialog with one themed content scrollport, modal focus containment, Escape dismissal, body lock, and trigger focus restoration.
3. Theme the document and explicit scroll regions, preserve sticky controls, and make result auto-scroll reduced-motion-safe with sufficient scroll margin.
4. Verify desktop/mobile/keyboard extremes, run frontend checks and the Impeccable detector, then record completion evidence.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented natural document scrolling on desktop, removed reusable sidebar scroll ownership, rebuilt the mobile drawer with Kobalte Dialog and one themed content scrollport, and made results auto-scroll reduced-motion-safe with sticky-header clearance. Verification: typecheck, lint, 25 unit tests, production build, git diff check, and Impeccable layout detector all passed. Browser checks passed at 1440x900, 1024x768, and 390x844 plus a 200% zoom approximation, using 64 playlists and 36 result groups: no desktop nested scrollports, one locked mobile drawer scrollport, no horizontal overflow, sticky controls, reachable footer/results/downloads, reduced-motion auto scrolling, keyboard focus containment/restoration, playlist selection, Escape dismissal, and empty/error states.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Unified Match My Music scrolling so desktop content uses the document while mobile playlist navigation uses one accessible, themed Kobalte drawer scrollport. Preserved sticky search controls, long-content reachability, matching and download interactions, and reduced-motion behavior.
<!-- SECTION:FINAL_SUMMARY:END -->
