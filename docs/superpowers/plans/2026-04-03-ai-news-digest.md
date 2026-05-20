# AI News Digest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated AI news digest system that collects news from RSS feeds and APIs, summarizes via Claude API, saves as Markdown, and sends push notifications via Ntfy.sh.

**Architecture:** Async collector layer (httpx + asyncio.gather) feeds articles into Claude API summarizer, output saved as Markdown to repo, push notification via Ntfy.sh. GitHub Actions runs daily/weekly on cron. iOS Shortcut triggers manual runs.

**Tech Stack:** Python 3.12, httpx, feedparser, arxiv, anthropic SDK, Jinja2, tenacity, Ntfy.sh, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-04-03-ai-news-digest-design.md`

**GitHub:** `ahlerjam/ai-news-digest`

---

## File Map

| File                                   | Purpose                                    |
| -------------------------------------- | ------------------------------------------ |
| `requirements.txt`                     | Python dependencies                        |
| `requirements-dev.txt`                 | Test dependencies (pytest, pytest-asyncio) |
| `.gitignore`                           | Python + project-specific ignores          |
| `.env.example`                         | Template for secrets                       |
| `config.yaml`                          | Sources, settings, ntfy config             |
| `src/__init__.py`                      | Package init                               |
| `src/models.py`                        | Article + DigestResult dataclasses         |
| `src/config.py`                        | Config loading + validation                |
| `src/collectors/__init__.py`           | Factory: build_collectors()                |
| `src/collectors/base.py`               | BaseCollector ABC                          |
| `src/collectors/rss.py`                | RSSCollector                               |
| `src/collectors/github.py`             | GitHubCollector (releases + trending)      |
| `src/collectors/arxiv.py`              | ArxivCollector                             |
| `src/summarizer.py`                    | Claude API integration                     |
| `src/notifier.py`                      | Ntfy.sh push notifications                 |
| `templates/daily.md.j2`                | Jinja2 template for daily output           |
| `daily_digest.py`                      | Entrypoint: daily run                      |
| `weekly_summary.py`                    | Entrypoint: weekly run                     |
| `.github/workflows/daily-digest.yml`   | GitHub Actions: daily cron                 |
| `.github/workflows/weekly-summary.yml` | GitHub Actions: weekly cron                |
| `README.md`                            | Setup guide + iOS Shortcut instructions    |
| `tests/test_models.py`                 | Tests for models                           |
| `tests/test_config.py`                 | Tests for config loader                    |
| `tests/test_rss_collector.py`          | Tests for RSS collector                    |
| `tests/test_github_collector.py`       | Tests for GitHub collector                 |
| `tests/test_arxiv_collector.py`        | Tests for ArXiv collector                  |
| `tests/test_factory.py`                | Tests for collector factory                |
| `tests/test_summarizer.py`             | Tests for summarizer                       |
| `tests/test_notifier.py`               | Tests for notifier                         |
| `tests/test_daily_digest.py`           | Tests for daily orchestrator               |
| `tests/test_weekly_summary.py`         | Tests for weekly orchestrator              |

---

### Task 1: Project Scaffolding

**Files:**

- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `config.yaml`
- Create: `src/__init__.py`
- Create: `src/collectors/__init__.py`
- Create: `tests/__init__.py`
- Create: `output/daily/.gitkeep`
- Create: `output/weekly/.gitkeep`
- Create: `data/.gitkeep`
- Create: `templates/.gitkeep`

- [ ] **Step 1: Create requirements.txt**

```
feedparser>=6.0
httpx>=0.27
arxiv>=2.1
anthropic>=0.40
pyyaml>=6.0
python-dotenv>=1.0
jinja2>=3.1
tenacity>=8.0
```

- [ ] **Step 2: Create requirements-dev.txt**

```
-r requirements.txt
pytest>=8.0
pytest-asyncio>=0.24
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.env
.venv/
venv/
*.egg-info/
dist/
build/
.pytest_cache/
.mypy_cache/
```

- [ ] **Step 4: Create .env.example**

```
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
```

- [ ] **Step 5: Create config.yaml**

Full config as specified in the design spec (see spec section "Config (config.yaml)"). Copy the complete YAML block from the spec verbatim.

- [ ] **Step 6: Create empty package files**

```bash
mkdir -p src/collectors tests templates output/daily output/weekly data
touch src/__init__.py src/collectors/__init__.py tests/__init__.py
touch output/daily/.gitkeep output/weekly/.gitkeep data/.gitkeep templates/.gitkeep
```

- [ ] **Step 7: Set up venv and install**

```bash
cd ~/Repos/ai-news-digest
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run: `python -c "import feedparser, httpx, anthropic, yaml; print('OK')"`
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: project scaffolding with dependencies and config"
```

---

### Task 2: Models (src/models.py)

**Files:**

- Create: `src/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for Article and DigestResult**

```python
# tests/test_models.py
from datetime import datetime, date
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
        articles=[],
        digest_markdown="# Digest\nContent here",
        top3_summary="Top 3 summary text",
    )
    assert digest.date == date(2026, 4, 3)
    assert digest.digest_markdown.startswith("# Digest")
    assert len(digest.top3_summary) < 500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models'`

- [ ] **Step 3: Implement models**

```python
# src/models.py
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, date


@dataclass
class Article:
    title: str
    url: str
    source: str
    category: str
    published: datetime
    summary: str | None
    content: str | None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published"] = self.published.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Article:
        return cls(
            title=d["title"],
            url=d["url"],
            source=d["source"],
            category=d["category"],
            published=datetime.fromisoformat(d["published"]),
            summary=d.get("summary"),
            content=d.get("content"),
        )


@dataclass
class DigestResult:
    date: date
    articles: list[Article]
    digest_markdown: str
    top3_summary: str
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_models.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add Article and DigestResult dataclasses with serialization"
```

---

### Task 3: Config Loader (src/config.py)

**Files:**

- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import os
import tempfile
from pathlib import Path
from src.config import load_config


def test_load_config_from_file():
    yaml_content = """
settings:
  language: de
  daily_model: claude-sonnet-4-20250514
  weekly_model: claude-opus-4-6
  max_articles_per_source: 10
  max_age_hours: 26
  request_timeout: 30
  max_retries: 3
  log_level: INFO
  cleanup_days: 90

ntfy:
  enabled: true
  server: https://ntfy.sh
  topic: test-topic

sources:
  anthropic:
    - name: Anthropic Blog
      type: rss
      url: https://www.anthropic.com/rss.xml
      priority: high

output:
  daily_dir: output/daily
  weekly_dir: output/weekly
  data_dir: data
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config = load_config(f.name)

    assert config["settings"]["daily_model"] == "claude-sonnet-4-20250514"
    assert config["ntfy"]["topic"] == "test-topic"
    assert len(config["sources"]["anthropic"]) == 1
    assert config["output"]["daily_dir"] == "output/daily"
    os.unlink(f.name)


def test_load_config_default_path(monkeypatch):
    """load_config() without args should look for config.yaml in project root."""
    monkeypatch.chdir(Path(__file__).parent.parent)
    config = load_config()
    assert "settings" in config
    assert "sources" in config
    assert "ntfy" in config


def test_load_config_missing_file():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path.yaml")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement config loader**

```python
# src/config.py
from pathlib import Path

import yaml


def load_config(path: str | None = None) -> dict:
    if path is None:
        path = Path.cwd() / "config.yaml"
    else:
        path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        return yaml.safe_load(f)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config loader with YAML parsing"
```

---

### Task 4: BaseCollector + Factory (src/collectors/)

**Files:**

- Create: `src/collectors/base.py`
- Modify: `src/collectors/__init__.py`
- Create: `tests/test_factory.py`

- [ ] **Step 1: Write failing tests for factory**

```python
# tests/test_factory.py
from src.collectors import build_collectors
from src.collectors.base import BaseCollector


def test_build_collectors_creates_correct_types():
    config = {
        "sources": {
            "anthropic": [
                {"name": "Anthropic Blog", "type": "rss", "url": "https://example.com/rss", "priority": "high"},
            ],
            "research": [
                {"name": "ArXiv cs.AI", "type": "arxiv", "arxiv_category": "cs.AI", "max_results": 5, "priority": "medium"},
            ],
            "tools": [
                {"name": "GitHub Trending", "type": "github_trending", "query": "AI", "min_stars": 50, "priority": "low"},
            ],
        },
        "settings": {"max_articles_per_source": 10, "max_age_hours": 26, "request_timeout": 30, "max_retries": 3},
    }
    collectors = build_collectors(config)
    assert len(collectors) == 3
    for c in collectors:
        assert isinstance(c, BaseCollector)


def test_build_collectors_injects_category():
    config = {
        "sources": {
            "anthropic": [
                {"name": "Blog", "type": "rss", "url": "https://example.com", "priority": "high"},
            ],
        },
        "settings": {"max_articles_per_source": 10, "max_age_hours": 26, "request_timeout": 30, "max_retries": 3},
    }
    collectors = build_collectors(config)
    assert collectors[0].config["category"] == "anthropic"


def test_build_collectors_empty_sources():
    config = {"sources": {}, "settings": {}}
    collectors = build_collectors(config)
    assert collectors == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_factory.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement BaseCollector**

```python
# src/collectors/base.py
from abc import ABC, abstractmethod

import httpx

from src.models import Article


class BaseCollector(ABC):
    def __init__(self, source_config: dict, settings: dict):
        self.config = source_config
        self.settings = settings

    @property
    def name(self) -> str:
        return self.config["name"]

    @property
    def category(self) -> str:
        return self.config["category"]

    @abstractmethod
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        ...
```

- [ ] **Step 4: Implement factory (stub collectors for now)**

Note: We create minimal stub implementations so the factory can instantiate them. Real logic comes in Tasks 5-7.

```python
# src/collectors/__init__.py
from src.collectors.base import BaseCollector
from src.collectors.rss import RSSCollector
from src.collectors.github import GitHubCollector
from src.collectors.arxiv import ArxivCollector

COLLECTOR_MAP: dict[str, type[BaseCollector]] = {
    "rss": RSSCollector,
    "github_releases": GitHubCollector,
    "github_trending": GitHubCollector,
    "arxiv": ArxivCollector,
}


def build_collectors(config: dict) -> list[BaseCollector]:
    collectors = []
    for category, sources in config["sources"].items():
        for source in sources:
            source_with_category = {**source, "category": category}
            cls = COLLECTOR_MAP[source["type"]]
            collectors.append(cls(source_with_category, config["settings"]))
    return collectors
```

```python
# src/collectors/rss.py
import httpx
from src.collectors.base import BaseCollector
from src.models import Article


class RSSCollector(BaseCollector):
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        raise NotImplementedError
```

```python
# src/collectors/github.py
import httpx
from src.collectors.base import BaseCollector
from src.models import Article


class GitHubCollector(BaseCollector):
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        raise NotImplementedError
```

```python
# src/collectors/arxiv.py
import httpx
from src.collectors.base import BaseCollector
from src.models import Article


class ArxivCollector(BaseCollector):
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        raise NotImplementedError
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_factory.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/collectors/ tests/test_factory.py
git commit -m "feat: add BaseCollector ABC and collector factory"
```

---

### Task 5: RSSCollector (src/collectors/rss.py)

**Files:**

- Modify: `src/collectors/rss.py`
- Create: `tests/test_rss_collector.py`

- [ ] **Step 1: Write failing tests**

```python
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
    """Articles older than max_age_hours should be excluded."""
    collector = RSSCollector(rss_config, settings)
    rss_body = _make_rss_with_recent_dates()

    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=httpx.Response(200, text=rss_body)):
            articles = await collector.collect(client)

    # "Old Article" from 2020 should be filtered out
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
async def test_rss_collector_handles_http_error(rss_config, settings):
    collector = RSSCollector(rss_config, settings)

    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", side_effect=httpx.ConnectError("Connection refused")):
            articles = await collector.collect(client)

    assert articles == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_rss_collector.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement RSSCollector**

```python
# src/collectors/rss.py
import logging
from datetime import datetime, timezone, timedelta

import feedparser
import httpx

from src.collectors.base import BaseCollector
from src.models import Article

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        url = self.config["url"]
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch RSS feed {self.name}: {e}")
            return []

        feed = feedparser.parse(response.text)
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.settings["max_age_hours"]
        )
        max_articles = self.settings["max_articles_per_source"]

        articles = []
        for entry in feed.entries:
            published = self._parse_date(entry)
            if published and published < cutoff:
                continue

            articles.append(
                Article(
                    title=entry.get("title", "Untitled"),
                    url=entry.get("link", ""),
                    source=self.name,
                    category=self.category,
                    published=published or datetime.now(timezone.utc),
                    summary=entry.get("summary"),
                    content=entry.get("content", [{}])[0].get("value") if entry.get("content") else None,
                )
            )

            if len(articles) >= max_articles:
                break

        return articles

    def _parse_date(self, entry) -> datetime | None:
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if time_struct is None:
            return None
        from calendar import timegm
        timestamp = timegm(time_struct)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_rss_collector.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/collectors/rss.py tests/test_rss_collector.py
git commit -m "feat: implement RSSCollector with date filtering"
```

---

### Task 6: GitHubCollector (src/collectors/github.py)

**Files:**

- Modify: `src/collectors/github.py`
- Create: `tests/test_github_collector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_github_collector.py
import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import httpx

from src.collectors.github import GitHubCollector
from src.models import Article


@pytest.fixture
def settings():
    return {
        "max_articles_per_source": 10,
        "max_age_hours": 26,
        "request_timeout": 30,
        "max_retries": 3,
    }


# --- GitHub Releases ---

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
            return_value=httpx.Response(200, json=response_data),
        ):
            articles = await collector.collect(client)

    assert len(articles) == 1
    assert articles[0].title == "Release 1.2.0"
    assert articles[0].source == "Claude Code Releases"
    assert articles[0].category == "anthropic"


# --- GitHub Trending ---

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
            return_value=httpx.Response(200, json=response_data),
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_github_collector.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement GitHubCollector**

```python
# src/collectors/github.py
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
                )
            )
        return articles[: self.settings["max_articles_per_source"]]

    async def _collect_trending(self, client: httpx.AsyncClient) -> list[Article]:
        query = self.config["query"]
        min_stars = self.config.get("min_stars", 0)
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"{query} created:>{yesterday}",
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
                )
            )
        return articles

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_github_collector.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/collectors/github.py tests/test_github_collector.py
git commit -m "feat: implement GitHubCollector for releases and trending repos"
```

---

### Task 7: ArxivCollector (src/collectors/arxiv.py)

**Files:**

- Modify: `src/collectors/arxiv.py`
- Create: `tests/test_arxiv_collector.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_arxiv_collector.py -v`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement ArxivCollector**

```python
# src/collectors/arxiv.py
import asyncio
import logging
from datetime import datetime, timezone, timedelta

import arxiv
import httpx

from src.collectors.base import BaseCollector
from src.models import Article

logger = logging.getLogger(__name__)


class ArxivCollector(BaseCollector):
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        try:
            results = await asyncio.to_thread(self._search)
        except Exception as e:
            logger.error(f"ArXiv search failed for {self.name}: {e}")
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.settings["max_age_hours"]
        )
        articles = []
        for paper in results:
            published = paper.published.replace(tzinfo=timezone.utc) if paper.published.tzinfo is None else paper.published
            if published < cutoff:
                continue
            articles.append(
                Article(
                    title=paper.title,
                    url=paper.entry_id,
                    source=self.name,
                    category=self.category,
                    published=published,
                    summary=paper.summary[:500] if paper.summary else None,
                    content=None,
                )
            )
        return articles

    def _search(self) -> list:
        max_results = self.config.get("max_results", 5)
        # The config "category" field is the source category (e.g. "research").
        # The arxiv category (e.g. "cs.AI") is stored in the source config
        # under a separate key. We use the source name to derive the arxiv query.
        arxiv_category = self.config.get("arxiv_category", "cs.AI")
        search = arxiv.Search(
            query=f"cat:{arxiv_category}",
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )
        arxiv_client = arxiv.Client()
        return list(arxiv_client.results(search))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_arxiv_collector.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/collectors/arxiv.py tests/test_arxiv_collector.py
git commit -m "feat: implement ArxivCollector with date filtering"
```

---

### Task 8: Summarizer (src/summarizer.py)

**Files:**

- Create: `src/summarizer.py`
- Create: `tests/test_summarizer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_summarizer.py
import pytest
from datetime import datetime, date, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from src.summarizer import summarize_daily, summarize_top3, summarize_weekly
from src.models import Article, DigestResult


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


@pytest.mark.asyncio
async def test_summarize_daily_calls_api(sample_articles, settings):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="# AI Digest\n\nContent here")]

    with patch("src.summarizer.anthropic.AsyncAnthropic") as MockAnthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        MockAnthropic.return_value = mock_client

        result = await summarize_daily(sample_articles, settings)

    assert result == "# AI Digest\n\nContent here"
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-20250514"


@pytest.mark.asyncio
async def test_summarize_top3(settings):
    digest_md = "# AI Digest\n\nLots of content here about AI developments"

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Claude 4 released. GPT-5 announced. New AI tool trending.")]

    with patch("src.summarizer.anthropic.AsyncAnthropic") as MockAnthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        MockAnthropic.return_value = mock_client

        result = await summarize_top3(digest_md, settings)

    assert len(result) <= 500
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_summarize_weekly(settings):
    daily_digests = ["# Day 1\nContent"] * 7

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="# Weekly Summary\n\nTrends")]

    with patch("src.summarizer.anthropic.AsyncAnthropic") as MockAnthropic:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        MockAnthropic.return_value = mock_client

        result = await summarize_weekly(daily_digests, settings)

    assert result.startswith("# Weekly Summary")
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-6"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_summarizer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement summarizer**

```python
# src/summarizer.py
import json
import logging

import anthropic

from src.models import Article

logger = logging.getLogger(__name__)

DAILY_PROMPT = """Du bist ein AI-Industry-Analyst. Hier sind die gesammelten News und Updates der letzten 24 Stunden aus dem AI/ML-Bereich.

Erstelle einen strukturierten Morning Briefing auf Deutsch mit folgenden Abschnitten:

1. **Top 3 des Tages** — Die drei wichtigsten Entwicklungen, kurz und knackig
2. **Claude & Anthropic** — Alles Neue von Anthropic (Features, Updates, Releases)
3. **Große Labs** — Updates von OpenAI, Google, Meta, Microsoft etc.
4. **News & Trends** — Wichtige Nachrichten aus der AI-Branche
5. **Research Highlights** — Spannende neue Papers (1-2 Sätze pro Paper)
6. **Tools & Produkte** — Neue oder bemerkenswerte AI-Tools
7. **Markt & Business** — Funding, Partnerships, Regulierung (falls relevant)

Regeln:
- Jeder Punkt maximal 2-3 Sätze
- Verlinke auf Originalquellen wo möglich
- Wenn eine Sektion keine News hat, lass sie weg
- Dedupliziere: Wenn mehrere Quellen dasselbe berichten, fasse zusammen
- Antworte nur mit dem formatierten Digest, kein Meta-Kommentar

Hier sind die gesammelten Daten:
{collected_data}"""

TOP3_PROMPT = """Fasse die drei wichtigsten AI-News des Tages in maximal 500 Zeichen zusammen. Nur Fließtext, keine Markdown-Formatierung. Deutsch.

{digest_markdown}"""

WEEKLY_PROMPT = """Du bist ein Senior AI-Industry-Analyst. Hier sind die 7 täglichen AI-Digests der vergangenen Woche.

Erstelle einen umfassenden Wochenrückblick auf Deutsch:

1. **Top 10 der Woche** — Die 10 wichtigsten Entwicklungen, gerankt nach Impact
2. **Trend-Analyse** — Welche übergeordneten Trends zeichnen sich ab?
3. **Ausblick** — Was kommt nächste Woche? Worauf sollte man achten?
4. **Action Items** — Konkrete Dinge, die ich mir diese Woche anschauen/ausprobieren sollte
5. **Wochenstatistik** — Anzahl neue Tools, Papers, Major Releases etc.

Hier sind die 7 Tages-Digests:
{weekly_data}"""


async def _call_claude(prompt: str, model: str) -> str:
    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


async def summarize_daily(articles: list[Article], settings: dict) -> str:
    collected_data = json.dumps(
        [a.to_dict() for a in articles],
        ensure_ascii=False,
        indent=2,
    )
    prompt = DAILY_PROMPT.format(collected_data=collected_data)
    return await _call_claude(prompt, settings["daily_model"])


async def summarize_top3(digest_markdown: str, settings: dict) -> str:
    prompt = TOP3_PROMPT.format(digest_markdown=digest_markdown)
    result = await _call_claude(prompt, settings["daily_model"])
    return result[:500]


async def summarize_weekly(daily_digests: list[str], settings: dict) -> str:
    weekly_data = "\n\n---\n\n".join(daily_digests)
    prompt = WEEKLY_PROMPT.format(weekly_data=weekly_data)
    return await _call_claude(prompt, settings["weekly_model"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_summarizer.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/summarizer.py tests/test_summarizer.py
git commit -m "feat: implement Claude API summarizer with daily/weekly/top3 prompts"
```

---

### Task 9: Notifier (src/notifier.py)

**Files:**

- Create: `src/notifier.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_notifier.py
import pytest
import os
from datetime import date
from unittest.mock import patch, AsyncMock

import httpx

from src.notifier import notify
from src.models import DigestResult


@pytest.fixture
def digest():
    return DigestResult(
        date=date(2026, 4, 3),
        articles=[],
        digest_markdown="# Full Digest",
        top3_summary="Claude 4 released. GPT-5 announced. New AI tool trending.",
    )


@pytest.fixture
def config():
    return {
        "ntfy": {
            "enabled": True,
            "server": "https://ntfy.sh",
            "topic": "test-topic",
        },
    }


@pytest.mark.asyncio
async def test_notify_sends_to_ntfy(digest, config):
    with patch("src.notifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_response = httpx.Response(200)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        await notify(digest, config)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "ntfy.sh/test-topic" in call_args[0][0]
        assert call_args[1]["headers"]["Title"] == "AI Digest 2026-04-03"


@pytest.mark.asyncio
async def test_notify_skips_when_disabled(digest, config):
    config["ntfy"]["enabled"] = False

    with patch("src.notifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value = mock_client

        await notify(digest, config)

        mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_notify_handles_error(digest, config):
    """Ntfy errors should be logged, not raised."""
    with patch("src.notifier.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        # Should not raise
        await notify(digest, config)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_notifier.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement notifier**

```python
# src/notifier.py
import logging
import os

import httpx

from src.models import DigestResult

logger = logging.getLogger(__name__)


async def notify(digest: DigestResult, config: dict) -> None:
    ntfy_config = config["ntfy"]
    if not ntfy_config.get("enabled", False):
        return

    server = ntfy_config["server"]
    topic = ntfy_config["topic"]
    url = f"{server}/{topic}"

    repo = os.environ.get("GITHUB_REPOSITORY", "ahlerjam/ai-news-digest")
    github_url = f"https://github.com/{repo}/blob/main/output/daily/{digest.date}.md"

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                content=digest.top3_summary.encode("utf-8"),
                headers={
                    "Title": f"AI Digest {digest.date}",
                    "Click": github_url,
                    "Tags": "robot,newspaper",
                    "Priority": "default",
                },
            )
        logger.info(f"Ntfy notification sent to {topic}")
    except httpx.HTTPError as e:
        logger.error(f"Failed to send Ntfy notification: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_notifier.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/notifier.py tests/test_notifier.py
git commit -m "feat: implement Ntfy.sh push notification"
```

---

### Task 10: Daily Digest Orchestrator (daily_digest.py)

**Files:**

- Create: `templates/daily.md.j2`
- Create: `daily_digest.py`
- Create: `tests/test_daily_digest.py`

- [ ] **Step 1: Create Jinja2 template**

```jinja2
{# templates/daily.md.j2 #}
# AI Digest — {{ date }}

{{ digest_markdown }}

---

*Quellen: {{ article_count }} Artikel aus {{ source_count }} Quellen*
*Generiert am {{ generated_at }}*
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_daily_digest.py
import pytest
import json
import os
from datetime import datetime, date, timezone
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

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
        articles=sample_articles,
        digest_markdown="# Digest\nContent",
        top3_summary="Top 3 summary",
    )


def test_save_markdown(sample_digest, tmp_path):
    config = {"output": {"daily_dir": str(tmp_path / "daily")}}
    save_markdown(sample_digest, config)

    output_file = tmp_path / "daily" / "2026-04-03.md"
    assert output_file.exists()
    content = output_file.read_text()
    assert "AI Digest" in content
    assert "# Digest" in content


def test_save_json(sample_articles, tmp_path):
    config = {"output": {"data_dir": str(tmp_path / "data")}}
    save_json(sample_articles, date(2026, 4, 3), config)

    output_file = tmp_path / "data" / "2026-04-03.json"
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
        "sources": {
            "news": [
                {"name": "Test", "type": "rss", "url": "https://example.com/rss", "priority": "high"},
            ],
        },
        "ntfy": {"enabled": False, "server": "https://ntfy.sh", "topic": "test"},
        "output": {
            "daily_dir": str(tmp_path / "daily"),
            "weekly_dir": str(tmp_path / "weekly"),
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
         patch("daily_digest.notify", new_callable=AsyncMock):

        mock_collector = AsyncMock()
        mock_collector.collect = AsyncMock(return_value=mock_articles)
        mock_build.return_value = [mock_collector]

        await run_daily(config_path=None, _config_override=config)

    assert (tmp_path / "daily").exists()
    assert (tmp_path / "data").exists()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_daily_digest.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement daily_digest.py**

```python
# daily_digest.py
import asyncio
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader

from src.collectors import build_collectors
from src.config import load_config
from src.models import Article, DigestResult
from src.notifier import notify
from src.summarizer import summarize_daily, summarize_top3

logger = logging.getLogger("ai-news-digest")


def save_markdown(digest: DigestResult, config: dict) -> Path:
    output_dir = Path(config["output"]["daily_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    template_dir = Path(__file__).parent / "templates"
    if template_dir.exists():
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("daily.md.j2")
        sources = set(a.source for a in digest.articles)
        content = template.render(
            date=digest.date,
            digest_markdown=digest.digest_markdown,
            article_count=len(digest.articles),
            source_count=len(sources),
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )
    else:
        content = f"# AI Digest — {digest.date}\n\n{digest.digest_markdown}"

    output_path = output_dir / f"{digest.date}.md"
    output_path.write_text(content, encoding="utf-8")
    logger.info(f"Digest saved to {output_path}")
    return output_path


def save_json(articles: list[Article], digest_date: date, config: dict) -> Path:
    data_dir = Path(config["output"]["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)

    data = [a.to_dict() for a in articles]
    output_path = data_dir / f"{digest_date}.json"
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Raw data saved to {output_path}")
    return output_path


async def run_daily(config_path: str | None = None, _config_override: dict | None = None) -> None:
    config = _config_override or load_config(config_path)
    log_level = config.get("settings", {}).get("log_level", "INFO")
    logging.basicConfig(level=getattr(logging, log_level), format="%(asctime)s %(name)s %(levelname)s %(message)s")

    logger.info("Starting daily digest collection")
    collectors = build_collectors(config)
    logger.info(f"Built {len(collectors)} collectors")

    timeout = config["settings"].get("request_timeout", 30)
    async with httpx.AsyncClient(timeout=timeout) as client:
        results = await asyncio.gather(
            *[c.collect(client) for c in collectors],
            return_exceptions=True,
        )

    articles: list[Article] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Collector {collectors[i].name} failed: {result}")
        else:
            articles.extend(result)

    logger.info(f"Collected {len(articles)} articles total")

    if not articles:
        logger.warning("No articles collected, skipping digest generation")
        return

    today = date.today()
    settings = config["settings"]

    digest_markdown = await summarize_daily(articles, settings)
    top3_summary = await summarize_top3(digest_markdown, settings)

    digest = DigestResult(
        date=today,
        articles=articles,
        digest_markdown=digest_markdown,
        top3_summary=top3_summary,
    )

    save_markdown(digest, config)
    save_json(articles, today, config)
    await notify(digest, config)

    logger.info("Daily digest completed successfully")


def main():
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(run_daily())


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_daily_digest.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add daily_digest.py templates/daily.md.j2 tests/test_daily_digest.py
git commit -m "feat: implement daily digest orchestrator with Jinja2 template"
```

---

### Task 11: Weekly Summary (weekly_summary.py)

**Files:**

- Create: `weekly_summary.py`
- Create: `tests/test_weekly_summary.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_weekly_summary.py
import pytest
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch, AsyncMock


def test_load_daily_digests(tmp_path):
    from weekly_summary import load_daily_digests

    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    for i in range(1, 8):
        (daily_dir / f"2026-04-0{i}.md").write_text(f"# Digest Day {i}")

    digests = load_daily_digests(str(daily_dir), days=7)
    assert len(digests) == 7
    assert "Day 1" in digests[0]


def test_load_daily_digests_fewer_than_7(tmp_path):
    from weekly_summary import load_daily_digests

    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    (daily_dir / "2026-04-01.md").write_text("# Only one")

    digests = load_daily_digests(str(daily_dir), days=7)
    assert len(digests) == 1


@pytest.mark.asyncio
async def test_run_weekly(tmp_path):
    from weekly_summary import run_weekly

    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    for i in range(1, 8):
        (daily_dir / f"2026-04-0{i}.md").write_text(f"# Digest Day {i}")

    weekly_dir = tmp_path / "weekly"
    config = {
        "settings": {
            "weekly_model": "claude-opus-4-6",
            "language": "de",
            "log_level": "INFO",
        },
        "ntfy": {"enabled": False, "server": "https://ntfy.sh", "topic": "test"},
        "output": {
            "daily_dir": str(daily_dir),
            "weekly_dir": str(weekly_dir),
            "data_dir": str(tmp_path / "data"),
        },
    }

    with patch("weekly_summary.load_config", return_value=config), \
         patch("weekly_summary.summarize_weekly", new_callable=AsyncMock, return_value="# Weekly\nTrends"), \
         patch("weekly_summary.summarize_top3", new_callable=AsyncMock, return_value="Weekly top 3"), \
         patch("weekly_summary.notify", new_callable=AsyncMock):

        await run_weekly(config_path=None, _config_override=config)

    assert weekly_dir.exists()
    weekly_files = list(weekly_dir.glob("*.md"))
    assert len(weekly_files) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_weekly_summary.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement weekly_summary.py**

```python
# weekly_summary.py
import asyncio
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from src.config import load_config
from src.models import DigestResult
from src.notifier import notify
from src.summarizer import summarize_weekly, summarize_top3

logger = logging.getLogger("ai-news-digest")


def load_daily_digests(daily_dir: str, days: int = 7) -> list[str]:
    path = Path(daily_dir)
    if not path.exists():
        return []

    md_files = sorted(path.glob("*.md"), reverse=True)[:days]
    md_files.reverse()  # chronological order
    return [f.read_text(encoding="utf-8") for f in md_files]


async def run_weekly(config_path: str | None = None, _config_override: dict | None = None) -> None:
    config = _config_override or load_config(config_path)
    log_level = config.get("settings", {}).get("log_level", "INFO")
    logging.basicConfig(level=getattr(logging, log_level), format="%(asctime)s %(name)s %(levelname)s %(message)s")

    daily_dir = config["output"]["daily_dir"]
    digests = load_daily_digests(daily_dir)

    if not digests:
        logger.warning("No daily digests found, skipping weekly summary")
        return

    logger.info(f"Loaded {len(digests)} daily digests for weekly summary")

    settings = config["settings"]
    weekly_markdown = await summarize_weekly(digests, settings)
    top3 = await summarize_top3(weekly_markdown, settings)

    today = date.today()
    week_number = today.isocalendar()[1]
    year = today.isocalendar()[0]

    weekly_dir = Path(config["output"]["weekly_dir"])
    weekly_dir.mkdir(parents=True, exist_ok=True)
    output_path = weekly_dir / f"{year}-W{week_number:02d}.md"
    output_path.write_text(
        f"# AI Weekly Summary — KW {week_number} {year}\n\n{weekly_markdown}\n\n---\n\n"
        f"*Basierend auf {len(digests)} Tages-Digests*\n"
        f"*Generiert am {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*\n",
        encoding="utf-8",
    )

    digest = DigestResult(
        date=today,
        articles=[],
        digest_markdown=weekly_markdown,
        top3_summary=top3,
    )
    await notify(digest, config)

    logger.info(f"Weekly summary saved to {output_path}")


def main():
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(run_weekly())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/test_weekly_summary.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add weekly_summary.py tests/test_weekly_summary.py
git commit -m "feat: implement weekly summary orchestrator"
```

---

### Task 12: GitHub Actions Workflows

**Files:**

- Create: `.github/workflows/daily-digest.yml`
- Create: `.github/workflows/weekly-summary.yml`

- [ ] **Step 1: Create daily-digest.yml**

```yaml
name: Daily AI Digest
on:
  schedule:
    - cron: "0 5 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python daily_digest.py
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - name: Commit digest
        run: |
          git config user.name "AI Digest Bot"
          git config user.email "bot@digest.local"
          git add output/ data/
          git diff --staged --quiet || git commit -m "Daily Digest $(date +%Y-%m-%d)"
          git push
      - name: Cleanup old digests
        run: |
          find output/ data/ -type f -name "*.md" -mtime +90 -delete
          find output/ data/ -type f -name "*.json" -mtime +90 -delete
          git add -A output/ data/
          git diff --staged --quiet || git commit -m "Cleanup: remove digests older than 90 days"
          git push
```

- [ ] **Step 2: Create weekly-summary.yml**

```yaml
name: Weekly AI Summary
on:
  schedule:
    - cron: "0 17 * * 0"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  summary:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python weekly_summary.py
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - name: Commit summary
        run: |
          git config user.name "AI Digest Bot"
          git config user.email "bot@digest.local"
          git add output/ data/
          git diff --staged --quiet || git commit -m "Weekly Summary $(date +%Y-%m-%d)"
          git push
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/
git commit -m "ci: add GitHub Actions workflows for daily digest and weekly summary"
```

---

### Task 13: README + Final Setup

**Files:**

- Create: `README.md`

- [ ] **Step 1: Create README.md**

````markdown
# AI News Digest

Automated daily AI/ML news digest powered by Claude API. Collects news from RSS feeds and APIs, summarizes them, and sends push notifications via Ntfy.sh.

## Features

- **Daily Digest:** Collects AI news from 15+ sources, summarized by Claude Sonnet
- **Weekly Summary:** Trend analysis and top-10 ranking by Claude Opus
- **Push Notifications:** Top-3 summary via Ntfy.sh to your phone
- **GitHub Actions:** Fully automated, no server needed
- **iOS Shortcut:** Trigger digest manually from your iPhone

## Setup

### 1. Fork & Clone

```bash
git clone https://github.com/ahlerjam/ai-news-digest.git
cd ai-news-digest
```
````

### 2. GitHub Secrets

Go to Settings → Secrets and variables → Actions, add:

| Secret              | Value                                          |
| ------------------- | ---------------------------------------------- |
| `ANTHROPIC_API_KEY` | Your Claude API key from console.anthropic.com |

`GITHUB_TOKEN` is provided automatically by GitHub Actions.

### 3. Configure Ntfy

1. Install [Ntfy app](https://ntfy.sh) on your phone
2. Subscribe to your topic (e.g., `ai-digest-jonas`)
3. Update `config.yaml` → `ntfy.topic` with your topic name

### 4. Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env  # Fill in your API keys
python daily_digest.py
```

### 5. iOS Shortcut (Manual Trigger)

Create an Apple Shortcut with these steps:

1. **Get Contents of URL**
   - URL: `https://api.github.com/repos/ahlerjam/ai-news-digest/actions/workflows/daily-digest.yml/dispatches`
   - Method: POST
   - Headers:
     - `Authorization`: `Bearer YOUR_GITHUB_PAT`
     - `Accept`: `application/vnd.github+v3+json`
   - Request Body (JSON): `{"ref": "main"}`

2. **Show Notification**: "AI Digest wird generiert..."

**Requirements:** GitHub Personal Access Token with `repo` and `actions` scope.

**Usage:** Tap the shortcut, say "Hey Siri, AI Digest", or add it as a Lock Screen widget. The digest arrives ~2-3 minutes later via Ntfy push.

## Architecture

```
RSS Feeds / GitHub API / ArXiv API
        ↓ (async collectors)
    Article objects
        ↓
    Claude API (summarize)
        ↓
    Markdown + JSON files
        ↓
    Ntfy.sh push notification
```

## Configuration

Edit `config.yaml` to customize sources, models, and notification settings.

## Costs

- **Daily:** ~$0.01–0.05 (Claude Sonnet)
- **Weekly:** ~$0.10–0.30 (Claude Opus)
- **Monthly total:** ~$1–2

````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup instructions and iOS Shortcut guide"
````

---

### Task 14: Run Full Test Suite + Push

- [ ] **Step 1: Run all tests**

Run: `cd ~/Repos/ai-news-digest && python -m pytest tests/ -v`
Expected: All tests pass (19 tests)

- [ ] **Step 2: Fix any failures**

If tests fail, fix the issues and re-run.

- [ ] **Step 3: Create GitHub repo and push**

```bash
cd ~/Repos/ai-news-digest
gh repo create ahlerjam/ai-news-digest --private --source=. --push
```

- [ ] **Step 4: Add ANTHROPIC_API_KEY secret**

```bash
gh secret set ANTHROPIC_API_KEY
```

(Prompts for the value interactively)

- [ ] **Step 5: Test with workflow_dispatch**

```bash
gh workflow run daily-digest.yml
gh run watch
```

- [ ] **Step 6: Verify Ntfy notification arrives**

Check your Ntfy app — a push should arrive within 2-3 minutes.
