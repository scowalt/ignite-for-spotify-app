import base64
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "frontend_notices", Path(__file__).with_name("collect-frontend-notices.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FrontendNoticeTests(unittest.TestCase):
    def test_uses_exact_source_commit_from_registry_provenance(self):
        statement = {
            "predicateType": "https://slsa.dev/provenance/v1",
            "predicate": {
                "buildDefinition": {
                    "resolvedDependencies": [
                        {
                            "uri": "git+https://github.com/example/library@refs/heads/main",
                            "digest": {"gitCommit": "a" * 40},
                        }
                    ]
                }
            },
        }
        envelope = {
            "attestations": [
                {
                    "bundle": {
                        "dsseEnvelope": {
                            "payload": base64.b64encode(
                                json.dumps(statement).encode()
                            ).decode()
                        }
                    }
                }
            ]
        }
        metadata = {
            "repository": {"url": "git+https://github.com/example/library.git"},
            "dist": {"attestations": {"url": "https://registry.npmjs.org/fixture"}},
        }
        with patch.object(MODULE, "registry_json", return_value=envelope):
            self.assertEqual(
                MODULE.source_reference("example", "1.0", metadata),
                ("example/library", "a" * 40),
            )

    def test_refuses_credential_bearing_or_non_registry_metadata_urls(self):
        for url in (
            "https://user:fixture@registry.npmjs.org/example",
            "https://example.invalid/metadata",
            "http://registry.npmjs.org/example",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                MODULE.registry_json(url)

    def test_pinned_signalr_source_is_version_specific(self):
        self.assertEqual(
            MODULE.source_reference("@microsoft/signalr", "8.0.29", {}),
            ("dotnet/aspnetcore", "03ef277b368eb3b02122ca62f97d155845cfd5fa"),
        )
        self.assertIsNone(
            MODULE.source_reference("@microsoft/signalr", "other-version", {})
        )


if __name__ == "__main__":
    unittest.main()
