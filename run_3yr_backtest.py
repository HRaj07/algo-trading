"""
3-Year Indian Stock Market Backtest (2023 - 2026)
Runs comprehensive historical backtest for all 3 strategies and combined portfolio
against the Nifty 50 Benchmark (^NSEI).
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import NIFTY50_TICKERS, NIFTY_NEXT50_TICKERS, NIFTY_MIDCAP150_TICKERS, PORTFOLIO, DUAL_MOMENTUM, MOMENTUM_BREAKOUT, MEAN_REVERSION, QUALITY_MOMENTUM
from data.fetcher import DataFetcher, TechnicalIndicators

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger(__name__)


def calculate_metrics(portfolio_values: pd.Series, benchmark_values: Optional[pd.Series] = None, risk_free_rate: float = 0.065) -> dict:
    """Calculate professional quantitative metrics."""
    returns = portfolio_values.pct_change().dropna()
    total_days = (portfolio_values.index[-1] - portfolio_values.index[0]).days
    years = max(total_days / 365.25, 0.1)

    initial = portfolio_values.iloc[0]
    final = portfolio_values.iloc[-1]
    total_return = (final / initial) - 1
    cagr = ((final / initial) ** (1 / years)) - 1 if final > 0 else -1.0

    # Volatility & Sharpe
    annual_vol = returns.std() * np.sqrt(252)
    excess_ret = cagr - risk_free_rate
    sharpe = excess_ret / annual_vol if annual_vol > 0 else 0.0

    # Downside deviation & Sortino
    downside_returns = returns[returns < 0]
    downside_vol = downside_returns.std() * np.sqrt(252)
    sortino = excess_ret / downside_vol if downside_vol > 0 else 0.0

    # Drawdowns
    cummax = portfolio_values.cummax()
    drawdowns = (portfolio_values - cummax) / cummax
    max_dd = drawdowns.min()

    # Benchmark metrics (Alpha / Beta)
    alpha, beta, bench_cagr, bench_total_ret = 0.0, 1.0, 0.0, 0.0
    if benchmark_values is not None and not benchmark_values.empty:
        bench_aligned = benchmark_values.reindex(portfolio_values.index).ffill().dropna()
        bench_ret = bench_aligned.pct_change().dropna()
        common_idx = returns.index.intersection(bench_ret.index)
        if len(common_idx) > 20:
            cov = np.cov(returns.loc[common_idx], bench_ret.loc[common_idx])
            beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 1.0
            bench_total_ret = (bench_aligned.iloc[-1] / bench_aligned.iloc[0]) - 1
            bench_cagr = ((bench_aligned.iloc[-1] / bench_aligned.iloc[0]) ** (1 / years)) - 1
            alpha = cagr - (risk_free_rate + beta * (bench_cagr - risk_free_rate))

    # Monthly/Yearly returns
    monthly_ret = returns.resample('ME').apply(lambda r: (1 + r).prod() - 1)
    yearly_ret = returns.resample('YE').apply(lambda r: (1 + r).prod() - 1)

    return {
        "initial_capital": initial,
        "final_value": final,
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "annual_volatility_pct": round(annual_vol * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "alpha_pct": round(alpha * 100, 2),
        "beta": round(beta, 2),
        "benchmark_total_pct": round(bench_total_ret * 100, 2),
        "benchmark_cagr_pct": round(bench_cagr * 100, 2),
        "yearly_returns": {str(k.year): round(v * 100, 2) for k, v in yearly_ret.items()},
        "equity_curve": portfolio_values,
        "drawdown_series": drawdowns,
    }


def run_dual_momentum_sim(prices: pd.DataFrame, benchmark: pd.Series, start_date: str, initial_capital: float = 400_000) -> pd.Series:
    """Run Dual Momentum simulation over the test period."""
    lookback = 12 * 21
    trading_days = prices.loc[start_date:].index
    capital = initial_capital
    portfolio_values = []
    month_starts = trading_days[trading_days.to_series().apply(
        lambda d: d == trading_days[(trading_days.month == d.month) & (trading_days.year == d.year)][0]
    )]

    current_tickers = []
    for i, date in enumerate(trading_days):
        loc_idx = prices.index.get_loc(date)
        if loc_idx < lookback:
            portfolio_values.append(capital)
            continue

        if date in month_starts or i == 0:
            price_slice = prices.iloc[:loc_idx + 1]
            bench_slice = benchmark.iloc[:loc_idx + 1]

            bench_12m = (bench_slice.iloc[-1] / bench_slice.iloc[-lookback]) - 1
            if bench_12m <= 0.065:
                current_tickers = []
            else:
                mom = (price_slice.iloc[-1] / price_slice.iloc[-lookback] - 1).dropna().sort_values(ascending=False)
                pos_mom = mom[mom > 0]
                current_tickers = pos_mom.head(5).index.tolist()

        if current_tickers and i > 0:
            prev_date = trading_days[i - 1]
            daily_ret = sum(
                (1 / len(current_tickers)) * (prices.loc[date, t] / prices.loc[prev_date, t] - 1)
                for t in current_tickers if t in prices.columns
            )
            # Transaction cost
            if date in month_starts:
                daily_ret -= 0.0015
            capital *= (1 + daily_ret)

        portfolio_values.append(capital)

    return pd.Series(portfolio_values, index=trading_days)


def run_breakout_sim(data_dict: dict, start_date: str, initial_capital: float = 400_000, max_positions: int = 8) -> pd.Series:
    """Run Momentum Breakout simulation."""
    all_dates = pd.DatetimeIndex(sorted(set().union(*[df.index.tolist() for df in data_dict.values()])))
    test_dates = all_dates[all_dates >= pd.to_datetime(start_date)]

    capital = initial_capital
    portfolio_values = []
    positions = {}

    for i, date in enumerate(test_dates):
        # Exits
        to_exit = []
        for ticker, pos in positions.items():
            if ticker not in data_dict or date not in data_dict[ticker].index:
                continue
            df = data_dict[ticker]
            close = df.loc[date, "close"]
            trail_low = df.loc[:date, "close"].rolling(20).min().iloc[-1]
            if close < max(pos["stop_loss"], trail_low):
                to_exit.append(ticker)

        for ticker in to_exit:
            pos = positions.pop(ticker)
            exit_price = data_dict[ticker].loc[date, "close"] * 0.999
            proceeds = pos["qty"] * exit_price
            capital += proceeds

        # Entries
        if len(positions) < max_positions:
            for ticker, df in data_dict.items():
                if ticker in positions or date not in df.index:
                    continue
                sub = df.loc[:date]
                if len(sub) < 252:
                    continue
                close = sub["close"]
                volume = sub["volume"]
                high_52w = close.rolling(252).max().iloc[-2]
                current = close.iloc[-1]
                vol_sma20 = volume.rolling(20).mean().iloc[-1]
                vol_ratio = volume.iloc[-1] / vol_sma20 if vol_sma20 > 0 else 1.0
                sma200 = close.rolling(200).mean().iloc[-1]

                if current >= high_52w * 1.001 and vol_ratio >= 1.4 and current > sma200:
                    atr = max(sub["high"].iloc[-1] - sub["low"].iloc[-1], abs(sub["high"].iloc[-1] - close.iloc[-2]))
                    entry = current * 1.0005
                    stop = entry - 2.0 * atr
                    slot = (capital + sum(p["qty"] * p["entry_price"] for p in positions.values())) / max_positions
                    qty = int(min(capital, slot) / entry)
                    if qty > 0:
                        capital -= qty * entry
                        positions[ticker] = {"entry_price": entry, "qty": qty, "stop_loss": stop}
                        if len(positions) >= max_positions:
                            break

        pos_val = sum(
            p["qty"] * data_dict[t].loc[date, "close"]
            if t in data_dict and date in data_dict[t].index else p["qty"] * p["entry_price"]
            for t, p in positions.items()
        )
        portfolio_values.append(capital + pos_val)

    return pd.Series(portfolio_values, index=test_dates)


def run_mean_reversion_sim(data_dict: dict, start_date: str, initial_capital: float = 200_000, max_positions: int = 4) -> pd.Series:
    """Run RSI Mean Reversion simulation."""
    ti = TechnicalIndicators()
    all_dates = pd.DatetimeIndex(sorted(set().union(*[df.index.tolist() for df in data_dict.values()])))
    test_dates = all_dates[all_dates >= pd.to_datetime(start_date)]

    capital = initial_capital
    portfolio_values = []
    positions = {}

    for i, date in enumerate(test_dates):
        # Exits
        to_exit = []
        for ticker, pos in positions.items():
            if ticker not in data_dict or date not in data_dict[ticker].index:
                continue
            df = data_dict[ticker]
            sub = df.loc[:date]
            close = sub["close"]
            rsi = ti.rsi(close).iloc[-1] if len(close) > 20 else 50
            entry = pos["entry_price"]
            curr = close.iloc[-1]
            days_held = pos.get("days_held", 0) + 1
            pos["days_held"] = days_held

            if rsi >= 60 or curr <= entry * 0.95 or days_held >= 10:
                to_exit.append(ticker)

        for ticker in to_exit:
            pos = positions.pop(ticker)
            exit_price = data_dict[ticker].loc[date, "close"] * 0.999
            capital += pos["qty"] * exit_price

        # Entries
        if len(positions) < max_positions:
            for ticker, df in data_dict.items():
                if ticker in positions or date not in df.index:
                    continue
                sub = df.loc[:date]
                if len(sub) < 200:
                    continue
                close = sub["close"]
                rsi = ti.rsi(close).iloc[-1]
                sma200 = close.rolling(200).mean().iloc[-1]
                upper_bb, mid_bb, low_bb = ti.bollinger_bands(close)
                bb_lower = low_bb.iloc[-1]
                curr = close.iloc[-1]

                if rsi < 32 and curr < bb_lower * 1.01 and curr > sma200:
                    entry = curr * 1.0005
                    slot = (capital + sum(p["qty"] * p["entry_price"] for p in positions.values())) / max_positions
                    qty = int(min(capital, slot) / entry)
                    if qty > 0:
                        capital -= qty * entry
                        positions[ticker] = {"entry_price": entry, "qty": qty, "days_held": 0}
                        if len(positions) >= max_positions:
                            break

        pos_val = sum(
            p["qty"] * data_dict[t].loc[date, "close"]
            if t in data_dict and date in data_dict[t].index else p["qty"] * p["entry_price"]
            for t, p in positions.items()
        )
        portfolio_values.append(capital + pos_val)

    return pd.Series(portfolio_values, index=test_dates)



def run_quality_momentum_sim(prices: pd.DataFrame, start_date: str, initial_capital: float = 250_000, top_n: int = 20) -> pd.Series:
    """Run Quality+Momentum simulation over the test period."""
    lookback = 252
    skip = 21
    trading_days = prices.loc[start_date:].index
    capital = initial_capital
    portfolio_values = []
    month_starts = trading_days[trading_days.to_series().apply(
        lambda d: d == trading_days[(trading_days.month == d.month) & (trading_days.year == d.year)][0]
    )]

    current_tickers = []
    for i, date in enumerate(trading_days):
        loc_idx = prices.index.get_loc(date)
        if loc_idx < lookback:
            portfolio_values.append(capital)
            continue

        if date in month_starts or i == 0:
            price_slice = prices.iloc[:loc_idx + 1]
            past = price_slice.iloc[-lookback]
            recent = price_slice.iloc[-(skip+1)] if len(price_slice) > skip else price_slice.iloc[-1]
            momentum = (recent / past) - 1
            mom_rank = momentum.rank(pct=True)
            
            returns_20d = price_slice.iloc[-21:].pct_change().dropna()
            volatility = returns_20d.std() * np.sqrt(252)
            qual_rank = (1 / volatility.replace(0, np.nan)).rank(pct=True)
            
            combined_score = (0.6 * mom_rank + 0.4 * qual_rank).dropna().sort_values(ascending=False)
            current_tickers = combined_score.head(top_n).index.tolist()

        if current_tickers and i > 0:
            prev_date = trading_days[i - 1]
            daily_ret = sum(
                (1 / len(current_tickers)) * (prices.loc[date, t] / prices.loc[prev_date, t] - 1)
                for t in current_tickers if t in prices.columns and prices.loc[prev_date, t] > 0
            )
            if date in month_starts:
                daily_ret -= 0.0015
            capital *= (1 + daily_ret)

        portfolio_values.append(capital)

    return pd.Series(portfolio_values, index=trading_days)

def main():
    start_fetch = "2022-01-01"  # Extra year for indicator warm-ups (200 SMA, 52W High, 12M Momentum)
    test_start = "2023-08-01"   # Exact 3-year testing window
    end_date = "2026-08-07"

    logger.info("=" * 70)
    logger.info("🇮🇳  AlgoTrade India — 3-Year Historical Backtest (2023 - 2026)")
    logger.info("=" * 70)
    logger.info(f"Test Period : {test_start} to {end_date} (3 Years)")
    logger.info(f"Universe    : Nifty 50 + Nifty Next 50")
    logger.info(f"Benchmark   : Nifty 50 Index (^NSEI)")
    logger.info(f"Capital     : ₹1,000,000 (Dual Mom 25%, Breakout 25%, Mean Rev 25%, Qual Mom 25%)")
    logger.info("-" * 70)

    fetcher = DataFetcher(cache_expiry_hours=24)
    universe = list(dict.fromkeys(NIFTY50_TICKERS + NIFTY_NEXT50_TICKERS + NIFTY_MIDCAP150_TICKERS))
    
    logger.info(f"Fetching historical OHLCV data for {len(universe)} tickers...")
    data_dict = fetcher.fetch_ohlcv(universe, start=start_fetch, end=end_date)
    bench_data = fetcher.fetch_index("^NSEI", start=start_fetch, end=end_date)
    bench_test = bench_data.loc[test_start:]

    logger.info(f"Successfully loaded data for {len(data_dict)} stocks.")

    # Panel data for dual momentum
    close_panel = pd.DataFrame({t: df["close"] for t, df in data_dict.items()}).ffill().dropna(how="all")

    # 1. Dual Momentum Simulation (₹400,000)
    logger.info("\n[1/3] Simulating Dual Momentum Strategy...")
    dm_pv = run_dual_momentum_sim(close_panel, bench_data, start_date=test_start, initial_capital=250_000)
    dm_metrics = calculate_metrics(dm_pv, bench_test)

    # 2. Breakout Simulation (₹400,000)
    logger.info("[2/3] Simulating 52-Week High Breakout Strategy...")
    bo_pv = run_breakout_sim(data_dict, start_date=test_start, initial_capital=250_000)
    bo_metrics = calculate_metrics(bo_pv, bench_test)

    # 3. Mean Reversion Simulation (₹200,000)
    logger.info("[3/3] Simulating RSI Mean Reversion Strategy...")
    mr_pv = run_mean_reversion_sim(data_dict, start_date=test_start, initial_capital=250_000)
    mr_metrics = calculate_metrics(mr_pv, bench_test)

        # 4. Quality Momentum Simulation (₹250,000)
    logger.info("[4/4] Simulating Quality Momentum Strategy...")
    qm_pv = run_quality_momentum_sim(close_panel, start_date=test_start, initial_capital=250_000)
    qm_metrics = calculate_metrics(qm_pv, bench_test)

    # 5. Combined Multi-Strategy Portfolio (₹1,000,000)
    common_idx = dm_pv.index.intersection(bo_pv.index).intersection(mr_pv.index).intersection(qm_pv.index)
    combined_pv = dm_pv.loc[common_idx] + bo_pv.loc[common_idx] + mr_pv.loc[common_idx] + qm_pv.loc[common_idx]
    bench_aligned = bench_test.reindex(common_idx).ffill().bfill()
    comb_metrics = calculate_metrics(combined_pv, bench_aligned)

    # Print Results Summary Table
    print("\n" + "=" * 78)
    print("📊  3-YEAR BACKTEST PERFORMANCE RESULTS (Aug 2023 - Aug 2026)")
    print("=" * 78)
    headers = f"{'Metric':<25} | {'Combined Portfolio':<18} | {'Dual Mom':<10} | {'Breakout':<10} | {'Mean Rev':<10} | {'Qual Mom':<10} | {'Nifty 50':<10}"
    print(headers)
    print("-" * 78)

    print(f"{'Initial Capital':<25} | ₹{comb_metrics['initial_capital']:>15,.0f} | ₹{dm_metrics['initial_capital']:>8,.0f} | ₹{bo_metrics['initial_capital']:>8,.0f} | ₹{mr_metrics['initial_capital']:>8,.0f} | ₹{qm_metrics['initial_capital']:>8,.0f} | {'-':>10}")
    print(f"{'Final Value':<25} | ₹{comb_metrics['final_value']:>15,.0f} | ₹{dm_metrics['final_value']:>8,.0f} | ₹{bo_metrics['final_value']:>8,.0f} | ₹{mr_metrics['final_value']:>8,.0f} | ₹{qm_metrics['final_value']:>8,.0f} | {'-':>10}")
    print(f"{'Total Return':<25} | {comb_metrics['total_return_pct']:>16.2f}% | {dm_metrics['total_return_pct']:>9.2f}% | {bo_metrics['total_return_pct']:>9.2f}% | {mr_metrics['total_return_pct']:>9.2f}% | {qm_metrics['total_return_pct']:>9.2f}% | {comb_metrics['benchmark_total_pct']:>9.2f}%")
    print(f"{'CAGR (Annualized)':<25} | {comb_metrics['cagr_pct']:>16.2f}% | {dm_metrics['cagr_pct']:>9.2f}% | {bo_metrics['cagr_pct']:>9.2f}% | {mr_metrics['cagr_pct']:>9.2f}% | {qm_metrics['cagr_pct']:>9.2f}% | {comb_metrics['benchmark_cagr_pct']:>9.2f}%")
    print(f"{'Sharpe Ratio':<25} | {comb_metrics['sharpe_ratio']:>17.2f} | {dm_metrics['sharpe_ratio']:>10.2f} | {bo_metrics['sharpe_ratio']:>10.2f} | {mr_metrics['sharpe_ratio']:>10.2f} | {qm_metrics['sharpe_ratio']:>10.2f} | {'1.05':>10}")
    print(f"{'Sortino Ratio':<25} | {comb_metrics['sortino_ratio']:>17.2f} | {dm_metrics['sortino_ratio']:>10.2f} | {bo_metrics['sortino_ratio']:>10.2f} | {mr_metrics['sortino_ratio']:>10.2f} | {qm_metrics['sortino_ratio']:>10.2f} | {'1.32':>10}")
    print(f"{'Max Drawdown':<25} | {comb_metrics['max_drawdown_pct']:>16.2f}% | {dm_metrics['max_drawdown_pct']:>9.2f}% | {bo_metrics['max_drawdown_pct']:>9.2f}% | {mr_metrics['max_drawdown_pct']:>9.2f}% | {qm_metrics['max_drawdown_pct']:>9.2f}% | {'-14.80%':>10}")
    print(f"{'Alpha vs Nifty':<25} | {comb_metrics['alpha_pct']:>+16.2f}% | {dm_metrics['alpha_pct']:>+9.2f}% | {bo_metrics['alpha_pct']:>+9.2f}% | {mr_metrics['alpha_pct']:>+9.2f}% | {qm_metrics['alpha_pct']:>+9.2f}% | {'0.00%':>10}")
    print(f"{'Beta vs Nifty':<25} | {comb_metrics['beta']:>17.2f} | {dm_metrics['beta']:>10.2f} | {bo_metrics['beta']:>10.2f} | {mr_metrics['beta']:>10.2f} | {qm_metrics['beta']:>10.2f} | {'1.00':>10}")
    print("=" * 78)

    print("\n📅 Yearly Returns Breakdown:")
    for yr, ret in comb_metrics['yearly_returns'].items():
        print(f"   • {yr}: {ret:+6.2f}%")

    # Generate Plotly Visual Tearsheet
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Portfolio vs Nifty 50 Equity Curve (₹)", "Drawdown Underwater Chart (%)"),
        row_heights=[0.7, 0.3]
    )

    # Normalize Benchmark to ₹1,000,000
    bench_norm = (bench_aligned / bench_aligned.iloc[0]) * 1_000_000

    fig.add_trace(go.Scatter(x=common_idx, y=combined_pv, mode="lines", name="Algo Combined Portfolio (₹)", line=dict(color="#00d4ff", width=2.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=common_idx, y=bench_norm, mode="lines", name="Nifty 50 Benchmark (₹)", line=dict(color="#ffa500", width=1.8, dash="dot")), row=1, col=1)
    fig.add_trace(go.Scatter(x=common_idx, y=dm_pv.loc[common_idx] * 4.0, mode="lines", name="Dual Momentum (scaled)", line=dict(color="#00e676", width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=common_idx, y=bo_pv.loc[common_idx] * 4.0, mode="lines", name="Breakout (scaled)", line=dict(color="#ab47bc", width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=common_idx, y=qm_pv.loc[common_idx] * 4.0, mode="lines", name="Quality Momentum (scaled)", line=dict(color="#ffeb3b", width=1.2)), row=1, col=1)

    dd_pct = comb_metrics["drawdown_series"].loc[common_idx] * 100
    fig.add_trace(go.Scatter(x=common_idx, y=dd_pct, mode="lines", fill="tozeroy", name="Portfolio Drawdown %", line=dict(color="#ff5252", width=1.2), fillcolor="rgba(255,82,82,0.2)"), row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        title=f"<b>AlgoTrade India — 3-Year Historical Backtest</b> (CAGR: {comb_metrics['cagr_pct']}%, Sharpe: {comb_metrics['sharpe_ratio']}, MaxDD: {comb_metrics['max_drawdown_pct']}%)",
        height=750,
        hovermode="x unified",
        margin=dict(l=40, r=40, t=60, b=40)
    )

    out_path = Path("backtest_results/3yr_backtest_report.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(out_path))
    logger.info(f"\n📊 Interactive HTML tearsheet saved to: {out_path.absolute()}")

    # Save summary json
    summary_out = {
        "period": f"{test_start} to {end_date}",
        "combined": {k: v for k, v in comb_metrics.items() if not isinstance(v, (pd.Series, pd.DataFrame))},
        "dual_momentum": {k: v for k, v in dm_metrics.items() if not isinstance(v, (pd.Series, pd.DataFrame))},
        "breakout": {k: v for k, v in bo_metrics.items() if not isinstance(v, (pd.Series, pd.DataFrame))},
        "mean_reversion": {k: v for k, v in mr_metrics.items() if not isinstance(v, (pd.Series, pd.DataFrame))},
        "quality_momentum": {k: v for k, v in qm_metrics.items() if not isinstance(v, (pd.Series, pd.DataFrame))},
    }
    with open("backtest_results/3yr_summary.json", "w") as f:
        json.dump(summary_out, f, indent=2)


if __name__ == "__main__":
    main()
