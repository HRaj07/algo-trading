"""
Quality + Momentum Strategy

Logic:
1. Universe: ALL_TICKERS (Nifty 500)
2. Momentum proxy: 12-month return skipping the most recent month
3. Quality proxy: Inverse of 20-day volatility (low volatility = stable)
4. Score: 0.6 * momentum_rank + 0.4 * quality_rank
5. Pick top 20 stocks
6. Rebalance monthly on 1st trading day

Since we only have price data, this is practically a Low Volatility + Momentum combo.
"""

import logging
from typing import List, Dict, Optional
import pandas as pd
import numpy as np

from data.fetcher import DataFetcher
from config import QUALITY_MOMENTUM, ALL_TICKERS

logger = logging.getLogger(__name__)

class QualityMomentumStrategy:
    """Quality (Low Volatility) + Momentum Strategy."""

    def __init__(self, fetcher: DataFetcher):
        self.fetcher = fetcher
        self.params = QUALITY_MOMENTUM
        self.name = "Quality Momentum"
        self.tickers = ALL_TICKERS

    def get_signals(
        self,
        prices: pd.DataFrame,
        as_of_date: Optional[str] = None,
    ) -> Dict:
        if as_of_date:
            prices = prices.loc[:as_of_date]

        lookback_momentum = self.params.get("lookback_momentum", 252)
        skip = self.params.get("skip_recent_days", 21)
        top_n = self.params.get("top_n", 20)
        
        if len(prices) < lookback_momentum:
            logger.warning(f"Quality Momentum: Insufficient data. Need {lookback_momentum}")
            return {"selected": [], "scores": {}}

        # 1. Momentum: 12-month return skipping last month
        past = prices.iloc[-(lookback_momentum)]
        recent = prices.iloc[-(skip + 1)] if len(prices) > skip else prices.iloc[-1]
        momentum = (recent / past) - 1
        mom_rank = momentum.rank(pct=True)

        # 2. Quality (Low Volatility): 20-day annualized volatility
        returns_20d = prices.iloc[-21:].pct_change().dropna()
        volatility = returns_20d.std() * np.sqrt(252)
        # Quality rank is inverted volatility (lower vol = higher rank)
        qual_rank = (1 / volatility.replace(0, np.nan)).rank(pct=True)

        # 3. Combined Score
        mom_weight = self.params.get("momentum_weight", 0.6)
        qual_weight = self.params.get("quality_weight", 0.4)
        
        combined_score = mom_weight * mom_rank + qual_weight * qual_rank
        combined_score = combined_score.dropna().sort_values(ascending=False)

        selected = combined_score.head(top_n).index.tolist()

        logger.info(f"Quality Momentum: Selected {len(selected)} stocks.")
        
        return {
            "selected": selected,
            "scores": combined_score.to_dict(),
            "signal_date": prices.index[-1],
        }

    def generate_today_signal(
        self,
        start: str = "2015-01-01",
        end: Optional[str] = None,
    ) -> Dict:
        logger.info("Quality Momentum: Fetching data for today's signal...")
        prices = self.fetcher.fetch_close_panel(self.tickers, start, end)
        if prices.empty:
            logger.error("No price data fetched for Quality Momentum")
            return {}
        return self.get_signals(prices)
