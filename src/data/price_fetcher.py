"""
price_fetcher.py
----------------
Fetches historical OHLCV data for tickers via yfinance.

For each ticker we compute:
- current_price: latest closing price
- high_100d: highest closing price in the past 100 trading days
- sma_50: 50-day simple moving average (latest value)
- distance_from_high_pct: how far current price is below 100-day high

These are used by the filter layer (trend, proximity, breakout).
"""

import logging
from typing import Optional, Dict, List

import pandas as pd
import yfinance as yf

from src.config import STRATEGY

logger = logging.getLogger(__name__)


def fetch_price_history(ticker: str, days: int = 180) -> Optional[pd.DataFrame]:
    """
    Fetch daily OHLCV data for a ticker.

    Args:
        ticker: Stock symbol, e.g. "AAPL"
        days: How many calendar days of history. Default 180 gives
              us comfortably more than 100 trading days plus 50-day
              SMA warmup.

    Returns:
        DataFrame with Date index and OHLCV columns, or None on error.
    """
    try:
        period = f"{days}d"
        df = yf.download(
            ticker,
            period=period,
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        if df is None or df.empty:
            logger.warning(f"No price data returned for {ticker}")
            return None

        # Flatten multi-level columns if yfinance returns them
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        return df

    except Exception as e:
        logger.error(f"Failed to fetch price history for {ticker}: {e}")
        return None


def compute_metrics(ticker: str) -> Optional[Dict]:
    """
    Compute the price-derived metrics needed by the strategy filters.

    Returns:
        Dict with keys: ticker, current_price, high_100d, sma_50,
        distance_from_high_pct, days_of_data
        Or None if data is insufficient.
    """
    lookback = STRATEGY["high_lookback_days"]  # 100
    sma_window = STRATEGY["sma_window"]        # 50

    df = fetch_price_history(ticker, days=max(180, lookback + sma_window + 20))

    if df is None or df.empty:
        return None

    min_required = max(lookback, sma_window)
    if len(df) < min_required:
        logger.warning(
            f"{ticker}: only {len(df)} days of data, need {min_required}."
        )
        return None

    current_price = float(df["Close"].iloc[-1])
    # Exclude today's bar: the 100-day high is HISTORICAL resistance,
    # which today's price must break ABOVE. Including today would make
    # breakout detection logically impossible (high >= price always).
    high_lookback = float(df["High"].iloc[-(lookback + 1):-1].max())
    sma_50 = float(df["Close"].iloc[-sma_window:].mean())

    distance_from_high_pct = (high_lookback - current_price) / high_lookback

    # Volume confirmation: compare latest volume to the 50-day average.
    # A breakout on above-average volume is far more reliable.
    latest_volume = float(df["Volume"].iloc[-1])
    avg_volume_50 = float(df["Volume"].iloc[-sma_window:].mean())
    volume_ratio = (latest_volume / avg_volume_50) if avg_volume_50 > 0 else 0.0

    return {
        "ticker": ticker,
        "current_price": round(current_price, 2),
        "high_100d": round(high_lookback, 2),
        "sma_50": round(sma_50, 2),
        "distance_from_high_pct": round(distance_from_high_pct, 4),
        "latest_volume": int(latest_volume),
        "avg_volume_50": int(avg_volume_50),
        "volume_ratio": round(volume_ratio, 2),
        "days_of_data": len(df),
    }

def enrich_candidates(tickers: List[str]) -> pd.DataFrame:
    """
    Compute price metrics for a list of tickers.

    Args:
        tickers: List of stock symbols

    Returns:
        DataFrame with one row per ticker that returned valid metrics.
        Tickers with missing/insufficient data are silently skipped.
    """
    logger.info(f"Fetching price data for {len(tickers)} tickers...")

    results = []
    for i, ticker in enumerate(tickers, start=1):
        if i % 25 == 0:
            logger.info(f"  Progress: {i}/{len(tickers)}")

        metrics = compute_metrics(ticker)
        if metrics is not None:
            results.append(metrics)

    df = pd.DataFrame(results)
    logger.info(
        f"Price enrichment complete: {len(df)}/{len(tickers)} "
        f"tickers had usable data."
    )
    return df