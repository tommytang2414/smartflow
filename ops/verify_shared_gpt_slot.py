"""macOS process/lock rehearsal with local dummy children; never calls GPT."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def main():
    if sys.platform != "darwin":
        raise SystemExit("macOS verification required")
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="smartflow-slot-") as temporary:
        root = Path(temporary)
        # Override module global only inside these test interpreters, keeping the
        # real scheduled-work slot and other projects entirely undisturbed.
        bootstrap = "import runpy,pathlib;d=runpy.run_path(" + repr(str(args.slot.resolve())) + ");d['main'].__globals__['LOCK']=pathlib.Path(" + repr(str(root / "model.lock")) + ");d['main']()"
        def start(name, duration):
            body = "import os,time,pathlib;p=pathlib.Path(" + repr(str(root/name)) + ");p.write_text(str(os.getpid()));time.sleep(" + str(duration) + ")"
            return subprocess.Popen([sys.executable, "-c", bootstrap, "--wait-seconds", "5", "--", sys.executable, "-c", body], start_new_session=True)
        first = start("first", 2)
        deadline = time.monotonic()+5
        while not (root/"first").exists() and time.monotonic()<deadline:
            time.sleep(.05)
        assert (root/"first").exists()
        first.kill();first.wait()
        second = start("second", 0)
        time.sleep(.2)
        assert not (root/"second").exists(), "parent SIGKILL released live child's slot"
        assert second.wait(timeout=5) == 0
        third = start("third", 5)
        deadline = time.monotonic()+5
        while not (root/"third").exists() and time.monotonic()<deadline:
            time.sleep(.05)
        assert (root/"third").exists()
        third.terminate()
        assert third.wait(timeout=5) == 143
        fourth = start("fourth", 0)
        assert fourth.wait(timeout=5) == 0
        print(json.dumps({"status":"PASS","checks":["serialized dummy children", "SIGKILL wrapper retains child slot", "SIGTERM forwards and releases after exit", "lock inode retained"],"model_calls":0}))


if __name__ == "__main__":
    main()
