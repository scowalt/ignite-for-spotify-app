---
id: TASK-7
title: Mark official DLC in match results
status: Done
assignee:
  - '@scowalt'
created_date: '2026-07-22 18:33'
updated_date: '2026-08-16 00:04'
labels:
  - frontend
  - matching
  - metadata
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Match results do not distinguish official downloadable content from community-created arrangements, making it harder to choose the appropriate version.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Matches identified as official DLC display a clear, accessible marker in the results list
- [x] #2 Community or unknown matches are not incorrectly labeled as official DLC
- [x] #3 The official-DLC marker remains visible when alternate versions are collapsed or expanded
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Data model (backend):
1. Add OfficialDlc bool to Song entity (Entities.fs), mapped to songs.official_dlc in IgniteDbContext (default false).
2. Detect official DLC in CdlcScraper ParseSongCard: Ignition4 marks official DLC rows with a red highlight (KB: red = Official DLC). Extract IsOfficial from the card HTML the same way part-lead etc. are detected.
3. Persist: set OfficialDlc in UpsertAsync and BulkUpsertAsync (SongRepository).
4. Surface it: add officialDlc to CdlcMatchInfo (SearchHub.fs) and populate in PlaylistSearchJob when building matches.

Schema: DB uses EnsureCreated (no migrations). Add column via a defensive ALTER TABLE songs ADD COLUMN official_dlc (ignoring 'duplicate column' error) next to EnsureCreatedAsync in DependencyInjection.fs, so existing Turso DBs pick it up.

Frontend:
5. Add officialDlc to CdlcMatchInfo (signalr.ts) and CdlcSong (types/api.ts).
6. In MatchMyMusic.tsx render an accessible 'Official DLC' badge (styled like existing Lead/Rhythm/Bass chips, distinct color e.g. rose/red, with title/tooltip) inside each match row - so it shows both in the collapsed first match and in expanded alternates (AC #1, #3). Only rendered when officialDlc true, so community/unknown are never mislabeled (AC #2).

Tests:
7. Backend: extend CdlcScraperTests song card with the official marker; add a PlaylistSearchJobTests case asserting officialDlc flows into the SignalR payload for an official song and stays false otherwise.
8. Verify with dotnet build + dotnet test (backend) and bun test + frontend build/lint.

Note: rows shown as official by Ignition4 are marked; everything else stays unmarked (no false positives). Existing rows become accurate after the next incremental scrape.
<!-- SECTION:PLAN:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Marked official DLC in match results by piping an official-DLC flag end to end: Ignition4 scraper → Song (new official_dlc column) → search payload → UI badges.

Data source: Ignition4 highlights official DLC rows with a red indicator (per its documented Table Legend: red = Official DLC); the scraper now detects that marker and stores it with the song, so detection is source-driven rather than a lookup list. Only songs the source marks official are labeled, so community/unknown matches are never mislabeled (AC #2) and existing rows default to false until the next incremental scrape.

Backend
- Song.OfficialDlc persisted (songs.official_dlc); defensive ALTER TABLE … ADD COLUMN official_dlc during startup for DBs created before the column existed (idempotent, guarded; verified idempotency and legacy default=false against live SQLite; safe for both Microsoft.Data.Sqlite and Turso drivers).
- Scraper tags cards whose preceding result row carries the official indicator; persisted through UpsertAsync/BulkUpsertAsync.
- officialDlc exposed via the SignalR search payload (CdlcMatchInfo) and the /api/songs REST DTO.

Frontend
- Accessible "Official DLC" badge (rose chip styled like the existing part badges, with a tooltip) on each official match row; since the badge is on the row inside the collapsible list, it is visible both when alternate versions are expanded and collapsed (AC #3), and the track header also shows it when any of its versions is official.
- Added officialDlc to the frontend CdlcMatchInfo/CdlcSong types; Discover & Export table shows an "Official" chip for parity.

Tests
- backend/tests: scraper test with a multi-card page proving only the official row is flagged (no bleed to neighbors); job test asserting the flag reaches the search payload; EF Core round-trip test for the new column. All suites pass (75 backend tests) plus frontend lint/typecheck/tests/build.
<!-- SECTION:FINAL_SUMMARY:END -->
