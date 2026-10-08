from __future__ import annotations

import argparse
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .common import beneath, canonical, digest, file_hash, read_json, stamp, utc, write_json
from .evidence import select_events
from .model import ANALYSIS_SCHEMA, REVIEW_SCHEMA, render_report, run_model, validate_analysis, validate_review
from .news import import_news
from .pack import build_pack
from .snapshots import KEYS, import_snapshot, sync_aws
from .store import ResearchStore


@contextmanager
def single_writer(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    with (root / "research.lock").open("a+b") as stream:
        try:
            if os.name == "nt":
                import msvcrt
                stream.seek(0)
                if not stream.read(1):
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("another_research_writer_is_running") from error
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def prepare(store: ResearchStore, alias_path: Path, as_of: datetime, news_root: Path | None) -> tuple[dict, str, Path]:
    definitions = read_json(alias_path)
    news = import_news(news_root, definitions, as_of, store.root / "news-cache") if news_root else None
    pack = build_pack(store, definitions, as_of=as_of, news=news)
    if not pack["dossiers"]:
        raise ValueError("no_eligible_research_dossiers_check_source_gates")
    pack_hash = digest(canonical(pack))
    run_id = "R" + pack_hash[:24]
    previous = store.db.execute("SELECT * FROM runs WHERE pack_hash=?", (pack_hash,)).fetchone()
    if previous:
        raise ValueError("run_already_exists_use_status_no_implicit_replay")
    directory = store.root / "runs" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "PACK.json").write_bytes(canonical(pack))
    write_json(directory / "aliases.json", definitions)
    (directory / "DETERMINISTIC.md").write_text(render_report(pack, None, status="Deterministic evidence，未完成 GPT review"), encoding="utf-8")
    with store.db:
        store.db.execute("INSERT INTO runs(id,pack_hash,directory,status) VALUES(?,?,?,'prepared')", (run_id, pack_hash, directory.relative_to(store.root).as_posix()))
    return pack, run_id, directory


def analyze(store: ResearchStore, alias_path: Path, executable: Path, as_of: datetime, news_root: Path | None) -> dict:
    pack, run_id, directory = prepare(store, alias_path, as_of, news_root)
    pack_hash = digest(canonical(pack))
    deadline = time.monotonic() + 45 * 60
    with store.db:
        store.db.execute("UPDATE runs SET status='analyzing' WHERE id=?", (run_id,))
    repair = None
    try:
        for revision in range(2):
            payload = {"pack": pack, "pack_sha256": pack_hash}
            if repair:
                payload["correction"] = repair
            analysis, analyst_receipt = run_model(executable, directory, f"analyst-{revision}", payload, ANALYSIS_SCHEMA,
                                                  timeout=max(1, min(900, int(deadline - time.monotonic()))))
            try:
                validate_analysis(pack, analysis)
            except ValueError as error:
                if revision:
                    raise
                repair = {"reason_code": str(error), "previous_analysis": analysis}
                continue
            frozen_analysis = canonical(analysis)
            analysis_hash = digest(frozen_analysis)
            candidate = render_report(pack, analysis, status="GPT 分析；正式 verdict 見 REVIEW.json").encode()
            report_hash = digest(candidate)
            (directory / f"candidate-{revision}.md").write_bytes(candidate)
            review, reviewer_receipt = run_model(executable, directory, f"review-{revision}",
                {"pack": pack, "pack_sha256": pack_hash, "analysis": analysis, "analysis_sha256": analysis_hash,
                 "report": candidate.decode(), "report_sha256": report_hash}, REVIEW_SCHEMA,
                timeout=max(1, min(900, int(deadline - time.monotonic()))))
            validate_review(review)
            if set(review) != set(REVIEW_SCHEMA["properties"]) or not (
                review["pack_sha256"] == pack_hash and review["analysis_sha256"] == analysis_hash and review["report_sha256"] == report_hash
                and analyst_receipt["thread_id"] != reviewer_receipt["thread_id"]):
                raise ValueError("independent_review_binding_invalid")
            if review["verdict"] != "PASS_WITH_LIMITATIONS":
                if revision == 0 and review["verdict"] == "NEEDS_REVISION":
                    repair = {"review": review, "previous_analysis": analysis}
                    continue
                raise ValueError("independent_review_rejected")
            if file_hash(directory / "PACK.json") != pack_hash:
                raise ValueError("frozen_pack_tamper")
            (directory / "ANALYSIS.json").write_bytes(frozen_analysis)
            (directory / "REPORT.md").write_bytes(candidate)
            (directory / "REVIEW.json").write_bytes(canonical(review))
            manifest = {"run_id": run_id, "pack_hash": pack_hash, "analysis_hash": analysis_hash,
                        "revision": revision, "files": {name: file_hash(directory / name) for name in
                        ("PACK.json", "aliases.json", "ANALYSIS.json", "REPORT.md", "REVIEW.json", f"analyst-{revision}-execution.json", f"review-{revision}-execution.json")}}
            write_json(directory / "manifest.json", manifest)
            store.approve(run_id, pack, analysis, report_hash, file_hash(directory / "REVIEW.json"), file_hash(directory / "manifest.json"))
            return {"status": "approved", "run_id": run_id, "report": str(directory / "REPORT.md"),
                    "pack_hash": pack_hash, "review": review["verdict"], "delivery": "report_only_no_send"}
        raise ValueError("analysis_corrections_exhausted")
    except Exception as error:
        code = str(error) if isinstance(error, ValueError) else type(error).__name__
        write_json(directory / "failure.json", {"status": "needs_attention", "reason_code": code[:160], "recorded_at": stamp()})
        with store.db:
            store.db.execute("UPDATE runs SET status='needs_attention',completed_at=? WHERE id=?", (stamp(), run_id))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartFlow isolated manual research; no collector/scheduler/email commands")
    parser.add_argument("--state", type=Path, default=Path("data/research-prototype/state"))
    commands = parser.add_subparsers(dest="command", required=True)
    sync = commands.add_parser("sync", help="Download exact S3 snapshot versions using existing operator AWS auth")
    sync.add_argument("--destination", type=Path, required=True)
    ingest = commands.add_parser("import", help="Verify and ingest immutable snapshot files")
    ingest.add_argument("--snapshots", type=Path, required=True)
    for name in ("prepare", "analyze"):
        command = commands.add_parser(name)
        command.add_argument("--aliases", type=Path, required=True)
        command.add_argument("--as-of", type=utc, default=None)
        command.add_argument("--news-root", type=Path)
        if name == "analyze":
            command.add_argument("--codex", type=Path, required=True)
    commands.add_parser("status")
    suggest = commands.add_parser("alias-candidates", help="Print candidates, never auto-approve identity mappings")
    args = parser.parse_args()
    if args.command == "sync":
        print(json.dumps(sync_aws(args.destination), ensure_ascii=False))
        return
    if args.command == "status":
        print(json.dumps(ResearchStore.read_status(args.state), ensure_ascii=False))
        return
    with single_writer(args.state):
        store = ResearchStore(args.state)
        try:
            if args.command == "import":
                results = {}
                for group in KEYS:
                    manifest = read_json(args.snapshots / (group + "-manifest.json"))
                    results[group] = import_snapshot(store, group, beneath(args.snapshots, manifest["file"]), manifest)
                result = results
            elif args.command == "alias-candidates":
                events, _ = select_events(store, datetime.now(timezone.utc))
                candidates = {}
                for event in events:
                    if event["source"] == "sec_form4":
                        key = (event["ticker"], event["security_id"], event["attributes"].get("security_title"))
                        candidates.setdefault(key, {"ticker": key[0], "issuer_cik": key[1], "security_title": key[2], "proof_id": event["id"]})
                result = list(candidates.values())
            elif args.command == "prepare":
                pack, run_id, directory = prepare(store, args.aliases, args.as_of or datetime.now(timezone.utc), args.news_root)
                result = {"run_id": run_id, "pack": str(directory / "PACK.json"), "dossiers": len(pack["dossiers"]), "status": "prepared_not_analyzed"}
            else:
                result = analyze(store, args.aliases, args.codex, args.as_of or datetime.now(timezone.utc), args.news_root)
            print(json.dumps(result, ensure_ascii=False))
        finally:
            store.close()


if __name__ == "__main__":
    main()
