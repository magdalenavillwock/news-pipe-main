# tests/test_daily_digest.py
import pytest
import json
from datetime import datetime, date, timezone
from pathlib import Path
from unittest.mock import patch, AsyncMock

from daily_digest import run_daily, save_markdown, save_json
from src.models import Article, DigestResult


@pytest.fixture
def sample_articles():
    return [
        Article(
            title="Test Article",
            url="https://example.com",
            source="Test Source",
            category="news",
            published=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
            summary="A test article",
            content=None,
        ),
    ]


@pytest.fixture
def sample_digest(sample_articles):
    return DigestResult(
        date=date(2026, 4, 3),
        subscription_id="ai-news",
        subscription_name="AI & ML News",
        articles=sample_articles,
        digest_markdown="# Digest\nContent",
        top3_summary="Top 3 summary",
    )


def test_save_markdown(sample_digest, tmp_path):
    save_markdown(sample_digest, str(tmp_path))

    output_file = tmp_path / "ai-news" / "daily" / "2026-04-03.md"
    assert output_file.exists()
    content = output_file.read_text()
    assert "AI & ML News" in content
    assert "# Digest" in content


def test_save_markdown_includes_diagnostics(sample_digest, tmp_path):
    configured_sources = ["Test Source", "OpenAI Blog", "Google DeepMind"]
    save_markdown(sample_digest, str(tmp_path), configured_sources=configured_sources)

    output_file = tmp_path / "ai-news" / "daily" / "2026-04-03.md"
    content = output_file.read_text()
    assert "3 konfigurierten Quellen" in content
    assert "Keine Daten von:" in content
    assert "OpenAI Blog" in content
    assert "Google DeepMind" in content


def test_save_json(sample_articles, tmp_path):
    save_json(sample_articles, date(2026, 4, 3), "ai-news", str(tmp_path))

    output_file = tmp_path / "ai-news" / "2026-04-03.json"
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert len(data) == 1
    assert data[0]["title"] == "Test Article"


@pytest.mark.asyncio
async def test_run_daily_full_pipeline(tmp_path):
    config = {
        "settings": {
            "max_articles_per_source": 10,
            "max_age_hours": 26,
            "request_timeout": 30,
            "max_retries": 3,
            "daily_model": "claude-sonnet-4-20250514",
            "language": "de",
            "log_level": "INFO",
        },
        "subscriptions": {
            "test-abo": {
                "name": "Test Abo",
                "language": "de",
                "prompt_focus": "",
                "ntfy": {"enabled": False, "server": "https://ntfy.sh", "topic": "test"},
                "sources": {
                    "news": [
                        {"name": "Test", "type": "rss", "url": "https://example.com/rss", "priority": "high"},
                    ],
                },
            },
        },
        "output": {
            "base_dir": str(tmp_path / "output"),
            "data_dir": str(tmp_path / "data"),
        },
    }
    mock_articles = [
        Article(
            title="News",
            url="https://example.com",
            source="Test",
            category="news",
            published=datetime.now(timezone.utc),
            summary="Summary",
            content=None,
        ),
    ]

    with patch("daily_digest.load_config", return_value=config), \
         patch("daily_digest.build_collectors") as mock_build, \
         patch("daily_digest.summarize_daily", new_callable=AsyncMock, return_value="# Digest"), \
         patch("daily_digest.summarize_top3", new_callable=AsyncMock, return_value="Top 3"), \
         patch("daily_digest.summarize_notification", new_callable=AsyncMock, return_value="## Full notification"), \
         patch("daily_digest.notify", new_callable=AsyncMock):

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_articles)
        mock_build.return_value = [mock_collector]

        await run_daily(config_path=None, _config_override=config)

    assert (tmp_path / "output" / "test-abo" / "daily").exists()
    assert (tmp_path / "data" / "test-abo").exists()
