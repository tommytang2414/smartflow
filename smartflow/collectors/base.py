from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.exc import IntegrityError
from smartflow.db.engine import get_session, init_db
from smartflow.db.models import SmartMoneySignal, CollectionRun
from smartflow.utils import get_logger


class BaseCollector(ABC):
    """Abstract base class for all data collectors."""

    name: str = "base"
    market: str = "UNKNOWN"

    def __init__(self):
        self.logger = get_logger(self.name)
        init_db()

    @abstractmethod
    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch raw data from source. Returns list of signal dicts."""
        ...

    def run(self) -> int:
        """Execute a collection run. Returns number of new records inserted."""
        session = get_session()
        run = CollectionRun(
            collector=self.name,
            started_at=datetime.utcnow(),
            status="running",
        )
        session.add(run)
        session.commit()

        try:
            raw_signals = self.fetch()
            inserted = 0

            for data in raw_signals:
                signal = SmartMoneySignal(
                    source=self.name,
                    market=data.get("market", self.market),
                    signal_type=data.get("signal_type", "unknown"),
                    ticker=data.get("ticker"),
                    entity_name=data.get("entity_name"),
                    entity_type=data.get("entity_type"),
                    direction=data.get("direction"),
                    quantity=data.get("quantity"),
                    price=data.get("price"),
                    value_usd=data.get("value_usd"),
                    filed_at=data.get("filed_at"),
                    traded_at=data.get("traded_at"),
                    raw_data=data.get("raw_data"),
                    source_id=data.get("source_id"),
                )
                session.add(signal)
                try:
                    session.commit()
                    inserted += 1
                except IntegrityError:
                    session.rollback()  # duplicate source_id, skip

            run.finished_at = datetime.utcnow()
            run.records_found = inserted
            run.status = "success"
            session.commit()
            self.logger.info(f"Collection complete: {inserted} new signals")
            return inserted

        except Exception as e:
            run.finished_at = datetime.utcnow()
            run.status = "error"
            run.error_message = str(e)[:500]
            session.commit()
            self.logger.error(f"Collection failed: {e}")
            raise
        finally:
            session.close()
