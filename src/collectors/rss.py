from __future__ import annotations

# src/collectors/rss.py
import logging
from datetime import datetime, timezone, timedelta

import feedparser
import httpx

from src.collectors.base import BaseCollector
from src.models import Article

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        url = self.config["url"]
        try:
            response = await client.get(url, headers={"User-Agent": "NewsDigest/1.0 (RSS Reader)"})
            if response.status_code >= 400:
                logger.error(f"HTTP {response.status_code} fetching RSS feed {self.name}")
                return []
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch RSS feed {self.name}: {e}")
            return []

        feed = feedparser.parse(response.text)
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.settings["max_age_hours"]
        )
        max_articles = self.settings["max_articles_per_source"]

        articles = []
        for entry in feed.entries:
            published = self._parse_date(entry)
            if published and published < cutoff:
                continue

            articles.append(
                Article(
                    title=entry.get("title", "Untitled"),
                    url=entry.get("link", ""),
                    source=self.name,
                    category=self.category,
                    published=published or datetime.now(timezone.utc),
                    summary=entry.get("summary"),
                    content=entry.get("content", [{}])[0].get("value") if entry.get("content") else None,
                    priority=self.priority,
                )
            )

            if len(articles) >= max_articles:
                break

        return articles

    def _parse_date(self, entry) -> datetime | None:
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if time_struct is None:
            return None
        from calendar import timegm
        timestamp = timegm(time_struct)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
