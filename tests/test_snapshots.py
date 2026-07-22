import sqlite3
import tempfile
import unittest
from pathlib import Path

from smartflow.db.snapshots import (
    create_sqlite_snapshot,
    rehearse_snapshot_restore,
    restore_sqlite_snapshot,
)


class SQLiteSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.source = self.directory / "source.db"
        connection = sqlite3.connect(self.source)
        try:
            connection.execute("CREATE TABLE evidence (id INTEGER PRIMARY KEY, value TEXT)")
            connection.executemany(
                "INSERT INTO evidence (value) VALUES (?)",
                [("alpha",), ("beta",), ("gamma",)],
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_snapshot_restore_is_logically_and_byte_identical(self):
        result = rehearse_snapshot_restore(self.source)

        self.assertEqual(result["tables_verified"], 1)
        self.assertEqual(result["rows_verified"], 3)
        self.assertEqual(result["quick_check"], "ok")
        self.assertEqual(result["snapshot_sha256"], result["restore_sha256"])
        self.assertTrue(result["byte_identical_restore"])

    def test_snapshot_and_restore_refuse_to_overwrite_targets(self):
        snapshot = self.directory / "snapshot.db"
        restored = self.directory / "restored.db"
        create_sqlite_snapshot(self.source, snapshot)
        restore_sqlite_snapshot(snapshot, restored)

        with self.assertRaises(FileExistsError):
            create_sqlite_snapshot(self.source, snapshot)
        with self.assertRaises(FileExistsError):
            restore_sqlite_snapshot(snapshot, restored)


if __name__ == "__main__":
    unittest.main()
