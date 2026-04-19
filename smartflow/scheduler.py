"""APScheduler-based orchestrator for all collectors.

Features:
- Circuit breaker: after CIRCUIT_BREAKER_THRESHOLD consecutive failures, backs off to
  CIRCUIT_BREAKER_BACKOFF seconds. Logs a clear CIRCUIT OPEN message.
- Hard timeout: each collector run is wrapped with a wall-clock timeout. Hangs are
  counted as failures toward the circuit breaker.
- S3 upload throttle: only uploads when new signals are found (count > 0).
- Disabled collectors: any name in config.DISABLED_COLLECTORS is skipped entirely.
"""

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from apscheduler.schedulers.blocking import BlockingScheduler
from smartflow.config import (
    POLL_INTERVALS,
    DISABLED_COLLECTORS,
    CIRCUIT_BREAKER_THRESHOLD,
    CIRCUIT_BREAKER_BACKOFF,
    COLLECTOR_TIMEOUTS,
)
from smartflow.utils import get_logger

logger = get_logger("scheduler")

# Registry of available collectors
COLLECTOR_REGISTRY = {}

# Circuit breaker state: collector_name → consecutive failure count
_failure_counts: dict[str, int] = {}

# Reference to the running scheduler (set in start_scheduler)
_scheduler = None


def _register_collectors():
    """Lazily import and register all collectors."""
    from smartflow.collectors.sec_insider import SECInsiderCollector
    from smartflow.collectors.sec_13f import SEC13FCollector
    from smartflow.collectors.congress import CongressCollector
    from smartflow.collectors.sec_form144 import SECForm144Collector
    from smartflow.collectors.sec_13d import SEC13DCollector
    from smartflow.collectors.crypto_coinglass import CoinGlassWhaleCollector, CoinGlassOICollector
    from smartflow.collectors.crypto_dex import DEXWhaleCollector
    from smartflow.collectors.crypto_whale import WhaleAlertCollector
    from smartflow.collectors.crypto_arkham import ArkhamWhaleLabelCollector
    from smartflow.collectors.hkex_director import HKEXDirectorCollector
    from smartflow.collectors.hkex_ccass import CCASSCollector
    from smartflow.collectors.hkex_northbound import HKEXNorthboundCollector
    from smartflow.collectors.hkex_short import SFCShortCollector
    from smartflow.collectors.hkex_dealings import HKEXDealingsCollector
    from smartflow.collectors.nq_si import NQSICollector

    COLLECTOR_REGISTRY.update({
        "sec_form4": SECInsiderCollector,
        "sec_13f": SEC13FCollector,
        "congress": CongressCollector,
        "sec_form144": SECForm144Collector,
        "sec_13d": SEC13DCollector,
        "coinglass_whale": CoinGlassWhaleCollector,
        "coinglass_oi": CoinGlassOICollector,
        "dex_whale": DEXWhaleCollector,
        "whale_alert": WhaleAlertCollector,
        "arkham_labels": ArkhamWhaleLabelCollector,
        "hkex_director": HKEXDirectorCollector,
        "hkex_ccass": CCASSCollector,
        "hkex_northbound": HKEXNorthboundCollector,
        "sfc_short": SFCShortCollector,
        "hkex_dealings": HKEXDealingsCollector,
        "nq_si": NQSICollector,
    })


def _upload_db_to_s3():
    """Upload local DB to S3."""
    try:
        import boto3
        from smartflow.config import DATA_DIR
        s3 = boto3.client("s3")
        db_path = str(DATA_DIR / "smartflow.db")
        s3.upload_file(db_path, "smartflow-tommy-db", "smartflow.db")
        logger.info("DB uploaded to S3")
    except Exception as e:
        logger.warning(f"S3 upload failed: {e}")


def _do_collect(name: str) -> int:
    """Run a single collector and return the count of new signals."""
    collector = COLLECTOR_REGISTRY[name]()
    return collector.run()


def _open_circuit(name: str, fails: int, last_error: Exception):
    """Back off a collector to CIRCUIT_BREAKER_BACKOFF interval."""
    global _scheduler
    logger.error(
        f"[{name}] CIRCUIT OPEN — {fails} consecutive failures. "
        f"Backing off to {CIRCUIT_BREAKER_BACKOFF}s ({CIRCUIT_BREAKER_BACKOFF // 3600}h). "
        f"Fix the underlying issue and restart the scheduler to reset. "
        f"Last error: {last_error}"
    )
    if _scheduler:
        try:
            _scheduler.reschedule_job(
                name, trigger="interval", seconds=CIRCUIT_BREAKER_BACKOFF
            )
        except Exception as reschedule_err:
            logger.warning(f"[{name}] Could not reschedule for backoff: {reschedule_err}")


def _run_collector(name: str):
    """Run a collector with timeout + circuit breaker."""
    global _failure_counts

    if name not in COLLECTOR_REGISTRY:
        logger.error(f"Unknown collector: {name}")
        return

    timeout = COLLECTOR_TIMEOUTS.get(name, COLLECTOR_TIMEOUTS["default"])
    count = 0
    error = None

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"sf-{name}") as executor:
        future = executor.submit(_do_collect, name)
        try:
            count = future.result(timeout=timeout)
        except FuturesTimeoutError:
            error = RuntimeError(f"Hard timeout after {timeout}s — collector hung")
            logger.error(f"[{name}] {error}")
        except Exception as exc:
            error = exc
            logger.error(f"[{name}] Failed: {exc}")

    if error is None:
        # Success — reset circuit breaker
        if _failure_counts.get(name, 0) > 0:
            logger.info(f"[{name}] Recovered after {_failure_counts[name]} failures")
        _failure_counts[name] = 0
        logger.info(f"[{name}] Collected {count} new signals")
        # S3 upload only when new data was found
        if count > 0:
            _upload_db_to_s3()
    else:
        fails = _failure_counts.get(name, 0) + 1
        _failure_counts[name] = fails
        threshold = CIRCUIT_BREAKER_THRESHOLD
        logger.warning(f"[{name}] Failure {fails}/{threshold}: {error}")
        if fails >= threshold:
            _open_circuit(name, fails, error)


def start_scheduler(collectors: list[str] = None):
    """Start the polling scheduler for specified collectors (or all)."""
    global _scheduler

    _register_collectors()

    if collectors is None:
        collectors = list(COLLECTOR_REGISTRY.keys())

    # Filter out disabled collectors up front
    active = [n for n in collectors if n not in DISABLED_COLLECTORS]
    skipped = [n for n in collectors if n in DISABLED_COLLECTORS]
    if skipped:
        logger.info(f"Skipping disabled collectors: {', '.join(skipped)}")

    _scheduler = BlockingScheduler()

    for name in active:
        if name not in COLLECTOR_REGISTRY:
            logger.warning(f"Skipping unknown collector: {name}")
            continue

        interval = POLL_INTERVALS.get(name, 3600)
        _scheduler.add_job(
            _run_collector,
            "interval",
            seconds=interval,
            args=[name],
            id=name,
            name=f"collect_{name}",
            max_instances=1,
        )
        logger.info(f"Scheduled {name} every {interval}s")

    # Run all active collectors once immediately at startup
    for name in active:
        if name in COLLECTOR_REGISTRY:
            _run_collector(name)

    logger.info("Starting scheduler...")
    try:
        _scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")
