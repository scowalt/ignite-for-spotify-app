# Ignite for Spotify

Bridge between Spotify and Rocksmith CDLC (Custom Downloadable Content).

The intended development and production source of truth is
`scowalt/ignite-for-spotify-app`. Source and validation CI are public; production
publishing is not yet activated. Follow the [full handover plan](docs/operations/public-repository-handover.md)
before moving development, automation or publishing. The old repository retains
private history; it is not intended to remain a development or deployment mirror.

Original code and custom artwork are [MIT-licensed](LICENSE). Dependencies retain
their own terms; see [third-party notices](THIRD_PARTY_NOTICES.md).

## What is CDLC?

CDLC (Custom Downloadable Content) are community-created songs for Rocksmith, a music video game that helps you learn guitar and bass. The [CustomsForge](https://customsforge.com) community hosts thousands of custom songs you can play in Rocksmith.

## Features

- **Match My Music**: Find CDLC songs that match your Spotify playlists - discover which of your favorite songs are available to play in Rocksmith
- **Discover & Export**: Browse the CDLC database and create Spotify playlists from songs you want to learn - preview before you download

## Tech Stack

- **Backend**: .NET 10 with Hangfire
- **Frontend**: SolidJS + TypeScript + TailwindCSS
- **Database**: SQLite on the production VPS, with encrypted off-host backups in Cloudflare R2
- **Secrets**: Doppler

## Development

### Prerequisites

- .NET 10 SDK (preview)
- Bun
- OpenTofu (for infrastructure)

### Backend

```bash
cd backend
dotnet restore
dotnet run --project src/Ignite.Api
```

### Frontend

```bash
cd frontend
bun install
bun run dev
```

## Deployment

During the migration, use the separately approved
[first-release procedure](docs/operations/fresh-image-cutover.md), not the generic
commands below. The new publisher remains disabled until the operational handover.

Uses Docker Compose with Caddy reverse proxy. Secrets are managed via Doppler.

```bash
doppler run --project ignite-for-spotify --config prd -- \
  docker compose -f docker/docker-compose.prod.yml up -d
```

Production requires an existing `/app/data/ignite.db` in the `ignite-data`
volume and will not silently create an empty replacement. Follow the
[Turso-to-SQLite cutover runbook](docs/operations/turso-to-local-sqlite.md) for
the initial migration and the [SQLite backup runbook](docs/operations/sqlite-backup-recovery.md)
for backup and restore operations.

### Accessing Hangfire Dashboard

The Hangfire dashboard is only accessible via localhost (not exposed to the public internet). Use an SSH tunnel:

```bash
ssh -L 5050:localhost:5050 your-server
```

Then open http://localhost:5050/hangfire in your browser.

## Local GlitchTip/Paseo Controller

The GlitchTip/Paseo controller is a local user operation, not part of the Docker
application deployment. It reads only GlitchTip projects 1 and 2 and relies on GitHub
protected-branch CI plus auto-merge as its only merge decision. Its initial CI job is
intentionally non-required.

Start with the fixture-backed or live **observe** gate. Dispatch is disabled by default
and requires both the persisted `controller.dispatch_enabled` policy and an explicit
`dispatch --once --enable-dispatch` command; normal `report` cannot dispatch. Each tick
launches at most one queued job and never auto-retries. The controller passes the shared
`GITHUB_AUTOMATION_TOKEN` to the Paseo coding agent with its explicit per-agent `--env`
option, never in a prompt, log, status output, or static configuration. GitHub required CI
and auto-merge are the only merge authority; after a confirmed linked PR merge, the
controller makes a normal current-state read and GlitchTip resolved-status update before
cleanup. Dispatch templates remain disabled by default. No live dispatch, Doppler use,
or service installation/enablement was performed for this change. See the [controller
operations runbook](docs/operations/glitchtip-paseo-controller.md) and [guarded legacy
cutover runbook](docs/operations/legacy-glitchtip-remediator-cutover.md).

### Setting Up GHCR Authentication

Watchtower needs GHCR credentials to pull private images. On the server, run:

```bash
# Create a GitHub PAT with read:packages scope, then:
echo $GITHUB_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

This creates `/root/.docker/config.json` which Watchtower mounts for authentication. After this one-time setup, Watchtower will automatically pull new images.

### Updating Production

Watchtower automatically pulls new images, but it **cannot** apply docker-compose.yml changes (port bindings, volumes, env vars). For compose changes:

```bash
git pull
docker compose --env-file .env -f docker/docker-compose.prod.yml up -d
```

If Watchtower isn't pulling updates, verify GHCR auth is set up (see above) or pull manually:

```bash
docker pull ghcr.io/scowalt/ignite-for-spotify-app/backend:latest
docker pull ghcr.io/scowalt/ignite-for-spotify-app/frontend:latest
docker compose --env-file .env -f docker/docker-compose.prod.yml up -d --force-recreate
```

### IPv6-Only VPS Architecture

The production VPS is **IPv6-only** (no IPv4 connectivity). Docker bridge networks don't support IPv6 by default, so we use host networking:

- **Backend**: Uses `network_mode: host`, binds to `127.0.0.1:5050`
- **Caddy**: Uses `network_mode: host`, proxies to `127.0.0.1:5050` (backend) and `127.0.0.1:3000` (frontend)
- **Frontend**: Uses bridge network with port mapping `127.0.0.1:3000:80`

This allows the backend to make outbound IPv6 connections (e.g., to ignition4.customsforge.com) using the host's network stack.

### Triggering Background Jobs

Jobs can be triggered from the Hangfire dashboard:

1. SSH tunnel: `ssh -L 5050:localhost:5050 your-server`
2. Open http://localhost:5050/hangfire
3. Go to **Recurring Jobs**
4. Click **Trigger now** on the desired job (e.g., `scrape-cdlc`)
