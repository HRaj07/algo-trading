"""
Dual Momentum Strategy — Gary Antonacci

Logic:
1. Absolute Momentum: 12-month return > risk-free rate → stocks beat cash
2. Relative Momentum: Pick top N stocks by 12-month return
3. If market (Nifty) 12m return < 0 → go to cash (LIQUIDBEES)

Rebalances monthly on the 1st trading day.
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Optional

import pandas as pd
import numpy as np

from data.fetcher import DataFetcher, TechnicalIndicators
from config import DUAL_MOMENTUM, NIFTY50_TICKERS, DATA

logger = logging.getLogger(__name__)


class DualMomentumStrategy:
    """Gary Antonacci's Dual Momentum adapted for Indian markets."""

    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher
        self.params = DUAL_MOMENTUM
        self.name = "Dual Momentum"
        self.tickers = NIFTY50_TICKERS

    def compute_momentum_scores(
        self, prices: pd.DataFrame, as_of_date: Optional[str] = None
    ) -> pd.Series:
        """Compute 12-month momentum for all tickers."""
        if as_of_date:
            prices = prices.loc[:as_of_date]

        lookback = self.params["lookback_months"] * 21  # ~252 trading days
        if len(prices) < lookback:
            logger.warning(f"Insufficient data: {len(prices)} rows, need {lookback}")
            return pd.Series(dtype=float)

        # 12m momentum excluding last month (skip 21 days to avoid reversal)
        latest = prices.iloc[-1]
        past = prices.iloc[-(lookback + 1)]
        skip = prices.iloc[-21] if len(prices) >= 21 else prices.iloc[-1]

        momentum = (skip / past) - 1  # 12m return, skip last month
        return momentum.sort_values(ascending=False)

    def get_signals(
        self,
        prices: pd.DataFrame,
        benchmark_prices: pd.Series,
        as_of_date: Optional[str] = None,
    ) -> Dict:
        """Generate buy/sell signals.
        
        Returns dict with:
        - selected: list of tickers to hold
        - in_cash: bool (True = go to cash)
        - scores: momentum scores
        """
        if as_of_date:
            prices = prices.loc[:as_of_date]
            benchmark_prices = benchmark_prices.loc[:as_of_date]

        lookback = self.params["lookback_months"] * 21
        risk_free_monthly = (1 + self.params["risk_free_rate"]) ** (1/12) - 1
        risk_free_annual = self.params["risk_free_rate"]

        # 1. Absolute momentum on benchmark (Nifty 50)
        if len(benchmark_prices) >= lookback:
            benchmark_12m = (benchmark_prices.iloc[-21] / benchmark_prices.iloc[-(lookback+1)]) - 1
            absolute_momentum_ok = benchmark_12m > risk_free_annual
        else:
            absolute_momentum_ok = True  # Default to invested

        # If absolute momentum is negative → cash
        if not absolute_momentum_ok:
            logger.info("Dual Momentum: Absolute momentum negative → Cash mode")
            return {
                "selected": [],
                "in_cash": True,
                "scores": pd.Series(dtype=float),
                "benchmark_12m": benchmark_12m,
                "signal_date": prices.index[-1],
            }

        # 2. Relative momentum — pick top N stocks
        momentum_scores = self.compute_momentum_scores(prices)
        momentum_scores = momentum_scores.dropna()

        # Filter: only include stocks with positive momentum
        positive = momentum_scores[momentum_scores > 0]
        top_n = min(self.params["top_n_stocks"], len(positive))

        if top_n == 0:
            logger.info("Dual Momentum: No stocks with positive momentum → Cash")
            return {
                "selected": [],
                "in_cash": True,
                "scores": momentum_scores,
                "benchmark_12m": benchmark_12m,
                "signal_date": prices.index[-1],
            }

        selected = positive.head(top_n).index.tolist()

        logger.info(
            f"Dual Momentum: Selected {len(selected)} stocks | "
            f"Benchmark 12m: {benchmark_12m:.1%} | In cash: False"
        )
        logger.info(f"  Selected: {selected}")

        return {
            "selected": selected,
            "in_cash": False,
            "scores": momentum_scores,
            "benchmark_12m": benchmark_12m,
            "signal_date": prices.index[-1],
        }

    def is_rebalance_day(self, current_date: pd.Timestamp, trading_days: pd.DatetimeIndex) -> bool:
        """Check if today is the 1st trading day of the month."""
        month_start = trading_days[
            (trading_days.month == current_date.month) &
            (trading_days.year == current_date.year)
        ]
        if len(month_start) == 0:
            return False
        return current_date == month_start[0]

    def backtest(
        self,
        prices: pd.DataFrame,
        benchmark: pd.Series,
        initial_capital: float = 1_000_000,
    ) -> pd.DataFrame:
        """Run a vectorized backtest of the Dual Momentum strategy."""
        trading_days = prices.index
        portfolio_value = pd.Series(index=trading_days, dtype=float)
        positions = {}
        capital = initial_capital
        cash = capital
        current_holdings = []

        signals_log = []

        for i, date in enumerate(trading_days):
            if i < 252:  # Need at least 12 months
                portfolio_value[date] = capital
                continue

            is_rebal = self.is_rebalance_day(date, trading_days)

            if is_rebal or i == 252:
                signals = self.get_signals(
                    prices.iloc[:i+1],
                    benchmark.iloc[:i+1]
                )
                new_holdings = signals["selected"]

                # Rebalance
                n = len(new_holdings)
                if n > 0 and not signals["in_cash"]:
                    weight = 1.0 / n
                    positions = {t: weight for t in new_holdings}
                    current_holdings = new_holdings
                else:
                    positions = {}
                    current_holdings = []

                signals_log.append({
                    "date": date,
                    "in_cash": signals["in_cash"],
                    "holdings": new_holdings,
                    "benchmark_12m": signals.get("benchmark_12m", None),
                })

            # Compute portfolio value
            if current_holdings and i > 0:
                portfolio_return = sum(
                    positions.get(t, 0) * 
                    (prices[t].iloc[i] / prices[t].iloc[i-1] - 1)
                    for t in current_holdings
                    if t in prices.columns and prices[t].iloc[i-1] != 0
                )
                capital *= (1 + portfolio_return)

            portfolio_value[date] = capital

        return portfolio_value, pd.DataFrame(signals_log)

    def generate_today_signal(
        self,
        start: str = "2015-01-01",
        end: Optional[str] = None,
    ) -> Dict:
        """Generate today's trading signal."""
        logger.info("Dual Momentum: Fetching data for today's signal...")

        prices = self.fetcher.fetch_close_panel(self.tickers, start, end)
        benchmark = self.fetcher.fetch_index(self.params["benchmark_ticker"], start, end)

        if prices.empty:
            logger.error("No price data fetched")
            return {}

        # Align
        common_idx = prices.index.intersection(benchmark.index)
        prices = prices.loc[common_idx]
        benchmark = benchmark.loc[common_idx]

        return self.get_signals(prices, benchmark)
