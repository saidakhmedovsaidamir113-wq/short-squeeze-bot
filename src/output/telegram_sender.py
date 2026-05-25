"""
telegram_sender.py
------------------
Sends short squeeze signals to Telegram, ranked by squeeze readiness.

Ranking (research-backed): breakout proximity is the timing signal,
short float is the magnitude. So we rank:
  1. BREAKOUTS (price broke 100-day high)
  2. NEAR-BREAKOUTS (within 3% of high)
  3. WATCHLIST (passed filters, further out)
...and within each, sort by short float (bigger potential move first).

Each stock gets a direct per-ticker Musaffa link for one-tap halal check.
"""

import logging
import time
import requests

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.halal.manual_link_checker import get_musaffa_link, get_zoya_link

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
MAX_MESSAGE_LEN = 3800


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send a single text message to the configured Telegram chat."""
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        logger.error(f"Telegram HTTP error: {e} | {detail}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram network error: {e}")
        return False


def _format_stock_block(row: dict) -> str:
    """Format one stock into a multi-line block with per-ticker halal link."""
    ticker = row["ticker"]
    sf = row.get("short_float_pct")
    sf_str = f"{sf:.1f}%" if sf is not None and sf == sf else "n/a"
    sr = row.get("Short Ratio", 0)
    price = row.get("current_price", 0)
    category = row.get("category", "WATCHLIST")

    # Conviction & volume badges
    badges = ""
    if row.get("high_conviction"):
        badges += " 💪"  # Short Ratio > 8
    if row.get("volume_confirmed"):
        badges += " 📈"  # above-average volume

    # First line differs by category
    if category == "BREAKOUT":
        first = (
            f"🚨 <b>${ticker}</b>{badges} | SF {sf_str} | SR {sr:.1f} | "
            f"${price:.2f} <b>BROKE ${row['high_100d']:.2f}</b>"
        )
    elif category == "NEAR_BREAKOUT":
        dist = row.get("distance_from_high_pct", 0) * 100
        first = (
            f"⭐ <b>${ticker}</b>{badges} | SF {sf_str} | SR {sr:.1f} | "
            f"${price:.2f} ({dist:.1f}% from ${row['high_100d']:.2f})"
        )
    else:  # WATCHLIST
        dist = row.get("distance_from_high_pct", 0) * 100
        first = (
            f"• <b>${ticker}</b>{badges} | SF {sf_str} | SR {sr:.1f} | "
            f"${price:.2f} ({dist:.1f}% below high)"
        )

    musaffa = get_musaffa_link(ticker)
    zoya = get_zoya_link(ticker)
    second = (
        f"   ☪️ <a href=\"{musaffa}\">Musaffa ${ticker}</a> | "
        f"<a href=\"{zoya}\">Zoya</a>"
    )
    return first + "\n" + second


def _build_section(df, title: str) -> list:
    """Build message(s) for one section, sorted closest-to-breakout first."""
    if df.empty:
        return []
    df = df.copy()
    # Sort by distance to 100-day high, ascending = closest to breakout first.
    # (Breakouts have negative distance, so they naturally lead.)
    if "distance_from_high_pct" in df.columns:
        df = df.sort_values("distance_from_high_pct", ascending=True)

    header = f"{title}\n━━━━━━━━━━━━━━━━━━━\n"
    blocks = [_format_stock_block(r.to_dict()) for _, r in df.iterrows()]

    messages, current = [], header
    for b in blocks:
        if len(current) + len(b) + 2 > MAX_MESSAGE_LEN:
            messages.append(current)
            current = header + b + "\n"
        else:
            current += b + "\n"
    messages.append(current)
    return messages


def send_signals(df) -> int:
    """
    Send signals ranked by squeeze readiness, with per-ticker halal links.

    Legend (sent once at top):
      🚨 breakout | ⭐ near-breakout | • watchlist
      💪 Short Ratio>8 | 📈 above-avg volume
    """
    if df is None or df.empty:
        send_message(
            "📭 <b>Short Squeeze Scan Complete</b>\n\n"
            "No stocks passed the full strategy this run.\n"
            "<i>The strategy is selective — this is normal.</i>"
        )
        return 1

    # Legend / header message
    legend = (
        "📊 <b>SHORT SQUEEZE SIGNALS</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🚨 = Breakout (broke 100-day high)\n"
        "⭐ = Near breakout (within 3%)\n"
        "• = Watchlist\n"
        "💪 = High conviction (Short Ratio &gt; 8)\n"
        "📈 = Volume confirmed (above average)\n\n"
        "<i>Tap a ticker's halal link to verify before trading.\n"
        "⚠️ Not financial advice. Always DYOR.</i>"
    )
    sent = 0
    if send_message(legend):
        sent += 1
        time.sleep(0.5)

    # Sections in priority order
    sections = [
        (df[df["category"] == "BREAKOUT"], "🚨 <b>BREAKOUTS — ENTRY READY</b> 🚨"),
        (df[df["category"] == "NEAR_BREAKOUT"], "⭐ <b>NEAR BREAKOUT — TOP WATCH</b>"),
        (df[df["category"] == "WATCHLIST"], "👀 <b>WATCHLIST</b>"),
    ]

    for section_df, title in sections:
        for msg in _build_section(section_df, title):
            if send_message(msg):
                sent += 1
                time.sleep(0.5)

    logger.info(f"Sent {sent} message(s) to Telegram.")
    return sent