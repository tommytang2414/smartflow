from datetime import datetime
from sqlalchemy import Column, Integer, Text, Float, Boolean, DateTime, JSON, Date, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SmartMoneySignal(Base):
    __tablename__ = "smart_money_signals"

    id = Column(Integer, primary_key=True)
    source = Column(Text, nullable=False)       # 'sec_form4', 'hkex_director', 'whale_alert', etc.
    market = Column(Text, nullable=False)        # 'US', 'HK', 'CRYPTO', 'OPTIONS'
    signal_type = Column(Text, nullable=False)   # 'insider_buy', 'insider_sell', '13f_new_position', etc.
    ticker = Column(Text)
    entity_name = Column(Text)
    entity_type = Column(Text)                   # 'insider', 'institution', 'congress', 'whale', 'director'
    direction = Column(Text)                     # 'BUY', 'SELL', 'TRANSFER_IN', 'TRANSFER_OUT'
    quantity = Column(Float)
    price = Column(Float)
    value_usd = Column(Float)
    filed_at = Column(DateTime)
    traded_at = Column(DateTime)
    raw_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    source_id = Column(Text, unique=True)        # Dedup key

    def __repr__(self):
        return f"<Signal {self.source}:{self.signal_type} {self.ticker} {self.direction} ${self.value_usd:,.0f}>"


class TrackedEntity(Base):
    __tablename__ = "tracked_entities"

    id = Column(Integer, primary_key=True)
    entity_type = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    identifier = Column(Text)                    # CIK, wallet address, HKEX code
    market = Column(Text, nullable=False)
    notes = Column(Text)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Entity {self.entity_type}:{self.name}>"


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id = Column(Integer, primary_key=True)
    collector = Column(Text, nullable=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    records_found = Column(Integer)
    status = Column(Text)                        # 'success', 'error', 'rate_limited'
    error_message = Column(Text)

    def __repr__(self):
        return f"<Run {self.collector} {self.status} +{self.records_found}>"


class CCASSwatchlist(Base):
    """Stocks to monitor via CCASS daily scraping."""
    __tablename__ = "ccass_watchlist"

    id = Column(Integer, primary_key=True)
    stock_code = Column(Text, nullable=False, unique=True)  # e.g. '00700', '02706'
    stock_name = Column(Text)
    board = Column(Text)          # 'MAIN', 'GEM'
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=datetime.utcnow)


class CCASSHolding(Base):
    """Daily snapshot of CCASS participant holdings per stock."""
    __tablename__ = "ccass_holdings"

    id = Column(Integer, primary_key=True)
    stock_code = Column(Text, nullable=False)
    holding_date = Column(Date, nullable=False)
    participant_id = Column(Text, nullable=False)    # e.g. 'B01955'
    participant_name = Column(Text)
    participant_type = Column(Text)                  # 'broker', 'bank', 'clearing', 'other'
    shares_held = Column(Float)
    pct_of_total = Column(Float)                     # % of total issued shares in CCASS
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('stock_code', 'holding_date', 'participant_id', name='uq_ccass_holding'),
    )


class CCASSMetric(Base):
    """Daily computed concentration metrics per stock."""
    __tablename__ = "ccass_metrics"

    id = Column(Integer, primary_key=True)
    stock_code = Column(Text, nullable=False)
    metric_date = Column(Date, nullable=False)
    total_ccass_shares = Column(Float)       # total shares in CCASS
    adjusted_float = Column(Float)           # total minus A00005 (immobilized)
    participant_count = Column(Integer)      # number of unique participants
    broker_count = Column(Integer)           # B-prefix only
    brkt5 = Column(Float)                    # top 5 broker % of adjusted float
    brkt5_prev = Column(Float)               # previous day BrkT5
    brkt5_change = Column(Float)             # day-on-day change in BrkT5
    futu_pct = Column(Float)                 # FUTU (B01955) % of adjusted float
    futu_pct_prev = Column(Float)
    top1_broker_id = Column(Text)
    top1_broker_name = Column(Text)
    top1_broker_pct = Column(Float)
    concentration_flag = Column(Text)        # 'RED', 'AMBER', 'GREEN'
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('stock_code', 'metric_date', name='uq_ccass_metric'),
    )


class NorthboundFlow(Base):
    """Daily Stock Connect northbound/southbound turnover."""
    __tablename__ = "northbound_flow"

    id = Column(Integer, primary_key=True)
    trade_date = Column(Date, nullable=False, unique=True)
    northbound_hkd = Column(Float)       # Northbound turnover in HKD
    southbound_hkd = Column(Float)       # Southbound turnover in HKD
    northbound_quota_pct = Column(Float)  # % of northbound quota used
    created_at = Column(DateTime, default=datetime.utcnow)


class SFCShortData(Base):
    """Weekly SFC short position data."""
    __tablename__ = "sfc_short_data"

    id = Column(Integer, primary_key=True)
    week_end_date = Column(Date, nullable=False, unique=True)
    raw_data = Column(JSON)  # List of {stock_code, short_value_hkd, total_turnover_hkd, short_pct}
    created_at = Column(DateTime, default=datetime.utcnow)
