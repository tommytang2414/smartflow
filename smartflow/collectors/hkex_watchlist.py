"""Seed and manage the CCASS stock watchlist.

Default watchlist covers:
- Recent IPOs (GEM + Main Board, last 12 months) — highest 莊家 risk
- GEM board stocks — small cap, less regulated
- Hand-picked suspicious stocks
- Hang Seng small cap index constituents
"""

from smartflow.db.engine import get_session, init_db
from smartflow.db.models import CCASSwatchlist
from smartflow.utils import get_logger

logger = get_logger("ccass_watchlist")

# Default seed watchlist
# Format: (stock_code, stock_name, board, notes)
# Stock codes are zero-padded to 5 digits
DEFAULT_WATCHLIST = [
    # ── Recent GEM IPOs (high 莊家 risk) ────────────────────────────────────
    ("08619", "WAC Holdings", "GEM", "Recent IPO"),
    ("08668", "HK Asia Holdings", "GEM", "Recent IPO"),
    ("08367", "China Shengda Packaging", "GEM", "GEM small cap"),
    ("08645", "Lerthai Group", "GEM", "GEM small cap"),
    ("08676", "Maxeon Solar Tech", "GEM", "Recent IPO"),
    ("08659", "Go Up Holdings", "GEM", "Recent IPO"),
    ("08631", "Suncorp Technologies", "GEM", "GEM small cap"),
    ("08283", "Zheng Li Holdings", "GEM", "GEM small cap"),

    # ── Main Board small cap / frequent movers ───────────────────────────────
    ("01357", "Meitu", "MAIN", "Volatile small cap"),
    ("01530", "3SBio", "MAIN", "Biotech"),
    ("02120", "Scienjoy", "MAIN", "Small cap"),
    ("01562", "Glenturret", "MAIN", "Recent IPO"),
    ("02611", "Guotai Junan International", "MAIN", "Brokerage"),
    ("01681", "Consun Pharmaceutical", "MAIN", "Pharma small cap"),
    ("01466", "Artini China", "MAIN", "Small cap"),
    ("02132", "HK Haina Tech", "MAIN", "Tech small cap"),

    # ── Blue chips for baseline comparison ──────────────────────────────────
    ("00700", "Tencent", "MAIN", "Baseline - large cap"),
    ("09988", "Alibaba", "MAIN", "Baseline - large cap"),
    ("00005", "HSBC Holdings", "MAIN", "Baseline - large cap"),
    ("00941", "China Mobile", "MAIN", "Baseline - large cap"),
    ("02318", "Ping An Insurance", "MAIN", "Baseline - large cap"),

    # ── Property / Real Estate small caps ───────────────────────────────────
    ("01813", "KWG Group", "MAIN", "Property small cap"),
    ("02768", "Jiuzi Holdings", "MAIN", "Property"),
    ("06823", "HKT Trust", "MAIN", "Telecom"),
]


def seed_watchlist(overwrite: bool = False):
    """Seed the default watchlist into DB. Skips existing entries unless overwrite=True."""
    init_db()
    session = get_session()

    added = 0
    for code, name, board, notes in DEFAULT_WATCHLIST:
        existing = session.query(CCASSwatchlist).filter_by(stock_code=code).first()
        if existing:
            if overwrite:
                existing.stock_name = name
                existing.board = board
                existing.notes = notes
        else:
            session.add(CCASSwatchlist(
                stock_code=code,
                stock_name=name,
                board=board,
                notes=notes,
                is_active=True,
            ))
            added += 1

    session.commit()
    session.close()
    logger.info(f"Watchlist seeded: {added} new stocks added")
    return added


def get_active_watchlist() -> list[dict]:
    """Return list of active watchlist stocks."""
    session = get_session()
    stocks = session.query(CCASSwatchlist).filter_by(is_active=True).all()
    result = [
        {"stock_code": s.stock_code, "stock_name": s.stock_name, "board": s.board}
        for s in stocks
    ]
    session.close()
    return result


def add_stock(stock_code: str, stock_name: str = "", board: str = "MAIN", notes: str = ""):
    """Add a single stock to the watchlist."""
    code = stock_code.zfill(5)
    session = get_session()
    existing = session.query(CCASSwatchlist).filter_by(stock_code=code).first()
    if existing:
        existing.is_active = True
        session.commit()
        logger.info(f"Re-activated {code} in watchlist")
    else:
        session.add(CCASSwatchlist(stock_code=code, stock_name=stock_name,
                                   board=board, notes=notes))
        session.commit()
        logger.info(f"Added {code} ({stock_name}) to watchlist")
    session.close()
