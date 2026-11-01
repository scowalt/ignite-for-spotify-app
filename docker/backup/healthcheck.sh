#!/bin/sh
set -eu

marker=${BACKUP_STATE_DIRECTORY:-/state}/last-success

if [ ! -f "$marker" ]; then
    echo "no successful database backup has been recorded" >&2
    exit 1
fi

now=$(date -u +%s)
last_success=$(stat -c %Y "$marker")
maximum_age=${BACKUP_MAX_AGE_SECONDS:-129600}
age=$((now - last_success))

if [ "$age" -gt "$maximum_age" ]; then
    echo "last successful database backup is $age seconds old" >&2
    exit 1
fi

