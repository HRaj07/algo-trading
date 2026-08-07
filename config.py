"""
Algo Trading System Configuration
All strategy parameters, universe definitions, and system settings.
"""

from datetime import datetime

# =============================================================================
# SYSTEM SETTINGS
# =============================================================================
SYSTEM = {
    "mode": "paper",            # "paper" or "live"
    "initial_capital": 1_000_000,  # ₹10 Lakhs
    "currency": "INR",
    "timezone": "Asia/Kolkata",
    "log_level": "INFO",
}

# =============================================================================
# DATA SETTINGS
# =============================================================================
DATA = {
    "primary_source": "yfinance",
    "backup_source": "nsepy",
    "benchmark": "^NSEI",          # Nifty 50 index
    "start_date": "2015-01-01",
    "end_date": None,               # None = today
    "cache_dir": "data/cache",
    "cache_expiry_hours": 6,
}

# =============================================================================
# UNIVERSE DEFINITION
# =============================================================================
NIFTY50_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS",
    "INFY.NS", "SBIN.NS", "HINDUNILVR.NS", "ITC.NS", "LT.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "NESTLEIND.NS", "ULTRACEMCO.NS", "POWERGRID.NS", "NTPC.NS",
    "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "INDUSINDBK.NS", "ASIANPAINT.NS",
    "BAJAJFINSV.NS", "M&M.NS", "TATAMOTORS.NS", "ONGC.NS", "COALINDIA.NS",
    "ADANIPORTS.NS", "BPCL.NS", "CIPLA.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "GRASIM.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "JSWSTEEL.NS", "BRITANNIA.NS",
    "APOLLOHOSP.NS", "DIVISLAB.NS", "SBILIFE.NS", "HDFCLIFE.NS",
    "TATACONSUM.NS", "BAJAJ-AUTO.NS", "SHRIRAMFIN.NS", "TATASTEEL.NS", "BEL.NS",
]

NIFTY_NEXT50_TICKERS = [
    "ABB.NS", "ADANIENSOL.NS", "ADANIENT.NS", "ADANIGREEN.NS",
    "AMBUJACEM.NS", "BANKBARODA.NS", "BERGEPAINT.NS", "BOSCHLTD.NS", "CANBK.NS",
    "CHOLAFIN.NS", "COLPAL.NS", "DLF.NS", "GAIL.NS", "GODREJCP.NS",
    "HAVELLS.NS", "ICICIGI.NS", "ICICIPRULI.NS", "INDUSTOWER.NS", "IRCTC.NS",
    "JINDALSTEL.NS", "LICI.NS", "LUPIN.NS", "UNITDSPR.NS", "MPHASIS.NS",
    "NAUKRI.NS", "NMDC.NS", "OBEROIRLTY.NS", "PERSISTENT.NS", "PETRONET.NS",
    "PIIND.NS", "PNB.NS", "SBICARD.NS", "SIEMENS.NS", "TATACOMM.NS", "TATAPOWER.NS",
    "TRENT.NS", "UNIONBANK.NS", "VBL.NS", "VEDL.NS", "ZOMATO.NS",
]

NIFTY_MIDCAP150_TICKERS = [
    "DIXON.NS", "TRENT.NS", "VOLTAS.NS", "MFSL.NS", "MAXHEALTH.NS",
    "KPITTECH.NS", "PERSISTENT.NS", "COFORGE.NS", "LTTS.NS", "ANGELONE.NS",
    "CUMMINSIND.NS", "AIAENG.NS", "TTKPRESTIG.NS", "SUPREMEIND.NS", "BLUEDART.NS",
    "SUNDRMFAST.NS", "KAJARIACER.NS", "ASTRAL.NS", "POLYCAB.NS", "AAVAS.NS",
    "CREDITACC.NS", "FIVESTAR.NS", "JKCEMENT.NS", "RADICO.NS", "MARICO.NS",
    "EMAMILTD.NS", "PGHH.NS", "GILLETTE.NS", "CHAMBLFERT.NS", "DEEPAKNTR.NS",
    "GNFC.NS", "ATUL.NS", "FINEORG.NS", "NAVINFLUOR.NS", "SRF.NS",
    "AARTIIND.NS", "CLEAN.NS", "FLUOROCHEM.NS", "ALKYLAMINE.NS", "VINATIORGA.NS",
    "SOLARINDS.NS", "EPIGRAL.NS", "IDFCFIRSTB.NS", "RBLBANK.NS", "BANDHANBNK.NS",
    "FEDERALBNK.NS", "EQUITASBNK.NS", "SURYAROSNI.NS", "CENTURYPLY.NS", "GREENPLY.NS",
]

ALL_TICKERS = NIFTY50_TICKERS + NIFTY_NEXT50_TICKERS + NIFTY_MIDCAP150_TICKERS

# =============================================================================
# PORTFOLIO ALLOCATION
# =============================================================================
PORTFOLIO = {
    "strategies": {
        "dual_momentum": 0.25,      # 25% allocation
        "momentum_breakout": 0.25,  # 25% allocation
        "mean_reversion": 0.25,     # 25% allocation
        "quality_momentum": 0.25,   # 25% allocation
    },
    "max_position_pct": 0.10,       # Max 10% per stock
    "max_sector_pct": 0.30,         # Max 30% per sector
    "min_position_pct": 0.02,       # Min 2% per position
    "kelly_fraction": 0.5,          # Half-Kelly for safety
    "max_positions": 15,            # Max simultaneous positions
    "cash_buffer_pct": 0.05,        # Keep 5% as cash buffer
}

# =============================================================================
# STRATEGY 1: DUAL MOMENTUM PARAMETERS
# =============================================================================
DUAL_MOMENTUM = {
    "lookback_months": 12,          # 12-month momentum lookback
    "top_n_stocks": 5,              # Select top 5 stocks
    "universe": "nifty50",          # Universe to screen
    "rebalance_day": 1,             # 1st trading day of month
    "risk_free_rate": 0.065,        # 6.5% (approximate Indian risk-free rate)
    "benchmark_ticker": "^NSEI",   # Compare against Nifty 50
    "cash_equivalent": "LIQUIDBEES.NS",  # ETF when in cash
}

# =============================================================================
# STRATEGY 2: MOMENTUM BREAKOUT PARAMETERS  
# =============================================================================
MOMENTUM_BREAKOUT = {
    "lookback_52w": 252,            # 52-week high lookback (trading days)
    "volume_multiplier": 1.5,       # Volume must be 1.5x 20-day avg
    "volume_sma_period": 20,        # Volume SMA period
    "atr_period": 14,               # ATR period for stop loss
    "atr_multiplier": 2.0,          # Stop at 2x ATR below entry
    "trailing_stop_days": 20,       # Trailing stop lookback
    "min_price": 50,                # Minimum stock price ₹50
    "min_market_cap_cr": 1000,      # Minimum ₹1000 Cr market cap
    "universe": "all",              # Screen all tickers
    "max_positions": 8,             # Max concurrent breakout positions
    "trend_filter_sma": 200,        # Price must be above 200 SMA
    "supertrend_period": 10,      # Supertrend ATR period
    "supertrend_mult": 3.0,        # Supertrend multiplier
    "adx_period": 14,              # ADX period
    "adx_threshold": 25,           # Only enter when ADX > 25 (strong trend)
}

# =============================================================================
# STRATEGY 2B: QUALITY MOMENTUM PARAMETERS
# =============================================================================
QUALITY_MOMENTUM = {
    "universe": "nifty500",
    "lookback_momentum": 252,      # 12-month momentum
    "skip_recent_days": 21,        # Skip last month (avoid reversal)
    "top_n": 20,                   # Pick top 20 quality+momentum stocks
    "rebalance_day": 1,            # 1st trading day of month
    "min_roe": 15.0,               # ROE > 15%
    "min_roce": 15.0,              # ROCE > 15% (using gross profit as proxy)
    "max_debt_equity": 1.0,        # Low leverage
    "momentum_weight": 0.6,        # Weight on momentum in combined score
    "quality_weight": 0.4,         # Weight on quality in combined score
}

# =============================================================================
# STRATEGY 3: MEAN REVERSION PARAMETERS
# =============================================================================
MEAN_REVERSION = {
    "rsi_period": 14,               # RSI period
    "rsi_oversold": 30,             # Entry when RSI < 30
    "rsi_overbought": 60,           # Exit when RSI > 60
    "bb_period": 20,                # Bollinger Band period
    "bb_std": 2.0,                  # Bollinger Band std dev
    "trend_sma": 200,               # Must be above 200 SMA (trend filter)
    "stop_loss_pct": 0.05,          # 5% hard stop loss
    "max_hold_days": 10,            # Max holding period
    "universe": "nifty50",          # Only quality stocks
    "max_positions": 3,             # Max concurrent MR positions
}

# =============================================================================
# RISK MANAGEMENT
# =============================================================================
RISK = {
    "max_portfolio_drawdown": 0.15,     # Switch to cash if drawdown > 15%
    "daily_loss_limit": 0.03,           # Halt if daily loss > 3%
    "correlation_limit": 0.70,          # Avoid highly correlated positions
    "volatility_scaling": True,         # Scale positions by inverse volatility
    "vol_lookback": 20,                 # Volatility calculation period
    "target_portfolio_vol": 0.15,       # Target 15% annual portfolio vol
}

# =============================================================================
# REPORTING
# =============================================================================
REPORTING = {
    "github_pages_branch": "gh-pages",
    "slack_webhook": None,              # Optional: set in GitHub Secrets
    "telegram_bot_token": None,         # Optional: set in GitHub Secrets  
    "report_dir": "reports",
    "log_dir": "logs",
    "backtest_dir": "backtest_results",
}
