import json
import sys
from pathlib import Path

POLICY_PATH = (
    Path(__file__).resolve().parents[1] / "infra/public-source/main-protection.json"
)


def validate(snapshot):
    if not isinstance(snapshot, dict):
        raise TypeError("Protection snapshot must be an object.")
    expected = json.loads(POLICY_PATH.read_text())
    if snapshot.get("required_pull_request_reviews") is not None:
        raise ValueError("Review requirements changed; obtain a new protection review.")
    if snapshot.get("restrictions") is not None:
        raise ValueError("Push restrictions changed; obtain a new protection review.")
    actual = {"url": snapshot["url"]}
    for key in expected.keys() - {"url", "required_status_checks"}:
        value = snapshot[key]["enabled"]
        if type(value) is not bool:
            raise ValueError("Protection flags must be booleans.")
        actual[key] = value
    checks = snapshot["required_status_checks"]
    if type(checks["strict"]) is not bool:
        raise ValueError("Status-check strictness must be a boolean.")
    actual["required_status_checks"] = {
        "strict": checks["strict"],
        "contexts": sorted(checks["contexts"]),
        "checks": sorted(checks["checks"], key=lambda check: check["context"]),
    }
    if actual != expected:
        raise ValueError("Main protection differs from the reviewed policy.")


def main():
    try:
        validate(json.load(sys.stdin))
    except (ValueError, KeyError, TypeError):
        print(
            "Main-protection verification failed; inspect privately before proceeding.",
            file=sys.stderr,
        )
        return 1
    print("Main protection matches the reviewed policy, including check app bindings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
