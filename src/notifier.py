# src/notifier.py
import json
import logging
import os

import httpx

from src.models import DigestResult

logger = logging.getLogger(__name__)


def _build_notification(digest: DigestResult, ntfy_config: dict) -> dict | None:
    if not ntfy_config.get("enabled", False):
        return None

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        return None
    ref_name = os.environ.get("GITHUB_REF_NAME", "")
    ref = os.environ.get("GITHUB_REF", "")
    branch = ref_name or (ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else "master")

    if digest.digest_type == "weekly":
        iso = digest.date.isocalendar()
        filename = f"{iso[0]}-W{iso[1]:02d}.md"
        subdir = "weekly"
    else:
        filename = f"{digest.date}.md"
        subdir = "daily"

    github_url = f"https://github.com/{repo}/blob/{branch}/output/{digest.subscription_id}/{subdir}/{filename}"
    logger.info(f"Ntfy link: branch={branch!r} url={github_url}")

    return {
        "server": ntfy_config["server"],
        "topic": ntfy_config["topic"],
        "github_url": github_url,
        "title": f"{digest.subscription_name} - {digest.date}",
        "body": digest.notification_summary or digest.top3_summary,
    }


async def _send(notification: dict) -> None:
    url = f"{notification['server']}/{notification['topic']}"
    github_url = notification["github_url"]
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=notification["body"].encode("utf-8"),
                headers={
                    "Title": notification["title"],
                    "Click": github_url,
                    "Actions": f"view, Vollstaendiger Digest, {github_url}",
                    "Tags": "robot,newspaper",
                    "Priority": "default",
                    "Markdown": "yes",
                },
            )
            if response.status_code >= 400:
                logger.error(f"Ntfy returned {response.status_code}: {response.text}")
            else:
                logger.info(f"Ntfy notification sent to {notification['topic']} (HTTP {response.status_code})")
    except httpx.HTTPError as e:
        logger.error(f"Failed to send Ntfy notification: {e}")


async def notify(digest: DigestResult, ntfy_config: dict) -> None:
    queue_path = os.environ.get("NOTIFY_QUEUE_FILE")
    notification = _build_notification(digest, ntfy_config)
    if notification is None:
        return

    if queue_path:
        with open(queue_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(notification, ensure_ascii=False) + "\n")
        logger.info(f"Notification queued to {queue_path}")
    else:
        await _send(notification)


async def flush_notifications(queue_path: str) -> None:
    try:
        with open(queue_path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        logger.info("No notification queue file found, nothing to send")
        return

    for line in lines:
        notification = json.loads(line)
        await _send(notification)

    os.remove(queue_path)
