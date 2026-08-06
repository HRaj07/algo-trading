#!/usr/bin/env python3
"""
Algo Trading System — Main Entry Point
Run daily by GitHub Actions to generate signals and update the dashboard.

Usage:
  python main.py              # Daily signal run
  python main.py --backtest   # Full backtest
  python main.py --init       # Initialize portfolio
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List

import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/run.log", mode="a"),
    ]
)
logger = logging.getLogger("main")


def ensure_dirs():
    """Create required directories."""
    for d in ["logs", "reports", "backtest_results", "data/cache"]:
        Path(d).mkdir(parents=True, exist_ok=True)


def run_daily_signals() -> List[Dict]:
    """Run all strategies and collect today's signals."""
    from config import DATA, SYSTEM, PORTFOLIO
    from data.fetcher import DataFetcher
    from strategies.dual_momentum import DualMomentumStrategy
    from strategies.momentum_breakout import MomentumBreakoutStrategy
    from strategies.mean_reversion import MeanReversionStrategy
    from engine.portfolio import Portfolio
    from engine.risk import RiskManager
    from reports.generate_report import ReportGenerator

    logger.info("="*60)
    logger.info(f"AlgoTrade India | Daily Run | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)

    fetcher = DataFetcher(
        cache_dir=DATA["cache_dir"],
        cache_expiry_hours=DATA["cache_expiry_hours"]
    )
    portfolio = Portfolio()
    risk = RiskManager()
    all_signals = []

    # --- Kill Switch Check ---
    if risk.check_kill_switch():
        logger.warning("KILL SWITCH ACTIVE — Skipping all trading signals")
        _send_notification("🚨 KILL SWITCH ACTIVE — No trades today. Review portfolio immediately.")
        _save_signals([])
        return []

    start_date = DATA["start_date"]

    # ---------------------------------------------------
    # STRATEGY 1: Dual Momentum (40% allocation)
    # ---------------------------------------------------
    logger.info("\n[1/3] Running Dual Momentum Strategy...")
    try:
        dm = DualMomentumStrategy(fetcher)
        dm_signal = dm.generate_today_signal(start=start_date)

        if dm_signal.get("in_cash"):
            logger.info("  → Dual Momentum: IN CASH")
            all_signals.append({
                "strategy": "dual_momentum",
                "action": "CASH",
                "signal": "CASH",
                "ticker": "LIQUIDBEES.NS",
                "reason": "absolute_momentum_negative",
                "signal_type": "dual_momentum",
            })
        else:
            for ticker in dm_signal.get("selected", []):
                score = dm_signal.get("scores", {}).get(ticker, 0)
                all_signals.append({
                    "strategy": "dual_momentum",
                    "action": "BUY",
                    "signal": "BUY",
                    "ticker": ticker,
                    "momentum_score": round(float(score) * 100, 2) if hasattr(score, 'item') else round(score * 100, 2),
                    "signal_type": "dual_momentum",
                    "stop_loss": None,
                })
                logger.info(f"  → BUY {ticker} (score: {score:.1%})")
    except Exception as e:
        logger.error(f"Dual Momentum error: {e}", exc_info=True)

    # ---------------------------------------------------
    # STRATEGY 2: Momentum Breakout (40% allocation)
    # ---------------------------------------------------
    logger.info("\n[2/3] Running Momentum Breakout Strategy...")
    try:
        mb = MomentumBreakoutStrategy(fetcher)
        mb_positions = portfolio.get_strategy_positions("momentum_breakout")
        mb_signal = mb.generate_today_signal(
            start=start_date, current_positions=mb_positions
        )

        for entry in mb_signal.get("entries", []):
            all_signals.append({**entry, "strategy": "momentum_breakout"})
            logger.info(f"  → BREAKOUT BUY {entry['ticker']} @ ₹{entry['current_price']} | SL: ₹{entry['stop_loss']}")

        for exit_ in mb_signal.get("exits", []):
            all_signals.append({**exit_, "strategy": "momentum_breakout"})
            logger.info(f"  → EXIT {exit_['ticker']} ({exit_['reason']}) | PnL: {exit_['pnl_pct']:.1%}")

        logger.info(f"  Scanned: {mb_signal.get('scan_count', 0)} | Breakouts: {mb_signal.get('breakout_count', 0)}")
    except Exception as e:
        logger.error(f"Momentum Breakout error: {e}", exc_info=True)

    # ---------------------------------------------------
    # STRATEGY 3: Mean Reversion (20% allocation)
    # ---------------------------------------------------
    logger.info("\n[3/3] Running Mean Reversion Strategy...")
    try:
        mr = MeanReversionStrategy(fetcher)
        mr_positions = portfolio.get_strategy_positions("mean_reversion")
        mr_signal = mr.generate_today_signal(
            start=start_date, current_positions=mr_positions
        )

        for entry in mr_signal.get("entries", []):
            all_signals.append({**entry, "strategy": "mean_reversion"})
            logger.info(f"  → MR BUY {entry['ticker']} RSI={entry['rsi']} | SL: ₹{entry['stop_loss']}")

        for exit_ in mr_signal.get("exits", []):
            all_signals.append({**exit_, "strategy": "mean_reversion"})
            logger.info(f"  → EXIT {exit_['ticker']} ({exit_['reason']}) | PnL: {exit_['pnl_pct']:.1%}")

    except Exception as e:
        logger.error(f"Mean Reversion error: {e}", exc_info=True)

    # ---------------------------------------------------
    # Execute paper trades
    # ---------------------------------------------------
    portfolio.update_days_held()
    buy_signals = [s for s in all_signals if s.get("signal") == "BUY"]
    sell_signals = [s for s in all_signals if s.get("signal") == "SELL"]

    # Process exits first
    for signal in sell_signals:
        ticker = signal.get("ticker")
        price = signal.get("current_price", 0)
        if ticker and price:
            portfolio.exit_position(ticker, price, reason=signal.get("reason", "signal"))

    # Process entries
    total_capital = portfolio.portfolio_value({})
    strategy_capital = {
        "dual_momentum": total_capital * 0.40,
        "momentum_breakout": total_capital * 0.40,
        "mean_reversion": total_capital * 0.20,
    }

    for signal in buy_signals:
        strategy = signal.get("strategy")
        ticker = signal.get("ticker")
        price = signal.get("current_price")

        if not price:
            price = fetcher.get_latest_price(ticker)

        if not price or ticker in portfolio.positions:
            continue

        alloc = strategy_capital.get(strategy, 0)
        existing = len(portfolio.get_strategy_positions(strategy))
        max_new = {"dual_momentum": 5, "momentum_breakout": 8, "mean_reversion": 3}[strategy]
        slots = max(0, max_new - existing)

        if slots > 0:
            position_value = alloc / max_new
            qty = int(position_value / price)
            stop = signal.get("stop_loss")

            if qty > 0:
                portfolio.enter_position(ticker, price, qty, strategy, stop_loss=stop)

    # ---------------------------------------------------
    # Update performance & generate report
    # ---------------------------------------------------
    risk.update_performance_log(portfolio.portfolio_value({}))
    _save_signals(all_signals)

    # Generate dashboard
    report = ReportGenerator()
    report.generate(today_signals=all_signals, portfolio_summary=portfolio.summary())

    logger.info(f"\n✅ Daily run complete | {len(buy_signals)} buys, {len(sell_signals)} sells")
    logger.info(f"Portfolio: {portfolio.summary()}")

    # Notifications
    summary_msg = (
        f"📊 AlgoTrade India | {date.today()}\n"
        f"BUY signals: {len(buy_signals)}\n"
        f"SELL signals: {len(sell_signals)}\n"
        f"Portfolio: ₹{portfolio.portfolio_value({{}}):.0f}"
    )
    _send_notification(summary_msg)

    return all_signals


def run_backtest() -> None:
    """Run full backtests for all strategies."""
    from config import DATA, NIFTY50_TICKERS, ALL_TICKERS
    from data.fetcher import DataFetcher
    from engine.backtester import Backtester
    from reports.generate_report import ReportGenerator

    logger.info("="*60)
    logger.info("Running Full Backtest Suite...")
    logger.info("="*60)

    fetcher = DataFetcher()
    backtester = Backtester()
    backtest_results = []

    start = "2015-01-01"

    # --- Strategy 1: Dual Momentum ---
    logger.info("\n[1/3] Backtesting Dual Momentum...")
    prices_dm = fetcher.fetch_close_panel(NIFTY50_TICKERS[:20], start)  # Use subset for speed
    benchmark = fetcher.fetch_index(start=start)
    if not prices_dm.empty and not benchmark.empty:
        common = prices_dm.index.intersection(benchmark.index)
        result = backtester.run_dual_momentum_backtest(
            prices_dm.loc[common], benchmark.loc[common]
        )
        backtest_results.append(result)

    # --- Strategy 2: Momentum Breakout ---
    logger.info("\n[2/3] Backtesting Momentum Breakout...")
    data_mb = fetcher.fetch_ohlcv(NIFTY50_TICKERS[:15], start)  # Subset for speed
    if data_mb:
        result = backtester.run_breakout_backtest(data_mb)
        backtest_results.append(result)

    # --- Strategy 3: Mean Reversion ---
    logger.info("\n[3/3] Backtesting Mean Reversion...")
    data_mr = fetcher.fetch_ohlcv(NIFTY50_TICKERS[:10], start)  # Subset for speed
    if data_mr:
        result = backtester.run_mean_reversion_backtest(data_mr)
        backtest_results.append(result)

    # Generate tearsheet
    backtester.generate_tearsheet(
        backtest_results,
        output_path="backtest_results/tearsheet.html"
    )

    # Update dashboard with backtest data
    report = ReportGenerator()
    report.generate(backtest_results=backtest_results)

    logger.info("\n✅ Backtest complete!")
    for r in backtest_results:
        logger.info(
            f"  {r.get('strategy')}: CAGR={r.get('cagr_pct')}% | "
            f"Sharpe={r.get('sharpe_ratio')} | MaxDD={r.get('max_drawdown_pct')}%"
        )


def _save_signals(signals: List[Dict]) -> None:
    """Append today's signals to the log file."""
    log_entry = {
        "date": datetime.now().isoformat(),
        "signals": signals,
        "n_buy": sum(1 for s in signals if s.get("signal") == "BUY"),
        "n_sell": sum(1 for s in signals if s.get("signal") == "SELL"),
    }
    with open("logs/signals.json", "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def _send_notification(message: str) -> None:
    """Send Discord notification via webhook."""
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        logger.debug("Discord webhook not configured (DISCORD_WEBHOOK_URL not set)")
        return

    try:
        import urllib.request
        import json as _json

        # Format nicely for Discord (wrap in code block)
        discord_message = f"```\n{message}\n```"
        payload = _json.dumps({
            "username": "AlgoTrade India 🇮🇳",
            "avatar_url": "https://em-content.zobj.net/source/twitter/376/chart-increasing_1f4c8.png",
            "content": discord_message,
        }).encode("utf-8")

        req = urllib.request.Request(
            webhook_url, data=payload, method="POST"
        )
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=10)
        logger.info("✅ Discord notification sent")
    except Exception as e:
        logger.warning(f"Discord notification failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AlgoTrade India")
    parser.add_argument("--backtest", action="store_true", help="Run full backtest")
    parser.add_argument("--init", action="store_true", help="Initialize portfolio")
    parser.add_argument("--report-only", action="store_true", help="Regenerate report only")
    args = parser.parse_args()

    ensure_dirs()

    if args.backtest:
        run_backtest()
    elif args.report_only:
        from reports.generate_report import ReportGenerator
        ReportGenerator().generate()
    else:
        run_daily_signals()
