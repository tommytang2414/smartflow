"""Mac-only shared model slot; original command, streams and exit status retained."""
from __future__ import annotations

import argparse
import fcntl
import os
import signal
import subprocess
import time
from pathlib import Path


LOCK = Path.home() / "Library/Application Support/SmartFlow/gpt-model.lock"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-seconds", type=int, default=600)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not 0 <= args.wait_seconds <= 7200:
        raise SystemExit(64)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a+b") as stream:
        deadline = time.monotonic() + args.wait_seconds
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    # No model has started. The caller keeps its normal explicit
                    # failed/deferred receipt; never emit fake Codex JSON success.
                    raise SystemExit(75)
                time.sleep(0.25)
        # Child stays in this process group, and inherits the lock handle. A
        # SIGKILL of this wrapper cannot release the slot while Codex survives.
        child = subprocess.Popen(command, pass_fds=(stream.fileno(),))

        def forward(signum, _frame):
            if child.poll() is None:
                child.send_signal(signum)

        signal.signal(signal.SIGTERM, forward)
        signal.signal(signal.SIGINT, forward)
        code = child.wait()
        # Do not unlink the shared lock inode, including after errors.
        raise SystemExit(code if code >= 0 else 128 - code)


if __name__ == "__main__":
    main()
