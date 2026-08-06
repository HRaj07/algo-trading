# 🇮🇳 AlgoTrade India — GitHub-Native Algo Trading System

[![Daily Trading Run](https://github.com/YOUR_USERNAME/algo-trading/actions/workflows/daily_run.yml/badge.svg)](https://github.com/YOUR_USERNAME/algo-trading/actions/workflows/daily_run.yml)
[![Backtest](https://github.com/YOUR_USERNAME/algo-trading/actions/workflows/backtest.yml/badge.svg)](https://github.com/YOUR_USERNAME/algo-trading/actions/workflows/backtest.yml)
[![GitHub Pages](https://img.shields.io/badge/Dashboard-Live-00d4ff)](https://YOUR_USERNAME.github.io/algo-trading)

> **Paper Trading** • **Fully Automated** • **Zero Infrastructure Cost** • **Indian Stock Market (NSE)**

---

## 🎯 Overview

A fully automated algorithmic trading system for Indian stocks that runs **entirely on GitHub** — no servers, no cloud costs, completely free infrastructure.

- 📅 **Runs daily** via GitHub Actions at 3:45 PM IST (after NSE market close)
- 💾 **Auto-commits** signals, trade logs, and performance data to this repository  
- 🌐 **Live dashboard** at [GitHub Pages](https://YOUR_USERNAME.github.io/algo-trading)
- 📱 **Telegram alerts** for daily buy/sell signals

## 📊 Strategy Suite

### 1. Dual Momentum (40% allocation)
*Gary Antonacci's Dual Momentum adapted for Indian markets*
- **Universe**: Nifty 50 stocks
- **Signal**: 12-month momentum (relative + absolute)
- **Rebalance**: Monthly (1st trading day)
- **Historical CAGR**: ~18-22% | Max Drawdown: ~25%

### 2. Momentum Breakout (40% allocation)
*52-week high breakout with volume and trend confirmation*
- **Universe**: Nifty 50 + Nifty Next 50
- **Entry**: New 52-week high + Volume > 1.5x average + Above 200 SMA
- **Exit**: 2x ATR trailing stop
- **Historical CAGR**: ~20-25%

### 3. Mean Reversion (20% allocation)  
*RSI oversold on quality large caps in uptrend*
- **Universe**: Nifty 50 only
- **Entry**: RSI(14) < 30 + Above 200 SMA + Near lower Bollinger Band
- **Exit**: RSI > 60 or middle Bollinger Band or 5% stop loss
- **Max hold**: 10 days

## 📁 Repository Structure

```
algo-trading/
├── .github/
│   └── workflows/
│       ├── daily_run.yml        ← Runs daily at 3:45 PM IST
│       └── backtest.yml         ← On-demand backtesting
├── strategies/
│   ├── dual_momentum.py         ← Strategy 1: Dual Momentum
│   ├── momentum_breakout.py     ← Strategy 2: 52-week Breakout
│   └── mean_reversion.py        ← Strategy 3: RSI Mean Reversion
├── data/
│   ├── fetcher.py               ← yfinance data fetcher + indicators
│   └── universe.csv             ← Stock universe (Nifty 50 + Next 50)
├── engine/
│   ├── backtester.py            ← Backtesting engine
│   ├── portfolio.py             ← Paper trading portfolio manager
│   └── risk.py                  ← Risk management + kill switch
├── reports/
│   ├── generate_report.py       ← HTML dashboard generator
│   └── index.html               ← Live dashboard (GitHub Pages)
├── logs/
│   ├── signals.json             ← Daily signals log (auto-updated)
│   ├── performance.json         ← Running PnL (auto-updated)
│   └── portfolio_state.json     ← Portfolio positions (auto-updated)
├── backtest_results/
│   └── *.json, tearsheet.html   ← Backtest tearsheets
├── config.py                    ← All strategy parameters
├── main.py                      ← Entry point
└── requirements.txt
```

## 🚀 Setup Guide

### Step 1: Fork this repository
```bash
git clone https://github.com/YOUR_USERNAME/algo-trading
cd algo-trading
```

### Step 2: Enable GitHub Pages
1. Go to **Settings → Pages**
2. Set Source to **GitHub Actions**

### Step 3: Add GitHub Secrets (optional)
Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Required | Description |
|--------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram bot token for alerts |
| `TELEGRAM_CHAT_ID` | Optional | Your Telegram chat ID |
| `ANGEL_API_KEY` | Optional | Angel One API key (for live trading) |
| `ANGEL_CLIENT_ID` | Optional | Angel One client ID |
| `ANGEL_TOTP_SECRET` | Optional | Angel One TOTP secret |

### Step 4: Enable GitHub Actions
- Go to **Actions** tab and enable workflows
- The daily run will automatically trigger at **3:45 PM IST, Mon-Fri**

### Step 5: Run backtest manually
1. Go to **Actions → Run Backtest Suite**
2. Click **Run workflow**
3. View results in `backtest_results/`

### Step 6: Run locally (optional)
```bash
pip install -r requirements.txt

# Daily signal run
python main.py

# Full backtest
python main.py --backtest

# Regenerate dashboard only
python main.py --report-only
```

## 📱 Telegram Alerts Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot`
2. Copy the bot token → add as `TELEGRAM_BOT_TOKEN` secret
3. Message [@userinfobot](https://t.me/userinfobot) to get your chat ID → add as `TELEGRAM_CHAT_ID`

You'll receive daily alerts like:
```
📊 AlgoTrade India | 2025-01-15
BUY signals: 3
SELL signals: 1
Portfolio: ₹10,45,230
```

## ⚙️ Configuration

Edit `config.py` to customize:
- Initial capital (`SYSTEM.initial_capital`)
- Strategy allocation weights (`PORTFOLIO.strategies`)  
- Momentum lookback period (`DUAL_MOMENTUM.lookback_months`)
- Volume multiplier for breakouts (`MOMENTUM_BREAKOUT.volume_multiplier`)
- RSI thresholds (`MEAN_REVERSION.rsi_oversold`)

## 📈 Data Sources

| Source | Library | Cost | Used For |
|--------|---------|------|---------|
| Yahoo Finance | `yfinance` | **Free** | All historical OHLCV data |
| NSE (backup) | `nsepython` | **Free** | NSE-specific backup |
| Angel One SmartAPI | `smartapi-python` | **Free** | Live trading (optional) |

## ⚠️ Risk Disclaimer

> **This is a paper trading system for educational purposes only.**
> 
> - Past performance does not guarantee future results
> - Algorithmic trading involves significant financial risk
> - Never invest money you can't afford to lose
> - Run paper trading for at least 3-6 months before going live
> - This is not financial advice

## 📄 License

MIT License — free to use, modify, and distribute.

---

*Built with ❤️ | Data from Yahoo Finance | Runs on GitHub Actions (free tier)*
