import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ops.manage_v2_shadow import create_shadow_database


class SECShadowCLITests(unittest.TestCase):
    def test_missing_contact_fails_in_child_and_records_auth_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "smartflow-v2-shadow.db"
            create_shadow_database(database_path)
            environment = os.environ.copy()
            environment["SEC_EDGAR_EMAIL"] = ""

            completed = subprocess.run(
                [
                    sys.executable,
                    "ops/run_sec_shadow.py",
                    "--database",
                    str(database_path),
                    "--source",
                    "sec_form4",
                    "--limit",
                    "1",
                    "--timeout-seconds",
                    "10",
                ],
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn('"status": "error"', completed.stdout)
            connection = sqlite3.connect(database_path)
            try:
                outcome = connection.execute(
                    "SELECT status, failure_kind FROM collector_runs_v2"
                ).fetchone()
            finally:
                connection.close()
            self.assertEqual(outcome, ("error", "auth"))


if __name__ == "__main__":
    unittest.main()
