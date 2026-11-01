---
id: TASK-8
title: Match a playlist from a pasted Spotify URL
status: Done
assignee:
  - '@pi-agent'
created_date: '2026-07-22 18:33'
updated_date: '2026-08-09 15:27'
labels:
  - feature
  - frontend
  - spotify
  - matching
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Users can currently select only playlists already shown from their own library. Allow a Spotify playlist link to be submitted so an accessible playlist can be matched without first saving it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A user can paste a valid Spotify playlist URL and start matching that playlist
- [x] #2 An accessible playlist does not need to be saved in the user’s library before it can be matched
- [x] #3 Invalid, inaccessible, or unsupported links produce a clear actionable message
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Context: the backend matching endpoint POST /api/search/from-playlist already accepts ANY accessible playlist ID with no library-membership check — the restriction is purely frontend UI. Feature = URL input + parsing + preview endpoint + error mapping.

DECISIONS (defaults, user had no opinions):
- Input lives at top of PlaylistSidebar above "Your Playlists" (where selection already happens)
- Paste-time preview: new GET /api/spotify/playlists/{id} metadata endpoint; pasted playlist shown as a selectable card (name/image/track count) — fail fast on errors
- Accept: open.spotify.com/playlist/{id} (with ?si=, /intl-xx/, trailing junk), spotify:playlist:{id}, bare 22-char ID. Reject track/album/artist links with a specific message
- Map Spotify errors to actionable messages; mid-match failures use existing ReceiveError red banner (adequate)
- No persistence/recent-list; pasted playlist is session-only selection state
- No new test projects (repo has zero API endpoint tests and zero frontend tests; match existing bar)

STEPS:
1. Backend: add GetPlaylistAsync (wraps client.Playlists.Get) to ISpotifyClientService (Ignite.Core/Interfaces.fs) + RateLimitedSpotifyClient.fs implementation
2. Backend: GET /api/spotify/playlists/{playlistId} endpoint in Program.fs returning SpotifyPlaylist DTO (id/name/description/totalTracks/imageUrl); wrap Spotify call in try/catch mapping APIException 404 -> Results.NotFound({| error; message = "playlist is private or does not exist" |}), 403 -> Forbid/error JSON, others -> Problem. Pattern: follow /api/auth/me error style
3. Backend: add try/catch + same error mapping around the GetPlaylistTracksAsync call in POST /api/search/from-playlist so bad IDs stop producing 500s
4. Frontend: parseSpotifyPlaylistId() util (new file, e.g. src/lib/spotifyUrl.ts) — returns { ok: id } | { error: message } for the 3 accepted formats; rejects non-playlist Spotify links with "that link is an X, not a playlist" style messages
5. Frontend: api.ts — add spotify.getPlaylist(id) hitting the new endpoint
6. Frontend: PlaylistSidebar — paste input row at top; debounce/onEnter validate via util; on valid ID, TanStack Query fetches metadata; result shown as a highlighted card calling onSelectPlaylist; ApiError messages (invalid format / not found / inaccessible) shown inline in the sidebar
7. Frontend: MatchMyMusic — verify pasted playlist flows through selectedPlaylist -> startSearch unchanged (it takes only playlist.id); clear pasted-playlist state appropriately
8. Manual verification via dev server + typecheck/lint (frontend: npm run typecheck, lint; backend: dotnet build)
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- Backend: added GetPlaylistAsync to ISpotifyClientService + RateLimitedSpotifyClient (wraps client.Playlists.Get)
- Backend: new GET /api/spotify/playlists/{id} metadata endpoint with 404/403/400 error mapping; same mapping added to POST /api/search/from-playlist (bad IDs no longer 500)
- Frontend: parseSpotifyPlaylistId util (URL with ?si//intl-xx, spotify: URI, bare ID; specific messages for track/album/etc links)
- Frontend: api.ts getPlaylist(); ApiError now prefers backend JSON message over statusText
- Frontend: PlaylistSidebar paste-link input -> preview card -> auto-selects via existing onSelectPlaylist flow; library IDs select directly without fetch; clear button on pasted card
- Verified: dotnet build 0 errors; bun typecheck 0 errors; eslint 0 errors (pre-existing warnings only); vite build OK
- Manual verification via dev server not done (requires Spotify auth session)

- Rebase onto main: upstream refactored from-playlist into Hangfire PlaylistSearchJob; kept upstream job flow and instead added PlaylistFetchException mapping (404 -> "private or does not exist", 403 -> "no access") surfaced via SignalR SendErrorAsync
- ApiError message handling kept upstream version (already prefers backend message)
- PlaylistSidebar user-info block removed upstream (PR #184); my paste-link section applied on top
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Paste-a-Spotify-link playlist matching: users can now match any playlist accessible to their Spotify account without saving it to their library first.

Changes:
- Backend: new GET /api/spotify/playlists/{id} metadata endpoint (GetPlaylistAsync wrapping client.Playlists.Get, through the existing rate-limit/retry pipeline); Spotify 404/403 mapped to actionable messages instead of 500s; same mapping added to POST /api/search/from-playlist track fetch.
- Frontend: parseSpotifyPlaylistId util accepting open.spotify.com/playlist/{id} (with ?si=/intl-xx junk), spotify:playlist: URIs, and bare 22-char IDs, with specific rejection messages for track/album/artist links.
- Frontend: paste-link input at the top of PlaylistSidebar; Enter validates, fetches a metadata preview, shows the playlist as a selectable card, and auto-selects it via the existing selection flow (library matches select directly with no fetch). ApiError now surfaces the backend's actionable message instead of HTTP status text.

Tests/verification:
- dotnet build: 0 errors
- tsc --noEmit: clean; eslint: 0 errors (pre-existing warnings only)
- vite build: OK
- Not manually verified in a browser (requires a Spotify auth session).

Risks/follow-ups: pasted playlists are session-only selection state (no persistence or recent list); TASK-10 may revisit this.
<!-- SECTION:FINAL_SUMMARY:END -->
