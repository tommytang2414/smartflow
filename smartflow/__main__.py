"""SmartFlow CLI.

Usage:
    python -m smartflow collect --source sec_form4
    python -m smartflow collect --all
    python -m smartflow query --market US --days 7
    python -m smartflow query --ticker AAPL
    python -m smartflow schedule --source sec_form4,congress
    python -m smartflow schedule --all
"""

import argparse
import sys
from datetime import datetime, timedelta

from smartflow.db.engine import init_db, get_session
from smartflow.db.models import SmartMoneySignal, CollectionRun, CCASSMetric, CCASSwatchlist


def cmd_collect(args):
    """Run a single collection."""
    from smartflow.scheduler import _register_collectors, _run_collector, COLLECTOR_REGISTRY

    init_db()
    _register_collectors()

    if args.all:
        sources = list(COLLECTOR_REGISTRY.keys())
    elif args.source:
        sources = [s.strip() for s in args.source.split(",")]
    else:
        print("Specify --source <name> or --all")
        sys.exit(1)

    for source in sources:
        if source not in COLLECTOR_REGISTRY:
            print(f"Unknown source: {source}")
            print(f"Available: {', '.join(COLLECTOR_REGISTRY.keys())}")
            continue
        print(f"Collecting from {source}...")
        _run_collector(source)


def cmd_query(args):
    """Query stored signals."""
    init_db()
    session = get_session()

    query = session.query(SmartMoneySignal)

    if args.market:
        query = query.filter(SmartMoneySignal.market == args.market.upper())
    if args.ticker:
        query = query.filter(SmartMoneySignal.ticker == args.ticker.upper())
    if args.source:
        query = query.filter(SmartMoneySignal.source == args.source)
    if args.direction:
        query = query.filter(SmartMoneySignal.direction == args.direction.upper())
    if args.days:
        cutoff = datetime.utcnow() - timedelta(days=args.days)
        query = query.filter(SmartMoneySignal.created_at >= cutoff)
    if args.min_value:
        query = query.filter(SmartMoneySignal.value_usd >= args.min_value)

    query = query.order_by(SmartMoneySignal.created_at.desc())
    results = query.limit(args.limit).all()

    if not results:
        print("No signals found.")
        return

    print(f"\n{'='*100}")
    print(f"{'Source':<15} {'Type':<20} {'Ticker':<8} {'Entity':<25} {'Dir':<6} {'Value':>15} {'Traded':<12}")
    print(f"{'='*100}")

    for s in results:
        value_str = f"${s.value_usd:,.0f}" if s.value_usd else "N/A"
        traded = s.traded_at.strftime("%Y-%m-%d") if s.traded_at else "N/A"
        entity = (s.entity_name or "")[:24]
        print(f"{s.source:<15} {s.signal_type:<20} {(s.ticker or 'N/A'):<8} {entity:<25} {(s.direction or ''):<6} {value_str:>15} {traded:<12}")

    print(f"\nTotal: {len(results)} signals")
    session.close()


def cmd_schedule(args):
    """Start the polling scheduler."""
    from smartflow.scheduler import start_scheduler

    if args.all:
        start_scheduler()
    elif args.source:
        sources = [s.strip() for s in args.source.split(",")]
        start_scheduler(sources)
    else:
        print("Specify --source <name> or --all")
        sys.exit(1)


def cmd_ccass(args):
    """Show CCASS concentration metrics — 莊家 detection."""
    init_db()
    session = get_session()

    query = session.query(CCASSMetric)

    if args.stock:
        query = query.filter(CCASSMetric.stock_code == args.stock.zfill(5))
    if args.flag:
        query = query.filter(CCASSMetric.concentration_flag == args.flag.upper())

    query = query.order_by(CCASSMetric.metric_date.desc(), CCASSMetric.brkt5.desc())
    results = query.limit(args.limit).all()

    if not results:
        print("No CCASS metrics yet. Run: python -m smartflow collect --source hkex_ccass")
        session.close()
        return

    print(f"\n{'='*100}")
    print(f"{'Stock':<8} {'Date':<12} {'BrkT5':>7} {'Δ':>6} {'FUTU%':>7} {'Top1 Broker':<28} {'Top1%':>6} {'Flag':<8} {'Parts':>5}")
    print(f"{'='*100}")

    for m in results:
        delta = f"{m.brkt5_change:+.1f}" if m.brkt5_change is not None else "N/A"
        broker = (m.top1_broker_name or "")[:27]
        flag = (m.concentration_flag or "")
        print(
            f"{m.stock_code:<8} {str(m.metric_date):<12} "
            f"{m.brkt5 or 0:>7.1f} {delta:>6} {m.futu_pct or 0:>7.1f} "
            f"{broker:<28} {m.top1_broker_pct or 0:>6.1f} {flag:<8} {m.participant_count or 0:>5}"
        )

    print(f"\nTotal: {len(results)} records")
    session.close()


def cmd_watchlist(args):
    """Manage CCASS stock watchlist."""
    init_db()

    if args.action == "list":
        from smartflow.collectors.hkex_watchlist import get_active_watchlist
        stocks = get_active_watchlist()
        print(f"\n{'Code':<8} {'Board':<6} {'Name'}")
        print("=" * 50)
        for s in stocks:
            print(f"{s['stock_code']:<8} {s.get('board',''):<6} {s.get('stock_name','')}")
        print(f"\nTotal: {len(stocks)} stocks")

    elif args.action == "add":
        if not args.code:
            print("Specify --code <stock_code>")
            return
        from smartflow.collectors.hkex_watchlist import add_stock
        add_stock(args.code, args.name or "", args.board or "MAIN")
        print(f"Added {args.code.zfill(5)} to watchlist")

    elif args.action == "seed":
        from smartflow.collectors.hkex_watchlist import seed_watchlist
        added = seed_watchlist()
        print(f"Seeded watchlist: {added} stocks added")


def cmd_status(args):
    """Show collection run history."""
    init_db()
    session = get_session()

    runs = session.query(CollectionRun).order_by(CollectionRun.id.desc()).limit(20).all()

    if not runs:
        print("No collection runs yet.")
        return

    print(f"\n{'Collector':<20} {'Status':<12} {'Records':>8} {'Started':<20} {'Duration':<10}")
    print(f"{'='*70}")

    for r in runs:
        started = r.started_at.strftime("%Y-%m-%d %H:%M") if r.started_at else "N/A"
        duration = ""
        if r.started_at and r.finished_at:
            d = (r.finished_at - r.started_at).total_seconds()
            duration = f"{d:.1f}s"
        records = str(r.records_found) if r.records_found is not None else "-"
        print(f"{r.collector:<20} {(r.status or 'N/A'):<12} {records:>8} {started:<20} {duration:<10}")

    session.close()


def main():
    parser = argparse.ArgumentParser(prog="smartflow", description="SmartFlow — Smart Money Data Pipeline")
    subparsers = parser.add_subparsers(dest="command")

    # collect
    p_collect = subparsers.add_parser("collect", help="Run a single collection")
    p_collect.add_argument("--source", type=str, help="Collector name(s), comma-separated")
    p_collect.add_argument("--all", action="store_true", help="Run all collectors")

    # query
    p_query = subparsers.add_parser("query", help="Query stored signals")
    p_query.add_argument("--market", type=str, help="Filter by market (US, HK, CRYPTO, OPTIONS)")
    p_query.add_argument("--ticker", type=str, help="Filter by ticker symbol")
    p_query.add_argument("--source", type=str, help="Filter by data source")
    p_query.add_argument("--direction", type=str, help="Filter by direction (BUY, SELL)")
    p_query.add_argument("--days", type=int, help="Only show signals from last N days")
    p_query.add_argument("--min-value", type=float, dest="min_value", help="Minimum USD value")
    p_query.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")

    # schedule
    p_sched = subparsers.add_parser("schedule", help="Start polling scheduler")
    p_sched.add_argument("--source", type=str, help="Collector name(s), comma-separated")
    p_sched.add_argument("--all", action="store_true", help="Schedule all collectors")

    # ccass
    p_ccass = subparsers.add_parser("ccass", help="Show CCASS concentration metrics (莊家 detection)")
    p_ccass.add_argument("--stock", type=str, help="Filter by stock code (e.g. 00700)")
    p_ccass.add_argument("--flag", type=str, choices=["RED", "AMBER", "GREEN"], help="Filter by concentration flag")
    p_ccass.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")

    # watchlist
    p_wl = subparsers.add_parser("watchlist", help="Manage CCASS stock watchlist")
    p_wl.add_argument("action", choices=["list", "add", "seed"], help="Action to perform")
    p_wl.add_argument("--code", type=str, help="Stock code for add action")
    p_wl.add_argument("--name", type=str, help="Stock name")
    p_wl.add_argument("--board", type=str, default="MAIN", choices=["MAIN", "GEM"])

    # status
    subparsers.add_parser("status", help="Show collection run history")

    args = parser.parse_args()

    if args.command == "collect":
        cmd_collect(args)
    elif args.command == "query":
        cmd_query(args)
    elif args.command == "schedule":
        cmd_schedule(args)
    elif args.command == "ccass":
        cmd_ccass(args)
    elif args.command == "watchlist":
        cmd_watchlist(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
