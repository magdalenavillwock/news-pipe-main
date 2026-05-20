# tests/test_summarizer.py
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

from src.summarizer import summarize_daily, summarize_notification, summarize_top3, summarize_weekly, _resolve_language
from src.models import Article


def test_resolve_language_maps_de():
    assert _resolve_language("de") == "Deutsch"


def test_resolve_language_maps_en():
    assert _resolve_language("en") == "English"


def test_resolve_language_passes_through_unknown():
    assert _resolve_language("Deutsch") == "Deutsch"


@pytest.fixture
def sample_articles():
    return [
        Article(
            title="Claude 4 Released",
            url="https://anthropic.com/claude-4",
            source="Anthropic Blog",
            category="anthropic",
            published=datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc),
            summary="New Claude model",
            content=None,
        ),
        Article(
            title="GPT-5 Announced",
            url="https://openai.com/gpt5",
            source="OpenAI Blog",
            category="big_labs",
            published=datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
            summary="OpenAI announces GPT-5",
            content=None,
        ),
    ]


@pytest.fixture
def settings():
    return {
        "language": "de",
        "daily_model": "claude-sonnet-4-20250514",
        "weekly_model": "claude-opus-4-6",
    }


def _mock_process(stdout_text: str, returncode: int = 0):
    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(
        return_value=(stdout_text.encode(), b"")
    )
    mock_proc.returncode = returncode
    return mock_proc


@pytest.mark.asyncio
async def test_summarize_daily_calls_cli(sample_articles, settings):
    mock_proc = _mock_process("# AI Digest\n\nContent here")

    with patch("src.summarizer.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await summarize_daily(sample_articles, settings, prompt_focus="Focus on AI")

    assert result == "# AI Digest\n\nContent here"
    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert call_args[0] == "claude"
    assert "--model" in call_args
    assert "claude-sonnet-4-20250514" in call_args


@pytest.mark.asyncio
async def test_summarize_top3(settings):
    digest_md = "# AI Digest\n\nLots of content here about AI developments"
    mock_proc = _mock_process("Claude 4 released. GPT-5 announced. New AI tool trending.")

    with patch("src.summarizer.asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await summarize_top3(digest_md, settings)

    assert len(result) <= 500
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_summarize_notification(settings):
    digest_md = "# AI Digest\n\nLots of content here about AI developments"
    mock_proc = _mock_process("## Top News\n\n- **Claude 4** veröffentlicht\n- **GPT-5** angekündigt")

    with patch("src.summarizer.asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await summarize_notification(digest_md, settings, prompt_focus="Focus on Claude")

    assert len(result) <= 3900
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_summarize_weekly(settings):
    daily_digests = ["# Day 1\nContent"] * 7
    mock_proc = _mock_process("# Weekly Summary\n\nTrends")

    with patch("src.summarizer.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await summarize_weekly(daily_digests, settings)

    assert result.startswith("# Weekly Summary")
    call_args = mock_exec.call_args[0]
    assert "claude-opus-4-6" in call_args


@pytest.mark.asyncio
async def test_summarize_daily_uses_flight_prompt_for_flight_deals(sample_articles, settings):
    mock_proc = _mock_process("# Flug-Deals\n\n1. FRA->DPS 487 EUR")

    with patch("src.summarizer.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await summarize_daily(
            sample_articles, settings, prompt_focus="Top 5 Fluege", subscription_type="flight_deals"
        )

    assert result == "# Flug-Deals\n\n1. FRA->DPS 487 EUR"


@pytest.mark.asyncio
async def test_summarize_daily_defaults_to_news_prompt(sample_articles, settings):
    mock_proc = _mock_process("# AI Digest\n\nNews content")

    with patch("src.summarizer.asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await summarize_daily(sample_articles, settings, prompt_focus="Focus on AI")

    assert result == "# AI Digest\n\nNews content"


@pytest.mark.asyncio
async def test_call_claude_error_raises(settings):
    mock_proc = _mock_process("", returncode=1)
    mock_proc.communicate = AsyncMock(
        return_value=(b"", b"Authentication failed")
    )

    with patch("src.summarizer.asyncio.create_subprocess_exec", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="Claude CLI failed"):
            await summarize_daily([], settings)
