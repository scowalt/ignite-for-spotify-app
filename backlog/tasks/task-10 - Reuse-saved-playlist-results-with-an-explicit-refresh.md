---
id: TASK-10
title: Reuse saved playlist results with an explicit refresh
status: Done
assignee:
  - '@scowalt'
created_date: '2026-07-22 18:33'
updated_date: '2026-08-16 17:35'
labels:
  - feature
  - frontend
  - backend
  - matching
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Repeatedly opening the same playlist rematches everything. Preserve the latest completed results and let users decide when to refresh them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Returning to a previously matched playlist presents its latest completed results without automatically rematching every track
- [x] #2 Saved results show when they were generated or otherwise make their freshness clear
- [x] #3 Users can explicitly refresh a playlist and receive newly generated results without losing the previous completed results if refresh fails
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Persist each user playlist latest fully completed match snapshot and expose an authenticated latest-results endpoint. 2. Load saved snapshots when playlists are selected, label their generation time, and make the primary action an explicit refresh. 3. Keep saved results visible during refresh and preserve them when a refresh is partial or fails. 4. Cover persistence, refresh safety, API, responsive UI, and accessibility with automated and browser verification.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented one latest fully completed playlist-search snapshot per Spotify user and playlist, including an idempotent SQLite schema upgrade, authenticated retrieval, and atomic replacement through the repository. Match My Music now loads saved results on selection without starting a job, shows their generation time, offers an explicit Refresh Matches action, keeps saved results visible during refresh, and retains them after partial or failed refreshes. Added responsive header hardening after mobile QA exposed clipped controls. Verification: backend build/tests passed (85 tests), frontend typecheck/lint/tests/build passed (30 tests), git diff check passed, and the Impeccable detector returned no findings. Browser checks covered saved-result loading without POST, keyboard-triggered failed refresh with preserved results, successful replacement/refetch, freshness copy, 1440x900 desktop, 390x844 mobile, and no horizontal overflow.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Saved Match My Music results now persist per Spotify user and playlist, load automatically when revisiting a playlist, display their freshness, and refresh only on explicit request. Failed or partial refreshes leave the prior completed result set intact.
<!-- SECTION:FINAL_SUMMARY:END -->
