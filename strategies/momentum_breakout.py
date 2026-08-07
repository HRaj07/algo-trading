"""
Momentum Breakout Strategy

Logic:
1. Stock makes a NEW 52-week high
2. Volume is > 1.5x its 20-day average (confirms conviction)
3. Price is above 200-day SMA (trend filter)
4. Enter at next open, exit on 2x ATR trailing stop or 20-day low

Rebalances daily — scans for new breakouts.
"""

import logging
from typing import List, Dict, Optional, Tuple

import pandas as pd
import numpy as np

from data.fetcher import DataFetcher, TechnicalIndicators
from config import MOMENTUM_BREAKOUT, ALL_TICKERS, DATA

logger = logging.getLogger(__name__)


class MomentumBreakoutStrategy:
    """52-week high breakout with volume and trend confirmation."""

    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher
        self.params = MOMENTUM_BREAKOUT
        self.name = "Momentum Breakout"
        self.tickers = ALL_TICKERS
        self.ti = TechnicalIndicators()

    def compute_signals(
        self, data_dict: Dict[str, pd.DataFrame], as_of_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Scan all stocks and return breakout signals."""
        signals = []

        for ticker, df in data_dict.items():
            if as_of_date:
                df = df.loc[:as_of_date]

            if len(df) < self.params["lookback_52w"]:
                continue

            signal = self._compute_single_signal(ticker, df)
            if signal:
                signals.append(signal)

        if not signals:
            return pd.DataFrame()

        result = pd.DataFrame(signals)
        # Rank by strength: (price - 52w high) / ATR → 0 for fresh breakouts
        result = result.sort_values("breakout_strength", ascending=False)
        return result

    def _compute_single_signal(
        self, ticker: str, df: pd.DataFrame
    ) -> Optional[Dict]:
        """Compute breakout signal for a single stock."""
        try:
            close = df["close"]
            high = df["high"]
            volume = df["volume"]

            # Skip low-priced stocks
            if close.iloc[-1] < self.params["min_price"]:
                return None

            # 52-week high (252 trading days)
            lookback = self.params["lookback_52w"]
            high_52w = close.rolling(lookback).max().iloc[-2]  # Previous day high
            current = close.iloc[-1]

            # Breakout: current price > previous 52w high
            is_52w_breakout = current >= high_52w * 1.001  # 0.1% buffer

            if not is_52w_breakout:
                return None

            # Volume confirmation
            vol_period = self.params["volume_sma_period"]
            avg_volume = volume.rolling(vol_period).mean().iloc[-1]
            current_volume = volume.iloc[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            volume_ok = volume_ratio >= self.params["volume_multiplier"]

            # Trend filter: price > 200 SMA
            sma_200 = self.ti.sma(close, self.params["trend_filter_sma"]).iloc[-1]
            trend_ok = current > sma_200

            # Supertrend filter: must be in bullish regime
            supertrend_dir = self.ti.supertrend(df, self.params.get("supertrend_period", 10), self.params.get("supertrend_mult", 3.0))
            supertrend_ok = supertrend_dir.iloc[-1] == 1  # Bullish

            # ADX filter: trend must be strong
            adx_val = self.ti.adx(df, self.params.get("adx_period", 14)).iloc[-1]
            adx_ok = adx_val >= self.params.get("adx_threshold", 25)

            if not (volume_ok and trend_ok and supertrend_ok and adx_ok):
                return None

            # ATR-based stop loss
            atr = self.ti.atr(df, self.params["atr_period"]).iloc[-1]
            stop_loss = current - self.params["atr_multiplier"] * atr
            stop_pct = (current - stop_loss) / current

            # Breakout strength = how much above 52w high
            breakout_strength = (current - high_52w) / high_52w

            return {
                "ticker": ticker,
                "signal": "BUY",
                "current_price": round(current, 2),
                "high_52w": round(high_52w, 2),
                "breakout_strength": round(breakout_strength, 4),
                "volume_ratio": round(volume_ratio, 2),
                "atr": round(atr, 2),
                "stop_loss": round(stop_loss, 2),
                "stop_pct": round(stop_pct, 4),
                "sma_200": round(sma_200, 2),
                "supertrend_direction": int(supertrend_dir.iloc[-1]),
                "adx_value": round(adx_val, 1),
                "signal_type": "momentum_breakout",
            }

        except Exception as e:
            logger.debug(f"Error computing signal for {ticker}: {e}")
            return None

    def get_exit_signals(
        self, positions: Dict, data_dict: Dict[str, pd.DataFrame]
    ) -> List[Dict]:
        """Check exit conditions for current positions."""
        exits = []

        for ticker, pos in positions.items():
            if ticker not in data_dict:
                continue

            df = data_dict[ticker]
            close = df["close"]
            current = close.iloc[-1]

            entry_price = pos.get("entry_price", current)
            stop_loss = pos.get("stop_loss", 0)

            # Update trailing stop (20-day low)
            trail_days = self.params["trailing_stop_days"]
            trailing_stop = close.rolling(trail_days).min().iloc[-1]
            new_stop = max(stop_loss, trailing_stop)

            should_exit = current < new_stop
            exit_reason = "trailing_stop" if should_exit else None

            if should_exit:
                exits.append({
                    "ticker": ticker,
                    "signal": "SELL",
                    "reason": exit_reason,
                    "current_price": current,
                    "entry_price": entry_price,
                    "pnl_pct": (current - entry_price) / entry_price,
                })

        return exits

    def generate_today_signal(
        self,
        start: str = "2015-01-01",
        end: Optional[str] = None,
        current_positions: Optional[Dict] = None,
    ) -> Dict:
        """Generate today's breakout signals."""
        logger.info("Momentum Breakout: Fetching data...")

        data_dict = self.fetcher.fetch_ohlcv(self.tickers, start, end)

        # New entries
        entries = self.compute_signals(data_dict)

        # Exits from current positions
        exits = []
        if current_positions:
            exits = self.get_exit_signals(current_positions, data_dict)

        # Limit entries by max positions
        max_new = self.params["max_positions"]
        top_entries = entries.head(max_new).to_dict("records") if not entries.empty else []

        return {
            "entries": top_entries,
            "exits": exits,
            "scan_count": len(data_dict),
            "breakout_count": len(entries),
        }
