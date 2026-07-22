import hashlib
import tempfile
import unittest
from pathlib import Path

from ops.manage_v2_shadow import create_shadow_database, verify_shadow_database
from smartflow.db.v2_schema import V2_TABLES


class V2ShadowDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_create_publishes_empty_wal_database_and_verify_is_read_only(self):
        database_path = self.directory / "smartflow-v2-shadow.db"

        created = create_shadow_database(database_path)
        before_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()
        verified = verify_shadow_database(database_path)
        after_hash = hashlib.sha256(database_path.read_bytes()).hexdigest()

        self.assertTrue(created["created"])
        self.assertEqual(created["journal_mode"], "wal")
        self.assertEqual(created["foreign_keys"], "on")
        self.assertEqual(created["quick_check"], "ok")
        self.assertEqual(set(created["tables"]), V2_TABLES)
        self.assertTrue(all(count == 0 for count in created["row_counts"].values()))
        self.assertEqual(verified["tables"], created["tables"])
        self.assertEqual(before_hash, after_hash)

    def test_create_refuses_existing_database(self):
        database_path = self.directory / "smartflow-v2-shadow.db"
        database_path.write_bytes(b"existing evidence")

        with self.assertRaises(FileExistsError):
            create_shadow_database(database_path)

        self.assertEqual(database_path.read_bytes(), b"existing evidence")

    def test_create_and_verify_refuse_legacy_database_name(self):
        legacy_path = self.directory / "smartflow.db"

        with self.assertRaises(ValueError):
            create_shadow_database(legacy_path)
        with self.assertRaises(ValueError):
            verify_shadow_database(legacy_path)


if __name__ == "__main__":
    unittest.main()
