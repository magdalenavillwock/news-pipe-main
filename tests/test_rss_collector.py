# tests/test_rss_collector.py
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import httpx

from src.collectors.rss import RSSCollector
from src.models import Article


@pytest.fixture
def rss_config():
    return {
        "name": "Test Feed",
        "type": "rss",
        "url": "https://example.com/rss.xml",
        "priority": "high",
        "category": "news",
    }


@pytest.fixture
def settings():
    return {
        "max_articles_per_source": 3,
        "max_age_hours": 26,
        "request_timeout": 30,
        "max_retries": 3,
    }


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Article 1</title>
      <link>https://example.com/1</link>
      <description>Summary of article 1</description>
      <pubDate>RECENT_DATE</pubDate>
    </item>
    <item>
      <title>Article 2</title>
      <link>https://example.com/2</link>
      <description>Summary of article 2</description>
      <pubDate>RECENT_DATE</pubDate>
    </item>
    <item>
      <title>Old Article</title>
      <link>https://example.com/old</link>
      <description>This is old</description>
      <pubDate>Thu, 01 Jan 2020 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


def _make_rss_with_recent_dates():
    from email.utils import format_datetime
    now = datetime.now(timezone.utc)
    recent = format_datetime(now - timedelta(hours=1))
    return SAMPLE_RSS.replace("RECENT_DATE", recent)


@pytest.mark.asyncio
async def test_rss_collector_returns_articles(rss_config, settings):
    collector = RSSCollector(rss_config, settings)
    rss_body = _make_rss_with_recent_dates()

    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=httpx.Response(200, text=rss_body)):
            articles = await collector.collect(client)

    assert len(articles) == 2
    assert all(isinstance(a, Article) for a in articles)
    assert articles[0].title == "Article 1"
    assert articles[0].source == "Test Feed"
    assert articles[0].category == "news"


@pytest.mark.asyncio
async def test_rss_collector_filters_old_articles(rss_config, settings):
    collector = RSSCollector(rss_config, settings)
    rss_body = _make_rss_with_recent_dates()

    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=httpx.Response(200, text=rss_body)):
            articles = await collector.collect(client)

    titles = [a.title for a in articles]
    assert "Old Article" not in titles


@pytest.mark.asyncio
async def test_rss_collector_respects_max_articles(rss_config, settings):
    settings["max_articles_per_source"] = 1
    collector = RSSCollector(rss_config, settings)
    rss_body = _make_rss_with_recent_dates()

    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=httpx.Response(200, text=rss_body)):
            articles = await collector.collect(client)

    assert len(articles) <= 1


@pytest.mark.asyncio
async def test_rss_collector_passes_priority(rss_config, settings):
    rss_config["priority"] = "high"
    collector = RSSCollector(rss_config, settings)
    rss_body = _make_rss_with_recent_dates()

    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=httpx.Response(200, text=rss_body)):
            articles = await collector.collect(client)

    assert len(articles) > 0
    assert all(a.priority == "high" for a in articles)


@pytest.mark.asyncio
async def test_rss_collector_handles_http_error(rss_config, settings):
    collector = RSSCollector(rss_config, settings)

    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", side_effect=httpx.ConnectError("Connection refused")):
            articles = await collector.collect(client)

    assert articles == []
