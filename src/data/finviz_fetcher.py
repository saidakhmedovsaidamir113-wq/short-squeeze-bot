"""
finviz_fetcher.py
-----------------
Fetches stocks from Finviz's screener filtered by Short Float.

We scan three tiers:
- Short Float > 20%
- Short Float > 25%
- Short Float > 30%

Returns a pandas DataFrame with columns including:
  Ticker, Company, Price, Short Float, Short Ratio, ...

Uses the unofficial finvizfinance library, routed through
ScraperAPI proxy when SCRAPERAPI_KEY is set in .env
(needed for regions where Finviz blocks direct access).
"""

import logging
from typing import Optional

import pandas as pd
from finvizfinance.screener.ownership import Ownership
from finvizfinance.util import set_proxy

from src.config import STRATEGY, SCRAPERAPI_KEY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------
# Configure ScraperAPI proxy if key is present
# ---------------------------------------------------------------
if SCRAPERAPI_KEY:
    # premium=true uses ScraperAPI's premium proxy pool, which
    # greatly reduces dropped connections on heavy requests
    # (like the large 20% short-float tier).
    scraperapi_proxy = (
        f"http://scraperapi.premium=true:{SCRAPERAPI_KEY}"
        f"@proxy-server.scraperapi.com:8001"
    )
    set_proxy({
        "http": scraperapi_proxy,
        "https": scraperapi_proxy,
    })

    # ---------------------------------------------------------------
    # Force-disable SSL verification for ALL requests in this process.
    # ScraperAPI uses its own cert chain that Python can't verify
    # locally. Since we're scraping a public price screener (no
    # credentials, no sensitive payload), this tradeoff is safe.
    # ---------------------------------------------------------------
    import requests
    import urllib3

    # Patch the default Session to (1) never verify SSL and
    # (2) force a long timeout — ScraperAPI needs up to 60s to
    # retry through different proxies on big result sets.
    original_request = requests.Session.request
    def patched_request(self, *args, **kwargs):
        kwargs["verify"] = False
        # Only set timeout if the caller didn't specify one,
        # or if their timeout is too short for ScraperAPI
        existing = kwargs.get("timeout")
        if existing is None or (isinstance(existing, (int, float)) and existing < 70):
            kwargs["timeout"] = 70
        return original_request(self, *args, **kwargs)
    requests.Session.request = patched_request

    # Suppress the warnings that flood the terminal
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    logger.info("ScraperAPI proxy configured (SSL verification disabled).")
else:
    logger.info("No ScraperAPI key found — direct connection mode.")

# Map our tier labels to Finviz's exact filter values
FINVIZ_SHORT_FLOAT_FILTER = {
    "Over 20%": "Over 20%",
    "Over 25%": "Over 25%",
    "Over 30%": "Over 30%",
}


def fetch_tier(tier_label: str, max_retries: int = 3) -> Optional[pd.DataFrame]:
    """
    Fetch a single Short Float tier from Finviz, with automatic retry.

    Args:
        tier_label: One of "Over 20%", "Over 25%", "Over 30%"
        max_retries: Number of attempts before giving up. Default 3.

    Returns:
        DataFrame of stocks, or None if all retries failed.
    """
    import time

    if tier_label not in FINVIZ_SHORT_FLOAT_FILTER:
        logger.error(f"Unknown tier label: {tier_label}")
        return None

    for attempt in range(1, max_retries + 1):
        logger.info(
            f"Fetching Finviz tier: Short Float {tier_label} "
            f"(attempt {attempt}/{max_retries})"
        )

        try:
            screener = Ownership()
            filters = {"Float Short": FINVIZ_SHORT_FLOAT_FILTER[tier_label]}
            screener.set_filter(filters_dict=filters)
            df = screener.screener_view()

            if df is None or df.empty:
                logger.warning(f"Finviz returned no results for {tier_label}")
                return pd.DataFrame()

            df["Tier"] = tier_label
            logger.info(f"  -> {len(df)} stocks found in {tier_label}")
            return df

        except Exception as e:
            logger.warning(
                f"Attempt {attempt}/{max_retries} failed for {tier_label}: {e}"
            )
            if attempt < max_retries:
                wait_seconds = 5 * attempt  # 5s, 10s, 15s backoff
                logger.info(f"Retrying in {wait_seconds}s...")
                time.sleep(wait_seconds)
            else:
                logger.error(
                    f"All {max_retries} attempts failed for {tier_label}. Giving up."
                )
                return None


def fetch_all_tiers() -> pd.DataFrame:
    """
    Fetch all configured Short Float tiers and combine into one DataFrame.

    Deduplicates by ticker, keeping the row from the highest tier.
    """
    tiers = STRATEGY["short_float_tiers"]
    all_dfs = []

    for tier in tiers:
        df = fetch_tier(tier)
        if df is not None and not df.empty:
            all_dfs.append(df)

    if not all_dfs:
        logger.warning("No data fetched from any tier.")
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)

    # Deduplicate: keep highest tier when stock appears in multiple
    tier_priority = {"Over 30%": 3, "Over 25%": 2, "Over 20%": 1}
    combined["_tier_rank"] = combined["Tier"].map(tier_priority).fillna(0)
    combined = combined.sort_values("_tier_rank", ascending=False)
    combined = combined.drop_duplicates(subset="Ticker", keep="first")
    combined = combined.drop(columns="_tier_rank").reset_index(drop=True)

    logger.info(f"Total unique short-squeeze candidates: {len(combined)}")
    return combined


def apply_short_ratio_filter(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only stocks with Short Ratio above the configured minimum.
    """
    min_ratio = STRATEGY["min_short_ratio"]

    if df.empty:
        return df

    df = df.copy()
    df["Short Ratio"] = pd.to_numeric(df["Short Ratio"], errors="coerce")
    filtered = df[df["Short Ratio"] >= min_ratio].reset_index(drop=True)

    logger.info(
        f"Short Ratio filter (>={min_ratio}): "
        f"{len(filtered)} of {len(df)} stocks passed."
    )
    return filtered
def clean_short_float(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert the 'Float Short' column (e.g. '32.40%') into a numeric
    percentage (32.4). Adds a 'short_float_pct' column.
    """
    if df.empty or "Short Float" not in df.columns:
        return df

    df = df.copy()
    # Short Float comes as string like "32.40%" — strip % and convert
    df["short_float_pct"] = (
        df["Short Float"]
        .astype(str)
        .str.replace("%", "", regex=False)
    )
    df["short_float_pct"] = pd.to_numeric(df["short_float_pct"], errors="coerce")
    return df