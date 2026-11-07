# Match My Music

A signed-in user picks one of their Spotify playlists, or pastes a playlist link, and sees which tracks have Rocksmith CDLC, with download links. Signed out, the page asks the user to log in.

## Sub-features

- `match-signed-out` shows `Login with Spotify to access your playlists` and a `Login with Spotify` button.
- `match-playlists` lists the user's playlists under `Your Playlists`, filterable with `Filter playlists...`.
- `match-paste-link` accepts a pasted playlist link in `Paste a playlist link...`, clearable with `Clear pasted playlist`.
- `match-search` runs `Search for Matches` for the chosen playlist and shows per-track CDLC matches with `Download` links, or `No matches found`.
- `match-saved-result` shows the last completed result for a playlist on return and offers `Refresh Matches`.
- `match-alternates` expands and collapses alternate CDLC versions of a track (`Hide alternate versions`).
- `match-errors` reports `Search failed` and `Playlist search returned partial results`.

## How to get to it (user POV)

- Open `/match` directly.
- Choose `Match My Music` in the header navigation.
- Choose the `Match My Music` card on Home.

## Driving it with ignite-verify

Preconditions:

- Baseline run from [the index](./README.md), `$V doctor` exits `0`.
- Every sub-feature except `match-signed-out` needs a signed-in Spotify session with at least one playlist whose tracks match fixture songs by Spotify track ID. An isolated run cannot sign in, and the fixture track IDs (`verifyfixturetrack000N`) are not real Spotify IDs. Report those sub-features as failed with that reason.

- **Open from navigation.** Run `$V browser goto /` then `$V browser click --role link --name "Match My Music" --exact --nth 0`, then `$V browser wait --role heading --name "Match My Music" --exact`. `$V browser url` ends with `/match`.
- **Signed-out gate.** Run `$V browser wait --text "Login with Spotify to access your playlists"`, then `$V browser snapshot --path match-my-music/01-signed-out.aria.yml` and `$V browser screenshot --path match-my-music/01-signed-out.png`. The snapshot shows `button "Login with Spotify"` and no `Your Playlists` region.
- **Second view.** Run `$V api GET /api/spotify/playlists`. Prints `HTTP 401`, confirming the gate matches the server.
- **Playlists, paste, search, saved result, alternates, errors.** Not reachable. Report each ID as failed: Spotify sign-in is unavailable in an isolated run.

## Gotchas

- The header link and the Home card both have the name `Match My Music`; use `--exact --nth 0` for the header link, or `goto /match`.
- The page shows a loading state while the session check runs. Wait for the signed-out text, not the heading alone.
- Matching runs over SignalR at `/hubs/search` through the Vite proxy. A signed-in verification on a configured instance must wait for the result list, not the button state.
- Making the signed-in journeys verifiable needs Spotify credentials with a redirect URI registered for the run's origin and a seed whose `spotify_track_id` values are real track IDs from the test account's playlist. Both are owner decisions; do not work around them.
