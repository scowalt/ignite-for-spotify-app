# Ignite for Spotify verification map

This directory is the maintained source for verifying the user-facing behavior of Ignite for Spotify. Read the index before driving the app, then use the matching feature file as the recipe. All commands assume `V=.claude/skills/verify/scripts/ignite-verify` from the repository root.

## Baseline preconditions

- Start a run with `$V up`. It launches the API, the Vite web app, and headless Chrome, isolated under one `RUN_ID`.
- The run's database holds exactly the six fixture songs from `scripts/seed.sql`: Metallica `Enter Sandman`, `Nothing Else Matters`, `One`; Foo Fighters `Everlong`; Muse `Hysteria`; Nirvana `Come as You Are`. `One` and `Come as You Are` have no Spotify match.
- No browser session is signed in to Spotify, and none can be: the run has no Spotify client credentials.
- `$V doctor` exits `0` and its `web` line names the `WEB_URL` you are about to drive.
- Never drive an instance that was not started by this verification run.

## Driving conventions

- Start every recipe with `$V browser goto <route>`. Page state persists between calls until the next `goto`, so a recipe that skips it inherits the previous recipe's URL, filters, and selections.
- Prefer ARIA roles and accessible names. The Discover filter inputs have no associated label, so address them with `--placeholder`.
- Treat every command as literal. Keep quoted names and flags unchanged.
- Wait on an element (`wait`, `wait-gone`, `wait-url`), never on a fixed sleep.
- Use `$V api` and `$V sql` only as second views of state the browser changed or displayed.
- The fixture catalog is read-only in every recipe. If a recipe needs different songs, change `scripts/seed.sql` and the fixture table in `SKILL.md`.

## Proof and skip reporting

- Capture the user action and the resulting state, not only the final screen.
- UI proof is an ARIA snapshot plus a screenshot, written under `EVIDENCE_DIR/<feature-id>/` with `$V browser snapshot --path` and `$V browser screenshot --path`.
- Data claims pair the page with `$V sql` or `$V api` output that shows the same rows.
- Record the feature ID and entry point used with every artifact.
- Report an unreachable path as failed, with the attempted command and the unmet precondition. Journeys behind Spotify sign-in are failed with `GET /api/auth/login returns 500: no Spotify client credentials in an isolated run`.
- Do not report a skipped entry point as verified through a different path.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order.

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with ignite-verify` starts with `Preconditions:` and uses labeled bullets that pair each user action with an exact command and observable result.
4. `Gotchas` lists traps that can waste or invalidate a verification run.

Keep implementation details out of the map. Name only user paths, stable handles, required state, commands, and observable proof.

## Features

- [Home](./home.md) covers the landing page, header navigation, catalog count, and calls to action.
- [Discover search](./discover-search.md) covers catalog stats, text and part filters, the Spotify-match filter, the empty state, and result rows.
- [Discover export](./discover-export.md) covers selecting results and exporting them to a new Spotify playlist.
- [Match My Music](./match-my-music.md) covers the sign-in gate, playlist selection, and CDLC matches for a playlist.
- [Spotify sign-in](./spotify-sign-in.md) covers every login entry point, the expired-link banner, and the signed-in header.
- [Privacy](./privacy.md) covers the privacy notice and the footer links that reach it.
