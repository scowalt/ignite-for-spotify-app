import re
import subprocess
import sys
from pathlib import PurePosixPath


FORBIDDEN_DIRECTORIES = {
    ".git",
    ".pi",
    ".glitchtip-remediator-home",
    ".venv",
    "__pycache__",
    "node_modules",
    "legacy-state",
    "secrets",
}
FORBIDDEN_FILES = {"auth.json", "controller.toml"}
FORBIDDEN_SUFFIXES = {".zip", ".pem", ".key", ".p12", ".pfx", ".tfstate"}
DATABASE = re.compile(r"\.(?:db|sqlite|sqlite3)(?:[-.].*)?$", re.IGNORECASE)


def rejection_reason(path, mode="100644"):
    parts = PurePosixPath(path).parts
    name = PurePosixPath(path).name.lower()
    if mode not in {"100644", "100755", "120000"}:
        return "submodule or other non-file Git entry"
    if any(part.lower() in FORBIDDEN_DIRECTORIES for part in parts):
        return "runtime, credential or dependency directory"
    if name in FORBIDDEN_FILES:
        return "runtime credential/configuration file"
    if name.startswith(".env") and name != ".env.example":
        return "environment file other than the reviewed example"
    if DATABASE.search(name):
        return "database or database sidecar"
    if PurePosixPath(name).suffix in FORBIDDEN_SUFFIXES or ".tfstate." in name:
        return "archive, key or infrastructure state"
    return None


def main():
    result = subprocess.run(
        ["git", "ls-files", "--stage", "-z"], capture_output=True, check=True
    )
    failures = []
    entries = [entry for entry in result.stdout.split(b"\0") if entry]
    for entry in entries:
        header, raw_path = entry.split(b"\t", 1)
        mode, _, stage = header.decode().split()
        path = raw_path.decode()
        reason = rejection_reason(path, mode)
        if stage != "0":
            reason = "unmerged index entry"
        if reason:
            failures.append((path, reason))
    for path, reason in failures:
        print(f"{path}: {reason}", file=sys.stderr)
    if not entries:
        print("No tracked files to check; stage the candidate first.", file=sys.stderr)
        return 1
    if failures:
        return 1
    print(f"Checked {len(entries)} tracked files for forbidden publication artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
