import sqlite3
import tempfile
import unittest
from pathlib import Path

from ops.manage_v2_shadow import create_shadow_database
from smartflow.db.v2_engine import open_v2_shadow_engine


class V2EngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_opens_only_verified_v2_wal_database(self):
        database_path = self.directory / "smartflow-v2-shadow.db"
        create_shadow_database(database_path)

        engine = open_v2_shadow_engine(database_path)
        try:
            with engine.connect() as connection:
                self.assertEqual(connection.exec_driver_sql("PRAGMA foreign_keys").scalar(), 1)
                self.assertEqual(connection.exec_driver_sql("PRAGMA journal_mode").scalar(), "wal")
        finally:
            engine.dispose()

    def test_refuses_legacy_name_and_non_v2_schema(self):
        with self.assertRaises(ValueError):
            open_v2_shadow_engine(self.directory / "smartflow.db")

        wrong_database = self.directory / "wrong-shadow.db"
        connection = sqlite3.connect(wrong_database)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE unexpected (id INTEGER PRIMARY KEY)")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(RuntimeError):
            open_v2_shadow_engine(wrong_database)


if __name__ == "__main__":
    unittest.main()
