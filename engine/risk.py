"""
Risk Management Module
Handles position sizing, portfolio-level risk, and kill switches.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

import pandas as pd
import numpy as np

from config import RISK, PORTFOLIO, SYSTEM

logger = logging.getLogger(__name__)


class RiskManager:
    """Portfolio-level risk management."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.params = RISK
        self.portfolio_params = PORTFOLIO

    # ------------------------------------------------------------------
    # POSITION SIZING
    # ------------------------------------------------------------------

    def kelly_position_size(
        self,
        capital: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        fraction: float = 0.5,
        max_pct: float = 0.10,
    ) -> float:
        """Half-Kelly position sizing."""
        if avg_loss == 0:
            return 0
        odds = avg_win / avg_loss
        kelly = win_rate - (1 - win_rate) / odds
        kelly = max(0, kelly) * fraction  # Half-Kelly
        kelly = min(kelly, max_pct)       # Cap at max
        return capital * kelly

    def atr_position_size(
        self,
        capital: float,
        atr: float,
        atr_multiplier: float = 2.0,
        risk_pct: float = 0.01,
    ) -> int:
        """ATR-based position size (shares)."""
        risk_amount = capital * risk_pct
        stop_distance = atr * atr_multiplier
        if stop_distance == 0:
            return 0
        return int(risk_amount / stop_distance)

    def equal_weight_size(
        self,
        capital: float,
        n_positions: int,
        price: float,
        max_pct: float = 0.10,
    ) -> int:
        """Equal-weight position sizing (shares)."""
        if n_positions == 0 or price == 0:
            return 0
        target_value = min(capital / n_positions, capital * max_pct)
        return int(target_value / price)

    def volatility_scaled_size(
        self,
        capital: float,
        target_vol: float,
        realized_vol: float,
        price: float,
        max_pct: float = 0.10,
    ) -> int:
        """Volatility-scaled position sizing."""
        if realized_vol == 0 or price == 0:
            return 0
        vol_scalar = target_vol / realized_vol
        vol_scalar = min(vol_scalar, 2.0)  # Cap at 2x
        target_value = capital * max_pct * vol_scalar
        return int(target_value / price)

    # ------------------------------------------------------------------
    # PORTFOLIO RISK CHECKS
    # ------------------------------------------------------------------

    def check_kill_switch(self, performance_path: str = "logs/performance.json") -> bool:
        """Returns True if trading should be halted."""
        perf_file = Path(performance_path)
        if not perf_file.exists():
            return False

        try:
            with open(perf_file) as f:
                perf = json.load(f)

            current_value = perf.get("portfolio_value", None)
            peak_value = perf.get("peak_value", None)
            yesterday_value = perf.get("yesterday_value", None)
            initial_capital = perf.get("initial_capital", SYSTEM["initial_capital"])

            if current_value is None:
                return False

            # Check daily loss
            if yesterday_value and yesterday_value > 0:
                daily_loss = (current_value - yesterday_value) / yesterday_value
                if daily_loss < -self.params["daily_loss_limit"]:
                    logger.warning(
                        f"KILL SWITCH: Daily loss {daily_loss:.1%} exceeds "
                        f"limit {self.params['daily_loss_limit']:.1%}"
                    )
                    return True

            # Check total drawdown
            if peak_value and peak_value > 0:
                drawdown = (current_value - peak_value) / peak_value
                if drawdown < -self.params["max_portfolio_drawdown"]:
                    logger.warning(
                        f"KILL SWITCH: Drawdown {drawdown:.1%} exceeds "
                        f"limit {self.params['max_portfolio_drawdown']:.1%}"
                    )
                    return True

        except Exception as e:
            logger.error(f"Error checking kill switch: {e}")

        return False

    def check_position_limits(
        self, proposed_positions: Dict[str, float], capital: float
    ) -> Dict[str, float]:
        """Clip positions that exceed limits."""
        max_pct = self.portfolio_params["max_position_pct"]
        clipped = {}
        for ticker, value in proposed_positions.items():
            pct = value / capital if capital > 0 else 0
            if pct > max_pct:
                clipped[ticker] = capital * max_pct
                logger.debug(f"Clipped {ticker} from {pct:.1%} to {max_pct:.1%}")
            else:
                clipped[ticker] = value
        return clipped

    def compute_portfolio_metrics(
        self, portfolio_values: pd.Series
    ) -> Dict:
        """Compute key portfolio risk metrics."""
        if len(portfolio_values) < 2:
            return {}

        returns = portfolio_values.pct_change().dropna()

        total_return = (portfolio_values.iloc[-1] / portfolio_values.iloc[0]) - 1
        n_years = len(returns) / 252
        cagr = (1 + total_return) ** (1 / max(n_years, 0.01)) - 1

        annual_vol = returns.std() * np.sqrt(252)
        risk_free = 0.065
        sharpe = (cagr - risk_free) / annual_vol if annual_vol > 0 else 0

        # Max drawdown
        roll_max = portfolio_values.cummax()
        drawdown = (portfolio_values - roll_max) / roll_max
        max_dd = drawdown.min()

        # Calmar ratio
        calmar = cagr / abs(max_dd) if max_dd != 0 else 0

        # Win rate (monthly)
        monthly_returns = returns.resample("ME").apply(lambda x: (1 + x).prod() - 1)
        win_rate = (monthly_returns > 0).mean()

        return {
            "total_return": round(total_return * 100, 2),
            "cagr": round(cagr * 100, 2),
            "annual_volatility": round(annual_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown": round(max_dd * 100, 2),
            "calmar_ratio": round(calmar, 3),
            "monthly_win_rate": round(win_rate * 100, 1),
            "n_trading_days": len(returns),
        }

    def update_performance_log(
        self,
        portfolio_value: float,
        log_path: str = "logs/performance.json",
    ) -> None:
        """Update the running performance log."""
        perf_file = Path(log_path)
        perf = {}
        if perf_file.exists():
            with open(perf_file) as f:
                perf = json.load(f)

        perf["yesterday_value"] = perf.get("portfolio_value", portfolio_value)
        perf["portfolio_value"] = portfolio_value
        perf["peak_value"] = max(perf.get("peak_value", 0), portfolio_value)
        perf["initial_capital"] = perf.get("initial_capital", SYSTEM["initial_capital"])
        perf["last_updated"] = datetime.now().isoformat()
        perf["total_return_pct"] = (
            (portfolio_value - perf["initial_capital"]) / perf["initial_capital"] * 100
        )

        with open(perf_file, "w") as f:
            json.dump(perf, f, indent=2)

        logger.info(
            f"Portfolio: ₹{portfolio_value:,.0f} | "
            f"Return: {perf['total_return_pct']:.1f}%"
        )
