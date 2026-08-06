"""
Backtesting Engine
Runs backtests for all three strategies using vectorbt.
Generates HTML tearsheets and performance metrics.
"""

import json
import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


class Backtester:
    """Strategy backtesting using pandas-based simulation."""

    def __init__(
        self,
        initial_capital: float = 1_000_000,
        commission: float = 0.001,  # 0.1% per trade
        slippage: float = 0.0005,  # 0.05% slippage
        results_dir: str = "backtest_results",
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def run_dual_momentum_backtest(
        self,
        prices: pd.DataFrame,
        benchmark: pd.Series,
        lookback_months: int = 12,
        top_n: int = 5,
        risk_free_rate: float = 0.065,
    ) -> Dict:
        """Backtest Dual Momentum strategy."""
        logger.info("Running Dual Momentum backtest...")
        lookback = lookback_months * 21
        trading_days = prices.index
        capital = self.initial_capital
        portfolio_values = []
        monthly_rebal_dates = []
        signal_log = []

        # Identify 1st trading day of each month
        month_starts = trading_days[
            trading_days.to_series().apply(
                lambda d: d == trading_days[
                    (trading_days.month == d.month) & (trading_days.year == d.year)
                ][0]
            )
        ]

        holdings = {}
        current_tickers = []

        for i, date in enumerate(trading_days):
            if i < lookback:
                portfolio_values.append(capital)
                continue

            is_rebal = date in month_starts

            if is_rebal or i == lookback:
                price_slice = prices.iloc[:i+1]
                bench_slice = benchmark.iloc[:i+1]

                # Absolute momentum
                bench_12m = (bench_slice.iloc[-21] / bench_slice.iloc[-(lookback+1)]) - 1
                abs_ok = bench_12m > risk_free_rate

                if not abs_ok:
                    current_tickers = []
                else:
                    # Relative momentum
                    mom_12m = (
                        price_slice.iloc[-21] / price_slice.iloc[-(lookback+1)] - 1
                    ).dropna().sort_values(ascending=False)
                    pos_mom = mom_12m[mom_12m > 0]
                    n = min(top_n, len(pos_mom))
                    current_tickers = pos_mom.head(n).index.tolist() if n > 0 else []

                signal_log.append({
                    "date": str(date.date()),
                    "in_cash": len(current_tickers) == 0,
                    "holdings": current_tickers,
                    "bench_12m": round(bench_12m * 100, 2),
                })

            # Daily P&L
            if current_tickers and i > 0:
                weights = {t: 1/len(current_tickers) for t in current_tickers}
                daily_ret = sum(
                    weights[t] *
                    (prices[t].iloc[i] / prices[t].iloc[i-1] - 1)
                    for t in current_tickers
                    if t in prices.columns
                )
                # Apply commission on rebalance days
                if is_rebal:
                    daily_ret -= self.commission * 2  # Round-trip cost
                capital *= (1 + daily_ret)

            portfolio_values.append(capital)

        pv_series = pd.Series(portfolio_values, index=trading_days)
        metrics = self._compute_metrics(pv_series, benchmark, "Dual Momentum")
        metrics["signal_log"] = signal_log
        return metrics

    def run_breakout_backtest(
        self,
        data_dict: Dict[str, pd.DataFrame],
        lookback_52w: int = 252,
        volume_mult: float = 1.5,
        atr_mult: float = 2.0,
        max_positions: int = 8,
    ) -> Dict:
        """Backtest 52-week high breakout strategy."""
        logger.info("Running Momentum Breakout backtest...")

        # Use the full date range from price data
        all_dates = pd.DatetimeIndex(sorted(set().union(
            *[df.index.tolist() for df in data_dict.values()]
        )))

        capital = self.initial_capital
        portfolio_values = []
        positions = {}  # {ticker: {entry_price, qty, stop_loss}}

        for i, date in enumerate(all_dates):
            if i < lookback_52w:
                portfolio_values.append(capital)
                continue

            # --- Check exits ---
            to_exit = []
            for ticker, pos in positions.items():
                if ticker not in data_dict:
                    continue
                df = data_dict[ticker]
                if date not in df.index:
                    continue
                close = df.loc[date, "close"]
                trail_low = df.loc[:date, "close"].rolling(20).min().iloc[-1]
                if close < max(pos["stop_loss"], trail_low):
                    to_exit.append(ticker)

            for ticker in to_exit:
                pos = positions.pop(ticker)
                df = data_dict[ticker]
                if date in df.index:
                    exit_price = df.loc[date, "close"] * (1 - self.slippage)
                    proceeds = pos["qty"] * exit_price
                    capital += proceeds - pos["qty"] * pos["entry_price"]

            # --- Check entries ---
            if len(positions) < max_positions:
                for ticker, df in data_dict.items():
                    if ticker in positions:
                        continue
                    if date not in df.index:
                        continue

                    sub = df.loc[:date]
                    if len(sub) < lookback_52w:
                        continue

                    close = sub["close"]
                    volume = sub["volume"]

                    high_52w = close.rolling(lookback_52w).max().iloc[-2]
                    current = close.iloc[-1]
                    vol_ratio = volume.iloc[-1] / volume.rolling(20).mean().iloc[-1]
                    sma200 = close.rolling(200).mean().iloc[-1]

                    if (
                        current >= high_52w * 1.001
                        and vol_ratio >= volume_mult
                        and current > sma200
                    ):
                        # High-True Range
                        prev_close = close.iloc[-2]
                        tr = max(
                            sub["high"].iloc[-1] - sub["low"].iloc[-1],
                            abs(sub["high"].iloc[-1] - prev_close),
                            abs(sub["low"].iloc[-1] - prev_close)
                        )
                        atr = tr  # Simplified; full ATR would use EWM
                        entry = current * (1 + self.slippage)
                        stop = entry - atr_mult * atr

                        slot_value = capital / max_positions
                        qty = int(slot_value / entry)

                        if qty > 0 and slot_value <= capital:
                            capital -= qty * entry
                            positions[ticker] = {
                                "entry_price": entry,
                                "qty": qty,
                                "stop_loss": stop,
                            }

            # Portfolio value = cash + mark-to-market positions
            pos_value = sum(
                p["qty"] * data_dict[t].loc[date, "close"]
                if t in data_dict and date in data_dict[t].index
                else p["qty"] * p["entry_price"]
                for t, p in positions.items()
            )
            portfolio_values.append(capital + pos_value)

        pv = pd.Series(portfolio_values, index=all_dates)
        return self._compute_metrics(pv, pd.Series(dtype=float), "Momentum Breakout")

    def run_mean_reversion_backtest(
        self,
        data_dict: Dict[str, pd.DataFrame],
        rsi_period: int = 14,
        rsi_entry: float = 30,
        rsi_exit: float = 60,
        stop_pct: float = 0.05,
        max_hold: int = 10,
    ) -> Dict:
        """Backtest Mean Reversion strategy."""
        logger.info("Running Mean Reversion backtest...")

        from data.fetcher import TechnicalIndicators
        ti = TechnicalIndicators()

        all_dates = pd.DatetimeIndex(sorted(set().union(
            *[df.index.tolist() for df in data_dict.values()]
        )))

        capital = self.initial_capital
        portfolio_values = []
        positions = {}

        for i, date in enumerate(all_dates):
            if i < 250:
                portfolio_values.append(capital)
                continue

            # --- Check exits ---
            to_exit = []
            for ticker, pos in positions.items():
                if ticker not in data_dict or date not in data_dict[ticker].index:
                    continue
                close = data_dict[ticker].loc[:date, "close"]
                current = close.iloc[-1]
                rsi_val = ti.rsi(close, rsi_period).iloc[-1]
                days_held = pos.get("days_held", 0) + 1

                if (
                    rsi_val >= rsi_exit
                    or current <= pos["entry_price"] * (1 - stop_pct)
                    or days_held >= max_hold
                ):
                    to_exit.append(ticker)
                else:
                    pos["days_held"] = days_held

            for ticker in to_exit:
                pos = positions.pop(ticker)
                df = data_dict[ticker]
                if date in df.index:
                    exit_price = df.loc[date, "close"] * (1 - self.slippage)
                    proceeds = pos["qty"] * exit_price
                    capital += proceeds - pos["qty"] * pos["entry_price"]

            # --- Check entries ---
            max_pos = 3
            if len(positions) < max_pos:
                for ticker, df in data_dict.items():
                    if ticker in positions or date not in df.index:
                        continue
                    sub = df.loc[:date]
                    if len(sub) < 250:
                        continue

                    close = sub["close"]
                    current = close.iloc[-1]
                    sma200 = close.rolling(200).mean().iloc[-1]
                    if current <= sma200:
                        continue

                    rsi_val = ti.rsi(close, rsi_period).iloc[-1]
                    if rsi_val >= rsi_entry:
                        continue

                    entry = current * (1 + self.slippage)
                    slot_value = capital / max_pos
                    qty = int(slot_value / entry)
                    if qty > 0 and slot_value <= capital:
                        capital -= qty * entry
                        positions[ticker] = {
                            "entry_price": entry,
                            "qty": qty,
                            "days_held": 0,
                        }

            pos_value = sum(
                p["qty"] * data_dict[t].loc[date, "close"]
                if t in data_dict and date in data_dict[t].index
                else p["qty"] * p["entry_price"]
                for t, p in positions.items()
            )
            portfolio_values.append(capital + pos_value)

        pv = pd.Series(portfolio_values, index=all_dates)
        return self._compute_metrics(pv, pd.Series(dtype=float), "Mean Reversion")

    def _compute_metrics(
        self,
        portfolio_values: pd.Series,
        benchmark: pd.Series,
        strategy_name: str,
    ) -> Dict:
        """Compute comprehensive backtest metrics."""
        pv = portfolio_values.dropna()
        returns = pv.pct_change().dropna()

        if len(returns) < 10:
            return {"strategy": strategy_name, "error": "Insufficient data"}

        total_ret = (pv.iloc[-1] / pv.iloc[0]) - 1
        n_years = len(returns) / 252
        cagr = (1 + total_ret) ** (1 / max(n_years, 0.01)) - 1
        annual_vol = returns.std() * np.sqrt(252)
        risk_free = 0.065
        sharpe = (cagr - risk_free) / annual_vol if annual_vol > 0 else 0

        roll_max = pv.cummax()
        drawdown = (pv - roll_max) / roll_max
        max_dd = drawdown.min()
        calmar = cagr / abs(max_dd) if max_dd != 0 else 0

        # Benchmark metrics
        bench_cagr = None
        if len(benchmark) > 10:
            bench_aligned = benchmark.reindex(pv.index, method="ffill").dropna()
            if len(bench_aligned) > 10:
                b_ret = (bench_aligned.iloc[-1] / bench_aligned.iloc[0]) - 1
                b_years = len(bench_aligned) / 252
                bench_cagr = round(((1 + b_ret) ** (1 / max(b_years, 0.01)) - 1) * 100, 2)

        result = {
            "strategy": strategy_name,
            "initial_capital": self.initial_capital,
            "final_value": round(pv.iloc[-1], 2),
            "total_return_pct": round(total_ret * 100, 2),
            "cagr_pct": round(cagr * 100, 2),
            "annual_volatility_pct": round(annual_vol * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "calmar_ratio": round(calmar, 3),
            "benchmark_cagr_pct": bench_cagr,
            "alpha_pct": round(cagr * 100 - (bench_cagr or 0), 2),
            "start_date": str(pv.index[0].date()),
            "end_date": str(pv.index[-1].date()),
            "n_years": round(n_years, 1),
            "portfolio_values": pv,
        }

        # Save JSON
        save_path = self.results_dir / f"{strategy_name.lower().replace(' ', '_')}_results.json"
        save_data = {k: v for k, v in result.items() if k != "portfolio_values"}
        with open(save_path, "w") as f:
            json.dump(save_data, f, indent=2)

        logger.info(
            f"\n{'='*50}\n"
            f"Strategy: {strategy_name}\n"
            f"CAGR: {cagr*100:.1f}% | Sharpe: {sharpe:.2f} | MaxDD: {max_dd*100:.1f}%\n"
            f"Benchmark CAGR: {bench_cagr or 'N/A'}%\n"
            f"{'='*50}"
        )

        return result

    def generate_tearsheet(
        self, backtest_results: List[Dict], output_path: str = "backtest_results/tearsheet.html"
    ) -> str:
        """Generate HTML tearsheet for backtest results."""
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[
                "Portfolio Value Growth",
                "Strategy CAGR Comparison",
                "Risk Metrics",
                "Monthly Returns Heatmap",
            ],
            specs=[[{"type": "scatter"}, {"type": "bar"}],
                   [{"type": "bar"}, {"type": "heatmap"}]],
        )

        colors = ["#00D4FF", "#FF6B6B", "#4ECDC4", "#45B7D1"]

        for idx, result in enumerate(backtest_results):
            if "portfolio_values" not in result:
                continue
            pv = result["portfolio_values"]
            normalized = pv / pv.iloc[0] * 100

            fig.add_trace(
                go.Scatter(
                    x=pv.index, y=normalized,
                    name=result["strategy"],
                    line=dict(color=colors[idx % len(colors)], width=2),
                ),
                row=1, col=1
            )

        # CAGR bar
        strategies = [r["strategy"] for r in backtest_results if "cagr_pct" in r]
        cagrs = [r["cagr_pct"] for r in backtest_results if "cagr_pct" in r]
        bench_cagr = next((r["benchmark_cagr_pct"] for r in backtest_results if r.get("benchmark_cagr_pct")), 12)
        strategies.append("Nifty 50 (Benchmark)")
        cagrs.append(bench_cagr or 12)

        fig.add_trace(
            go.Bar(x=strategies, y=cagrs, marker_color=colors[:len(strategies)], name="CAGR %"),
            row=1, col=2
        )

        # Risk metrics
        risk_metrics = ["sharpe_ratio", "calmar_ratio", "max_drawdown_pct"]
        for metric in risk_metrics:
            vals = [r.get(metric, 0) for r in backtest_results if metric in r]
            strats = [r["strategy"] for r in backtest_results if metric in r]
            if vals:
                fig.add_trace(
                    go.Bar(x=strats, y=vals, name=metric.replace("_", " ").title()),
                    row=2, col=1
                )

        fig.update_layout(
            title="Algo Trading System — Backtest Tearsheet",
            template="plotly_dark",
            height=800,
            showlegend=True,
            font=dict(family="Inter, sans-serif"),
        )

        html_content = fig.to_html(full_html=True)
        with open(output_path, "w") as f:
            f.write(html_content)

        logger.info(f"Tearsheet saved: {output_path}")
        return output_path
