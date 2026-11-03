import sys
import unittest

from deployment_process import OperationFailed, run


class DeploymentProcessTests(unittest.TestCase):
    def test_output_is_bounded_and_failed_command_details_are_not_disclosed(self):
        self.assertEqual(run([sys.executable, '-c', 'print("ok", end="")']), b'ok')
        for code in ['print("x"*100000)', 'import sys; print("fixture-private", file=sys.stderr); raise SystemExit(1)']:
            with self.assertRaises(OperationFailed) as failure:
                run([sys.executable, '-c', code], limit=1024)
            self.assertNotIn('fixture-private', str(failure.exception))

    def test_timeout_terminates_the_owned_process_group(self):
        with self.assertRaises(OperationFailed) as failure:
            run([sys.executable, '-c', 'import time; time.sleep(60)'], timeout=0.1)
        self.assertEqual(str(failure.exception), 'command_timeout')


if __name__ == '__main__':
    unittest.main()
