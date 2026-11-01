#!/bin/sh
set -eu

: "${RESTIC_REPOSITORY:?RESTIC_REPOSITORY is required}"
: "${RESTIC_PASSWORD:?RESTIC_PASSWORD is required}"

database_path=${DATABASE_PATH:-/data/ignite.db}
state_directory=${BACKUP_STATE_DIRECTORY:-/state}
backup_host=${BACKUP_HOST:-ignite-production}
backup_tag=${BACKUP_TAG:-ignite-database}

if [ ! -f "$database_path" ]; then
    echo "database backup failed: $database_path does not exist" >&2
    exit 1
fi

mkdir -p "$state_directory"
snapshot_directory=$(mktemp -d /tmp/ignite-backup.XXXXXX)
snapshot_path=$snapshot_directory/ignite.db

cleanup() {
    rm -f "$snapshot_path"
    rmdir "$snapshot_directory" 2>/dev/null || true
}

trap cleanup EXIT HUP INT TERM
umask 077

echo "creating consistent SQLite snapshot"
sqlite3 -cmd ".timeout 60000" "$database_path" ".backup '$snapshot_path'"

quick_check=$(sqlite3 "$snapshot_path" "PRAGMA quick_check;")

if [ "$quick_check" != "ok" ]; then
    echo "database backup failed quick_check: $quick_check" >&2
    exit 1
fi

if ! restic cat config >/dev/null 2>&1; then
    echo "initializing backup repository"
    restic init
fi

echo "uploading encrypted database snapshot"
restic backup \
    --host "$backup_host" \
    --tag "$backup_tag" \
    --stdin \
    --stdin-filename ignite.db < "$snapshot_path"

day_of_week=$(date -u +%u)

if [ "$day_of_week" = "7" ]; then
    echo "applying backup retention policy"
    restic forget \
        --host "$backup_host" \
        --tag "$backup_tag" \
        --keep-daily 30 \
        --keep-monthly 12 \
        --prune
fi

completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
marker_path=$state_directory/last-success
temporary_marker=$state_directory/.last-success.tmp
printf '%s\n' "$completed_at" > "$temporary_marker"
mv "$temporary_marker" "$marker_path"
echo "database backup completed at $completed_at"

