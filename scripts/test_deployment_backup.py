import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
import uuid

from deployment_backup import BackupTool, Stop

IMAGE = os.environ.get('IGNITE_BACKUP_FIXTURE_IMAGE')


@unittest.skipUnless(IMAGE, 'Set IGNITE_BACKUP_FIXTURE_IMAGE to the local credential-free backup test image.')
class DeploymentBackupTests(unittest.TestCase):
    def test_missing_repository_is_never_initialized_and_owned_tool_is_removed(self):
        with tempfile.TemporaryDirectory(prefix='ignite-missing-repo-') as directory:
            root = Path(directory)
            for name in ['data', 'repository', 'scratch']:
                (root / name).mkdir(mode=0o700)
            env = {**os.environ, 'RESTIC_REPOSITORY': '/repository', 'RESTIC_PASSWORD': 'fixture-only'}
            tool = BackupTool(['docker'], IMAGE, root / 'scratch', env, 'fixture-' + uuid.uuid4().hex,
                              'type=bind,src=' + str(root / 'data') + ',dst=/data,readonly', network='none',
                              extra_mounts=['type=bind,src=' + str(root / 'repository') + ',dst=/repository'])
            try:
                tool.start()
                with self.assertRaises(Stop):
                    tool.snapshot_restore()
            finally:
                tool.close()
            self.assertFalse((root / 'repository/config').exists())
            self.assertFalse((root / 'scratch').exists())

    def test_wal_database_is_backed_up_exactly_restored_and_cleaned_without_live_mutation(self):
        with tempfile.TemporaryDirectory(prefix='ignite-recovery-fixture-') as directory:
            root = Path(directory)
            data, repository, scratch = [root / name for name in ['data', 'repository', 'scratch']]
            for path in [data, repository, scratch]:
                path.mkdir(mode=0o700)
            writer = sqlite3.connect(data / 'ignite.db')
            self.addCleanup(writer.close)
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('create table fixture(value integer)')
            writer.execute('insert into fixture values(42)')
            writer.commit()
            env = {**os.environ, 'RESTIC_REPOSITORY': '/repository', 'RESTIC_PASSWORD': 'fixture-only'}
            initialized = subprocess.run(['docker', 'run', '--rm', '--network', 'none',
                '--mount', 'type=bind,src=' + str(repository) + ',dst=/repository',
                '--env', 'RESTIC_REPOSITORY', '--env', 'RESTIC_PASSWORD',
                '--entrypoint', 'restic', IMAGE, '--no-cache', 'init'],
                env=env, capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(initialized.returncode, 0)
            tool = BackupTool(['docker'], IMAGE, scratch, env, 'fixture-' + uuid.uuid4().hex,
                              'type=bind,src=' + str(data) + ',dst=/data,readonly', network='none',
                              extra_mounts=['type=bind,src=' + str(repository) + ',dst=/repository'])
            try:
                tool.start()
                result = tool.snapshot_restore()
                self.assertTrue(result['restore_verified'] and result['integrity_ok'])
                self.assertRegex(result['snapshot_id'], r'^[a-f0-9]{64}$')
                self.assertGreater(result['snapshot_bytes'], 0)
                self.assertLessEqual(result['scratch_bytes'], 1024**3)
            finally:
                tool.close()
            self.assertFalse(scratch.exists())
            self.assertEqual(writer.execute('select value from fixture').fetchall(), [(42,)])
            writer.close()

    def test_fresh_operator_instance_can_clean_only_the_owned_interrupted_tool(self):
        with tempfile.TemporaryDirectory(prefix='ignite-interrupted-backup-') as directory:
            root = Path(directory)
            for name in ['data', 'repository', 'scratch']:
                (root / name).mkdir(mode=0o700)
            env = {**os.environ, 'RESTIC_REPOSITORY': '/repository', 'RESTIC_PASSWORD': 'fixture-only'}
            operation = 'fixture-' + uuid.uuid4().hex
            args = (['docker'], IMAGE, root / 'scratch', env, operation,
                    'type=bind,src=' + str(root / 'data') + ',dst=/data,readonly')
            settings = {'network': 'none', 'extra_mounts': ['type=bind,src=' + str(root / 'repository') + ',dst=/repository']}
            original = BackupTool(*args, **settings)
            try:
                original.start()
                original.exec(['sh', '-ec', 'printf fixture > /scratch/snapshot/owned'])
                resumed = BackupTool(*args, **settings)
                resumed.close()
                resumed.close()
                self.assertFalse((root / 'scratch').exists())
            finally:
                original.close()

    def test_resumed_cleanup_refuses_a_tool_with_a_different_scratch_mount(self):
        with tempfile.TemporaryDirectory(prefix='ignite-cleanup-identity-') as directory:
            root = Path(directory)
            for name in ['data', 'scratch', 'different']:
                (root / name).mkdir(mode=0o700)
            env = {**os.environ, 'RESTIC_REPOSITORY': '/repository', 'RESTIC_PASSWORD': 'fixture-only'}
            operation = 'fixture-' + uuid.uuid4().hex
            source = 'type=bind,src=' + str(root / 'data') + ',dst=/data,readonly'
            original = BackupTool(['docker'], IMAGE, root / 'scratch', env, operation, source, network='none')
            try:
                original.start()
                resumed = BackupTool(['docker'], IMAGE, root / 'different', env, operation, source, network='none')
                with self.assertRaises(Stop):
                    resumed.close()
                self.assertEqual(original.exec(['true']), '')
            finally:
                original.close()


if __name__ == '__main__':
    unittest.main()
