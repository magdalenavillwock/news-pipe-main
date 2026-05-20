# daily_digest.py
import asyncio
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from jinja2 import Environment, FileSystemLoader

from src.collectors import build_collectors
from src.config import load_config
from src.models import Article, DigestResult
from src.notifier import notify
from src.summarizer import summarize_daily, summarize_notification, summarize_top3

logger = logging.getLogger("news-push")


def save_markdown(digest: DigestResult, base_dir: str, configured_sources: Optional[list] = None) -> Path:
    output_dir = Path(base_dir) / digest.subscription_id / "daily"
    output_dir.mkdir(parents=True, exist_ok=True)

    template_dir = Path(__file__).parent / "templates"
    if template_dir.exists():
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("daily.md.j2")
        active_sources = set(a.source for a in digest.articles)
        all_configured = set(configured_sources) if configured_sources else active_sources
        missing_sources = sorted(all_configured - active_sources)
        content = template.render(
            date=digest.date,
            subscription_name=digest.subscription_name,
            digest_markdown=digest.digest_markdown,
            article_count=len(digest.articles),
            source_count=len(active_sources),
            total_configured=len(all_configured),
            missing_sources=missing_sources,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )
    else:
        content = f"# {digest.subscription_name} — {digest.date}\n\n{digest.digest_markdown}"

    output_path = output_dir / f"{digest.date}.md"
    output_path.write_text(content, encoding="utf-8")
    logger.info(f"Digest saved to {output_path}")
    return output_path


def save_json(articles: list[Article], digest_date: date, subscription_id: str, data_dir: str) -> Path:
    out_dir = Path(data_dir) / subscription_id
    out_dir.mkdir(parents=True, exist_ok=True)

    data = [a.to_dict() for a in articles]
    output_path = out_dir / f"{digest_date}.json"
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Raw data saved to {output_path}")
    return output_path


async def run_subscription(sub_id: str, sub_config: dict, settings: dict, output_config: dict) -> None:
    """Run the digest pipeline for a single subscription."""
    sub_name = sub_config["name"]
    language = sub_config.get("language", "de")
    prompt_focus = sub_config.get("prompt_focus", "")
    subscription_type = sub_config.get("type", "news")
    logger.info(f"[{sub_id}] Starting digest for '{sub_name}'")

    collectors = build_collectors(sub_config["sources"], settings)
    configured_sources = [c.name for c in collectors]
    logger.info(f"[{sub_id}] Built {len(collectors)} collectors")

    timeout = settings.get("request_timeout", 30)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        results = await asyncio.gather(
            *[c.collect(client) for c in collectors],
            return_exceptions=True,
        )

    articles = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"[{sub_id}] Collector {collectors[i].name} failed: {result}")
        else:
            articles.extend(result)

    logger.info(f"[{sub_id}] Collected {len(articles)} articles total")

    if not articles:
        logger.warning(f"[{sub_id}] No articles collected, skipping")
        return

    today = date.today()

    digest_markdown = await summarize_daily(articles, settings, prompt_focus, language, subscription_type)

    no_content = "keine relevanten" in digest_markdown.lower() or "nichts gefunden" in digest_markdown.lower()
    if no_content:
        top3_summary = digest_markdown.strip()
        notification_summary = digest_markdown.strip()
    else:
        top3_summary = await summarize_top3(digest_markdown, settings, language, subscription_type)
        notification_summary = await summarize_notification(digest_markdown, settings, prompt_focus, language, subscription_type)

    digest = DigestResult(
        date=today,
        subscription_id=sub_id,
        subscription_name=sub_name,
        articles=articles,
        digest_markdown=digest_markdown,
        top3_summary=top3_summary,
        notification_summary=notification_summary,
    )

    save_markdown(digest, output_config["base_dir"], configured_sources=configured_sources)
    save_json(articles, today, sub_id, output_config["data_dir"])

    ntfy_config = sub_config.get("ntfy", {})
    await notify(digest, ntfy_config)

    logger.info(f"[{sub_id}] Digest completed successfully")


async def run_daily(config_path=None, _config_override=None, subscription_filter=None) -> None:
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
            await run_subscription(sub_id, sub_config, settings, output_config)
        except Exception as e:
            logger.error(f"[{sub_id}] Failed: {e}", exc_info=True)

    logger.info("All subscriptions processed")


def main():
    from dotenv import load_dotenv
    load_dotenv()

    # Optional: run single subscription via CLI arg
    sub_filter = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_daily(subscription_filter=sub_filter))


if __name__ == "__main__":
    main()
