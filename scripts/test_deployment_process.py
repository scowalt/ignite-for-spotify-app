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

    def test_bounded_input_is_delivered_while_output_streams_are_drained(self):
        payload = b'fixture-data-' * 100000
        code = 'import sys; sys.stderr.write("x"*100000); sys.stderr.flush(); sys.stdout.buffer.write(sys.stdin.buffer.read())'
        self.assertEqual(run([sys.executable, '-c', code], input=payload), payload)
        self.assertEqual(run([sys.executable, '-c', 'import sys; print(len(sys.stdin.buffer.read()), end="")'], input=b''), b'0')

    def test_oversized_or_unconsumed_input_is_rejected_without_disclosure(self):
        with self.assertRaises(OperationFailed) as oversized:
            run([sys.executable, '-c', 'pass'], input=b'x' * (2 * 1024**2 + 1))
        self.assertEqual(str(oversized.exception), 'command_input_bound')
        with self.assertRaises(OperationFailed) as closed:
            run([sys.executable, '-c', 'pass'], input=b'fixture-private' * 100000)
        self.assertNotIn('fixture-private', str(closed.exception))

    def test_input_backpressure_does_not_defeat_the_deadline(self):
        with self.assertRaises(OperationFailed) as failure:
            run([sys.executable, '-c', 'import time; time.sleep(60)'], input=b'x' * 1024**2, timeout=0.1)
        self.assertEqual(str(failure.exception), 'command_timeout')

    def test_timeout_terminates_the_owned_process_group(self):
        with self.assertRaises(OperationFailed) as failure:
            run([sys.executable, '-c', 'import time; time.sleep(60)'], timeout=0.1)
        self.assertEqual(str(failure.exception), 'command_timeout')


if __name__ == '__main__':
    unittest.main()
