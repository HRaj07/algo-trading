import re

with open("run_3yr_backtest.py", "r") as f:
    content = f.read()

# 1. Imports
content = content.replace(
    "from config import NIFTY50_TICKERS, NIFTY_NEXT50_TICKERS, PORTFOLIO, DUAL_MOMENTUM, MOMENTUM_BREAKOUT, MEAN_REVERSION",
    "from config import NIFTY50_TICKERS, NIFTY_NEXT50_TICKERS, NIFTY_MIDCAP150_TICKERS, PORTFOLIO, DUAL_MOMENTUM, MOMENTUM_BREAKOUT, MEAN_REVERSION, QUALITY_MOMENTUM"
)

# 2. Add run_quality_momentum_sim before main
qm_sim_code = """
def run_quality_momentum_sim(prices: pd.DataFrame, start_date: str, initial_capital: float = 250_000, top_n: int = 20) -> pd.Series:
    \"\"\"Run Quality+Momentum simulation over the test period.\"\"\"
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

def main():"""

content = content.replace("def main():", qm_sim_code)

# 3. Modify universe in main
content = content.replace(
    "universe = list(dict.fromkeys(NIFTY50_TICKERS + NIFTY_NEXT50_TICKERS))",
    "universe = list(dict.fromkeys(NIFTY50_TICKERS + NIFTY_NEXT50_TICKERS + NIFTY_MIDCAP150_TICKERS))"
)

# 4. Modify simulation calls
content = content.replace(
    "initial_capital=400_000)",
    "initial_capital=250_000)"
).replace(
    "initial_capital=200_000)",
    "initial_capital=250_000)"
)
content = content.replace(
    "Capital     : ₹1,000,000 (Dual Mom 40%, Breakout 40%, Mean Rev 20%)",
    "Capital     : ₹1,000,000 (Dual Mom 25%, Breakout 25%, Mean Rev 25%, Qual Mom 25%)"
)

# 5. Add QM simulation call
qm_call = """    # 4. Quality Momentum Simulation (₹250,000)
    logger.info("[4/4] Simulating Quality Momentum Strategy...")
    qm_pv = run_quality_momentum_sim(close_panel, start_date=test_start, initial_capital=250_000)
    qm_metrics = calculate_metrics(qm_pv, bench_test)

    # 5. Combined Multi-Strategy Portfolio (₹1,000,000)
    common_idx = dm_pv.index.intersection(bo_pv.index).intersection(mr_pv.index).intersection(qm_pv.index)
    combined_pv = dm_pv.loc[common_idx] + bo_pv.loc[common_idx] + mr_pv.loc[common_idx] + qm_pv.loc[common_idx]"""

content = re.sub(
    r"# 4\. Combined Multi-Strategy Portfolio.*?combined_pv = dm_pv\.loc\[common_idx\] \+ bo_pv\.loc\[common_idx\] \+ mr_pv\.loc\[common_idx\]",
    qm_call,
    content,
    flags=re.DOTALL
)

# 6. Update print statements
content = content.replace(
    "headers = f\"{'Metric':<25} | {'Combined Portfolio':<18} | {'Dual Mom':<10} | {'Breakout':<10} | {'Mean Rev':<10} | {'Nifty 50':<10}\"",
    "headers = f\"{'Metric':<25} | {'Combined Portfolio':<18} | {'Dual Mom':<10} | {'Breakout':<10} | {'Mean Rev':<10} | {'Qual Mom':<10} | {'Nifty 50':<10}\""
)

content = content.replace(
    "print(f\"{'Initial Capital':<25} | ₹{comb_metrics['initial_capital']:>15,.0f} | ₹{dm_metrics['initial_capital']:>8,.0f} | ₹{bo_metrics['initial_capital']:>8,.0f} | ₹{mr_metrics['initial_capital']:>8,.0f} | {'-':>10}\")",
    "print(f\"{'Initial Capital':<25} | ₹{comb_metrics['initial_capital']:>15,.0f} | ₹{dm_metrics['initial_capital']:>8,.0f} | ₹{bo_metrics['initial_capital']:>8,.0f} | ₹{mr_metrics['initial_capital']:>8,.0f} | ₹{qm_metrics['initial_capital']:>8,.0f} | {'-':>10}\")"
)
content = content.replace(
    "print(f\"{'Final Value':<25} | ₹{comb_metrics['final_value']:>15,.0f} | ₹{dm_metrics['final_value']:>8,.0f} | ₹{bo_metrics['final_value']:>8,.0f} | ₹{mr_metrics['final_value']:>8,.0f} | {'-':>10}\")",
    "print(f\"{'Final Value':<25} | ₹{comb_metrics['final_value']:>15,.0f} | ₹{dm_metrics['final_value']:>8,.0f} | ₹{bo_metrics['final_value']:>8,.0f} | ₹{mr_metrics['final_value']:>8,.0f} | ₹{qm_metrics['final_value']:>8,.0f} | {'-':>10}\")"
)
content = content.replace(
    "print(f\"{'Total Return':<25} | {comb_metrics['total_return_pct']:>16.2f}% | {dm_metrics['total_return_pct']:>9.2f}% | {bo_metrics['total_return_pct']:>9.2f}% | {mr_metrics['total_return_pct']:>9.2f}% | {comb_metrics['benchmark_total_pct']:>9.2f}%\")",
    "print(f\"{'Total Return':<25} | {comb_metrics['total_return_pct']:>16.2f}% | {dm_metrics['total_return_pct']:>9.2f}% | {bo_metrics['total_return_pct']:>9.2f}% | {mr_metrics['total_return_pct']:>9.2f}% | {qm_metrics['total_return_pct']:>9.2f}% | {comb_metrics['benchmark_total_pct']:>9.2f}%\")"
)
content = content.replace(
    "print(f\"{'CAGR (Annualized)':<25} | {comb_metrics['cagr_pct']:>16.2f}% | {dm_metrics['cagr_pct']:>9.2f}% | {bo_metrics['cagr_pct']:>9.2f}% | {mr_metrics['cagr_pct']:>9.2f}% | {comb_metrics['benchmark_cagr_pct']:>9.2f}%\")",
    "print(f\"{'CAGR (Annualized)':<25} | {comb_metrics['cagr_pct']:>16.2f}% | {dm_metrics['cagr_pct']:>9.2f}% | {bo_metrics['cagr_pct']:>9.2f}% | {mr_metrics['cagr_pct']:>9.2f}% | {qm_metrics['cagr_pct']:>9.2f}% | {comb_metrics['benchmark_cagr_pct']:>9.2f}%\")"
)
content = content.replace(
    "print(f\"{'Sharpe Ratio':<25} | {comb_metrics['sharpe_ratio']:>17.2f} | {dm_metrics['sharpe_ratio']:>10.2f} | {bo_metrics['sharpe_ratio']:>10.2f} | {mr_metrics['sharpe_ratio']:>10.2f} | {'1.05':>10}\")",
    "print(f\"{'Sharpe Ratio':<25} | {comb_metrics['sharpe_ratio']:>17.2f} | {dm_metrics['sharpe_ratio']:>10.2f} | {bo_metrics['sharpe_ratio']:>10.2f} | {mr_metrics['sharpe_ratio']:>10.2f} | {qm_metrics['sharpe_ratio']:>10.2f} | {'1.05':>10}\")"
)
content = content.replace(
    "print(f\"{'Sortino Ratio':<25} | {comb_metrics['sortino_ratio']:>17.2f} | {dm_metrics['sortino_ratio']:>10.2f} | {bo_metrics['sortino_ratio']:>10.2f} | {mr_metrics['sortino_ratio']:>10.2f} | {'1.32':>10}\")",
    "print(f\"{'Sortino Ratio':<25} | {comb_metrics['sortino_ratio']:>17.2f} | {dm_metrics['sortino_ratio']:>10.2f} | {bo_metrics['sortino_ratio']:>10.2f} | {mr_metrics['sortino_ratio']:>10.2f} | {qm_metrics['sortino_ratio']:>10.2f} | {'1.32':>10}\")"
)
content = content.replace(
    "print(f\"{'Max Drawdown':<25} | {comb_metrics['max_drawdown_pct']:>16.2f}% | {dm_metrics['max_drawdown_pct']:>9.2f}% | {bo_metrics['max_drawdown_pct']:>9.2f}% | {mr_metrics['max_drawdown_pct']:>9.2f}% | {'-14.80%':>10}\")",
    "print(f\"{'Max Drawdown':<25} | {comb_metrics['max_drawdown_pct']:>16.2f}% | {dm_metrics['max_drawdown_pct']:>9.2f}% | {bo_metrics['max_drawdown_pct']:>9.2f}% | {mr_metrics['max_drawdown_pct']:>9.2f}% | {qm_metrics['max_drawdown_pct']:>9.2f}% | {'-14.80%':>10}\")"
)
content = content.replace(
    "print(f\"{'Alpha vs Nifty':<25} | {comb_metrics['alpha_pct']:>+16.2f}% | {dm_metrics['alpha_pct']:>+9.2f}% | {bo_metrics['alpha_pct']:>+9.2f}% | {mr_metrics['alpha_pct']:>+9.2f}% | {'0.00%':>10}\")",
    "print(f\"{'Alpha vs Nifty':<25} | {comb_metrics['alpha_pct']:>+16.2f}% | {dm_metrics['alpha_pct']:>+9.2f}% | {bo_metrics['alpha_pct']:>+9.2f}% | {mr_metrics['alpha_pct']:>+9.2f}% | {qm_metrics['alpha_pct']:>+9.2f}% | {'0.00%':>10}\")"
)
content = content.replace(
    "print(f\"{'Beta vs Nifty':<25} | {comb_metrics['beta']:>17.2f} | {dm_metrics['beta']:>10.2f} | {bo_metrics['beta']:>10.2f} | {mr_metrics['beta']:>10.2f} | {'1.00':>10}\")",
    "print(f\"{'Beta vs Nifty':<25} | {comb_metrics['beta']:>17.2f} | {dm_metrics['beta']:>10.2f} | {bo_metrics['beta']:>10.2f} | {mr_metrics['beta']:>10.2f} | {qm_metrics['beta']:>10.2f} | {'1.00':>10}\")"
)

# 7. Add Plotly line
content = content.replace(
    "fig.add_trace(go.Scatter(x=common_idx, y=bo_pv.loc[common_idx] * 2.5, mode=\"lines\", name=\"Breakout (scaled)\", line=dict(color=\"#ab47bc\", width=1.2)), row=1, col=1)",
    "fig.add_trace(go.Scatter(x=common_idx, y=bo_pv.loc[common_idx] * 4.0, mode=\"lines\", name=\"Breakout (scaled)\", line=dict(color=\"#ab47bc\", width=1.2)), row=1, col=1)\n    fig.add_trace(go.Scatter(x=common_idx, y=qm_pv.loc[common_idx] * 4.0, mode=\"lines\", name=\"Quality Momentum (scaled)\", line=dict(color=\"#ffeb3b\", width=1.2)), row=1, col=1)"
)
content = content.replace("dm_pv.loc[common_idx] * 2.5", "dm_pv.loc[common_idx] * 4.0")

# 8. Add QM to summary JSON
content = content.replace(
    "\"mean_reversion\": {k: v for k, v in mr_metrics.items() if not isinstance(v, (pd.Series, pd.DataFrame))},",
    "\"mean_reversion\": {k: v for k, v in mr_metrics.items() if not isinstance(v, (pd.Series, pd.DataFrame))},\n        \"quality_momentum\": {k: v for k, v in qm_metrics.items() if not isinstance(v, (pd.Series, pd.DataFrame))},"
)

with open("run_3yr_backtest.py", "w") as f:
    f.write(content)
