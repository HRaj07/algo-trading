# Strategy Upgrade Plan: Research-Backed Improvements

## Changes
1. **config.py** — Add Nifty 500 MidCap tickers, new strategy params (Supertrend+ADX, Quality)
2. **strategies/momentum_breakout.py** — Add Supertrend+ADX filter + Quality (ROE) screen
3. **strategies/quality_momentum.py** — NEW: Quality+Momentum factor strategy (biggest alpha source)
4. **data/fetcher.py** — Add Supertrend + ADX indicator methods + FII/DII fetch
5. **run_3yr_backtest.py** — Add new strategies to 3yr backtest comparison
6. **main.py** — Wire new Quality+Momentum strategy into daily run
