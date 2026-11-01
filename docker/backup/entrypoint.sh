#!/bin/sh
set -eu

command=${1:-daemon}

case "$command" in
    daemon)
        mkdir -p "${BACKUP_STATE_DIRECTORY:-/state}"

        if [ "${BACKUP_ON_START:-false}" = "true" ]; then
            /usr/local/bin/backup-database
        fi

        exec crond -f -l 2
        ;;
    backup-once)
        exec /usr/local/bin/backup-database
        ;;
    restore)
        shift
        exec /usr/local/bin/restore-database "${1:-/restore}"
        ;;
    *)
        exec "$@"
        ;;
esac

