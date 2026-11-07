import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("check-public-source.py")
SPEC = importlib.util.spec_from_file_location("check_public_source", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PublicSourceTests(unittest.TestCase):
    def test_rejects_runtime_and_database_artifacts(self):
        for path in (
            "backend/hangfire.db-wal", "backend/hangfire.db-shm",
            "data.sqlite-journal", "data.SQLITE3", "data.db.backup",
            ".env", "frontend/.env.production", "function.zip",
            ".glitchtip-remediator-home/anything", "nested/auth.json",
            "config/controller.toml", "infra/local.tfstate.backup",
            "node_modules/package/index.js", "secrets/token", "key.pem",
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(MODULE.rejection_reason(path))

    def test_allows_source_and_reviewed_examples(self):
        for path in (
            ".env.example", ".gitignore", "LICENSE", "backend/DatabaseTests.fs",
            "config/controller.example.toml", "tests/fixtures/github-evidence.json",
            "docs/operations/sqlite-backup-recovery.md",
        ):
            with self.subTest(path=path):
                self.assertIsNone(MODULE.rejection_reason(path))

    def test_allows_symlinks(self):
        self.assertIsNone(MODULE.rejection_reason("source", "120000"))

    def test_applies_path_rules_to_symlinks(self):
        self.assertIsNotNone(MODULE.rejection_reason("secrets/token", "120000"))

    def test_rejects_submodules(self):
        self.assertIsNotNone(MODULE.rejection_reason("source", "160000"))

    def test_checks_index_instead_of_only_working_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            empty = subprocess.run([sys.executable, str(SCRIPT)], cwd=root, capture_output=True)
            self.assertNotEqual(empty.returncode, 0)
            (root / "LICENSE").write_text("fixture")
            subprocess.run(["git", "add", "LICENSE"], cwd=root, check=True)
            clean = subprocess.run([sys.executable, str(SCRIPT)], cwd=root, capture_output=True)
            self.assertEqual(clean.returncode, 0)
            sidecar = root / "hangfire.db-wal"
            sidecar.write_bytes(b"synthetic fixture, not a database")
            subprocess.run(["git", "add", sidecar.name], cwd=root, check=True)
            sidecar.unlink()
            unsafe = subprocess.run([sys.executable, str(SCRIPT)], cwd=root, capture_output=True)
            self.assertNotEqual(unsafe.returncode, 0)
            self.assertIn(b"hangfire.db-wal", unsafe.stderr)


if __name__ == "__main__":
    unittest.main()
