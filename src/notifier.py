# src/notifier.py
import logging
import os

import httpx

from src.models import DigestResult

logger = logging.getLogger(__name__)


async def notify(digest: DigestResult, ntfy_config: dict) -> None:
    """Send push notification for a digest via Ntfy.

    Args:
        digest: The digest result to notify about.
        ntfy_config: Subscription-level ntfy config with server, topic, enabled.
    """
    if not ntfy_config.get("enabled", False):
        return

    server = ntfy_config["server"]
    topic = ntfy_config["topic"]
    url = f"{server}/{topic}"

    repo = os.environ.get("GITHUB_REPOSITORY", "ahlerjam/news-pipe")
    ref_name = os.environ.get("GITHUB_REF_NAME", "")
    ref = os.environ.get("GITHUB_REF", "")
    branch = ref_name or (ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else "master")
    github_url = f"https://github.com/{repo}/blob/{branch}/output/{digest.subscription_id}/daily/{digest.date}.md"
    logger.info(f"Ntfy link: GITHUB_REF_NAME={ref_name!r} GITHUB_REF={ref!r} branch={branch!r} url={github_url}")

    body = digest.notification_summary or digest.top3_summary

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                content=body.encode("utf-8"),
                headers={
                    "Title": f"{digest.subscription_name} - {digest.date}",
                    "Click": github_url,
                    "Actions": f"view, Open Digest, {github_url}",
                    "Tags": "robot,newspaper",
                    "Priority": "default",
                    "Markdown": "yes",
                },
            )
            if response.status_code >= 400:
                logger.error(f"Ntfy returned {response.status_code}: {response.text}")
            else:
                logger.info(f"Ntfy notification sent to {topic} (HTTP {response.status_code})")
    except httpx.HTTPError as e:
        logger.error(f"Failed to send Ntfy notification: {e}")
