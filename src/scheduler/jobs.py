"""
jobs.py
-------
Scheduler that runs the bot automatically.

- Weekly full scan: Sunday evening (Tashkent) — fresh watchlist for the week
- Daily breakout check: weekday mornings (Tashkent) — uses prior US close

Uses APScheduler's BlockingScheduler. On a cloud server this process
stays alive 24/7 and fires the jobs on schedule.

Run with:  python -m src.scheduler.jobs
"""

import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import OUTPUT, PROJECT_ROOT, SCHEDULE

# ---------------------------------------------------------------
# Logging
# ---------------------------------------------------------------
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
logger = logging.getLogger("scheduler")

from src.main import run_scan
from src.output.telegram_sender import send_message


def weekly_scan_job():
    """Sunday evening full scan."""
    logger.info(">>> WEEKLY SCAN triggered")
    try:
        run_scan()
    except Exception as e:
        logger.exception(f"Weekly scan failed: {e}")
        send_message(f"⚠️ <b>Weekly scan failed</b>\n<code>{e}</code>")


def daily_check_job():
    """Weekday morning breakout check."""
    logger.info(">>> DAILY CHECK triggered")
    try:
        run_scan()
    except Exception as e:
        logger.exception(f"Daily check failed: {e}")
        send_message(f"⚠️ <b>Daily check failed</b>\n<code>{e}</code>")


def main():
    tz = SCHEDULE["timezone"]
    scheduler = BlockingScheduler(timezone=tz)

    # Weekly scan — Sunday evening
    scheduler.add_job(
        weekly_scan_job,
        CronTrigger(
            day_of_week=SCHEDULE["weekly_scan_day"],
            hour=int(SCHEDULE["weekly_scan_time"].split(":")[0]),
            minute=int(SCHEDULE["weekly_scan_time"].split(":")[1]),
            timezone=tz,
        ),
        id="weekly_scan",
        name="Weekly full scan",
    )

    # Daily check — weekday mornings
    scheduler.add_job(
        daily_check_job,
        CronTrigger(
            day_of_week=SCHEDULE["daily_check_days"],
            hour=int(SCHEDULE["daily_check_time"].split(":")[0]),
            minute=int(SCHEDULE["daily_check_time"].split(":")[1]),
            timezone=tz,
        ),
        id="daily_check",
        name="Daily breakout check",
    )

    logger.info("=" * 60)
    logger.info(f"SCHEDULER STARTED (timezone: {tz})")
    logger.info(f"  Weekly scan: {SCHEDULE['weekly_scan_day']} at {SCHEDULE['weekly_scan_time']}")
    logger.info(f"  Daily check: {SCHEDULE['daily_check_days']} at {SCHEDULE['daily_check_time']}")
    logger.info("  Waiting for scheduled times... (Ctrl+C to stop)")
    logger.info("=" * 60)

    # Notify on startup so you know the scheduler is alive
    try:
        send_message(
            "🤖 <b>Short Squeeze Bot is LIVE</b>\n\n"
            f"📅 Weekly scan: Sunday {SCHEDULE['weekly_scan_time']}\n"
            f"📈 Daily check: Mon–Fri {SCHEDULE['daily_check_time']}\n"
            f"🌍 Timezone: {tz}\n\n"
            "<i>I'll send signals automatically. Standing by.</i>"
        )
    except Exception:
        pass

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()