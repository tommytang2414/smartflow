"""APScheduler-based orchestrator for all collectors."""

from apscheduler.schedulers.blocking import BlockingScheduler
from smartflow.config import POLL_INTERVALS
from smartflow.utils import get_logger

logger = get_logger("scheduler")

# Registry of available collectors
COLLECTOR_REGISTRY = {}


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


def _run_collector(name: str):
    """Run a single collector by name."""
    if name not in COLLECTOR_REGISTRY:
        logger.error(f"Unknown collector: {name}")
        return

    try:
        collector = COLLECTOR_REGISTRY[name]()
        count = collector.run()
        logger.info(f"[{name}] Collected {count} new signals")
    except Exception as e:
        logger.error(f"[{name}] Failed: {e}")


def start_scheduler(collectors: list[str] = None):
    """Start the polling scheduler for specified collectors (or all)."""
    _register_collectors()

    if collectors is None:
        collectors = list(COLLECTOR_REGISTRY.keys())

    scheduler = BlockingScheduler()

    for name in collectors:
        if name not in COLLECTOR_REGISTRY:
            logger.warning(f"Skipping unknown collector: {name}")
            continue

        interval = POLL_INTERVALS.get(name, 3600)
        scheduler.add_job(
            _run_collector,
            "interval",
            seconds=interval,
            args=[name],
            id=name,
            name=f"collect_{name}",
            max_instances=1,
        )
        logger.info(f"Scheduled {name} every {interval}s")

    # Run all once immediately
    for name in collectors:
        if name in COLLECTOR_REGISTRY:
            _run_collector(name)

    logger.info("Starting scheduler...")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")
