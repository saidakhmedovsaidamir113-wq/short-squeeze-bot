"""
main.py
-------
Entry point for the Short Squeeze Bot.

Runs the complete pipeline:
  1. Fetch Finviz candidates (all short-float tiers)
  2. Filter by Short Ratio
  3. Enrich with price data (100d high, SMA50, volume)
  4. Apply trend + proximity filters
  5. Classify (breakout / near-breakout / watchlist)
  6. Send signals to Telegram
  7. Log signals to Excel

Run with:  python -m src.main
"""

import logging
import sys
from datetime import datetime

# ---------------------------------------------------------------
# Logging setup — writes to both console and logs/bot.log
# ---------------------------------------------------------------
from src.config import OUTPUT, PROJECT_ROOT

LOG_FILE = PROJECT_ROOT / OUTPUT["log_file"]
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")

# Imports after logging is configured
from src.data.finviz_fetcher import (
    fetch_all_tiers, apply_short_ratio_filter, clean_short_float
)
from src.data.price_fetcher import enrich_candidates
from src.filters.trend_filter import apply_trend_filter
from src.filters.proximity_filter import apply_proximity_filter
from src.filters.breakout_detector import classify_candidates
from src.output.telegram_sender import send_signals
from src.output.excel_logger import log_signals


def run_scan() -> None:
    """Execute the full short-squeeze scan and dispatch signals."""
    start = datetime.now()
    logger.info("=" * 60)
    logger.info("SHORT SQUEEZE SCAN STARTING")
    logger.info("=" * 60)

    # --- Stage 1-2: Finviz candidates + short ratio ---
    finviz_df = clean_short_float(apply_short_ratio_filter(fetch_all_tiers()))
    logger.info(f"Finviz candidates passing Short Ratio: {len(finviz_df)}")

    if finviz_df.empty:
        logger.warning("No Finviz candidates. Sending empty notice.")
        send_signals(finviz_df)
        return

    # --- Stage 3: Price enrichment (ALL candidates) ---
    tickers = finviz_df["Ticker"].tolist()
    price_df = enrich_candidates(tickers)

    if price_df.empty:
        logger.warning("No price data returned for any candidate.")
        send_signals(price_df)
        return

    # Merge Finviz info into price data
    merged = price_df.merge(
        finviz_df[["Ticker", "Tier", "Short Ratio", "short_float_pct"]],
        left_on="ticker", right_on="Ticker", how="left"
    ).drop(columns="Ticker")

    # --- Stage 4-5: Filters ---
    merged = apply_trend_filter(merged)
    merged = apply_proximity_filter(merged)

    # --- Stage 6: Classify ---
    merged = classify_candidates(merged)

    n_break = int((merged["category"] == "BREAKOUT").sum()) if not merged.empty else 0
    n_near = int((merged["category"] == "NEAR_BREAKOUT").sum()) if not merged.empty else 0
    n_watch = int((merged["category"] == "WATCHLIST").sum()) if not merged.empty else 0
    logger.info(
        f"Final signals: {len(merged)} "
        f"({n_break} breakout, {n_near} near, {n_watch} watchlist)"
    )

    # --- Stage 7: Dispatch + log ---
    sent = send_signals(merged)
    logged = log_signals(merged)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info(f"Scan complete in {elapsed:.0f}s. Sent {sent} messages, logged {logged} rows.")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        run_scan()
    except Exception as e:
        logger.exception(f"SCAN FAILED: {e}")
        # Notify via Telegram so a silent failure doesn't go unnoticed
        try:
            from src.output.telegram_sender import send_message
            send_message(
                f"⚠️ <b>Bot Error</b>\n\nThe scan failed:\n<code>{e}</code>\n\n"
                "Check the server logs."
            )
        except Exception:
            pass
        sys.exit(1)