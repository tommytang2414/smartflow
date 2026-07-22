"""Create and restore a disposable SQLite snapshot, then verify exact recovery."""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smartflow.db.snapshots import rehearse_snapshot_restore


def verify_s3_snapshot(bucket: str, key: str) -> dict:
    aws_command = shutil.which("aws") or shutil.which("aws.cmd")
    if not aws_command:
        raise RuntimeError("AWS CLI was not found on PATH")
    with tempfile.TemporaryDirectory(prefix="smartflow-s3-restore-") as temporary_directory:
        download_path = Path(temporary_directory) / "source.db"
        subprocess.run(
            [
                aws_command,
                "s3",
                "cp",
                f"s3://{bucket}/{key}",
                str(download_path),
                "--only-show-errors",
            ],
            check=True,
        )
        result = rehearse_snapshot_restore(download_path)
        result["source"] = f"s3://{bucket}/{key}"
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path, nargs="?")
    parser.add_argument("--s3-bucket")
    parser.add_argument("--s3-key")
    args = parser.parse_args()
    if args.database and not args.s3_bucket and not args.s3_key:
        result = rehearse_snapshot_restore(args.database)
    elif not args.database and args.s3_bucket and args.s3_key:
        result = verify_s3_snapshot(args.s3_bucket, args.s3_key)
    else:
        parser.error("provide a database path or both --s3-bucket and --s3-key")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
