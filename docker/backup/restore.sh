#!/bin/sh
set -eu

: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required}"

restore_directory=${1:-/restore}
backup_host=${BACKUP_HOST:-ignite-production}
backup_tag=${BACKUP_TAG:-ignite-database}

if [ "$restore_directory" = "/data" ]; then
    echo "refusing to restore directly over the live database volume" >&2
    exit 1
fi

mkdir -p "$restore_directory"

if [ -n "$(find "$restore_directory" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    echo "restore directory must be empty: $restore_directory" >&2
    exit 1
fi

umask 077
restic restore latest \
    --host "$backup_host" \
    --tag "$backup_tag" \
    --target "$restore_directory"

restored_database=$restore_directory/ignite.db

if [ ! -f "$restored_database" ]; then
    echo "restore did not produce $restored_database" >&2
    exit 1
fi

integrity_check=$(sqlite3 "$restored_database" "PRAGMA integrity_check;")

if [ "$integrity_check" != "ok" ]; then
    echo "restored database failed integrity_check: $integrity_check" >&2
    exit 1
fi

sqlite3 -header -column "$restored_database" <<'SQL'
SELECT 'songs' AS table_name, COUNT(*) AS row_count FROM songs
UNION ALL
SELECT 'user_sessions', COUNT(*) FROM user_sessions
UNION ALL
SELECT 'scraping_jobs', COUNT(*) FROM scraping_jobs;
SQL

echo "database restored and verified at $restored_database"

