# tests/test_github_collector.py
import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import httpx

from src.collectors.github import GitHubCollector
from src.models import Article

_DUMMY_REQUEST = httpx.Request("GET", "https://api.github.com/")


@pytest.fixture
def settings():
    return {
        "max_articles_per_source": 10,
        "max_age_hours": 26,
        "request_timeout": 30,
        "max_retries": 3,
    }


@pytest.fixture
def releases_config():
    return {
        "name": "Claude Code Releases",
        "type": "github_releases",
        "repo": "anthropics/claude-code",
        "priority": "high",
        "category": "anthropic",
    }


def _make_releases_response():
    now = datetime.now(timezone.utc)
    return [
        {
            "tag_name": "v1.2.0",
            "name": "Release 1.2.0",
            "html_url": "https://github.com/anthropics/claude-code/releases/tag/v1.2.0",
            "body": "New features and fixes",
            "published_at": now.isoformat(),
        },
        {
            "tag_name": "v0.1.0",
            "name": "Old Release",
            "html_url": "https://github.com/anthropics/claude-code/releases/tag/v0.1.0",
            "body": "Initial release",
            "published_at": "2020-01-01T00:00:00Z",
        },
    ]


@pytest.mark.asyncio
async def test_github_releases_returns_recent(releases_config, settings):
    collector = GitHubCollector(releases_config, settings)
    response_data = _make_releases_response()

    async with httpx.AsyncClient() as client:
        with patch.object(
            client, "get",
            return_value=httpx.Response(200, json=response_data, request=_DUMMY_REQUEST),
        ):
            articles = await collector.collect(client)

    assert len(articles) == 1
    assert articles[0].title == "Release 1.2.0"
    assert articles[0].source == "Claude Code Releases"
    assert articles[0].category == "anthropic"


@pytest.fixture
def trending_config():
    return {
        "name": "GitHub Trending AI",
        "type": "github_trending",
        "query": "artificial intelligence OR LLM",
        "min_stars": 50,
        "priority": "low",
        "category": "tools",
    }


def _make_trending_response():
    return {
        "items": [
            {
                "full_name": "cool/ai-tool",
                "html_url": "https://github.com/cool/ai-tool",
                "description": "An amazing AI tool",
                "stargazers_count": 200,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "full_name": "small/repo",
                "html_url": "https://github.com/small/repo",
                "description": "Too few stars",
                "stargazers_count": 10,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
    }


@pytest.mark.asyncio
async def test_github_trending_filters_by_stars(trending_config, settings):
    collector = GitHubCollector(trending_config, settings)
    response_data = _make_trending_response()

    async with httpx.AsyncClient() as client:
        with patch.object(
            client, "get",
            return_value=httpx.Response(200, json=response_data, request=_DUMMY_REQUEST),
        ):
            articles = await collector.collect(client)

    assert len(articles) == 1
    assert "cool/ai-tool" in articles[0].title


@pytest.mark.asyncio
async def test_github_collector_handles_error(releases_config, settings):
    collector = GitHubCollector(releases_config, settings)

    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", side_effect=httpx.ConnectError("fail")):
            articles = await collector.collect(client)

    assert articles == []
