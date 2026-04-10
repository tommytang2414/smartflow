"""NQ Short Interest Collector — Nasdaq-100 composite SI signals.

Reads FINRA bi-monthly short interest data from the nq-short-interest parquet cache,
computes the market-cap-weighted composite SI index and contrarian signal,
then stores results in SmartFlow DB.

Signal logic (from nq-short-interest signal_builder.py):
  - SI z-score > 1.5  → BUY  (contrarian: extreme short interest → short squeeze)
  - SI z-score < -1.5 → SELL (contrarian: low short interest → complacency)
  - Otherwise          → HOLD

Requires nq-short-interest data at: C:/Users/user/nq-short-interest/data/
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from smartflow.collectors.base import BaseCollector
from smartflow.utils import get_logger

NQ_DATA_DIR = Path("C:/Users/user/nq-short-interest/data")
SIGNAL_THRESHOLD_ZSCORE = 1.5
SI_HIGH_THRESHOLD = 0.05   # +5% MoM SI change → contrarian long
SI_LOW_THRESHOLD = -0.05   # -5% MoM SI change → contrarian short
MIN_TRAIN_PERIODS = 10


class NQSICollector(BaseCollector):
    """Collect NQ composite short interest signals from FINRA data."""

    name = "nq_si"
    market = "OPTIONS"

    def _load_si_data(self) -> pd.DataFrame:
        """Load cached short interest parquet."""
        path = NQ_DATA_DIR / "short_interest.parquet"
        if not path.exists():
            self.logger.warning(f"SI cache not found: {path}")
            return pd.DataFrame()
        return pd.read_parquet(path)

    def _load_weights(self) -> dict[str, float]:
        """Load and normalize market-cap weights."""
        path = NQ_DATA_DIR / "market_caps.json"
        if not path.exists():
            return {}
        with open(path) as f:
            caps = json.load(f)
        total = sum(caps.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in caps.items()}

    def _update_cache_if_stale(self) -> bool:
        """Re-run nq-short-interest data fetch if cache is older than 14 days."""
        si_path = NQ_DATA_DIR / "short_interest.parquet"
        if si_path.exists():
            age_days = (datetime.now().timestamp() - si_path.stat().st_mtime) / 86400
            if age_days < 14:
                return False  # cache fresh

        self.logger.info("NQ SI cache stale (>14 days), refreshing data...")
        result = subprocess.run(
            [sys.executable, "-c",
             "from data_fetcher import fetch_all_data; fetch_all_data(force=True)"],
            cwd=str(NQ_DATA_DIR.parent),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            self.logger.error(f"SI data refresh failed: {result.stderr}")
            return False
        self.logger.info("NQ SI data refreshed.")
        return True

    def _compute_composite(self, si: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
        """Build composite SI index from per-stock data."""
        if si.empty:
            return pd.DataFrame()

        df = si.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df[df["ticker"].isin(weights)].copy()
        if df.empty:
            return pd.DataFrame()

        df["weight"] = df["ticker"].map(weights)

        records = []
        for date, group in df.groupby("date"):
            w = group["weight"].values
            w_sum = w.sum()
            if w_sum == 0:
                continue
            w_norm = w / w_sum
            dtc = group["days_to_cover"].fillna(0).values
            records.append({
                "date": date,
                "composite_si_pct_float": np.average(group["short_pct_float"].fillna(0).values, weights=w_norm),
                "composite_short_ratio": np.average(dtc, weights=w_norm),
                "composite_si_change_pct": np.average(group["si_change_pct"].fillna(0).values, weights=w_norm),
                "n_stocks": len(group),
                "total_weight_coverage": w_sum,
            })

        if not records:
            return pd.DataFrame()

        out = pd.DataFrame(records).sort_values("date").reset_index(drop=True)

        # Z-score
        out["si_rolling_mean"] = out["composite_si_pct_float"].rolling(window=20, min_periods=20).mean()
        out["si_rolling_std"] = out["composite_si_pct_float"].rolling(window=20, min_periods=20).std()
        out["si_zscore"] = np.where(
            out["si_rolling_std"] > 0,
            (out["composite_si_pct_float"] - out["si_rolling_mean"]) / out["si_rolling_std"],
            0.0,
        )
        out["si_change_rate"] = out["composite_si_change_pct"]

        return out

    def _generate_signal(self, row: pd.Series, n_periods: int, min_train: int) -> str:
        """Convert z-score to direction signal."""
        enough_history = n_periods >= min_train
        z = row.get("si_zscore", 0)
        chg = row.get("si_change_rate", 0)

        if not enough_history:
            if chg > SI_HIGH_THRESHOLD:
                return "BUY"
            elif chg < SI_LOW_THRESHOLD:
                return "SELL"
            return "HOLD"

        if z > SIGNAL_THRESHOLD_ZSCORE:
            return "BUY"
        elif z < -SIGNAL_THRESHOLD_ZSCORE:
            return "SELL"
        return "HOLD"

    def fetch(self) -> list[dict[str, Any]]:
        self._update_cache_if_stale()

        si = self._load_si_data()
        weights = self._load_weights()

        if si.empty:
            self.logger.warning("No SI data loaded")
            return []

        composite = self._compute_composite(si, weights)
        if composite.empty:
            return []

        # Get latest signal only (most recent date)
        latest = composite.iloc[-1]
        n_periods = len(composite)
        direction = self._generate_signal(latest, n_periods, MIN_TRAIN_PERIODS)
        filed_at = pd.Timestamp(latest["date"]).to_pydatetime()

        # source_id for dedup
        date_str = filed_at.strftime("%Y-%m-%d")
        source_id = f"nq_si_composite_{date_str}"

        # Build signal
        signals = [{
            "signal_type": "nq_si_contrarian",
            "ticker": "NQ100",
            "entity_name": "Nasdaq-100 Composite",
            "entity_type": "index",
            "direction": direction,
            "quantity": None,
            "price": None,
            "value_usd": float(latest["composite_si_pct_float"]) * 100,  # proxy: SI% × 100
            "filed_at": filed_at,
            "traded_at": None,
            "raw_data": {
                "composite_si_pct_float": float(latest["composite_si_pct_float"]),
                "composite_short_ratio": float(latest["composite_short_ratio"]),
                "composite_si_change_pct": float(latest["composite_si_change_pct"]),
                "si_zscore": float(latest["si_zscore"]) if "si_zscore" in latest else None,
                "si_change_rate": float(latest["si_change_rate"]) if "si_change_rate" in latest else None,
                "n_stocks": int(latest["n_stocks"]),
                "date_str": date_str,
            },
            "source_id": source_id,
        }]

        # Also emit per-ticker high-SI signals (>15% short interest → bearish)
        cutoff = si["date"] == latest["date"]
        high_si = si[cutoff & (si["short_pct_float"] > 15)]
        for _, row in high_si.iterrows():
            ticker = row["ticker"]
            signals.append({
                "signal_type": "nq_ticker_high_si",
                "ticker": ticker,
                "entity_name": f"{ticker} short interest",
                "entity_type": "stock",
                "direction": "SELL",  # high short interest = bearish for the stock
                "quantity": float(row["shares_short"]),
                "price": None,
                "value_usd": float(row["short_pct_float"]) * 1000,  # rough proxy
                "filed_at": filed_at,
                "traded_at": None,
                "raw_data": {
                    "shares_short": float(row["shares_short"]),
                    "shares_short_prior": float(row["shares_short_prior"]),
                    "short_pct_float": float(row["short_pct_float"]),
                    "si_change_pct": float(row["si_change_pct"]),
                    "days_to_cover": float(row["days_to_cover"]),
                },
                "source_id": f"nq_si_ticker_{ticker}_{date_str}",
            })

        self.logger.info(
            f"NQ SI: composite={direction} z={latest.get('si_zscore', 0):.2f} "
            f"| {len(high_si)} high-SI tickers"
        )
        return signals
