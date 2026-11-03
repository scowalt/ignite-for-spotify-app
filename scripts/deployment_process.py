import os
import selectors
import signal
import subprocess
import time


class OperationFailed(RuntimeError):
    pass


def run(command, *, env=None, timeout=90, limit=2 * 1024**2):
    deadline = time.monotonic() + timeout
    output = bytearray()
    completed = False
    with subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, start_new_session=True) as process:
        try:
            with selectors.DefaultSelector() as streams:
                streams.register(process.stdout, selectors.EVENT_READ, True)
                streams.register(process.stderr, selectors.EVENT_READ, False)
                while streams.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise OperationFailed('command_timeout')
                    for key, _ in streams.select(min(remaining, 1)):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            streams.unregister(key.fileobj)
                        elif key.data:
                            output.extend(chunk)
                            if len(output) > limit:
                                raise OperationFailed('command_output_bound')
            if process.wait(timeout=max(0.1, deadline - time.monotonic())):
                raise OperationFailed('command_failed')
            completed = True
            return bytes(output)
        except subprocess.TimeoutExpired:
            raise OperationFailed('command_timeout') from None
        finally:
            if not completed:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
