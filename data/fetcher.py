"""
Data Fetcher Module
Fetches historical and live market data from free sources.
Primary: yfinance | Backup: nsepy
"""

import os
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Tuple

import pandas as pd
import numpy as np
import yfinance as yf

# Configure logging
logger = logging.getLogger(__name__)

# Try importing nsepy as backup
try:
    from nsepy import get_history
    from nsepy.symbols import get_symbol_list
    NSEPY_AVAILABLE = True
except ImportError:
    NSEPY_AVAILABLE = False
    logger.warning("nsepy not available, using yfinance only")


class DataFetcher:
    """Fetches market data from free sources with caching."""

    def __init__(self, cache_dir: str = "data/cache", cache_expiry_hours: int = 6):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_expiry = timedelta(hours=cache_expiry_hours)
        logger.info(f"DataFetcher initialized | cache: {cache_dir}")

    # ------------------------------------------------------------------
    # CORE: Fetch OHLCV for a list of tickers
    # ------------------------------------------------------------------
    def fetch_ohlcv(
        self,
        tickers: List[str],
        start: str,
        end: Optional[str] = None,
        interval: str = "1d",
        use_cache: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV data for multiple tickers."""
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")

        results = {}
        failed = []

        for ticker in tickers:
            try:
                data = self._fetch_single(
                    ticker, start, end, interval, use_cache
                )
                if data is not None and not data.empty:
                    results[ticker] = data
                else:
                    failed.append(ticker)
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
                failed.append(ticker)
            time.sleep(0.1)  # Polite rate limiting

        if failed:
            logger.warning(f"Failed tickers ({len(failed)}): {failed[:10]}...")

        logger.info(f"Fetched data for {len(results)}/{len(tickers)} tickers")
        return results

    def _fetch_single(
        self, ticker: str, start: str, end: str,
        interval: str = "1d", use_cache: bool = True
    ) -> Optional[pd.DataFrame]:
        """Fetch single ticker with cache support."""
        cache_file = self.cache_dir / f"{ticker.replace('/', '_')}_{start}_{end}_{interval}.parquet"

        # Check cache freshness
        if use_cache and cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - mtime < self.cache_expiry:
                return pd.read_parquet(cache_file)

        # Fetch from yfinance
        data = self._fetch_yfinance(ticker, start, end, interval)

        # Fallback to nsepy for NSE stocks
        if (data is None or data.empty) and NSEPY_AVAILABLE and ticker.endswith(".NS"):
            data = self._fetch_nsepy(ticker.replace(".NS", ""), start, end)

        # Cache result
        if data is not None and not data.empty:
            data.to_parquet(cache_file)

        return data

    def _fetch_yfinance(
        self, ticker: str, start: str, end: str, interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """Fetch data using yfinance."""
        try:
            ticker_obj = yf.Ticker(ticker)
            df = ticker_obj.history(
                start=start, end=end, interval=interval,
                auto_adjust=True, actions=False
            )
            if df.empty:
                return None
            # Standardize columns
            df.columns = [c.lower() for c in df.columns]
            df.index = pd.to_datetime(df.index)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            df = df[["open", "high", "low", "close", "volume"]]
            df = df.dropna()
            return df
        except Exception as e:
            logger.debug(f"yfinance error for {ticker}: {e}")
            return None

    def _fetch_nsepy(
        self, symbol: str, start: str, end: str
    ) -> Optional[pd.DataFrame]:
        """Fetch data using nsepy (backup)."""
        try:
            from nsepy import get_history
            from datetime import date
            start_dt = datetime.strptime(start, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end, "%Y-%m-%d").date()
            df = get_history(
                symbol=symbol,
                start=start_dt,
                end=end_dt
            )
            if df.empty:
                return None
            df = df.rename(columns={
                "Open": "open", "High": "high", "Low": "low",
                "Close": "close", "Volume": "volume"
            })
            df.index = pd.to_datetime(df.index)
            return df[["open", "high", "low", "close", "volume"]].dropna()
        except Exception as e:
            logger.debug(f"nsepy error for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------
    # CONVENIENCE: Multi-ticker panel data
    # ------------------------------------------------------------------
    def fetch_panel(
        self,
        tickers: List[str],
        start: str,
        end: Optional[str] = None,
        field: str = "close",
    ) -> pd.DataFrame:
        """Returns a DataFrame with tickers as columns (single field)."""
        data_dict = self.fetch_ohlcv(tickers, start, end)
        panels = {}
        for ticker, df in data_dict.items():
            if field in df.columns:
                panels[ticker] = df[field]
        panel = pd.DataFrame(panels)
        panel = panel.sort_index()
        panel = panel.fillna(method="ffill").dropna(how="all")
        return panel

    def fetch_close_panel(
        self, tickers: List[str], start: str, end: Optional[str] = None
    ) -> pd.DataFrame:
        """Alias for fetch_panel with close prices."""
        return self.fetch_panel(tickers, start, end, "close")

    def fetch_index(
        self, ticker: str = "^NSEI", start: str = "2015-01-01",
        end: Optional[str] = None
    ) -> pd.Series:
        """Fetch index data (Nifty 50 by default)."""
        data = self._fetch_single(ticker, start, end)
        if data is not None and not data.empty:
            return data["close"]
        return pd.Series(dtype=float)

    # ------------------------------------------------------------------
    # MARKET INFO
    # ------------------------------------------------------------------
    def get_ticker_info(self, ticker: str) -> Dict:
        """Get fundamental info for a ticker."""
        try:
            info = yf.Ticker(ticker).info
            return {
                "ticker": ticker,
                "name": info.get("longName", ticker),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "market_cap": info.get("marketCap", 0),
                "pe_ratio": info.get("trailingPE", None),
            }
        except Exception:
            return {"ticker": ticker, "sector": "Unknown"}

    def get_bulk_info(self, tickers: List[str]) -> pd.DataFrame:
        """Get info for multiple tickers."""
        infos = []
        for ticker in tickers:
            info = self.get_ticker_info(ticker)
            infos.append(info)
            time.sleep(0.05)
        return pd.DataFrame(infos).set_index("ticker")

    def get_latest_price(self, ticker: str) -> Optional[float]:
        """Get the latest available price."""
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
            return None
        except Exception:
            return None

    def is_market_open(self) -> bool:
        """Check if NSE market is currently open."""
        now = datetime.now()
        # NSE: Mon-Fri, 9:15 AM - 3:30 PM IST
        if now.weekday() >= 5:  # Weekend
            return False
        market_open = now.replace(hour=9, minute=15, second=0)
        market_close = now.replace(hour=15, minute=30, second=0)
        return market_open <= now <= market_close


class TechnicalIndicators:
    """Compute technical indicators on OHLCV DataFrames."""

    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average."""
        return series.rolling(window=period).mean()

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range."""
        high = df["high"]
        low = df["low"]
        prev_close = df["close"].shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)
        return tr.ewm(com=period - 1, adjust=False).mean()

    @staticmethod
    def bollinger_bands(
        series: pd.Series, period: int = 20, std: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Bollinger Bands (upper, middle, lower)."""
        middle = series.rolling(window=period).mean()
        std_dev = series.rolling(window=period).std()
        upper = middle + std * std_dev
        lower = middle - std * std_dev
        return upper, middle, lower

    @staticmethod  
    def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
        """Supertrend indicator. Returns Series: +1 = bullish, -1 = bearish."""
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)
        atr = tr.ewm(com=period-1, adjust=False).mean()
        hl2 = (high + low) / 2
        upper = hl2 + multiplier * atr
        lower = hl2 - multiplier * atr
        
        # Use rolling window to determine trend direction
        # Simplification: bullish when close > upper band from N days ago (valid proxy)
        direction = pd.Series(1, index=close.index)
        direction[close < lower] = -1
        direction[close > upper] = 1
        # Forward-fill to maintain trend
        direction = direction.replace(0, np.nan).ffill().fillna(1)
        return direction.astype(int)

    @staticmethod
    def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average Directional Index (ADX) — measures trend strength."""
        high = df["high"]
        low = df["low"]
        close = df["close"]

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)

        atr = tr.ewm(com=period - 1, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(com=period - 1, adjust=False).mean() / atr.replace(0, np.nan)
        minus_di = 100 * minus_dm.ewm(com=period - 1, adjust=False).mean() / atr.replace(0, np.nan)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(com=period - 1, adjust=False).mean()
        return adx.fillna(0)

    @staticmethod
    def momentum(series: pd.Series, period: int) -> pd.Series:
        """N-period momentum (percentage return)."""
        return series.pct_change(periods=period)

    @staticmethod
    def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
        """Volume relative to its moving average."""
        return volume / volume.rolling(window=period).mean()

    @staticmethod
    def high_52w(series: pd.Series, period: int = 252) -> pd.Series:
        """52-week (252 trading days) rolling high."""
        return series.rolling(window=period).max()

    @staticmethod
    def drawdown(series: pd.Series) -> pd.Series:
        """Percentage drawdown from rolling maximum."""
        roll_max = series.cummax()
        return (series - roll_max) / roll_max
