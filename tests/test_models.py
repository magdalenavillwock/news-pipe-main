# tests/test_models.py
from datetime import datetime, date, timezone
from src.models import Article, DigestResult


def test_article_creation():
    article = Article(
        title="Claude 4 Released",
        url="https://anthropic.com/claude-4",
        source="Anthropic Blog",
        category="anthropic",
        published=datetime(2026, 4, 3, 10, 0),
        summary="Anthropic releases Claude 4",
        content=None,
    )
    assert article.title == "Claude 4 Released"
    assert article.category == "anthropic"
    assert article.content is None


def test_article_to_dict():
    article = Article(
        title="Test",
        url="https://example.com",
        source="Test Source",
        category="news",
        published=datetime(2026, 4, 3, 10, 0),
        summary="Summary",
        content="Full content",
    )
    d = article.to_dict()
    assert d["title"] == "Test"
    assert d["published"] == "2026-04-03T10:00:00"
    assert isinstance(d, dict)


def test_article_from_dict():
    d = {
        "title": "Test",
        "url": "https://example.com",
        "source": "Test Source",
        "category": "news",
        "published": "2026-04-03T10:00:00",
        "summary": "Summary",
        "content": None,
    }
    article = Article.from_dict(d)
    assert article.title == "Test"
    assert article.published == datetime(2026, 4, 3, 10, 0)


def test_digest_result_creation():
    digest = DigestResult(
        date=date(2026, 4, 3),
        subscription_id="ai-news",
        subscription_name="AI & ML News",
        articles=[],
        digest_markdown="# Digest\nContent here",
        top3_summary="Top 3 summary text",
    )
    assert digest.date == date(2026, 4, 3)
    assert digest.subscription_id == "ai-news"
    assert digest.subscription_name == "AI & ML News"
    assert digest.digest_markdown.startswith("# Digest")
    assert len(digest.top3_summary) < 500
    assert digest.notification_summary == ""


def test_article_priority_field():
    article = Article(
        title="Test",
        url="https://example.com",
        source="Test Source",
        category="news",
        published=datetime(2026, 4, 3, tzinfo=timezone.utc),
        summary="summary",
        content=None,
        priority="high",
    )
    assert article.priority == "high"
    d = article.to_dict()
    assert d["priority"] == "high"


def test_article_priority_defaults_to_medium():
    article = Article(
        title="Test",
        url="https://example.com",
        source="Test Source",
        category="news",
        published=datetime(2026, 4, 3, tzinfo=timezone.utc),
        summary="summary",
        content=None,
    )
    assert article.priority == "medium"
