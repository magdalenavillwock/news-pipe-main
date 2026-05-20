# src/collectors/arxiv.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

import arxiv
import httpx

from src.collectors.base import BaseCollector
from src.models import Article

logger = logging.getLogger(__name__)


class ArxivCollector(BaseCollector):
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        try:
            results = await asyncio.to_thread(self._search)
        except Exception as e:
            logger.error(f"ArXiv search failed for {self.name}: {e}")
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.settings["max_age_hours"]
        )
        articles = []
        for paper in results:
            published = paper.published.replace(tzinfo=timezone.utc) if paper.published.tzinfo is None else paper.published
            if published < cutoff:
                continue
            articles.append(
                Article(
                    title=paper.title,
                    url=paper.entry_id,
                    source=self.name,
                    category=self.category,
                    published=published,
                    summary=paper.summary[:500] if paper.summary else None,
                    content=None,
                    priority=self.priority,
                )
            )
        return articles

    def _search(self) -> list:
        max_results = self.config.get("max_results", 5)
        arxiv_category = self.config.get("arxiv_category", "cs.AI")
        search = arxiv.Search(
            query=f"cat:{arxiv_category}",
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        arxiv_client = arxiv.Client()
        return list(arxiv_client.results(search))
