# Digest Balance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI news digest balanced across all sources, add an Extended section with per-source detail, fix broken feeds, and show diagnostics.

**Architecture:** Prompt-only approach for format changes — rewrite `DAILY_PROMPT` with two-part structure (short top, extended bottom). Add `priority` field to Article model so Claude knows source importance. Track source coverage in `daily_digest.py` and expose in template footer.

**Tech Stack:** Python 3.9, httpx, feedparser, Jinja2, pytest

**Spec:** `docs/superpowers/specs/2026-04-04-digest-balance-design.md`

---

## File Map

| File                          | Action | Responsibility                             |
| ----------------------------- | ------ | ------------------------------------------ |
| `src/models.py`               | Modify | Add `priority` field to Article            |
| `src/collectors/base.py`      | Modify | Add `priority` property                    |
| `src/collectors/rss.py`       | Modify | Pass priority to Article                   |
| `src/collectors/github.py`    | Modify | Pass priority to Article                   |
| `src/collectors/arxiv.py`     | Modify | Pass priority to Article                   |
| `src/summarizer.py`           | Modify | Rewrite DAILY_PROMPT for new format        |
| `daily_digest.py`             | Modify | Track source diagnostics, pass to template |
| `templates/daily.md.j2`       | Modify | Add diagnostics footer                     |
| `config.yaml`                 | Modify | Fix broken RSS URLs                        |
| `tests/test_models.py`        | Modify | Test priority field                        |
| `tests/test_rss_collector.py` | Modify | Test priority passthrough                  |
| `tests/test_daily_digest.py`  | Modify | Test diagnostics tracking                  |

---

### Task 1: Add `priority` field to Article model

**Files:**

- Modify: `src/models.py:10-34`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing test for priority field**

In `tests/test_models.py`, add:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py::test_article_priority_field tests/test_models.py::test_article_priority_defaults_to_medium -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'priority'`

- [ ] **Step 3: Add priority field to Article dataclass**

In `src/models.py`, modify the Article dataclass:

```python
@dataclass
class Article:
    title: str
    url: str
    source: str
    category: str
    published: datetime
    summary: str | None
    content: str | None
    priority: str = "medium"

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
            priority=d.get("priority", "medium"),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add priority field to Article model"
```

---

### Task 2: Pass priority through all collectors

**Files:**

- Modify: `src/collectors/base.py:9-24`
- Modify: `src/collectors/rss.py:40-49`
- Modify: `src/collectors/github.py:45-55,77-87`
- Modify: `src/collectors/arxiv.py:32-43`
- Modify: `tests/test_rss_collector.py`

- [ ] **Step 1: Write failing test for priority passthrough in RSSCollector**

In `tests/test_rss_collector.py`, add:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rss_collector.py::test_rss_collector_passes_priority -v`
Expected: FAIL — articles have `priority="medium"` (default) instead of `"high"`

- [ ] **Step 3: Add priority property to BaseCollector**

In `src/collectors/base.py`:

```python
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

    @property
    def priority(self) -> str:
        return self.config.get("priority", "medium")

    @abstractmethod
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        ...
```

- [ ] **Step 4: Pass priority in RSSCollector**

In `src/collectors/rss.py`, modify the Article creation (line ~40-49):

```python
            articles.append(
                Article(
                    title=entry.get("title", "Untitled"),
                    url=entry.get("link", ""),
                    source=self.name,
                    category=self.category,
                    published=published or datetime.now(timezone.utc),
                    summary=entry.get("summary"),
                    content=entry.get("content", [{}])[0].get("value") if entry.get("content") else None,
                    priority=self.priority,
                )
            )
```

- [ ] **Step 5: Pass priority in GitHubCollector (releases)**

In `src/collectors/github.py`, modify `_collect_releases` Article creation (line ~45-55):

```python
            articles.append(
                Article(
                    title=release.get("name") or release["tag_name"],
                    url=release["html_url"],
                    source=self.name,
                    category=self.category,
                    published=published,
                    summary=release.get("body", "")[:500],
                    content=release.get("body"),
                    priority=self.priority,
                )
            )
```

- [ ] **Step 6: Pass priority in GitHubCollector (trending)**

In `src/collectors/github.py`, modify `_collect_trending` Article creation (line ~77-87):

```python
            articles.append(
                Article(
                    title=f"{repo['full_name']} ({repo['stargazers_count']}★)",
                    url=repo["html_url"],
                    source=self.name,
                    category=self.category,
                    published=datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00")),
                    summary=repo.get("description"),
                    content=None,
                    priority=self.priority,
                )
            )
```

- [ ] **Step 7: Pass priority in ArxivCollector**

In `src/collectors/arxiv.py`, modify Article creation (line ~32-43):

```python
            articles.append(
                Article(
                    title=paper.title,
                    url=paper.entry_id,
                    source=self.name,
                    category=self.category,
                    published=published,
                    summary=paper.summary[:500] if paper.summary else None,
                    content=None,
                    priority=self.priority,
                )
            )
```

- [ ] **Step 8: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add src/collectors/ tests/test_rss_collector.py
git commit -m "feat: pass source priority through all collectors to Article"
```

---

### Task 3: Track source diagnostics in daily_digest.py

**Files:**

- Modify: `daily_digest.py:61-113`
- Modify: `templates/daily.md.j2`
- Modify: `tests/test_daily_digest.py`

- [ ] **Step 1: Write failing test for diagnostics in save_markdown**

In `tests/test_daily_digest.py`, add:

```python
def test_save_markdown_includes_diagnostics(sample_digest, tmp_path):
    configured_sources = ["Test Source", "OpenAI Blog", "Google DeepMind"]
    save_markdown(sample_digest, str(tmp_path), configured_sources=configured_sources)

    output_file = tmp_path / "ai-news" / "daily" / "2026-04-03.md"
    content = output_file.read_text()
    assert "3 konfigurierten Quellen" in content
    assert "Keine Daten von:" in content
    assert "OpenAI Blog" in content
    assert "Google DeepMind" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_daily_digest.py::test_save_markdown_includes_diagnostics -v`
Expected: FAIL — `TypeError: save_markdown() got an unexpected keyword argument 'configured_sources'`

- [ ] **Step 3: Update save_markdown to accept and pass diagnostics**

In `daily_digest.py`, modify `save_markdown`:

```python
def save_markdown(digest: DigestResult, base_dir: str, configured_sources: list[str] | None = None) -> Path:
    output_dir = Path(base_dir) / digest.subscription_id / "daily"
    output_dir.mkdir(parents=True, exist_ok=True)

    template_dir = Path(__file__).parent / "templates"
    if template_dir.exists():
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("daily.md.j2")
        active_sources = set(a.source for a in digest.articles)
        all_configured = set(configured_sources) if configured_sources else active_sources
        missing_sources = sorted(all_configured - active_sources)
        content = template.render(
            date=digest.date,
            subscription_name=digest.subscription_name,
            digest_markdown=digest.digest_markdown,
            article_count=len(digest.articles),
            source_count=len(active_sources),
            total_configured=len(all_configured),
            missing_sources=missing_sources,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )
    else:
        content = f"# {digest.subscription_name} — {digest.date}\n\n{digest.digest_markdown}"

    output_path = output_dir / f"{digest.date}.md"
    output_path.write_text(content, encoding="utf-8")
    logger.info(f"Digest saved to {output_path}")
    return output_path
```

- [ ] **Step 4: Update Jinja2 template with diagnostics footer**

In `templates/daily.md.j2`:

```jinja
{# templates/daily.md.j2 #}
# {{ subscription_name }} — {{ date }}

{{ digest_markdown }}

---

*Quellen: {{ article_count }} Artikel aus {{ source_count }} von {{ total_configured }} konfigurierten Quellen*
{% if missing_sources %}*Keine Daten von: {{ missing_sources | join(', ') }}*
{% endif %}*Generiert am {{ generated_at }}*
```

- [ ] **Step 5: Extract configured source names in run_subscription**

In `daily_digest.py`, modify `run_subscription` to collect all configured source names and pass them to `save_markdown`. After the `collectors = build_collectors(...)` line (line ~68):

```python
    collectors = build_collectors(sub_config["sources"], settings)
    configured_sources = [c.name for c in collectors]
    logger.info(f"[{sub_id}] Built {len(collectors)} collectors")
```

And update the `save_markdown` call (line ~107):

```python
    save_markdown(digest, output_config["base_dir"], configured_sources=configured_sources)
```

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add daily_digest.py templates/daily.md.j2 tests/test_daily_digest.py
git commit -m "feat: add source diagnostics to digest footer"
```

---

### Task 4: Rewrite DAILY_PROMPT for new format

**Files:**

- Modify: `src/summarizer.py:10-28`

- [ ] **Step 1: Rewrite the DAILY_PROMPT**

In `src/summarizer.py`, replace `DAILY_PROMPT` (lines 10-28):

```python
DAILY_PROMPT = """Du bist ein News-Analyst. Hier sind die gesammelten News und Updates der letzten 24 Stunden.

Erstelle einen strukturierten Morning Briefing auf {language} mit ZWEI Teilen:

## TEIL 1: Kompakter Überblick (oben)

1. **Top 3 des Tages** — Die drei wichtigsten Entwicklungen, kurz und knackig (1-2 Sätze je)
2. **Highlights** — Die wichtigsten News nach Thema gruppiert, KOMPAKT:
   - Anthropic/Claude: Maximal 4-5 Zeilen Zusammenfassung (Details kommen im Extended-Teil)
   - Andere Themen: Maximal 2-3 Sätze pro Themengruppe

Trenne mit einer Markdown-Linie (---) und dann:

## TEIL 2: Extended — Alle Quellen im Detail (unten)

Überschrift: ## 📖 Extended: Alle Quellen im Detail

Erstelle für JEDE Quelle die Daten geliefert hat einen eigenen Abschnitt (### Quellenname).
Hier wird ausführlich: Jedes Feature, jeder Bugfix, jede News vollständig beschrieben.

Reihenfolge der Quellen-Abschnitte:
1. Anthropic & Claude (alle high-priority Quellen zusammen, HIER ausführlich)
2. Big Labs (OpenAI, Google, Microsoft, Meta, Apple, AWS, NVIDIA — einzeln wenn genug Content)
3. News-Quellen (The Verge, TechCrunch, Ars Technica, VentureBeat)
4. Platforms (HuggingFace etc.)
5. 📄 ArXiv Papers (mit Abstract-Zusammenfassungen)
6. 🔥 GitHub Trending (Repos mit Beschreibung)

WICHTIG: Jede Quelle die Artikel geliefert hat, MUSS mindestens einmal im Extended-Teil vorkommen.

{prompt_focus}

Regeln:
- Verlinke auf Originalquellen wo möglich
- Wenn eine Sektion keine News hat, lass sie weg
- Dedupliziere: Wenn mehrere Quellen dasselbe berichten, fasse zusammen und nenne alle Quellen
- Die Artikel enthalten ein "priority" Feld (high/medium/low) — nutze es zur Gewichtung
- Antworte nur mit dem formatierten Digest, kein Meta-Kommentar

Hier sind die gesammelten Daten:
{collected_data}"""
```

- [ ] **Step 2: Run existing summarizer tests**

Run: `python -m pytest tests/test_summarizer.py -v`
Expected: ALL PASS (tests mock Claude calls, don't validate prompt content)

- [ ] **Step 3: Commit**

```bash
git add src/summarizer.py
git commit -m "feat: rewrite daily prompt for compact top + extended per-source format"
```

---

### Task 5: Fix broken RSS feed URLs

**Files:**

- Modify: `config.yaml`

For each broken source, test the current URL and find a working alternative. The following sources returned no data on 2026-04-03.

- [ ] **Step 1: Test all RSS feeds and find working URLs**

Run each URL with curl to check status. Test one by one:

```bash
# Test current URLs
curl -s -o /dev/null -w "%{http_code}" "https://openai.com/blog/rss.xml"
curl -s -o /dev/null -w "%{http_code}" "https://deepmind.google/blog/rss.xml"
curl -s -o /dev/null -w "%{http_code}" "https://blog.google/technology/ai/rss/"
curl -s -o /dev/null -w "%{http_code}" "https://blogs.microsoft.com/ai/feed/"
curl -s -o /dev/null -w "%{http_code}" "https://engineering.fb.com/feed/"
curl -s -o /dev/null -w "%{http_code}" "https://machinelearning.apple.com/rss.xml"
curl -s -o /dev/null -w "%{http_code}" "https://aws.amazon.com/blogs/machine-learning/feed/"
curl -s -o /dev/null -w "%{http_code}" "https://blogs.nvidia.com/feed/"
curl -s -o /dev/null -w "%{http_code}" "https://feeds.arstechnica.com/arstechnica/technology-lab"
curl -s -o /dev/null -w "%{http_code}" "https://huggingface.co/blog/feed.xml"
curl -s -o /dev/null -w "%{http_code}" "https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml"
```

- [ ] **Step 2: For each broken URL, search for the correct current RSS feed URL**

Common alternatives to try:

- OpenAI: `https://openai.com/index/rss.xml` or `https://openai.com/news/rss.xml`
- Google DeepMind: `https://deepmind.google/blog/feed/`
- Google AI: `https://blog.google/technology/ai/rss.xml`
- Microsoft: `https://blogs.microsoft.com/ai/feed/` or `https://www.microsoft.com/en-us/research/feed/`
- Apple: `https://machinelearning.apple.com/rss.xml`
- NVIDIA: `https://blogs.nvidia.com/blog/category/deep-learning/feed/`
- Ars Technica: `https://feeds.arstechnica.com/arstechnica/index`

For feeds that are simply stale (no posts in 26h), no URL change is needed — they'll appear in the diagnostics footer naturally.

- [ ] **Step 3: Update config.yaml with fixed URLs**

Replace each broken URL in `config.yaml` with the verified working alternative. Only change URLs that are actually broken (returning 4xx/5xx or empty feeds). Leave working-but-empty feeds alone.

- [ ] **Step 4: Test the fixed URLs**

Run: `curl -s "NEW_URL" | head -20` for each changed URL to verify RSS content is returned.

- [ ] **Step 5: Commit**

```bash
git add config.yaml
git commit -m "fix: update broken RSS feed URLs"
```

---

### Task 6: Integration test — full pipeline run

- [ ] **Step 1: Run all unit tests**

Run: `python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run the full pipeline**

Run: `python daily_digest.py ai-news`

Verify:

- Console output shows collectors being built and articles collected
- More than 10 sources return data (was only 10 before)
- Output file at `output/ai-news/daily/YYYY-MM-DD.md` has:
  - Compact Highlights section at top
  - Extended section with per-source detail at bottom
  - Diagnostics footer showing source coverage + missing sources

- [ ] **Step 3: Review the generated digest**

Read `output/ai-news/daily/YYYY-MM-DD.md` and verify:

- Top section is compact (Anthropic/Claude max 4-5 lines)
- Extended section has subsections per source
- Every source that returned data appears in Extended
- Footer shows "X Artikel aus Y von Z konfigurierten Quellen"
- Missing sources are listed

- [ ] **Step 4: Final commit**

```bash
git add output/ data/
git commit -m "ai-news: Digest YYYY-MM-DDTHH:MM"
```
