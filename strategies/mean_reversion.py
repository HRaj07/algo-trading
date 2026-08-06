"""
Mean Reversion Strategy (RSI Oversold + Bollinger Band)

Logic:
1. Stock is in uptrend: price > 200-day SMA
2. Short-term oversold: RSI(14) < 30
3. Price near/below lower Bollinger Band
4. Enter on the next open
5. Exit when RSI > 60, price > middle BB, 5% stop loss, or 10-day hold

Only applied to Nifty 50 quality stocks.
"""

import logging
from typing import List, Dict, Optional

import pandas as pd
import numpy as np

from data.fetcher import DataFetcher, TechnicalIndicators
from config import MEAN_REVERSION, NIFTY50_TICKERS

logger = logging.getLogger(__name__)


class MeanReversionStrategy:
    """RSI + Bollinger Band mean reversion on quality large caps."""

    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher
        self.params = MEAN_REVERSION
        self.name = "Mean Reversion"
        self.tickers = NIFTY50_TICKERS
        self.ti = TechnicalIndicators()

    def compute_signals(
        self, data_dict: Dict[str, pd.DataFrame], as_of_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Scan all stocks for mean reversion setups."""
        signals = []

        for ticker, df in data_dict.items():
            if as_of_date:
                df = df.loc[:as_of_date]

            if len(df) < 250:
                continue

            signal = self._compute_single_signal(ticker, df)
            if signal:
                signals.append(signal)

        if not signals:
            return pd.DataFrame()

        result = pd.DataFrame(signals)
        # Rank by most oversold RSI
        result = result.sort_values("rsi", ascending=True)
        return result

    def _compute_single_signal(
        self, ticker: str, df: pd.DataFrame
    ) -> Optional[Dict]:
        """Compute mean reversion signal for single stock."""
        try:
            close = df["close"]
            current = close.iloc[-1]

            # Trend filter: must be above 200 SMA
            sma_200 = self.ti.sma(close, self.params["trend_sma"]).iloc[-1]
            if current <= sma_200:
                return None

            # RSI oversold
            rsi = self.ti.rsi(close, self.params["rsi_period"]).iloc[-1]
            if rsi >= self.params["rsi_oversold"]:
                return None

            # Bollinger Band position
            upper_bb, middle_bb, lower_bb = self.ti.bollinger_bands(
                close,
                self.params["bb_period"],
                self.params["bb_std"]
            )
            bb_position = (current - lower_bb.iloc[-1]) / (
                upper_bb.iloc[-1] - lower_bb.iloc[-1] + 1e-8
            )

            # Additional filter: price near or below lower BB (bb_position < 0.3)
            if bb_position > 0.3:
                return None

            stop_loss_price = current * (1 - self.params["stop_loss_pct"])

            return {
                "ticker": ticker,
                "signal": "BUY",
                "current_price": round(current, 2),
                "rsi": round(rsi, 2),
                "bb_position": round(bb_position, 3),
                "sma_200": round(sma_200, 2),
                "lower_bb": round(lower_bb.iloc[-1], 2),
                "middle_bb": round(middle_bb.iloc[-1], 2),
                "stop_loss": round(stop_loss_price, 2),
                "target": round(middle_bb.iloc[-1], 2),  # Target = middle BB
                "signal_type": "mean_reversion",
            }

        except Exception as e:
            logger.debug(f"Error computing MR signal for {ticker}: {e}")
            return None

    def get_exit_signals(
        self, positions: Dict, data_dict: Dict[str, pd.DataFrame]
    ) -> List[Dict]:
        """Check exit conditions for current MR positions."""
        exits = []

        for ticker, pos in positions.items():
            if ticker not in data_dict:
                continue

            df = data_dict[ticker]
            close = df["close"]
            current = close.iloc[-1]

            entry_price = pos.get("entry_price", current)
            entry_date = pos.get("entry_date")
            days_held = pos.get("days_held", 0)

            # Compute RSI and BB
            rsi = self.ti.rsi(close, self.params["rsi_period"]).iloc[-1]
            _, middle_bb, _ = self.ti.bollinger_bands(
                close, self.params["bb_period"], self.params["bb_std"]
            )

            # Exit conditions
            rsi_exit = rsi >= self.params["rsi_overbought"]
            price_target = current >= middle_bb.iloc[-1]
            stop_loss_hit = current <= entry_price * (1 - self.params["stop_loss_pct"])
            max_hold = days_held >= self.params["max_hold_days"]

            should_exit = rsi_exit or price_target or stop_loss_hit or max_hold

            if should_exit:
                reason = (
                    "rsi_overbought" if rsi_exit else
                    "target_reached" if price_target else
                    "stop_loss" if stop_loss_hit else
                    "max_hold_period"
                )
                exits.append({
                    "ticker": ticker,
                    "signal": "SELL",
                    "reason": reason,
                    "current_price": current,
                    "entry_price": entry_price,
                    "rsi": round(rsi, 2),
                    "pnl_pct": (current - entry_price) / entry_price,
                })

        return exits

    def generate_today_signal(
        self,
        start: str = "2015-01-01",
        end: Optional[str] = None,
        current_positions: Optional[Dict] = None,
    ) -> Dict:
        """Generate today's mean reversion signals."""
        logger.info("Mean Reversion: Fetching data...")

        data_dict = self.fetcher.fetch_ohlcv(self.tickers, start, end)

        entries = self.compute_signals(data_dict)

        exits = []
        if current_positions:
            exits = self.get_exit_signals(current_positions, data_dict)

        max_new = self.params["max_positions"]
        top_entries = entries.head(max_new).to_dict("records") if not entries.empty else []

        return {
            "entries": top_entries,
            "exits": exits,
            "scan_count": len(data_dict),
            "setup_count": len(entries),
        }
