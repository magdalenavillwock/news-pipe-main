# src/collectors/github.py
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta

import httpx

from src.collectors.base import BaseCollector
from src.models import Article

logger = logging.getLogger(__name__)


class GitHubCollector(BaseCollector):
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        collector_type = self.config["type"]
        try:
            if collector_type == "github_releases":
                return await self._collect_releases(client)
            elif collector_type == "github_trending":
                return await self._collect_trending(client)
            else:
                logger.error(f"Unknown GitHub collector type: {collector_type}")
                return []
        except httpx.HTTPError as e:
            logger.error(f"GitHub API error for {self.name}: {e}")
            return []

    async def _collect_releases(self, client: httpx.AsyncClient) -> list[Article]:
        repo = self.config["repo"]
        url = f"https://api.github.com/repos/{repo}/releases"
        response = await client.get(url, headers=self._headers())
        response.raise_for_status()

        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.settings["max_age_hours"]
        )
        articles = []
        for release in response.json():
            published = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
            if published < cutoff:
                continue
            articles.append(
                Article(
                    title=release.get("name") or release["tag_name"],
                    url=release["html_url"],
                    source=self.name,
                    category=self.category,
                    published=published,
                    summary=release.get("body", "")[:500],
                    content=release.get("body"),
                    priority=self.priority,
                )
            )
        return articles[: self.settings["max_articles_per_source"]]

    async def _collect_trending(self, client: httpx.AsyncClient) -> list[Article]:
        query = self.config["query"]
        min_stars = self.config.get("min_stars", 100)
        days_back = self.config.get("days_back", 7)
        since = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"{query} pushed:>{since} stars:>{min_stars}",
            "sort": "stars",
            "order": "desc",
            "per_page": self.settings["max_articles_per_source"],
        }
        response = await client.get(url, params=params, headers=self._headers())
        response.raise_for_status()

        articles = []
        for repo in response.json().get("items", []):
            if repo["stargazers_count"] < min_stars:
                continue
            articles.append(
                Article(
                    title=f"{repo['full_name']} ({repo['stargazers_count']}★)",
                    url=repo["html_url"],
                    source=self.name,
                    category=self.category,
                    published=datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00")),
                    summary=repo.get("description"),
                    content=None,
                    priority=self.priority,
                )
            )
        return articles

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers
