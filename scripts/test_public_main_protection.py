import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_public_main_protection", ROOT / "scripts/verify-public-main-protection.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def snapshot():
    policy = json.loads(MODULE.POLICY_PATH.read_text())
    return {
        key: value if key in {"url", "required_status_checks"} else {"enabled": value}
        for key, value in policy.items()
    }


class MainProtectionTests(unittest.TestCase):
    def test_accepts_current_policy_and_unordered_contexts(self):
        value = snapshot()
        value["required_status_checks"]["contexts"].reverse()
        value["required_status_checks"]["checks"].reverse()
        MODULE.validate(value)

    def test_rejects_missing_or_unbound_required_check(self):
        for change in ("remove", "unbind", "duplicate"):
            with self.subTest(change=change):
                value = snapshot()
                checks = value["required_status_checks"]["checks"]
                if change == "remove":
                    checks.pop()
                elif change == "unbind":
                    checks[1]["app_id"] = None
                else:
                    checks.append(copy.deepcopy(checks[1]))
                with self.assertRaises(ValueError):
                    MODULE.validate(value)

    def test_rejects_flag_drift_and_non_boolean_values(self):
        for key, original in snapshot().items():
            if key in {"url", "required_status_checks"}:
                continue
            for replacement in (not original["enabled"], int(original["enabled"])):
                with self.subTest(key=key, replacement=replacement):
                    value = snapshot()
                    value[key]["enabled"] = replacement
                    with self.assertRaises(ValueError):
                        MODULE.validate(value)

    def test_rejects_old_repository_and_new_review_policy(self):
        value = snapshot()
        value["url"] = value["url"].replace(
            "ignite-for-spotify-app", "ignite-for-spotify-2"
        )
        with self.assertRaises(ValueError):
            MODULE.validate(value)
        value = snapshot()
        value["required_pull_request_reviews"] = {"required_approving_review_count": 1}
        with self.assertRaises(ValueError):
            MODULE.validate(value)


if __name__ == "__main__":
    unittest.main()
