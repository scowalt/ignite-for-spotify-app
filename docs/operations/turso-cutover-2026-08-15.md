# Turso to local SQLite cutover record

## Cutover

- Maintenance window: 2026-08-15 22:39–22:45 UTC
- Production data volume: `ignite-for-spotify_ignite-data`
- Application database: `/app/data/ignite.db`
- Verified backend image: `ghcr.io/scowalt/ignite-for-spotify-2/backend:cf9191d`
  (`sha256:b3ea0db2443e2e3d00aee2958bf2f7008a4b30b212056555d7b8a0e7d1ae0698`)
- Verified backup image: `ghcr.io/scowalt/ignite-for-spotify-2/backup:cf9191d`
  (`sha256:31628aec7e93e3c2cf62e0d634d09c3a7e48ee672aa7f687d3d08ede483db8dd`)

The backend and Watchtower were stopped before the authoritative Turso export.
The imported database passed `PRAGMA integrity_check`, contained all seven
required schema/FTS objects, and was installed with ownership `ignite:ignite`
and permission `0600`. The running database entered WAL mode.

## Source and target parity

| Metric | Turso source | Local target |
| --- | ---: | ---: |
| Songs | 158205 | 158205 |
| Songs with Spotify ID | 0 | 0 |
| Distinct Spotify IDs | 0 | 0 |
| User sessions | 88 | 88 |
| Scraping jobs | 445 | 445 |
| Maximum song ID | 158205 | 158205 |
| Maximum scraping job ID | 445 | 445 |

Maximum timestamps also matched exactly:

- Song update: `2026-07-15 09:17:06.796`
- Session update: `2026-08-15 03:17:07.566`
- Scraping job creation: `2026-08-15 06:01:02.756`

The rebuilt FTS index returned 578 Metallica results. The representative
Metallica-with-lead filter returned 261 results. Public readiness, statistics,
pagination, filtering, FTS, the Spotify login redirect, unauthenticated session
handling, and backend DNS resolution passed. A disposable write was read
through the HTTP API and then deleted; its FTS trigger entries were also
removed, the song count returned to 158205, and `PRAGMA quick_check` returned
`ok`.

## First encrypted backup and restore drill

- Backup completed: `2026-08-15T22:45:03Z`
- Restic snapshot: `71bbcf70`
- Repository host/tag: `ignite-production` / `ignite-database`
- Restored songs: 158205
- Restored sessions: 88
- Restored scraping jobs: 445
- Restored FTS Metallica results: 578
- Restored `PRAGMA integrity_check`: `ok`
- Live/restored aggregate parity: passed

The isolated plaintext restore, final Turso dump, imported staging database,
and rehearsal artifacts were securely removed after validation.

## Image promotion and steady state

Deployment workflow run `31915383456` completed successfully after the
`LOCAL_SQLITE_CUTOVER_COMPLETE` repository variable was enabled. The promoted
tags and verified production image digests are:

| Image | Tags | Digest |
| --- | --- | --- |
| Backend | `latest`, `3f8a473` | `sha256:3a2e121b534d1bf25dda0ea9553791144003e1498057b32d679b9086674facb1` |
| Backup | `latest`, `3f8a473` | `sha256:f45139370dcf2f75a124654753bd56d3888f0934c6ab2b9eeffffb799cec5675` |

Production Compose now references `latest` for the backend, backup, and
frontend. All three containers and Watchtower were healthy with zero restarts.
Watchtower's first post-cutover scan checked all three images and reported zero
failures and zero updates. Public readiness remained healthy, and the backup
container could read Restic snapshot `71bbcf70` using its production
credentials.

## Retirement gate

Do not revoke or delete Turso before `2026-08-22T22:45:03Z`. At that time:

1. Confirm at least seven successful daily backups and stable readiness.
2. Perform another isolated restore and repeat integrity, count, session, and
   FTS validation.
3. Revoke Turso credentials and remove `TURSO_CONNECTION_STRING` from Doppler.
4. Cancel the temporary Turso upgrade and delete the Turso database.
5. Securely remove the restricted VPS rollback directory after confirming it
   is no longer required.
