# SQLite backup and recovery

The `ignite-backup` container creates an online SQLite snapshot of only
`/data/ignite.db`, checks it, and sends it to a client-side encrypted Restic
repository in the private Cloudflare R2 bucket. Hangfire's database is excluded
to avoid replaying stale background jobs after a restore.

## Provisioning

1. Apply the OpenTofu configuration in `infra/` to create the private
   `ignite-for-spotify-db-backups` bucket.
2. In Cloudflare, create an R2 Object Read & Write token scoped only to that
   bucket. Do not reuse the OpenTofu state credentials.
3. Generate and retain a strong Restic password independently from the bucket.
   Losing it makes the backups unrecoverable.
4. Store these values in the production Doppler configuration:

   ```dotenv
   RESTIC_REPOSITORY=s3:https://a2dd27ff56de48a73e384881d22e60e2.r2.cloudflarestorage.com/ignite-for-spotify-db-backups
   RESTIC_PASSWORD=<generated-restic-password>
   R2_ACCESS_KEY_ID=<bucket-scoped-access-key>
   R2_SECRET_ACCESS_KEY=<bucket-scoped-secret-key>
   ```

5. Apply the production Compose changes. Run the first backup immediately so
   the backup container can become healthy:

   ```bash
   docker compose --env-file .env -f docker/docker-compose.prod.yml run --rm backup backup-once
   docker compose --env-file .env -f docker/docker-compose.prod.yml up -d backup
   docker inspect ignite-backup --format '{{json .State.Health}}'
   ```

The daemon runs daily at 10:00 UTC. On Sundays it retains 30 daily and 12
monthly snapshots and prunes unreferenced data. The container becomes unhealthy
when its most recent success marker is older than 36 hours. Its logs are
collected by the existing Alloy configuration.

## Inspecting backups

Use the same environment and image as production:

```bash
docker compose --env-file .env -f docker/docker-compose.prod.yml run --rm \
  --entrypoint restic backup snapshots --host ignite-production --tag ignite-database
```

The database includes Spotify refresh tokens. Never print, commit, or upload an
unencrypted database or SQL dump outside the restricted cutover directory.

## Isolated restore drill

Restore only into a new, empty directory. The restore command refuses `/data`
so it cannot overwrite the live volume.

```bash
restore_root=$(mktemp -d)
chmod 700 "$restore_root"
docker compose --env-file .env -f docker/docker-compose.prod.yml run --rm \
  --volume "$restore_root:/restore" backup restore /restore
sqlite3 "$restore_root/ignite.db" "PRAGMA integrity_check;"
sqlite3 "$restore_root/ignite.db" \
  "SELECT COUNT(*) FROM songs_fts WHERE songs_fts MATCH 'test*';"
```

Record the snapshot ID, integrity result, row counts, and drill date. Perform a
drill immediately after cutover and quarterly thereafter. Remove the isolated
plaintext restore after recording non-sensitive results.

## Disaster recovery

1. Keep the backend stopped; do not restore over a running database.
2. Resolve the exact `ignite-data` volume from the existing backend container:

   ```bash
   docker inspect ignite-backend --format \
     '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}'
   ```

3. Restore and validate into an isolated directory using the procedure above.
4. Quarantine the damaged `ignite.db`, `ignite.db-wal`, and `ignite.db-shm`
   files instead of deleting them.
5. Copy the validated restored file into the volume and set ownership using the
   backend image:

   ```bash
   data_volume=<validated-volume-name>
   restore_root=<validated-restore-directory>
   docker run --rm --user root \
     --volume "$data_volume:/app/data" \
     --volume "$restore_root:/restore:ro" \
     --entrypoint sh ghcr.io/scowalt/ignite-for-spotify-2/backend:latest \
     -c 'cp /restore/ignite.db /app/data/ignite.db && chown ignite:ignite /app/data/ignite.db'
   ```

6. Start the backend and require `/health/ready`, stats, filtered search, FTS,
   session lookup, and a controlled write to pass before restoring traffic.

