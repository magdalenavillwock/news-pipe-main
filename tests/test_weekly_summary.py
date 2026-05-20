# tests/test_weekly_summary.py
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import patch, AsyncMock


def test_load_daily_digests(tmp_path):
    from weekly_summary import load_daily_digests

    daily_dir = tmp_path / "ai-news" / "daily"
    daily_dir.mkdir(parents=True)
    for i in range(1, 8):
        (daily_dir / f"2026-04-0{i}.md").write_text(f"# Digest Day {i}")

    digests = load_daily_digests(str(tmp_path), "ai-news", days=7)
    assert len(digests) == 7
    assert "Day 1" in digests[0]


def test_load_daily_digests_fewer_than_7(tmp_path):
    from weekly_summary import load_daily_digests

    daily_dir = tmp_path / "ai-news" / "daily"
    daily_dir.mkdir(parents=True)
    (daily_dir / "2026-04-01.md").write_text("# Only one")

    digests = load_daily_digests(str(tmp_path), "ai-news", days=7)
    assert len(digests) == 1


@pytest.mark.asyncio
async def test_run_weekly(tmp_path):
    from weekly_summary import run_weekly

    daily_dir = tmp_path / "output" / "ai-news" / "daily"
    daily_dir.mkdir(parents=True)
    for i in range(1, 8):
        (daily_dir / f"2026-04-0{i}.md").write_text(f"# Digest Day {i}")

    config = {
        "settings": {
            "weekly_model": "claude-opus-4-6",
            "daily_model": "claude-sonnet-4-20250514",
            "language": "de",
            "log_level": "INFO",
        },
        "subscriptions": {
            "ai-news": {
                "name": "AI & ML News",
                "language": "de",
                "prompt_focus": "",
                "ntfy": {"enabled": False, "server": "https://ntfy.sh", "topic": "test"},
                "sources": {},
            },
        },
        "output": {
            "base_dir": str(tmp_path / "output"),
            "data_dir": str(tmp_path / "data"),
        },
    }

    with patch("weekly_summary.load_config", return_value=config), \
         patch("weekly_summary.summarize_weekly", new_callable=AsyncMock, return_value="# Weekly\nTrends"), \
         patch("weekly_summary.summarize_top3", new_callable=AsyncMock, return_value="Weekly top 3"), \
         patch("weekly_summary.summarize_notification", new_callable=AsyncMock, return_value="## Weekly summary"), \
         patch("weekly_summary.notify", new_callable=AsyncMock):

        await run_weekly(config_path=None, _config_override=config)

    weekly_dir = tmp_path / "output" / "ai-news" / "weekly"
    assert weekly_dir.exists()
    weekly_files = list(weekly_dir.glob("*.md"))
    assert len(weekly_files) == 1
