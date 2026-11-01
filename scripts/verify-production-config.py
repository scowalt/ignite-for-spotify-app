import argparse
import json
import re
import sys

PROJECT = "ignite-for-spotify"
IMAGE_PREFIX = "ghcr.io/scowalt/ignite-for-spotify-app/"
LEGACY_PREFIX = "ghcr.io/scowalt/ignite-for-spotify-2/"
VOLUMES = ("ignite-data", "backup-state", "caddy-data", "caddy-config")


def validate(config, require_digests=False, rollback=False):
    errors = []
    if config.get("name") != PROJECT:
        errors.append(
            "Unexpected Compose project; refusing a different volume namespace."
        )
    for volume in VOLUMES:
        definition = config.get("volumes", {}).get(volume, {})
        if definition.get("name") != f"{PROJECT}_{volume}":
            errors.append(f"Unexpected physical volume for {volume}.")
        if definition.get("driver_opts"):
            errors.append(f"Unexpected driver options for {volume}.")
    services = config.get("services", {})
    for name in ("backend", "frontend", "backup"):
        service = services.get(name, {})
        image = service.get("image", "")
        suffix = (
            r"@sha256:[0-9a-f]{64}"
            if require_digests or rollback
            else r"(?::[A-Za-z0-9_.-]+|@sha256:[0-9a-f]{64})"
        )
        prefix = LEGACY_PREFIX if rollback else IMAGE_PREFIX
        if not re.fullmatch(re.escape(prefix + name) + suffix, image):
            errors.append(f"Unexpected {name} image namespace or digest format.")
        if service.get("container_name") != f"ignite-{name}":
            errors.append(f"Unexpected container identity for {name}.")
    expected_mounts = {
        "backend": {("ignite-data", "/app/data")},
        "backup": {("ignite-data", "/data"), ("backup-state", "/state")},
    }
    for service, expected in expected_mounts.items():
        mounts = services.get(service, {}).get("volumes", [])
        actual = {
            (m.get("source"), m.get("target"))
            for m in mounts
            if m.get("type") == "volume" and not m.get("read_only", False)
        }
        if actual != expected or len(mounts) != len(expected):
            errors.append(f"Unexpected data/state mounts for {service}.")
    backend = services.get("backend", {})
    environment = backend.get("environment", {})
    for key, expected in {
        "Database__RequireExisting": "true",
        "ConnectionStrings__Database": "Data Source=/app/data/ignite.db;Default Timeout=60",
        "ConnectionStrings__Hangfire": "Data Source=/app/data/hangfire.db",
        "ASPNETCORE_URLS": "http://127.0.0.1:5050",
    }.items():
        if environment.get(key) != expected:
            errors.append(f"Unexpected backend setting: {key}.")
    if (
        backend.get("network_mode") != "host"
        or services.get("backup", {}).get("network_mode") != "host"
    ):
        errors.append("Unexpected backend/backup networking.")
    backup = services.get("backup", {}).get("environment", {})
    if (
        backup.get("BACKUP_HOST") != "ignite-production"
        or backup.get("BACKUP_TAG") != "ignite-database"
    ):
        errors.append("Unexpected backup repository identity labels.")
    ports = services.get("frontend", {}).get("ports", [])
    if (
        len(ports) != 1
        or ports[0].get("host_ip") != "127.0.0.1"
        or str(ports[0].get("published")) != "3000"
        or ports[0].get("target") != 80
    ):
        errors.append("Unexpected frontend port exposure.")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-digests", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    try:
        config = json.load(sys.stdin)
        errors = validate(config, args.require_digests, args.rollback)
    except (ValueError, TypeError, AttributeError):
        print(
            "Unable to validate Compose JSON; no configuration values printed.",
            file=sys.stderr,
        )
        return 1
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print("Production Compose identity/mount invariants verified; no services changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
