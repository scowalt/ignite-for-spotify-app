---
id: TASK-9
title: Prevent silent truncation of large playlists
status: Done
assignee:
  - '@myself'
created_date: '2026-07-22 18:33'
updated_date: '2026-07-28 00:34'
labels:
  - bug
  - backend
  - spotify
  - matching
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A 691-song playlist appeared to stop after roughly 180 songs and reported 117 matches without explaining whether processing failed or hit a limit. Large playlists must complete or clearly report why they cannot.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Matching retrieves and processes every available track from a 691-song Spotify playlist, including all paginated results
- [x] #2 The final summary reports total playlist tracks, processed tracks, matched tracks, and skipped or failed tracks consistently
- [x] #3 If a limit or failure prevents completion, the user sees a clear partial-results message and a reason instead of silent truncation
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Replace request-bound playlist matching with a Hangfire job that resolves the stored Ignite session and reports through SignalR.
2. Fetch Spotify playlist items in explicit retryable pages and preserve complete, skipped, and partial-fetch accounting.
3. Extend completion/API contracts and render complete versus partial summaries with consistent counts.
4. Add backend and frontend regression coverage, run all available verification, and record completion through Backlog CLI.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Replaced the request-bound playlist match loop with a Hangfire matching job; the authenticated endpoint now enqueues the stored Ignite session ID and returns 202 Accepted immediately.
- Added explicit 50-item Spotify pagination with per-page Retry-After handling, offset validation, no-duplicate retries, skipped-item accounting, and partial-fetch reasons.
- Extended SignalR and playlist-track API contracts with total, retrieved/processed, matched, skipped, failed, unprocessed, and completeness fields.
- Added accessible complete and partial-result summaries while preserving results from successful pages/tracks.
- Regression coverage includes 691 items across 14 pages, skipped items, terminal pagination failures, retry deduplication, 202 enqueue behavior, complete job accounting, per-track failures, and frontend summary presentation.
- Verification passed: .NET restore/build; 65 backend tests; 12 Bun tests; TypeScript; ESLint (0 errors, 3 pre-existing warnings); Vite production build; git diff --check. A live Spotify-account run was not performed because this worktree has no user-authenticated test session; the 691-item and asynchronous boundary are covered deterministically.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Prevented large playlist searches from being cancelled with the initiating HTTP request. Searches now enqueue a Hangfire job and return 202 immediately, fetch all Spotify pages with rate-limit-aware retries, retain partial results, and report complete count accounting through SignalR. The UI distinguishes accessible complete summaries from partial results with a concrete reason. Added backend coverage for 691-item pagination/job execution and frontend summary tests; all build and test checks pass.
<!-- SECTION:FINAL_SUMMARY:END -->
