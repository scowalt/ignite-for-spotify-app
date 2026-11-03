import os
import selectors
import signal
import subprocess
import time


class OperationFailed(RuntimeError):
    pass


def run(command, *, env=None, timeout=90, limit=2 * 1024**2, input=None):
    if input is not None and (not isinstance(input, bytes) or len(input) > 2 * 1024**2):
        raise OperationFailed('command_input_bound')
    deadline = time.monotonic() + timeout
    output = bytearray()
    completed = False
    position = 0
    with subprocess.Popen(command, env=env, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True) as process:
        try:
            with selectors.DefaultSelector() as streams:
                streams.register(process.stdout, selectors.EVENT_READ, 'stdout')
                streams.register(process.stderr, selectors.EVENT_READ, 'stderr')
                if input:
                    os.set_blocking(process.stdin.fileno(), False)
                    streams.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
                elif input is not None:
                    process.stdin.close()
                while streams.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise OperationFailed('command_timeout')
                    for key, _ in streams.select(min(remaining, 1)):
                        if key.data == 'stdin':
                            try:
                                position += os.write(key.fileobj.fileno(), memoryview(input)[position:position + 65536])
                            except BlockingIOError:
                                continue
                            except BrokenPipeError:
                                raise OperationFailed('command_input_incomplete') from None
                            if position == len(input):
                                streams.unregister(key.fileobj)
                                process.stdin.close()
                            continue
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            streams.unregister(key.fileobj)
                        elif key.data == 'stdout':
                            output.extend(chunk)
                            if len(output) > limit:
                                raise OperationFailed('command_output_bound')
            if process.wait(timeout=max(0.1, deadline - time.monotonic())):
                raise OperationFailed('command_failed')
            if input is not None and position != len(input):
                raise OperationFailed('command_input_incomplete')
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
