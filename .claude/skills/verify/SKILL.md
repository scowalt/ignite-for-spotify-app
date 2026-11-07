---
name: verify
description: Launch, drive, and prove Ignite for Spotify (SolidJS web app + F# API over a seeded SQLite catalog) in an isolated local run with a headless browser. Use when you need to show a user-facing change works in the real app — Discover & Export search, Home, Match My Music, Privacy, the login gate — or when asked to verify, smoke-test, or reproduce UI behavior.
---

# Verify Ignite for Spotify

One helper, `ignite-verify`, owns the whole loop. Every run is isolated: its own SQLite database, Hangfire database, Portless routes, API port, and headless Chrome profile, keyed by a `RUN_ID`. Two agents can run side by side in the same or different worktrees. Never drive the user's dev server, Docker stack, or production; drive only a run you started.

```bash
V=.claude/skills/verify/scripts/ignite-verify
```

Paths are relative to the repository root. `.agents/skills/verify` is a symlink to this directory, so Pi discovers the skill once the project is trusted.

Read [`features/README.md`](features/README.md) before driving, then the matching feature file as the recipe.

## Launch

```bash
$V up
```

`up` takes about 40 seconds warm, 2 minutes on a cold build, and does this in order:

1. Resolves a .NET 10 SDK and Chrome, and installs `playwright-core` into `.verify/tools/` and frontend dependencies if missing.
2. Builds `backend/src/Ignite.Api` (errors in `.verify/last-build.log`).
3. Starts the API under Portless as `ivfy-<RUN_ID>-api` with `ASPNETCORE_ENVIRONMENT=Development`, `Database__RequireExisting=false`, databases under `.verify/runs/<RUN_ID>/`, and Sentry disabled. Migrations run on startup.
4. Waits for `/health/ready`, then seeds six fixture songs from [`scripts/seed.sql`](scripts/seed.sql).
5. Starts Vite under Portless as `ivfy-<RUN_ID>-web` with `IGNITE_API_PROXY_TARGET` pointing its `/api` and `/hubs` proxy at this run's API.
6. Waits until `WEB_URL/api/songs/stats` reports `"totalSongs":6` through the proxy. That is the ready signal: app served, proxy wired, migrations done, seed visible.
7. Starts headless Chrome with a run-local profile and a DevTools port on `127.0.0.1`.

It prints the run variables (`RUN_ID`, `WEB_URL`, `EVIDENCE_DIR`, `API_PORT`, `CDP_PORT`, PIDs, `GIT_HEAD`) and records the run as current for this worktree. `$V env` prints them again. Set `IGNITE_VERIFY_RUN=<RUN_ID>` to address a specific run when you have more than one.

If `up` fails at any step it tears its own run down and keeps the logs in `.verify/evidence/<RUN_ID>/logs/`. Read them before retrying.

Overrides: `IGNITE_VERIFY_DOTNET=/path/to/dotnet` (mise's `dotnet` plugin is broken on this host, so the helper searches `~/.local/share/mise/installs/*/10.0.*/dotnet`), `IGNITE_VERIFY_CHROME=/path/to/chrome`.

The fixture catalog:

| id | Artist | Title | Album | Parts | Spotify |
|---|---|---|---|---|---|
| 1 | Metallica | Enter Sandman | Metallica | L R B | ✓ |
| 2 | Metallica | Nothing Else Matters | Metallica | L R | ✓ |
| 3 | Metallica | One | ...And Justice for All | L B | None |
| 4 | Foo Fighters | Everlong | The Colour and the Shape | L R B V | ✓ |
| 5 | Muse | Hysteria | Absolution | B | ✓ |
| 6 | Nirvana | Come as You Are | Nevermind | L B | None |

Stats therefore read `6` total, `4` with a Spotify match, `66.7%`.

## Doctor

```bash
$V doctor
```

Read-only, exit `1` when any line says `FAIL`. Run it right after `up`, before every proof, and whenever anything looks off. It checks that the three process groups this run started are alive, that the API port is held by a process under this run's API and that process reads this run's database, `/health/ready`, that `WEB_URL` serves the Ignite app and proxies to this run's seeded API, that both Portless routes are registered, that Chrome DevTools answers, that the backend build is newer than every `.fs` source, and that `HEAD` has not moved since launch. A stale build or moved `HEAD` means `$V down` then `$V up`; Vite hot-reloads frontend edits, the API does not reload.

## Drive

All UI actions go through `$V browser`, which attaches to this run's Chrome over CDP, acts on the single page, and detaches. Page state persists between calls, so a recipe is a sequence of one-line commands.

```bash
$V browser goto /discover
$V browser wait --role heading --name "Discover & Export"
$V browser fill --placeholder "e.g., Metallica" --value "Metallica"
$V browser wait --role cell --name "Enter Sandman"
$V browser count --role row
$V browser uncheck --role checkbox --name "Has Spotify Match"
$V browser text --role row --name "Metallica One"
```

Actions: `goto <path|url>`, `click`, `fill --value`, `check`, `uncheck`, `press --key`, `wait`, `wait-gone`, `wait-url <regex>`, `text`, `count`, `url`, `snapshot --path`, `screenshot --path [--full]`. Locators: `--role <role> [--name <name>]`, `--text`, `--placeholder`, `--label`, plus `--exact` and `--nth <n>`. `$V browser help` prints the full usage. Prefer roles and accessible names; the filter inputs have no associated labels, so address them by placeholder. Wait on an element, never on a fixed sleep. Every action is appended to `EVIDENCE_DIR/actions.log` with its result.

Non-UI side views, for proving side effects next to what the page shows:

```bash
$V api POST /api/search/cdlc '{"artist":"Metallica","hasSpotifyId":true,"page":1,"pageSize":50}'
$V api GET /api/auth/session
$V sql "select title, spotify_track_id from songs where artist = 'Metallica'"
```

`api` goes through the web origin's `/api` proxy, the same path the browser uses, and prints the body then `HTTP <status>`. `sql` opens this run's database read-only and prints JSON.

Spotify-authenticated journeys (playlists, Match My Music results, export) cannot be reached in an isolated run: the run has no Spotify client credentials, so `GET /api/auth/login` returns `500` (`String is empty or null (Parameter 'clientId')`), and the Doppler `dev` redirect URI points at the production domain. Report those journeys as failed with that reason. Do not insert rows into `user_sessions` or mock Spotify to get past the gate.

## Evidence

Everything for a run lands in `.verify/evidence/<RUN_ID>/` (gitignored) and survives `down`:

- `actions.log`: timestamped browser actions and their outcomes.
- `<feature>/*.aria.yml` and `<feature>/*.png`: from `$V browser snapshot --path <feature>/<step>.aria.yml [locator]` and `$V browser screenshot --path <feature>/<step>.png --full`. Relative paths resolve under `EVIDENCE_DIR`.
- `logs/api.log`, `logs/web.log`, `logs/chrome.log`, `logs/run.env`: copied at teardown.

Proof standards:

- Drive the real user path in the browser. `api` and `sql` are second views of the same state, never a substitute for the UI step.
- Capture the action and the resulting state. Snapshot or screenshot after each step that changes what the user sees, not only at the end.
- Pair what the page shows with a read of the source of truth (`sql` or `api`) when the claim is about data.
- Name the feature ID and entry point with each artifact, and cite artifact paths in the report.
- An unreachable journey is reported as failed with the command attempted and the unmet precondition. Never report it as verified through a different path.

## Cleanup

```bash
$V down          # the selected run
$V down --all    # every run under this worktree's .verify/runs/
```

`down` stops only the process trees this run started (Chrome, then Vite, then the API), by the group-leader PIDs recorded at launch, with `TERM` then `KILL` after 15 seconds. Stopping the Portless wrappers removes their routes. It then copies the logs into the evidence directory and deletes `.verify/runs/<RUN_ID>/` (databases, Chrome profile). It never touches other Portless routes, other worktrees' runs, or processes it did not start; never kill by process name. Run `down` after every failed attempt too. Afterwards `portless list` shows no `ivfy-` route and the evidence directory is intact.

## Helpers

All under `.claude/skills/verify/scripts/`:

- `ignite-verify` (executable): `up`, `doctor`, `env`, `browser`, `api`, `sql`, `down`. `$V help` prints usage.
- `browser.ts`: the CDP driver behind `$V browser`, run with Node's built-in TypeScript type stripping (Node 22.18 or later). Bun's WebSocket client cannot hold a CDP connection to Chrome, so do not run it with Bun.
- `seed.sql`: the six fixture songs. Add rows here when a journey needs new catalog state, update the fixture table above, and keep `SEEDED_SONGS` in `ignite-verify` equal to the row count.

State lives in `.verify/` at the repository root: `tools/` (pinned `playwright-core`), `runs/<RUN_ID>/` (scratch, deleted by `down`), `evidence/<RUN_ID>/` (kept), `current` (selected run).
