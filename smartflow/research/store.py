from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .common import canonical, digest, stamp, readonly


class ResearchStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "research.sqlite3", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS imports (
                identity TEXT PRIMARY KEY, source_group TEXT NOT NULL,
                manifest TEXT NOT NULL, imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS raw_evidence (
                identity TEXT PRIMARY KEY, payload_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY, source TEXT NOT NULL, event_id TEXT NOT NULL,
                parser_version TEXT NOT NULL, fingerprint TEXT NOT NULL,
                body TEXT NOT NULL, imported_at TEXT NOT NULL,
                UNIQUE(source,event_id,parser_version)
            );
            CREATE TABLE IF NOT EXISTS source_state (
                source TEXT PRIMARY KEY, import_id TEXT NOT NULL REFERENCES imports(identity),
                health TEXT NOT NULL, generated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, pack_hash TEXT NOT NULL UNIQUE, directory TEXT NOT NULL,
                status TEXT NOT NULL, analysis_hash TEXT, report_hash TEXT,
                review_hash TEXT, manifest_hash TEXT, completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS analyzed (
                evidence_id TEXT PRIMARY KEY REFERENCES evidence(id),
                run_id TEXT NOT NULL REFERENCES runs(id)
            );
            CREATE TABLE IF NOT EXISTS theses (
                run_id TEXT NOT NULL REFERENCES runs(id), security_key TEXT NOT NULL,
                body TEXT NOT NULL, PRIMARY KEY(run_id,security_key)
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, security_key TEXT NOT NULL, question TEXT NOT NULL,
                state TEXT NOT NULL, created_at TEXT NOT NULL, run_id TEXT NOT NULL REFERENCES runs(id)
            );
        """)
        # Upgrade only the task-owned early prototype schema, preserving imported facts.
        if "manifest_hash" not in {row[1] for row in self.db.execute("PRAGMA table_info(runs)")}:
            self.db.execute("ALTER TABLE runs ADD COLUMN manifest_hash TEXT")
        self.db.execute("PRAGMA user_version=1")
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def status(self) -> dict[str, Any]:
        return self._status(self.db)

    @staticmethod
    def read_status(root: Path) -> dict[str, Any]:
        connection = readonly(root / "research.sqlite3")
        try:
            connection.execute("BEGIN")
            return ResearchStore._status(connection)
        finally:
            connection.close()

    @staticmethod
    def _status(connection: sqlite3.Connection) -> dict[str, Any]:
        return {
            "evidence": connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
            "imports": connection.execute("SELECT COUNT(*) FROM imports").fetchone()[0],
            "runs": [dict(row) for row in connection.execute("SELECT id,status,completed_at FROM runs ORDER BY rowid DESC LIMIT 10")],
            "open_tasks": connection.execute("SELECT COUNT(*) FROM tasks WHERE state='pending'").fetchone()[0],
            "delivery": "report_only_no_send",
        }

    def approve(self, run_id: str, pack: dict, analysis: dict, report_hash: str, review_hash: str, manifest_hash: str) -> None:
        with self.db:
            current = self.db.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
            if current and current[0] == "approved":
                raise ValueError("approved_run_is_immutable")
            self.db.execute(
                "UPDATE runs SET status='approved',analysis_hash=?,report_hash=?,review_hash=?,manifest_hash=?,completed_at=? WHERE id=?",
                (digest(canonical(analysis)), report_hash, review_hash, manifest_hash, stamp(), run_id),
            )
            for dossier in pack["dossiers"]:
                for evidence in dossier["evidence"]:
                    if evidence["id"].startswith("E"):
                        self.db.execute("INSERT OR IGNORE INTO analyzed VALUES(?,?)", (evidence["id"], run_id))
            for item in analysis["items"]:
                self.db.execute("INSERT INTO theses VALUES(?,?,?)", (run_id, item["security_key"], canonical(item).decode()))
                for question in item["questions"]:
                    task_id = digest(canonical([item["security_key"], " ".join(question.split()).casefold()]))
                    self.db.execute("INSERT OR IGNORE INTO tasks VALUES(?,?,?,'pending',?,?)",
                                    (task_id, item["security_key"], question, stamp(), run_id))

    def previous(self, security_key: str) -> dict | None:
        row = self.db.execute(
            "SELECT t.body,r.directory,r.manifest_hash FROM theses t JOIN runs r ON r.id=t.run_id "
            "WHERE t.security_key=? AND r.status='approved' ORDER BY r.rowid DESC LIMIT 1", (security_key,),
        ).fetchone()
        if not row:
            return None
        from .common import beneath, file_hash, read_json
        directory = beneath(self.root, row["directory"])
        if file_hash(directory / "manifest.json") != row["manifest_hash"]:
            raise ValueError("previous_approved_manifest_tamper")
        for name, expected in read_json(directory / "manifest.json")["files"].items():
            if file_hash(beneath(directory, name)) != expected:
                raise ValueError("previous_approved_artifact_tamper")
        analysis = read_json(directory / "ANALYSIS.json")
        previous = json.loads(row["body"])
        if previous not in analysis["items"]:
            raise ValueError("previous_thesis_state_tamper")
        return previous
