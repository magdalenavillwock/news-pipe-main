# tests/test_notifier.py
import pytest
from datetime import date
from unittest.mock import patch, AsyncMock

import httpx

from src.notifier import notify
from src.models import DigestResult


@pytest.fixture
def digest():
    return DigestResult(
        date=date(2026, 4, 3),
        subscription_id="ai-news",
        subscription_name="AI & ML News",
        articles=[],
        digest_markdown="# Full Digest",
        top3_summary="Claude 4 released. GPT-5 announced. New AI tool trending.",
        notification_summary="## Top News\n\n- **Claude 4** released\n- **GPT-5** announced",
    )


@pytest.fixture
def ntfy_config():
    return {
        "enabled": True,
        "server": "https://ntfy.sh",
        "topic": "news-push-ai",
    }


@pytest.mark.asyncio
async def test_notify_sends_to_ntfy(digest, ntfy_config):
    with patch("src.notifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = httpx.Response(200)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        await notify(digest, ntfy_config)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "ntfy.sh/news-push-ai" in call_args[0][0]
        assert call_args[1]["headers"]["Title"] == "AI & ML News - 2026-04-03"
        assert call_args[1]["headers"]["Markdown"] == "yes"
        assert b"Claude 4 released" in call_args[1]["content"]


@pytest.mark.asyncio
async def test_notify_includes_actions_header(digest, ntfy_config):
    """Actions header adds a button inside the ntfy app."""
    with patch("src.notifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = httpx.Response(200)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        await notify(digest, ntfy_config)

        headers = mock_client.post.call_args[1]["headers"]
        assert "Actions" in headers
        assert headers["Actions"].startswith("view,")
        assert "github.com" in headers["Actions"]
        assert headers["Click"] in headers["Actions"]


@pytest.mark.asyncio
async def test_notify_falls_back_to_top3(ntfy_config):
    """When notification_summary is empty, fall back to top3_summary."""
    digest_no_notification = DigestResult(
        date=date(2026, 4, 3),
        subscription_id="ai-news",
        subscription_name="AI & ML News",
        articles=[],
        digest_markdown="# Full Digest",
        top3_summary="Short top3 fallback text.",
        notification_summary="",
    )

    with patch("src.notifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = httpx.Response(200)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        await notify(digest_no_notification, ntfy_config)

        call_args = mock_client.post.call_args
        assert b"Short top3 fallback text." in call_args[1]["content"]


@pytest.mark.asyncio
async def test_notify_skips_when_disabled(digest, ntfy_config):
    ntfy_config["enabled"] = False

    with patch("src.notifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value = mock_client

        await notify(digest, ntfy_config)

        mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_notify_handles_error(digest, ntfy_config):
    """Ntfy errors should be logged, not raised."""
    with patch("src.notifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        # Should not raise
        await notify(digest, ntfy_config)
