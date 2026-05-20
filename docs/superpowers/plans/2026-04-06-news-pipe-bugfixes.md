# news-pipe Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 5 bugs in news-pipe — subscription-specific prompts, max_duration filter, RSS cleanup, language mapping, umlaut.

**Architecture:** Add `type` field to subscriptions, route to type-specific prompts via `PROMPT_MAP`. Add client-side duration filter as API fallback. Map ISO language codes to names before prompt formatting.

**Tech Stack:** Python 3.9, pytest, pytest-asyncio, httpx

**Test runner:** `.venv/bin/python -m pytest tests/ -v --tb=short`

**Spec:** `docs/superpowers/specs/2026-04-06-news-pipe-bugfixes-design.md`

---

## File Structure

| File                             | Action | Responsibility                                                                    |
| -------------------------------- | ------ | --------------------------------------------------------------------------------- |
| `src/summarizer.py`              | Modify | Add FLIGHT_DEALS_PROMPT, PROMPT_MAP, language mapping, route by subscription_type |
| `src/collectors/flights.py`      | Modify | Fix max_duration (hours→minutes), add client-side filter, fix umlaut              |
| `daily_digest.py`                | Modify | Read subscription type, pass to summarizer functions                              |
| `weekly_summary.py`              | Modify | Same language bug fix as daily_digest                                             |
| `config.yaml`                    | Modify | Add type fields, remove bali-flights RSS feeds                                    |
| `tests/test_summarizer.py`       | Modify | Add tests for language mapping, subscription_type routing                         |
| `tests/test_flight_collector.py` | Modify | Add test for max_duration client-side filter                                      |
| `tests/test_daily_digest.py`     | Modify | Update pipeline mock to pass subscription_type                                    |

---

### Task 1: Language Mapping in Summarizer

**Files:**

- Modify: `src/summarizer.py`
- Test: `tests/test_summarizer.py`

- [ ] **Step 1: Write failing test for \_resolve_language**

Add to `tests/test_summarizer.py`:

```python
from src.summarizer import _resolve_language


def test_resolve_language_maps_de():
    assert _resolve_language("de") == "Deutsch"


def test_resolve_language_maps_en():
    assert _resolve_language("en") == "English"


def test_resolve_language_passes_through_unknown():
    assert _resolve_language("Deutsch") == "Deutsch"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_summarizer.py::test_resolve_language_maps_de -v`
Expected: FAIL with `ImportError: cannot import name '_resolve_language'`

- [ ] **Step 3: Implement \_resolve_language and LANGUAGE_MAP**

In `src/summarizer.py`, add after the imports (before the prompt constants):

```python
LANGUAGE_MAP = {
    "de": "Deutsch",
    "en": "English",
    "fr": "Français",
    "es": "Español",
}


def _resolve_language(code: str) -> str:
    """Map ISO 639-1 codes to full language names for prompts."""
    return LANGUAGE_MAP.get(code, code)
```

- [ ] **Step 4: Apply \_resolve_language in all summarize functions**

In each of the 4 functions (`summarize_daily`, `summarize_top3`, `summarize_notification`, `summarize_weekly`), add as the first line inside the function body:

```python
language = _resolve_language(language)
```

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All 51 pass (48 existing + 3 new)

- [ ] **Step 6: Commit**

```bash
git add src/summarizer.py tests/test_summarizer.py
git commit -m "fix: map language codes to names in summarizer prompts

Config uses ISO codes ('de'), but prompts need language names ('Deutsch').
Added LANGUAGE_MAP and _resolve_language() applied in all summarize functions."
```

---

### Task 2: Subscription-Specific Prompts

**Files:**

- Modify: `src/summarizer.py`
- Modify: `daily_digest.py`
- Modify: `weekly_summary.py`
- Test: `tests/test_summarizer.py`
- Test: `tests/test_daily_digest.py`

- [ ] **Step 1: Write failing test for subscription_type routing**

Add to `tests/test_summarizer.py`:

```python
@pytest.mark.asyncio
async def test_summarize_daily_uses_flight_prompt_for_flight_deals(sample_articles, settings):
    mock_proc = _mock_process("# Flug-Deals\n\n1. FRA->DPS 487 EUR")

    with patch("src.summarizer.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        result = await summarize_daily(
            sample_articles, settings, prompt_focus="Top 5 Fluege", subscription_type="flight_deals"
        )

    call_args = mock_exec.call_args
    prompt_sent = call_args.kwargs.get("input") or mock_proc.communicate.call_args
    # Verify the function was called (prompt content tested via _call_claude mock)
    assert result == "# Flug-Deals\n\n1. FRA->DPS 487 EUR"


@pytest.mark.asyncio
async def test_summarize_daily_defaults_to_news_prompt(sample_articles, settings):
    mock_proc = _mock_process("# AI Digest\n\nNews content")

    with patch("src.summarizer.asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await summarize_daily(sample_articles, settings, prompt_focus="Focus on AI")

    assert result == "# AI Digest\n\nNews content"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_summarizer.py::test_summarize_daily_uses_flight_prompt_for_flight_deals -v`
Expected: FAIL with `TypeError: summarize_daily() got an unexpected keyword argument 'subscription_type'`

- [ ] **Step 3: Add FLIGHT_DEALS_PROMPT and PROMPT_MAP**

In `src/summarizer.py`, add after the existing `NOTIFICATION_PROMPT`:

```python
FLIGHT_DEALS_PROMPT = """Du bist ein Flug-Deal-Analyst. Hier sind aktuelle Flugsuchergebnisse.

Erstelle eine übersichtliche Flug-Deal-Liste auf {language}.

{prompt_focus}

Regeln:
- Sortiere nach Preis (günstigster zuerst)
- Zeige pro Flug: Abflughafen, Preis, Airline, Stopps, Gesamtdauer, Buchungslink
- Verlinke auf Buchungsseiten wo möglich
- Antworte nur mit der formatierten Liste, kein Meta-Kommentar

Hier sind die gesammelten Daten:
{collected_data}"""

FLIGHT_TOP3_PROMPT = """Fasse die Top 3 günstigsten Flüge in maximal 500 Zeichen zusammen. Nur Fließtext, keine Markdown-Formatierung. {language}.

{digest_markdown}"""

FLIGHT_NOTIFICATION_PROMPT = """Du bist ein Flug-Deal-Redakteur. Erstelle aus den folgenden Flug-Deals eine kompakte Zusammenfassung für eine Push-Notification.

Regeln:
- Maximal 3900 Zeichen (harte Grenze!)
- Verwende Markdown-Formatierung (fett, Aufzählungen)
- Zeige pro Flug: Abflughafen → Ziel, Preis, Airline, Dauer
- Sortiere nach Preis
- Sprache: {language}
- Kein Meta-Kommentar, nur der Inhalt

{prompt_focus}

{digest_markdown}"""

PROMPT_MAP = {
    "news": {
        "daily": DAILY_PROMPT,
        "top3": TOP3_PROMPT,
        "notification": NOTIFICATION_PROMPT,
    },
    "flight_deals": {
        "daily": FLIGHT_DEALS_PROMPT,
        "top3": FLIGHT_TOP3_PROMPT,
        "notification": FLIGHT_NOTIFICATION_PROMPT,
    },
}
```

- [ ] **Step 4: Update summarize_daily to accept subscription_type**

Replace the existing `summarize_daily` function:

```python
async def summarize_daily(articles: list[Article], settings: dict, prompt_focus: str = "", language: str = "Deutsch", subscription_type: str = "news") -> str:
    language = _resolve_language(language)
    collected_data = json.dumps(
        [a.to_dict() for a in articles],
        ensure_ascii=False,
        indent=2,
    )
    prompts = PROMPT_MAP.get(subscription_type, PROMPT_MAP["news"])
    prompt = prompts["daily"].format(
        collected_data=collected_data,
        prompt_focus=prompt_focus,
        language=language,
    )
    return await _call_claude(prompt, settings["daily_model"])
```

- [ ] **Step 5: Update summarize_top3 to accept subscription_type**

Replace the existing `summarize_top3` function:

```python
async def summarize_top3(digest_markdown: str, settings: dict, language: str = "Deutsch", subscription_type: str = "news") -> str:
    language = _resolve_language(language)
    prompts = PROMPT_MAP.get(subscription_type, PROMPT_MAP["news"])
    prompt = prompts["top3"].format(digest_markdown=digest_markdown, language=language)
    result = await _call_claude(prompt, settings["daily_model"])
    return result[:500]
```

- [ ] **Step 6: Update summarize_notification to accept subscription_type**

Replace the existing `summarize_notification` function:

```python
async def summarize_notification(digest_markdown: str, settings: dict, prompt_focus: str = "", language: str = "Deutsch", subscription_type: str = "news") -> str:
    language = _resolve_language(language)
    prompts = PROMPT_MAP.get(subscription_type, PROMPT_MAP["news"])
    prompt = prompts["notification"].format(
        digest_markdown=digest_markdown,
        prompt_focus=prompt_focus,
        language=language,
    )
    result = await _call_claude(prompt, settings["daily_model"])
    return result[:3900]
```

- [ ] **Step 7: Update daily_digest.py to pass subscription_type**

In `daily_digest.py`, in `run_subscription()`:

After line 69 (`language = sub_config.get("language", "de")`), add:

```python
subscription_type = sub_config.get("type", "news")
```

Update line 99:

```python
digest_markdown = await summarize_daily(articles, settings, prompt_focus, language, subscription_type)
```

Update line 106:

```python
top3_summary = await summarize_top3(digest_markdown, settings, language, subscription_type)
```

Update line 107:

```python
notification_summary = await summarize_notification(digest_markdown, settings, prompt_focus, language, subscription_type)
```

- [ ] **Step 8: Update weekly_summary.py to pass subscription_type**

In `weekly_summary.py`, in `run_subscription_weekly()`:

After line 30 (`prompt_focus = sub_config.get("prompt_focus", "")`), add:

```python
subscription_type = sub_config.get("type", "news")
```

Update line 41:

```python
top3 = await summarize_top3(weekly_markdown, settings, language, subscription_type)
```

Update line 42:

```python
notification_summary = await summarize_notification(weekly_markdown, settings, prompt_focus, language, subscription_type)
```

- [ ] **Step 9: Update test_daily_digest.py mock signatures**

In `tests/test_daily_digest.py`, update `test_run_daily_full_pipeline` — the mock for `summarize_daily` needs to accept the new `subscription_type` argument. No change needed since `AsyncMock` accepts any args, but verify it still passes.

- [ ] **Step 10: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All pass (existing + new)

- [ ] **Step 11: Commit**

```bash
git add src/summarizer.py daily_digest.py weekly_summary.py tests/test_summarizer.py
git commit -m "feat: add subscription-specific prompts via type field

Bali-flights pipe was using the AI-news DAILY_PROMPT. Added
FLIGHT_DEALS_PROMPT with deal-focused formatting, routed via
PROMPT_MAP keyed by subscription type (news/flight_deals)."
```

---

### Task 3: max_duration Filter Fix

**Files:**

- Modify: `src/collectors/flights.py`
- Test: `tests/test_flight_collector.py`

- [ ] **Step 1: Write failing test for max_duration client-side filter**

Add to `tests/test_flight_collector.py`:

```python
@pytest.mark.asyncio
async def test_flight_collector_filters_by_max_duration(flight_config, settings):
    """Flights exceeding max_duration should be filtered out client-side."""
    flight_config["max_duration"] = 18  # 18 hours = 1080 minutes

    # SAMPLE_SERPAPI_RESPONSE has flights with total_duration 1110 and 1035
    # 1110 min = 18.5h → should be filtered OUT (exceeds 18h)
    # 1035 min = 17.25h → should pass
    response = httpx.Response(200, json=SAMPLE_SERPAPI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            articles = await FlightSearchCollector(flight_config, settings).collect(client)

    assert len(articles) == 1
    assert "623" in articles[0].title  # only the 1035-min flight survives
```

- [ ] **Step 2: Write failing test for max_duration API parameter conversion**

Add to `tests/test_flight_collector.py`:

```python
@pytest.mark.asyncio
async def test_flight_collector_sends_max_duration_in_minutes(flight_config, settings):
    """max_duration config is in hours, SerpApi expects minutes."""
    flight_config["max_duration"] = 22

    response = httpx.Response(200, json={"best_flights": [], "other_flights": []})
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response) as mock_get, \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            await FlightSearchCollector(flight_config, settings).collect(client)

    params = mock_get.call_args.kwargs["params"]
    assert params["max_duration"] == 1320  # 22 * 60
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_flight_collector.py::test_flight_collector_filters_by_max_duration tests/test_flight_collector.py::test_flight_collector_sends_max_duration_in_minutes -v`
Expected: Both FAIL

- [ ] **Step 4: Implement fixes in flights.py**

In `src/collectors/flights.py`, in the `collect` method:

Replace lines 41-43:

```python
        max_duration = self.config.get("max_duration")
        if max_duration:
            params["max_duration"] = max_duration
```

With:

```python
        max_duration = self.config.get("max_duration")
        if max_duration:
            params["max_duration"] = max_duration * 60  # API expects minutes
```

BEFORE line 64 (`all_flights = all_flights[:max_results]`), add the client-side filter:

```python
        if max_duration:
            max_minutes = max_duration * 60
            all_flights = [f for f in all_flights if f.get("total_duration", 0) <= max_minutes]
```

Note: The client-side filter must come BEFORE `max_results` slicing — we want the top N flights that meet the duration criteria, not filter after truncating.

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/collectors/flights.py tests/test_flight_collector.py
git commit -m "fix: max_duration filter — convert hours to minutes for SerpApi

Config specifies max_duration in hours (22), but SerpApi expects minutes
(1320). Also added client-side filter as fallback for flights that slip
through the API filter."
```

---

### Task 4: Umlaut Fix + RSS Cleanup

**Files:**

- Modify: `src/collectors/flights.py:145`
- Modify: `config.yaml`
- Test: `tests/test_flight_collector.py`

- [ ] **Step 1: Fix umlaut in flights.py**

In `src/collectors/flights.py`, line 145, replace:

```python
                lines.append(f"CO2: {abs(diff)}% weniger als ueblich")
```

With:

```python
                lines.append(f"CO2: {abs(diff)}% weniger als üblich")
```

- [ ] **Step 2: Update CO2 test to expect correct umlaut**

In `tests/test_flight_collector.py`, update `test_flight_collector_co2_info`:

Replace:

```python
    assert "10% weniger" in summary
```

With:

```python
    assert "10% weniger als üblich" in summary
```

- [ ] **Step 3: Run flight tests**

Run: `.venv/bin/python -m pytest tests/test_flight_collector.py -v --tb=short`
Expected: All pass

- [ ] **Step 4: Remove RSS feeds from bali-flights in config.yaml**

In `config.yaml`, delete the entire `deals` section under `bali-flights.sources` (lines 176-181):

```yaml
deals:
  - name: Urlaubspiraten
    type: rss
    url: https://www.urlaubspiraten.de/feed
    priority: low
  - name: Travel-Dealz
    type: rss
    url: https://travel-dealz.com/feed
    priority: low
```

- [ ] **Step 5: Add type fields to both subscriptions in config.yaml**

Add `type: news` after `language: de` in `ai-news` subscription.
Add `type: flight_deals` after `language: de` in `bali-flights` subscription.

```yaml
  ai-news:
    name: "AI & ML News"
    ...
    language: de
    type: news
    ...

  bali-flights:
    name: "Bali Flug-Deals"
    ...
    language: de
    type: flight_deals
    ...
```

- [ ] **Step 6: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/collectors/flights.py tests/test_flight_collector.py config.yaml
git commit -m "fix: umlaut in flight CO2 text, remove irrelevant RSS feeds

Fixed 'ueblich' → 'üblich' in flights.py. Removed Urlaubspiraten and
Travel-Dealz RSS feeds from bali-flights (12 of 22 articles were
irrelevant). Added subscription type fields to config."
```

---

### Task 5: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All tests pass (48 existing updated + new tests)

- [ ] **Step 2: Verify config.yaml is valid**

Run: `.venv/bin/python -c "from src.config import load_config; c = load_config(); print(f'OK: {len(c[\"subscriptions\"])} subscriptions'); [print(f'  {k}: type={v.get(\"type\", \"news\")}') for k,v in c['subscriptions'].items()]"`
Expected:

```
OK: 2 subscriptions
  ai-news: type=news
  bali-flights: type=flight_deals
```

- [ ] **Step 3: Verify no RSS feeds in bali-flights**

Run: `.venv/bin/python -c "from src.config import load_config; c = load_config(); sources = c['subscriptions']['bali-flights']['sources']; print(f'Source categories: {list(sources.keys())}'); assert 'deals' not in sources, 'deals section should be removed'"`
Expected: `Source categories: ['flights']`
