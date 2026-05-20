# tests/test_factory.py
from src.collectors import build_collectors
from src.collectors.base import BaseCollector


def test_build_collectors_creates_correct_types():
    sources = {
        "anthropic": [
            {"name": "Anthropic Blog", "type": "rss", "url": "https://example.com/rss", "priority": "high"},
        ],
        "research": [
            {"name": "ArXiv cs.AI", "type": "arxiv", "arxiv_category": "cs.AI", "max_results": 5, "priority": "medium"},
        ],
        "tools": [
            {"name": "GitHub Trending", "type": "github_trending", "query": "AI", "min_stars": 50, "priority": "low"},
        ],
    }
    settings = {"max_articles_per_source": 10, "max_age_hours": 26, "request_timeout": 30, "max_retries": 3}
    collectors = build_collectors(sources, settings)
    assert len(collectors) == 3
    for c in collectors:
        assert isinstance(c, BaseCollector)


def test_build_collectors_injects_category():
    sources = {
        "anthropic": [
            {"name": "Blog", "type": "rss", "url": "https://example.com", "priority": "high"},
        ],
    }
    settings = {"max_articles_per_source": 10, "max_age_hours": 26, "request_timeout": 30, "max_retries": 3}
    collectors = build_collectors(sources, settings)
    assert collectors[0].config["category"] == "anthropic"


def test_build_collectors_empty_sources():
    collectors = build_collectors({}, {})
    assert collectors == []
