# tests/test_arxiv_collector.py
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import httpx

from src.collectors.arxiv import ArxivCollector
from src.models import Article


@pytest.fixture
def arxiv_config():
    return {
        "name": "ArXiv cs.AI",
        "type": "arxiv",
        "category": "research",
        "arxiv_category": "cs.AI",
        "max_results": 3,
        "priority": "medium",
    }


@pytest.fixture
def settings():
    return {
        "max_articles_per_source": 10,
        "max_age_hours": 26,
        "request_timeout": 30,
        "max_retries": 3,
    }


def _make_mock_results():
    now = datetime.now(timezone.utc)
    mock1 = MagicMock()
    mock1.title = "Attention Is All You Need v2"
    mock1.entry_id = "http://arxiv.org/abs/2026.12345"
    mock1.summary = "We improve transformer architecture"
    mock1.published = now - timedelta(hours=2)
    mock1.pdf_url = "http://arxiv.org/pdf/2026.12345"

    mock2 = MagicMock()
    mock2.title = "Old Paper"
    mock2.entry_id = "http://arxiv.org/abs/2020.00001"
    mock2.summary = "Very old paper"
    mock2.published = datetime(2020, 1, 1, tzinfo=timezone.utc)
    mock2.pdf_url = "http://arxiv.org/pdf/2020.00001"

    return [mock1, mock2]


@pytest.mark.asyncio
async def test_arxiv_collector_returns_recent_papers(arxiv_config, settings):
    collector = ArxivCollector(arxiv_config, settings)
    mock_results = _make_mock_results()

    with patch("src.collectors.arxiv.arxiv.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.results.return_value = mock_results
        MockClient.return_value = mock_client

        async with httpx.AsyncClient() as client:
            articles = await collector.collect(client)

    assert len(articles) == 1
    assert articles[0].title == "Attention Is All You Need v2"
    assert articles[0].category == "research"


@pytest.mark.asyncio
async def test_arxiv_collector_handles_error(arxiv_config, settings):
    collector = ArxivCollector(arxiv_config, settings)

    with patch("src.collectors.arxiv.arxiv.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.results.side_effect = Exception("API error")
        MockClient.return_value = mock_client

        async with httpx.AsyncClient() as client:
            articles = await collector.collect(client)

    assert articles == []
