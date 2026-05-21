# weekly_summary.py
import asyncio
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from src.config import load_config
from src.models import DigestResult
from src.notifier import notify
from src.summarizer import summarize_weekly, summarize_top3, summarize_notification

logger = logging.getLogger("news-push")


def load_daily_digests(base_dir: str, subscription_id: str, days: int = 7) -> list[str]:
    path = Path(base_dir) / subscription_id / "daily"
    if not path.exists():
        return []

    md_files = sorted(path.glob("*.md"), reverse=True)[:days]
    md_files.reverse()  # chronological order
    return [f.read_text(encoding="utf-8") for f in md_files]


async def run_subscription_weekly(sub_id: str, sub_config: dict, settings: dict, output_config: dict) -> None:
    """Run weekly summary for a single subscription."""
    sub_name = sub_config["name"]
    language = sub_config.get("language", "de")
    prompt_focus = sub_config.get("prompt_focus", "")
    subscription_type = sub_config.get("type", "news")

    digests = load_daily_digests(output_config["base_dir"], sub_id)

    if not digests:
        logger.warning(f"[{sub_id}] No daily digests found, skipping weekly summary")
        return

    logger.info(f"[{sub_id}] Loaded {len(digests)} daily digests for weekly summary")

    weekly_markdown = await summarize_weekly(digests, settings, prompt_focus, language, subscription_type)
    top3 = await summarize_top3(weekly_markdown, settings, language, subscription_type)
    notification_summary = await summarize_notification(weekly_markdown, settings, prompt_focus, language, subscription_type)

    today = date.today()
    week_number = today.isocalendar()[1]
    year = today.isocalendar()[0]

    weekly_dir = Path(output_config["base_dir"]) / sub_id / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    output_path = weekly_dir / f"{year}-W{week_number:02d}.md"
    output_path.write_text(
        f"# {sub_name} — Wochenrückblick KW {week_number} {year}\n\n{weekly_markdown}\n\n---\n\n"
        f"*Basierend auf {len(digests)} Tages-Digests*\n"
        f"*Generiert am {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n",
        encoding="utf-8",
    )

    digest = DigestResult(
        date=today,
        subscription_id=sub_id,
        subscription_name=sub_name,
        articles=[],
        digest_markdown=weekly_markdown,
        top3_summary=top3,
        notification_summary=notification_summary,
        digest_type="weekly",
    )

    ntfy_config = sub_config.get("ntfy", {})
    await notify(digest, ntfy_config)

    logger.info(f"[{sub_id}] Weekly summary saved to {output_path}")


async def run_weekly(config_path=None, _config_override=None, subscription_filter=None) -> None:
    config = _config_override or load_config(config_path)
    log_level = config.get("settings", {}).get("log_level", "INFO")
    logging.basicConfig(level=getattr(logging, log_level), format="%(asctime)s %(name)s %(levelname)s %(message)s")

    settings = config["settings"]
    output_config = config["output"]
    subscriptions = config.get("subscriptions", {})

    if not subscriptions:
        logger.warning("No subscriptions configured")
        return

    for sub_id, sub_config in subscriptions.items():
        if subscription_filter and sub_id != subscription_filter:
            continue
        try:
            await run_subscription_weekly(sub_id, sub_config, settings, output_config)
        except Exception as e:
            logger.error(f"[{sub_id}] Weekly failed: {e}", exc_info=True)

    logger.info("All weekly summaries processed")


def main():
    from dotenv import load_dotenv
    load_dotenv()

    sub_filter = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_weekly(subscription_filter=sub_filter))


if __name__ == "__main__":
    main()
