"""Read-only audit of contained legacy CCASS data and unsupported directions."""

import sqlite3
from pathlib import Path


def audit_ccass_legacy(database: Path) -> dict:
    resolved = database.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    try:
        holdings = connection.execute(
            "SELECT COUNT(*), MIN(holding_date), MAX(holding_date) FROM ccass_holdings"
        ).fetchone()
        metrics = connection.execute(
            "SELECT COUNT(*), MIN(metric_date), MAX(metric_date) FROM ccass_metrics"
        ).fetchone()
        directions = dict(
            connection.execute(
                "SELECT direction, COUNT(*) FROM smart_money_signals "
                "WHERE source = 'hkex_ccass' GROUP BY direction"
            ).fetchall()
        )
        flags = dict(
            connection.execute(
                "SELECT concentration_flag, COUNT(*) FROM ccass_metrics "
                "GROUP BY concentration_flag"
            ).fetchall()
        )
        directional_count = sum(directions.values())
        return {
            "database": str(resolved),
            "quick_check": connection.execute("PRAGMA quick_check").fetchone()[0],
            "holding_rows": holdings[0],
            "holding_date_range": [holdings[1], holdings[2]],
            "metric_rows": metrics[0],
            "metric_date_range": [metrics[1], metrics[2]],
            "legacy_directional_signals": directional_count,
            "legacy_directions": directions,
            "legacy_concentration_flags": flags,
            "supported_directional_signals": 0,
            "status": "directional_semantics_unsupported",
            "reason": (
                "CCASS participant balances are custody/settlement snapshots and do not "
                "identify beneficial owners or prove purchases or sales"
            ),
        }
    finally:
        connection.close()
