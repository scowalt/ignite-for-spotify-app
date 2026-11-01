# Turso Cloud to local SQLite cutover

This runbook preserves `songs`, Spotify IDs, `user_sessions`, and
`scraping_jobs`. It uses a restricted plaintext staging directory; all files in
that directory contain secrets and must be handled accordingly.

## Preconditions

- Temporarily upgrade Turso if quota enforcement prevents exports or validation.
- Install authenticated `turso`, `sqlite3`, Docker, and Docker Compose clients on
  the VPS.
- Build and publish the new backend and backup images under immutable commit-SHA
  tags before starting. Leave the GitHub repository variable
  `LOCAL_SQLITE_CUTOVER_COMPLETE` unset or `false`; this prevents the deployment
  workflow from moving `latest` and triggering Watchtower before the database is
  staged.
- Configure and test the R2 repository described in
  [SQLite backup and recovery](sqlite-backup-recovery.md).
- Capture the old backend image digest, current Compose files, environment, and
  exact data volume. Disable Watchtower during the maintenance window.

```bash
old_backend_image=$(docker inspect ignite-backend --format '{{.Image}}')
data_volume=$(docker inspect ignite-backend --format \
  '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}')
test -n "$old_backend_image"
test -n "$data_volume"
cutover_root=$(mktemp -d)
chmod 700 "$cutover_root"
```

Do not continue unless the resolved volume is the mount currently used at
`/app/data` by `ignite-backend`.

## Rehearsal

Export, import, rebuild the FTS index from its authoritative `songs` content
table, and validate the candidate. The application secret has the form
`https://<database-host>/v2/pipeline;<database-token>`; the authenticated Turso
`/dump` endpoint is the non-interactive equivalent of the CLI `.dump` workflow.
Do not print either part of the secret.

```bash
umask 077
pipeline_url=${TURSO_CONNECTION_STRING%%;*}
database_token=${TURSO_CONNECTION_STRING#*;}
database_url=${pipeline_url%/v2/pipeline}
curl --fail --silent --show-error --location \
  "$database_url/dump" \
  --header "Authorization: Bearer $database_token" \
  --output "$cutover_root/rehearsal.sql"

# Turso's HTTP dump contains virtual-table internals that must not be imported.
# Remove that section and recreate FTS from the authoritative songs table.
awk '
  BEGIN { skip = 0 }
  /^PRAGMA writable_schema=ON;/ { skip = 1; next }
  skip && /^DELETE FROM sqlite_sequence;/ { skip = 0 }
  /^PRAGMA writable_schema=OFF;/ { next }
  !skip { print }
' "$cutover_root/rehearsal.sql" | sqlite3 "$cutover_root/rehearsal.db"

sqlite3 "$cutover_root/rehearsal.db" \
  "CREATE VIRTUAL TABLE songs_fts USING fts5(artist, title, album, content='songs', content_rowid='id');
   CREATE TRIGGER songs_ai AFTER INSERT ON songs BEGIN
     INSERT INTO songs_fts(rowid, artist, title, album) VALUES (new.id, new.artist, new.title, new.album);
   END;
   CREATE TRIGGER songs_ad AFTER DELETE ON songs BEGIN
     INSERT INTO songs_fts(songs_fts, rowid, artist, title, album)
       VALUES ('delete', old.id, old.artist, old.title, old.album);
   END;
   CREATE TRIGGER songs_au AFTER UPDATE ON songs BEGIN
     INSERT INTO songs_fts(songs_fts, rowid, artist, title, album)
       VALUES ('delete', old.id, old.artist, old.title, old.album);
     INSERT INTO songs_fts(rowid, artist, title, album)
       VALUES (new.id, new.artist, new.title, new.album);
   END;
   INSERT INTO songs_fts(songs_fts) VALUES('rebuild');
   PRAGMA wal_checkpoint(TRUNCATE);"
sqlite3 "$cutover_root/rehearsal.db" "PRAGMA integrity_check;"
sqlite3 -header -column "$cutover_root/rehearsal.db" <<'SQL'
SELECT 'songs' AS metric, COUNT(*) AS value FROM songs
UNION ALL SELECT 'songs_with_spotify_id', COUNT(*) FROM songs WHERE spotify_track_id IS NOT NULL
UNION ALL SELECT 'user_sessions', COUNT(*) FROM user_sessions
UNION ALL SELECT 'scraping_jobs', COUNT(*) FROM scraping_jobs;
SELECT type, name FROM sqlite_master
WHERE name IN ('songs', 'user_sessions', 'scraping_jobs', 'songs_fts', 'songs_ai', 'songs_ad', 'songs_au')
ORDER BY type, name;
SQL
```

Run the same aggregate queries against Turso and require exact parity. Also
compare maximum IDs and timestamps, then run the new backend image privately
against the rehearsal file and exercise readiness, stats, pagination, filtering,
FTS, session lookup, playlist matching, and one disposable write.

## Final maintenance window

1. Stop the backend and Watchtower. Caddy may remain running and return a
   temporary unavailable response.
2. Repeat the tested authenticated export, filtered import, FTS rebuild,
   integrity check, schema check, and source/target aggregate comparisons into
   `final.db`. Because the backend is stopped, this is the authoritative final
   Turso state.
3. Quarantine any existing local SQLite files, then install the final database:

   ```bash
   docker stop ignite-watchtower ignite-backend
   docker run --rm --user root \
     --volume "$data_volume:/app/data" \
     --volume "$cutover_root:/staging:ro" \
     --entrypoint sh "$NEW_BACKEND_IMAGE" -c '
       stamp=$(date -u +%Y%m%dT%H%M%SZ)
       for path in /app/data/ignite.db /app/data/ignite.db-wal /app/data/ignite.db-shm; do
         if [ -e "$path" ]; then mv "$path" "$path.pre-turso-cutover-$stamp"; fi
       done
       cp /staging/final.db /app/data/ignite.db
       chown ignite:ignite /app/data/ignite.db
       chmod 600 /app/data/ignite.db
     '
   ```

4. Set `BACKEND_IMAGE` and `BACKUP_IMAGE` to their new immutable tags, remove
   `TURSO_CONNECTION_STRING`, and apply production Compose.
5. Require the backend health check and the rehearsal smoke tests to pass.
6. Run `backup backup-once`, perform an isolated restore, and compare its counts
   to the live local database.
7. Restart Watchtower and reopen traffic only after every gate passes.
8. Set the GitHub repository variable `LOCAL_SQLITE_CUTOVER_COMPLETE=true` and
   manually dispatch the deployment workflow once. This publishes the verified
   images as `latest` and re-enables normal Watchtower deployments.

If any gate fails before traffic reopens, stop the new backend and restore the
captured old image, old Compose environment, and Turso connection. Once local
writes are accepted, Turso is stale; recover from local/R2 snapshots and fix
forward instead of reverting directly.

## Retirement gate

Keep Turso inaccessible to the application for seven days. Delete it only after
seven successful daily backups, stable readiness and application behavior, and
a documented restore drill. Then revoke its tokens, remove its Doppler secret,
cancel the temporary upgrade, and delete the Turso database.

Remove plaintext artifacts after cutover. On storage where secure overwrite is
supported, use `shred -u` for the SQL dumps and database copies before removing
the restricted staging directory; otherwise destroy the encrypted temporary
volume or follow the host provider's secure-deletion procedure.
