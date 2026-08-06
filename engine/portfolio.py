"""
Portfolio Manager
Tracks positions, computes weights, manages rebalancing.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

from config import PORTFOLIO, SYSTEM

logger = logging.getLogger(__name__)


class Portfolio:
    """Portfolio state manager for paper trading."""

    def __init__(
        self,
        initial_capital: float = None,
        state_path: str = "logs/portfolio_state.json",
    ):
        self.state_path = Path(state_path)
        self.params = PORTFOLIO
        self.initial_capital = initial_capital or SYSTEM["initial_capital"]
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load portfolio state from disk."""
        if self.state_path.exists():
            with open(self.state_path) as f:
                state = json.load(f)
            logger.info(
                f"Loaded portfolio: ₹{state.get('cash', 0):,.0f} cash, "
                f"{len(state.get('positions', {}))} positions"
            )
            return state

        # Initialize fresh portfolio
        state = {
            "cash": self.initial_capital,
            "positions": {},   # {ticker: {qty, entry_price, entry_date, strategy}}
            "trade_history": [],
            "last_updated": datetime.now().isoformat(),
            "strategy_allocations": {k: 0.0 for k in PORTFOLIO["strategies"]},
        }
        self._save_state(state)
        logger.info(f"Initialized new portfolio with ₹{self.initial_capital:,.0f}")
        return state

    def _save_state(self, state: Dict = None) -> None:
        """Persist portfolio state to disk."""
        if state is None:
            state = self.state
        state["last_updated"] = datetime.now().isoformat()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(state, f, indent=2, default=str)

    @property
    def cash(self) -> float:
        return self.state["cash"]

    @property
    def positions(self) -> Dict:
        return self.state["positions"]

    def portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """Compute total portfolio value at current prices."""
        pos_value = sum(
            pos["qty"] * current_prices.get(ticker, pos["entry_price"])
            for ticker, pos in self.positions.items()
        )
        return self.cash + pos_value

    def enter_position(
        self,
        ticker: str,
        price: float,
        qty: int,
        strategy: str,
        stop_loss: float = None,
    ) -> bool:
        """Enter a new position (paper trade)."""
        cost = price * qty
        if cost > self.cash:
            logger.warning(f"Insufficient cash: need ₹{cost:,.0f}, have ₹{self.cash:,.0f}")
            # Buy as many as possible
            qty = int(self.cash / price)
            cost = price * qty
            if qty == 0:
                return False

        if ticker in self.positions:
            logger.info(f"Already holding {ticker}, skipping")
            return False

        self.state["cash"] -= cost
        self.state["positions"][ticker] = {
            "qty": qty,
            "entry_price": price,
            "entry_date": datetime.now().date().isoformat(),
            "strategy": strategy,
            "stop_loss": stop_loss or price * 0.95,
            "days_held": 0,
        }

        trade = {
            "action": "BUY",
            "ticker": ticker,
            "qty": qty,
            "price": price,
            "value": cost,
            "date": datetime.now().isoformat(),
            "strategy": strategy,
        }
        self.state["trade_history"].append(trade)
        self._save_state()

        logger.info(f"BUY  {ticker}: {qty} @ ₹{price:.2f} = ₹{cost:,.0f} [{strategy}]")
        return True

    def exit_position(
        self, ticker: str, price: float, reason: str = "signal"
    ) -> Optional[Dict]:
        """Exit an existing position (paper trade)."""
        if ticker not in self.positions:
            logger.warning(f"No position in {ticker}")
            return None

        pos = self.positions[ticker]
        qty = pos["qty"]
        entry = pos["entry_price"]
        proceeds = price * qty
        pnl = (price - entry) * qty
        pnl_pct = (price - entry) / entry * 100

        self.state["cash"] += proceeds
        del self.state["positions"][ticker]

        trade = {
            "action": "SELL",
            "ticker": ticker,
            "qty": qty,
            "price": price,
            "value": proceeds,
            "entry_price": entry,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "date": datetime.now().isoformat(),
            "reason": reason,
            "strategy": pos["strategy"],
        }
        self.state["trade_history"].append(trade)
        self._save_state()

        emoji = "✅" if pnl > 0 else "❌"
        logger.info(
            f"SELL {ticker}: {qty} @ ₹{price:.2f} | "
            f"PnL: ₹{pnl:,.0f} ({pnl_pct:+.1f}%) {emoji} [{reason}]"
        )
        return trade

    def update_days_held(self) -> None:
        """Increment days_held for all positions (call once per day)."""
        for ticker in self.positions:
            self.state["positions"][ticker]["days_held"] = (
                self.state["positions"][ticker].get("days_held", 0) + 1
            )
        self._save_state()

    def get_strategy_positions(self, strategy: str) -> Dict:
        """Get positions belonging to a specific strategy."""
        return {
            k: v for k, v in self.positions.items()
            if v.get("strategy") == strategy
        }

    def get_trade_history_df(self) -> pd.DataFrame:
        """Return trade history as DataFrame."""
        trades = self.state.get("trade_history", [])
        if not trades:
            return pd.DataFrame()
        return pd.DataFrame(trades)

    def summary(self, current_prices: Dict[str, float] = None) -> Dict:
        """Portfolio summary."""
        if current_prices is None:
            current_prices = {}
        total_value = self.portfolio_value(current_prices)
        initial = SYSTEM["initial_capital"]
        return {
            "cash": round(self.cash, 2),
            "n_positions": len(self.positions),
            "total_value": round(total_value, 2),
            "total_return_pct": round((total_value / initial - 1) * 100, 2),
            "positions": list(self.positions.keys()),
            "last_updated": self.state.get("last_updated"),
        }
