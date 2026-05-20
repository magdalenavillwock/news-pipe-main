# AI News Digest System — Design Spec

**Datum:** 2026-04-03
**Status:** Approved

## Ziel

Automatisiertes System das täglich AI/ML-News aus RSS-Feeds und APIs sammelt, per Claude API zusammenfasst, als Markdown im Repo speichert und eine Push-Notification aufs Handy schickt. Wöchentlich werden die 7 Tages-Digests zu einem Trend-Report zusammengefasst.

Läuft vollständig über GitHub Actions (Cron-basiert, kein Server).

## Design-Entscheidungen

| Entscheidung          | Ergebnis                       | Begründung                                |
| --------------------- | ------------------------------ | ----------------------------------------- |
| Deduplizierung        | Claude beim Zusammenfassen     | Kein extra Code, Modell erkennt Duplikate |
| Delivery              | Ntfy.sh Push                   | Kostenlos, kein Account, Top-3 + Link     |
| PDF/E-Mail            | Entfällt                       | Ntfy + Markdown im Repo reicht            |
| Quellen Phase 1       | Nur RSS + APIs                 | Scraping fragil, später nachrüstbar       |
| Volltext lesen        | Markdown im GitHub Repo        | GitHub rendert .md nativ                  |
| Collector-Architektur | Async (httpx + asyncio.gather) | Future-proof für mehr Quellen             |
| Auto-Cleanup          | Dateien älter 90 Tage löschen  | Repo-Größe begrenzen                      |

## Projektstruktur

```
ai-news-digest/
├── .github/workflows/
│   ├── daily-digest.yml          # Cron 0 5 * * * (7:00 DE-Zeit)
│   └── weekly-summary.yml        # Cron 0 17 * * 0 (Sonntag 19:00 DE)
├── src/
│   ├── __init__.py
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py               # BaseCollector ABC (async interface)
│   │   ├── rss.py                # RSS/Atom Feeds (feedparser)
│   │   ├── github.py             # GitHub Releases + Trending (REST API)
│   │   └── arxiv.py              # ArXiv Papers (arxiv package)
│   ├── summarizer.py             # Claude API: raw articles → digest
│   ├── notifier.py               # Ntfy.sh Push-Notifications
│   ├── config.py                 # Config-Loading + Validation
│   └── models.py                 # Dataclasses: Article, DigestResult
├── config.yaml                   # Quellen + Einstellungen
├── templates/
│   └── daily.md.j2              # Jinja2 Template für Markdown-Output
├── output/
│   ├── daily/                   # YYYY-MM-DD.md
│   └── weekly/                  # YYYY-WXX.md
├── data/                        # JSON-Zwischenspeicher pro Tag
├── daily_digest.py              # Entrypoint: Daily Run
├── weekly_summary.py            # Entrypoint: Weekly Run
├── requirements.txt
├── .env.example
└── README.md
```

## Datenmodell

### Article

```python
@dataclass
class Article:
    title: str
    url: str
    source: str           # z.B. "Anthropic Blog"
    category: str         # z.B. "anthropic", "big_labs", "news", "research", "tools"
    published: datetime
    summary: str | None   # Kurzbeschreibung vom Feed
    content: str | None   # Volltext falls verfügbar
```

### DigestResult

```python
@dataclass
class DigestResult:
    date: date
    articles: list[Article]
    digest_markdown: str   # Claude-generierter Digest (vollständig)
    top3_summary: str      # Für Ntfy Push (max ~500 Zeichen)
```

## Config (config.yaml)

```yaml
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
  topic: ai-digest-jonas

sources:
  anthropic:
    - name: Anthropic Blog
      type: rss
      url: https://www.anthropic.com/rss.xml
      priority: high
    - name: Anthropic Engineering
      type: rss
      url: https://www.anthropic.com/engineering/rss.xml
      priority: high
    - name: Anthropic Research
      type: rss
      url: https://www.anthropic.com/research/rss.xml
      priority: high
    - name: Anthropic News
      type: rss
      url: https://www.anthropic.com/news/rss.xml
      priority: high
    - name: Claude Code Releases
      type: github_releases
      repo: anthropics/claude-code
      priority: high

  big_labs:
    - name: OpenAI Blog
      type: rss
      url: https://openai.com/blog/rss.xml
      priority: medium
    - name: Google DeepMind
      type: rss
      url: https://deepmind.google/blog/rss.xml
      priority: medium
    - name: Microsoft AI Blog
      type: rss
      url: https://blogs.microsoft.com/ai/feed/
      priority: medium

  news:
    - name: The Verge AI
      type: rss
      url: https://www.theverge.com/rss/ai-artificial-intelligence/index.xml
      priority: medium
    - name: TechCrunch AI
      type: rss
      url: https://techcrunch.com/category/artificial-intelligence/feed/
      priority: medium
    - name: Ars Technica
      type: rss
      url: https://feeds.arstechnica.com/arstechnica/technology-lab
      priority: low
    - name: VentureBeat AI
      type: rss
      url: https://venturebeat.com/category/ai/feed/
      priority: low

  research:
    - name: ArXiv cs.AI
      type: arxiv
      arxiv_category: cs.AI
      max_results: 5
      priority: medium
    - name: ArXiv cs.CL
      type: arxiv
      arxiv_category: cs.CL
      max_results: 5
      priority: medium

  tools:
    - name: GitHub Trending AI
      type: github_trending
      query: "artificial intelligence OR machine learning OR LLM"
      min_stars: 50
      priority: low

output:
  daily_dir: output/daily
  weekly_dir: output/weekly
  data_dir: data
```

## Collector-Layer

### BaseCollector (ABC)

```python
class BaseCollector(ABC):
    def __init__(self, source_config: dict, settings: dict):
        self.config = source_config
        self.settings = settings

    @abstractmethod
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        """Sammelt Artikel von dieser Quelle."""
        ...
```

### RSSCollector

- Nutzt `feedparser.parse()` auf die Feed-URL
- Filtert Einträge nach `max_age_hours` (published date)
- Mappt Feed-Entries auf `Article` Dataclass
- Begrenzt auf `max_articles_per_source`

### GitHubCollector

- **Releases:** `GET /repos/{owner}/{repo}/releases` — filtert nach Datum
- **Trending:** `GET /search/repositories?q={query}&sort=stars&created:>{yesterday}`
- Optional: `GITHUB_TOKEN` Header für höhere Rate Limits (5000 statt 60 req/h)

### ArxivCollector

- Nutzt `arxiv` Python-Package
- `arxiv.Search(query=category, sort_by=Relevance, max_results=N)`
- Filtert auf letzte 24h

### Factory

```python
COLLECTOR_MAP = {
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

## Orchestrierung (daily_digest.py)

```python
async def main():
    config = load_config()
    collectors = build_collectors(config)

    async with httpx.AsyncClient(timeout=config["settings"]["request_timeout"]) as client:
        results = await asyncio.gather(
            *[c.collect(client) for c in collectors],
            return_exceptions=True
        )

    articles = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Collector failed: {result}")
        else:
            articles.extend(result)

    if not articles:
        logger.warning("No articles collected, skipping digest")
        return

    digest = await summarize(articles, config)
    save_markdown(digest, config)
    save_json(articles, config)
    await notify(digest, config)
```

## Summarizer (Claude API)

### Daily Digest

- **Modell:** `claude-sonnet-4-20250514`
- **Input:** Alle gesammelten Artikel als JSON (title, url, source, category, summary)
- **Output:** Strukturierter Markdown-Digest auf Deutsch
- **Prompt:** Wie im Abschnitt "Prompts" definiert
- **Zweiter Call:** Separater kurzer Call um `top3_summary` zu generieren (max 500 Zeichen für Ntfy)

### Weekly Summary

- **Modell:** `claude-opus-4-6`
- **Input:** 7 Tages-Digests (Markdown) + 7 Tages-Daten (JSON)
- **Output:** Wochenrückblick mit Rankings, Trends, Action Items

## Prompts

### Daily Digest Prompt

```
Du bist ein AI-Industry-Analyst. Hier sind die gesammelten News und Updates der letzten 24 Stunden aus dem AI/ML-Bereich.

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
{collected_data}
```

### Top-3 Summary Prompt (für Ntfy)

```
Fasse die drei wichtigsten AI-News des Tages in maximal 500 Zeichen zusammen. Nur Fließtext, keine Markdown-Formatierung. Deutsch.

{digest_markdown}
```

### Weekly Summary Prompt

```
Du bist ein Senior AI-Industry-Analyst. Hier sind die 7 täglichen AI-Digests der vergangenen Woche.

Erstelle einen umfassenden Wochenrückblick auf Deutsch:

1. **Top 10 der Woche** — Die 10 wichtigsten Entwicklungen, gerankt nach Impact
2. **Trend-Analyse** — Welche übergeordneten Trends zeichnen sich ab?
3. **Ausblick** — Was kommt nächste Woche? Worauf sollte man achten?
4. **Action Items** — Konkrete Dinge, die ich mir diese Woche anschauen/ausprobieren sollte
5. **Wochenstatistik** — Anzahl neue Tools, Papers, Major Releases etc.

Hier sind die 7 Tages-Digests:
{weekly_data}
```

## Notifier (Ntfy.sh)

```python
async def notify(digest: DigestResult, config: dict):
    if not config["ntfy"]["enabled"]:
        return

    ntfy = config["ntfy"]
    repo_url = os.environ.get("GITHUB_REPOSITORY", "")
    github_url = f"https://github.com/{repo_url}/blob/main/output/daily/{digest.date}.md"

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{ntfy['server']}/{ntfy['topic']}",
            content=digest.top3_summary.encode(),
            headers={
                "Title": f"AI Digest {digest.date}",
                "Click": github_url,
                "Tags": "robot,newspaper",
                "Priority": "default",
            },
        )
```

## Auto-Cleanup (90 Tage)

In beiden GitHub Actions Workflows als Schritt nach dem Commit:

```yaml
- name: Cleanup old digests
  run: |
    find output/ data/ -type f -mtime +90 -delete
    git add -A output/ data/
    git diff --staged --quiet || git commit -m "Cleanup: remove digests older than 90 days"
    git push
```

Konfigurierbar über `settings.cleanup_days` in config.yaml.

## GitHub Actions

### daily-digest.yml

```yaml
name: Daily AI Digest
on:
  schedule:
    - cron: "0 5 * * *"
  workflow_dispatch:

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
          find output/ data/ -type f -mtime +90 -delete
          git add -A output/ data/
          git diff --staged --quiet || git commit -m "Cleanup: remove digests older than 90 days"
          git push
```

### weekly-summary.yml

```yaml
name: Weekly AI Summary
on:
  schedule:
    - cron: "0 17 * * 0"
  workflow_dispatch:

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

## Secrets (GitHub Repository Settings)

| Secret              | Pflicht     | Beschreibung                                 |
| ------------------- | ----------- | -------------------------------------------- |
| `ANTHROPIC_API_KEY` | Ja          | Claude API Key                               |
| `GITHUB_TOKEN`      | Automatisch | Wird von GitHub Actions bereitgestellt       |
| `NTFY_TOPIC`        | Nein        | Falls Topic nicht in config.yaml stehen soll |

## Dependencies (requirements.txt)

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

## Error Handling

- **Collector-Ebene:** `asyncio.gather(return_exceptions=True)` — jeder Collector kann unabhängig fehlschlagen
- **HTTP-Requests:** `tenacity` mit exponential backoff (3 Versuche, 1s/2s/4s)
- **Kein Artikel gesammelt:** Warnung loggen, kein leerer Digest generieren
- **Claude API Fehler:** Retry mit tenacity, bei totalem Ausfall: Raw-Artikelliste als Fallback-Markdown
- **Ntfy Fehler:** Loggen und ignorieren — Digest ist trotzdem im Repo
- **Logging:** Python `logging` Modul, Level konfigurierbar in config.yaml

## Manuelle Auslösung

Vier Wege den Digest manuell zu triggern:

1. **iPhone (primär):** iOS Shortcut der per GitHub API den Workflow triggert (siehe unten)
2. **Lokal:** `python daily_digest.py` bzw. `python weekly_summary.py` — braucht `.env` mit `ANTHROPIC_API_KEY`
3. **GitHub UI:** Repository → Actions → Workflow → "Run workflow" Button (`workflow_dispatch`)
4. **GitHub CLI:** `gh workflow run daily-digest.yml` bzw. `gh workflow run weekly-summary.yml`

Die Entrypoints erkennen automatisch ob sie lokal oder in GitHub Actions laufen (via `GITHUB_ACTIONS` Environment Variable) und passen Pfade/Commit-Verhalten entsprechend an.

### iOS Shortcut Setup

Ein Apple Shortcut der den GitHub Actions Workflow per API triggert:

**Shortcut-Schritte:**

1. URL: `https://api.github.com/repos/{owner}/ai-news-digest/actions/workflows/daily-digest.yml/dispatches`
2. Methode: POST
3. Header: `Authorization: Bearer {GITHUB_PAT}`, `Accept: application/vnd.github+v3+json`
4. Body (JSON): `{"ref": "main"}`
5. Optional: Benachrichtigung "Digest wird generiert..." anzeigen

**Voraussetzungen:**

- GitHub Personal Access Token (PAT) mit `repo` und `actions` Scope
- PAT wird im Shortcut gespeichert (verschlüsselt via iCloud Keychain)

**Nutzung:**

- Ein Tap auf dem Home Screen, Lock Screen Widget, oder "Hey Siri, AI Digest"
- Digest kommt ~2-3 Minuten später per Ntfy Push

**README enthält:** Schritt-für-Schritt Anleitung mit Screenshots zum Erstellen des iOS Shortcuts.

## Erweiterungsmöglichkeiten (nicht in Phase 1)

- Web-Scraping-Collector für Quellen ohne RSS (Meta AI, Product Hunt, TLDR AI, The Batch)
- HuggingFace Daily Papers Integration
- Mehrere Ntfy-Topics für verschiedene Kategorien
- GitHub Pages für hübschere Darstellung
- Historische Trend-Analyse über Monate
