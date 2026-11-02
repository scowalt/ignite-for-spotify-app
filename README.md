# Ignite for Spotify

Bridge between Spotify and Rocksmith CDLC (Custom Downloadable Content).

The development source of truth is `scowalt/ignite-for-spotify-app`. Source and
validation CI are public, and production runs the verified digest-pinned release
from this repository. Automatic publishing/updating remains paused. The owner's
permanent development checkout is `~/Code/ignite-for-spotify-app`. Follow the
[full handover plan](docs/operations/public-repository-handover.md) before changing
production, integrations or publishing. The old repository retains
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

- .NET 10 SDK (use the version pinned in `.mise.toml`)
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

The [runtime cutover record](docs/operations/runtime-cutover-plan.md) identifies the
active digest override, public Compose file and retained base directory. Use those
explicit identities for any separately approved operation, not a generic whole-stack
`compose up`. Existing volumes, Caddy/Alloy binds and credentials must be preserved.

Docker Compose and Caddy remain in use, with secrets supplied by Doppler. Watchtower
and both publishers are intentionally paused pending the continuing-CD decision.

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

## Error reporting and infrastructure

GlitchTip remains the application error tracker. Source-map uploads retain the
pinned debug-ID workflow; see [compatibility evidence and testing](docs/operations/source-map-compatibility.md).
The owner no longer uses Paseo, so its dispatch is retired from the handover.
Controller source/tests remain historical and inactive; do not install or enable them.

[Infrastructure adoption](infra/README.md) uses a separate root/state for the existing
public repository and its protected production environment. The retained infrastructure
root still owns the old private repository, DNS and backup bucket. Changing its repository
name is not a migration procedure. No import, apply or live configuration is performed
by CI.

### Registry access and production updates

The production client has verified pull access to all three deployed digests using
existing GHCR credentials. Watchtower is stopped, with its configuration retained. If access fails, stop for a
separately approved minimum-access credential plan; do not grant the public
repository access to legacy private package history.

Watchtower can update consumed image tags but cannot apply Compose changes. The
[first-release procedure](docs/operations/fresh-image-cutover.md) coordinates the
single updater/publisher, pins images and preserves the existing project, volumes,
backup identity and proxy binds. Do not substitute a whole-stack recreation or a
`git pull` in an old checkout for that procedure.

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
