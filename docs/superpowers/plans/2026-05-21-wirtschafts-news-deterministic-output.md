# Wirtschafts-News Deterministic Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Wirtschafts-News reports structurally consistent by having Claude output XML tags and Python render the final Markdown via Jinja2 templates.

**Architecture:** Claude writes only plain-text content inside XML tags (one per section). A regex extractor pulls out each section into a dict. A Jinja2 template renders the final Markdown deterministically — Claude never controls structure again.

**Tech Stack:** Python 3.12, Jinja2 (already in requirements.txt), pytest + pytest-asyncio, unittest.mock

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `templates/wirtschafts-news-daily.md.j2` | Create | Fixed Markdown layout for daily report |
| `templates/wirtschafts-news-weekly.md.j2` | Create | Fixed Markdown layout for weekly report |
| `src/summarizer.py` | Modify | XML extraction helpers, updated prompts, finance branches in summarize_daily/weekly |
| `tests/test_summarizer_xml.py` | Create | Unit tests for extraction, rendering, and summarize branches |
| `tests/conftest.py` | Create (if absent) | pytest-asyncio config |

`daily_digest.py`, `weekly_summary.py`, all workflows, `config.yaml` — **not touched**.

---

## Task 1: Create Jinja2 Templates

**Files:**
- Create: `templates/wirtschafts-news-daily.md.j2`
- Create: `templates/wirtschafts-news-weekly.md.j2`

- [ ] **Step 1: Create daily template**

Create `templates/wirtschafts-news-daily.md.j2` with this exact content:

```jinja
Morning-Briefing {{ date }}

## ① OVERNIGHT & VORBÖRSLICH

{{ sections.OVERNIGHT }}

## ② TAGESÜBERBLICK: SCHLÜSSELINDIZES

{{ sections.INDIZES }}

## ③ HEUTIGE TERMINE & TRIGGER

{{ sections.TERMINE }}

## ④ EIN RISIKO, EINE CHANCE

**Risiko:** {{ sections.RISIKO }}

**Chance:** {{ sections.CHANCE }}
{% if sections.WATCHLIST %}

## ⑤ WATCHLIST-HINWEIS

{{ sections.WATCHLIST }}
{% endif %}
```

- [ ] **Step 2: Create weekly template**

Create `templates/wirtschafts-news-weekly.md.j2` with this exact content:

```jinja
Wochenanalyse KW {{ week_number }} | {{ week_start }} – {{ week_end }}

## ① AKTUALITÄTS-CHECK

{{ sections.AKTUALITAET }}

## ② ONE-MINUTE-TAKEAWAY

{{ sections.TAKEAWAY }}

## ③ MARKTÜBERBLICK: INDIZES & EINZELWERTE

{{ sections.MARKT }}

## ④ TECHNISCHE ANALYSE

{{ sections.TECHNIK }}

## ⑤ MAKROÖKONOMISCHER KONTEXT

{{ sections.MAKRO }}

## ⑥ SONDERSITUATIONEN & MIKROÖKONOMIE

{{ sections.SONDER }}

## ⑦ WELTPOLITISCHE & FINANZPOLITISCHE LAGE

{{ sections.POLITIK }}

## ⑧ FAZIT & HANDLUNGSMÖGLICHKEITEN

{{ sections.FAZIT }}
```

- [ ] **Step 3: Commit templates**

```bash
git add templates/wirtschafts-news-daily.md.j2 templates/wirtschafts-news-weekly.md.j2
git commit -m "feat: add wirtschafts-news Jinja2 templates for deterministic rendering"
```

---

## Task 2: Write Failing Tests for Helpers

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_summarizer_xml.py`

- [ ] **Step 1: Create conftest.py if it doesn't exist**

Create `tests/conftest.py`:

```python
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
```

- [ ] **Step 2: Write failing tests for `_extract_sections` and `_render_finance_template`**

Create `tests/test_summarizer_xml.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.summarizer import _extract_sections, _render_finance_template

SAMPLE_DAILY_XML = """
<OVERNIGHT>Nikkei +0,3%. US-Futures leicht im Plus. Keine wesentlichen Overnight-Bewegungen.</OVERNIGHT>
<INDIZES>DAX: 18.450 (+0,2%). S&P 500: 5.320 (+0,1%). Nasdaq: 16.800 (unverändert).</INDIZES>
<TERMINE>14:30 – US CPI April (Erw. 3,2%). Bullish wenn darunter, bearish wenn darüber.</TERMINE>
<RISIKO>Samsung-Streik ab Donnerstag: 48.000 Beschäftigte, globale Halbleiter-Lieferketten gefährdet.</RISIKO>
<CHANCE>EU-US-Handelsdeal entschärft Zollsorgen. DAX könnte auf 18.600 steigen.</CHANCE>
<WATCHLIST>Nvidia vor Quartalszahlen nach Börsenschluss.</WATCHLIST>
"""

SAMPLE_DAILY_XML_NO_WATCHLIST = """
<OVERNIGHT>Keine wesentlichen Overnight-Bewegungen.</OVERNIGHT>
<INDIZES>DAX: 18.200 (-0,1%).</INDIZES>
<TERMINE>Kein relevanter Termin heute.</TERMINE>
<RISIKO>Inflationsdaten morgen könnten überraschen. CPI-Konsens bei 3,0%.</RISIKO>
<CHANCE>Technologiewerte nach Google I/O im Aufwind. Nasdaq +0,5% möglich.</CHANCE>
<WATCHLIST></WATCHLIST>
"""

DAILY_REQUIRED = ["OVERNIGHT", "INDIZES", "TERMINE", "RISIKO", "CHANCE"]
DAILY_OPTIONAL = ["WATCHLIST"]


# --- _extract_sections ---

def test_extract_sections_all_present():
    sections = _extract_sections(SAMPLE_DAILY_XML, DAILY_REQUIRED + DAILY_OPTIONAL)
    assert sections["OVERNIGHT"] == "Nikkei +0,3%. US-Futures leicht im Plus. Keine wesentlichen Overnight-Bewegungen."
    assert sections["INDIZES"] == "DAX: 18.450 (+0,2%). S&P 500: 5.320 (+0,1%). Nasdaq: 16.800 (unverändert)."
    assert sections["WATCHLIST"] == "Nvidia vor Quartalszahlen nach Börsenschluss."


def test_extract_sections_missing_tag_returns_none():
    sections = _extract_sections("<OVERNIGHT>text</OVERNIGHT>", ["OVERNIGHT", "INDIZES"])
    assert sections["INDIZES"] is None


def test_extract_sections_empty_tag_returns_empty_string():
    sections = _extract_sections(SAMPLE_DAILY_XML_NO_WATCHLIST, DAILY_OPTIONAL)
    assert sections["WATCHLIST"] == ""


def test_extract_sections_multiline_content():
    xml = "<TERMINE>09:30 – CPI\n14:00 – Zinsentscheid\n16:00 – Pressekonferenz</TERMINE>"
    sections = _extract_sections(xml, ["TERMINE"])
    assert "09:30 – CPI" in sections["TERMINE"]
    assert "14:00 – Zinsentscheid" in sections["TERMINE"]


# --- _render_finance_template (daily) ---

def test_render_daily_template_all_sections():
    sections = {
        "OVERNIGHT": "Keine wesentlichen Overnight-Bewegungen.",
        "INDIZES": "DAX: 18.450.",
        "TERMINE": "14:30 – CPI.",
        "RISIKO": "Streik-Risiko.",
        "CHANCE": "Handelsdeal bullish.",
        "WATCHLIST": "Nvidia watchen.",
    }
    result = _render_finance_template(
        "wirtschafts-news-daily.md.j2",
        {"sections": sections, "date": "21.05.2026"},
    )
    assert "Morning-Briefing 21.05.2026" in result
    assert "## ① OVERNIGHT & VORBÖRSLICH" in result
    assert "## ② TAGESÜBERBLICK: SCHLÜSSELINDIZES" in result
    assert "## ③ HEUTIGE TERMINE & TRIGGER" in result
    assert "**Risiko:** Streik-Risiko." in result
    assert "**Chance:** Handelsdeal bullish." in result
    assert "## ⑤ WATCHLIST-HINWEIS" in result
    assert "Nvidia watchen." in result


def test_render_daily_template_no_watchlist():
    sections = {
        "OVERNIGHT": "Ruhige Nacht.",
        "INDIZES": "DAX stabil.",
        "TERMINE": "Kein Termin.",
        "RISIKO": "Inflationsrisiko.",
        "CHANCE": "Technologie-Bounce.",
        "WATCHLIST": "",
    }
    result = _render_finance_template(
        "wirtschafts-news-daily.md.j2",
        {"sections": sections, "date": "21.05.2026"},
    )
    assert "## ⑤ WATCHLIST-HINWEIS" not in result


def test_render_daily_template_none_watchlist():
    sections = {
        "OVERNIGHT": "Ruhige Nacht.",
        "INDIZES": "DAX stabil.",
        "TERMINE": "Kein Termin.",
        "RISIKO": "Inflationsrisiko.",
        "CHANCE": "Technologie-Bounce.",
        "WATCHLIST": None,
    }
    result = _render_finance_template(
        "wirtschafts-news-daily.md.j2",
        {"sections": sections, "date": "21.05.2026"},
    )
    assert "## ⑤ WATCHLIST-HINWEIS" not in result


def test_render_weekly_template():
    sections = {t: f"Inhalt {t}" for t in
                ["AKTUALITAET", "TAKEAWAY", "MARKT", "TECHNIK", "MAKRO", "SONDER", "POLITIK", "FAZIT"]}
    result = _render_finance_template(
        "wirtschafts-news-weekly.md.j2",
        {"sections": sections, "week_number": 21, "week_start": "19.05.2026", "week_end": "25.05.2026"},
    )
    assert "Wochenanalyse KW 21 | 19.05.2026 – 25.05.2026" in result
    assert "## ① AKTUALITÄTS-CHECK" in result
    assert "## ⑧ FAZIT & HANDLUNGSMÖGLICHKEITEN" in result
    assert "Inhalt FAZIT" in result
```

- [ ] **Step 3: Run tests — verify they all FAIL with ImportError**

```bash
py -m pytest tests/test_summarizer_xml.py -v
```

Expected: `ImportError: cannot import name '_extract_sections' from 'src.summarizer'`

---

## Task 3: Implement `_extract_sections` and `_render_finance_template`

**Files:**
- Modify: `src/summarizer.py`

- [ ] **Step 1: Add missing imports at top of `src/summarizer.py`**

Replace the existing import block:

```python
# src/summarizer.py
import asyncio
import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.models import Article
```

- [ ] **Step 2: Add constants and helper functions after the `_resolve_language` function (after line ~22)**

Insert after the `_resolve_language` function definition:

```python
DAILY_REQUIRED = ["OVERNIGHT", "INDIZES", "TERMINE", "RISIKO", "CHANCE"]
DAILY_OPTIONAL = ["WATCHLIST"]
WEEKLY_REQUIRED = ["AKTUALITAET", "TAKEAWAY", "MARKT", "TECHNIK", "MAKRO", "SONDER", "POLITIK", "FAZIT"]


def _extract_sections(xml: str, tags: list[str]) -> dict[str, str | None]:
    return {
        tag: m.group(1).strip()
        if (m := re.search(f"<{tag}>(.*?)</{tag}>", xml, re.DOTALL))
        else None
        for tag in tags
    }


def _render_finance_template(template_name: str, context: dict) -> str:
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    return env.get_template(template_name).render(**context)
```

- [ ] **Step 3: Run tests — verify helper tests now PASS**

```bash
py -m pytest tests/test_summarizer_xml.py -v -k "extract or render"
```

Expected: all `test_extract_*` and `test_render_*` tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/summarizer.py tests/conftest.py tests/test_summarizer_xml.py
git commit -m "feat: add XML section extraction and Jinja2 rendering helpers"
```

---

## Task 4: Write Failing Tests for `summarize_daily` Finance Branch

**Files:**
- Modify: `tests/test_summarizer_xml.py`

- [ ] **Step 1: Append async tests for `summarize_daily`**

Add to the bottom of `tests/test_summarizer_xml.py`:

```python
# --- summarize_daily (finance branch) ---

@pytest.mark.asyncio
async def test_summarize_daily_finance_returns_structured_markdown():
    """finance type extracts XML and renders via template."""
    settings = {"daily_model": "claude-sonnet-4-6"}
    articles = []

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = SAMPLE_DAILY_XML
        from src.summarizer import summarize_daily
        result = await summarize_daily(articles, settings, subscription_type="finance")

    assert "Morning-Briefing" in result
    assert "## ① OVERNIGHT & VORBÖRSLICH" in result
    assert "## ② TAGESÜBERBLICK: SCHLÜSSELINDIZES" in result
    assert "**Risiko:**" in result
    assert "**Chance:**" in result
    mock_claude.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_daily_finance_retries_on_missing_section():
    """When a required section is missing, a second call is made."""
    incomplete_xml = """
<OVERNIGHT>Ruhige Nacht.</OVERNIGHT>
<INDIZES>DAX stabil.</INDIZES>
<TERMINE>Kein Termin.</TERMINE>
<RISIKO>Streik-Risiko.</RISIKO>
"""
    retry_xml = "<CHANCE>Handelsdeal ist die Chance.</CHANCE>"

    settings = {"daily_model": "claude-sonnet-4-6"}

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.side_effect = [incomplete_xml, retry_xml]
        from src.summarizer import summarize_daily
        result = await summarize_daily([], settings, subscription_type="finance")

    assert mock_claude.call_count == 2
    assert "**Chance:** Handelsdeal ist die Chance." in result


@pytest.mark.asyncio
async def test_summarize_daily_finance_fallback_after_failed_retry():
    """After retry, still-missing sections get fallback text."""
    incomplete_xml = "<OVERNIGHT>text</OVERNIGHT><INDIZES>text</INDIZES><TERMINE>text</TERMINE><RISIKO>text</RISIKO>"

    settings = {"daily_model": "claude-sonnet-4-6"}

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.side_effect = [incomplete_xml, ""]
        from src.summarizer import summarize_daily
        result = await summarize_daily([], settings, subscription_type="finance")

    assert "[Keine Daten verfügbar]" in result


@pytest.mark.asyncio
async def test_summarize_daily_news_type_unchanged():
    """news type still returns raw Claude output without XML processing."""
    settings = {"daily_model": "claude-sonnet-4-6"}
    raw_output = "# AI News\n\nSome content here."

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = raw_output
        from src.summarizer import summarize_daily
        result = await summarize_daily([], settings, subscription_type="news")

    assert result == raw_output
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
py -m pytest tests/test_summarizer_xml.py -v -k "summarize_daily"
```

Expected: all 4 `test_summarize_daily_*` tests FAIL (finance branch doesn't exist yet)

---

## Task 5: Implement `summarize_daily` Finance Branch

**Files:**
- Modify: `src/summarizer.py`

- [ ] **Step 1: Update `summarize_daily` to add finance branch**

In `src/summarizer.py`, replace the existing `summarize_daily` function with:

```python
async def summarize_daily(articles: list[Article], settings: dict, prompt_focus: str = "", language: str = "Deutsch", subscription_type: str = "news") -> str:
    language = _resolve_language(language)
    collected_data = json.dumps(
        [a.to_dict() for a in articles],
        ensure_ascii=False,
        indent=2,
    )
    prompts = PROMPT_MAP.get(subscription_type, PROMPT_MAP["news"])
    today = date.today()
    prompt = prompts["daily"].format(
        collected_data=collected_data,
        prompt_focus=prompt_focus,
        language=language,
        date=today.strftime("%d.%m.%Y"),
    )
    raw = await _call_claude(prompt, settings["daily_model"])

    if subscription_type == "finance":
        sections = _extract_sections(raw, DAILY_REQUIRED + DAILY_OPTIONAL)
        missing = [t for t in DAILY_REQUIRED if not sections.get(t)]
        if missing:
            logger.warning(f"[finance-daily] Missing sections after first call: {missing}")
            retry_prompt = (
                f"Folgende XML-Tags fehlen in deiner Antwort: "
                f"{', '.join(f'<{t}>' for t in missing)}. "
                f"Bitte ergänze ausschließlich die fehlenden Tags."
            )
            raw2 = await _call_claude(retry_prompt, settings["daily_model"])
            for tag, val in _extract_sections(raw2, missing).items():
                if val:
                    sections[tag] = val
            for t in DAILY_REQUIRED:
                if not sections.get(t):
                    logger.warning(f"[finance-daily] Section {t} still missing after retry, using fallback")
                    sections[t] = "[Keine Daten verfügbar]"
        return _render_finance_template(
            "wirtschafts-news-daily.md.j2",
            {"sections": sections, "date": today.strftime("%d.%m.%Y")},
        )

    return raw
```

- [ ] **Step 2: Run tests — verify they PASS**

```bash
py -m pytest tests/test_summarizer_xml.py -v -k "summarize_daily"
```

Expected: all 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/summarizer.py tests/test_summarizer_xml.py
git commit -m "feat: add finance branch to summarize_daily with XML extraction and retry"
```

---

## Task 6: Update `FINANCE_DAILY_PROMPT` to Request XML Output

**Files:**
- Modify: `src/summarizer.py`

- [ ] **Step 1: Replace the AUSGABE block in `FINANCE_DAILY_PROMPT`**

In `src/summarizer.py`, find the last lines of `FINANCE_DAILY_PROMPT` and replace:

```python
# OLD (last 4 lines of FINANCE_DAILY_PROMPT):
AUSGABE: Beginne mit „Morning-Briefing {date}", dann sofort ①.

Hier sind die gesammelten Nachrichtendaten des heutigen Tages:
{collected_data}"""
```

With:

```python
# NEW:
AUSGABE: Schreibe ausschließlich XML-Tags in exakt dieser Reihenfolge. Kein Text außerhalb der Tags.

<OVERNIGHT>Inhalt für Abschnitt ① hier</OVERNIGHT>
<INDIZES>Inhalt für Abschnitt ② hier</INDIZES>
<TERMINE>Inhalt für Abschnitt ③ hier</TERMINE>
<RISIKO>Nur den Risiko-Text für Abschnitt ④ hier (ohne das Wort „Risiko:")</RISIKO>
<CHANCE>Nur den Chance-Text für Abschnitt ④ hier (ohne das Wort „Chance:")</CHANCE>
<WATCHLIST>Inhalt für ⑤ hier — leer lassen wenn kein konkreter Hinweis vorliegt: <WATCHLIST></WATCHLIST></WATCHLIST>

Hier sind die gesammelten Nachrichtendaten des heutigen Tages:
{collected_data}"""
```

- [ ] **Step 2: Run full test suite to ensure nothing broke**

```bash
py -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/summarizer.py
git commit -m "feat: update FINANCE_DAILY_PROMPT to output XML tags"
```

---

## Task 7: Write Failing Tests for `summarize_weekly` Finance Branch

**Files:**
- Modify: `tests/test_summarizer_xml.py`

- [ ] **Step 1: Append async tests for `summarize_weekly`**

Add to the bottom of `tests/test_summarizer_xml.py`:

```python
# --- summarize_weekly (finance branch) ---

SAMPLE_WEEKLY_XML = """
<AKTUALITAET>Keine Ereignisse der letzten 48 Stunden überholen frühere Einschätzungen.</AKTUALITAET>
<TAKEAWAY>DAX +1,2% auf Wochenbasis. S&P 500 +0,8%. Nvidia-Zahlen überzeugen.</TAKEAWAY>
<MARKT>DAX: 18.600 (+1,2%). S&P 500: 5.340 (+0,8%). Gold: 2.380 USD (+0,5%).</MARKT>
<TECHNIK>DAX RSI: 58 (neutral). 50-Tage-MA: 18.100 (Kurs darüber). Widerstand: 18.800.</TECHNIK>
<MAKRO>EZB hält Zinsen bei 3,75%. US CPI April: 3,1% (unter Erwartung). Bullish für Anleihen.</MAKRO>
<SONDER>Nvidia Q1: Umsatz +262% YoY. Commerzbank widersteht Unicredit-Übernahme.</SONDER>
<POLITIK>EU-US-Handelsdeal unterzeichnet. Ukraine-Waffenstillstandsgespräche ohne Ergebnis.</POLITIK>
<FAZIT>Risk-on-Stimmung. Chance: Tech-Sektor. Risiko: CPI-Daten nächste Woche.</FAZIT>
"""


@pytest.mark.asyncio
async def test_summarize_weekly_finance_returns_structured_markdown():
    """finance type weekly extracts XML and renders via template."""
    settings = {"weekly_model": "claude-opus-4-6"}

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = SAMPLE_WEEKLY_XML
        from src.summarizer import summarize_weekly
        result = await summarize_weekly(["digest1", "digest2"], settings, subscription_type="finance")

    assert "Wochenanalyse KW" in result
    assert "## ① AKTUALITÄTS-CHECK" in result
    assert "## ⑧ FAZIT & HANDLUNGSMÖGLICHKEITEN" in result
    mock_claude.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_weekly_finance_retries_on_missing_section():
    """Missing required section triggers a retry call."""
    incomplete = "\n".join(
        f"<{t}>Inhalt {t}</{t}>"
        for t in ["AKTUALITAET", "TAKEAWAY", "MARKT", "TECHNIK", "MAKRO", "SONDER", "POLITIK"]
        # FAZIT missing
    )
    retry_xml = "<FAZIT>Risk-on. Watchlist: Nvidia.</FAZIT>"

    settings = {"weekly_model": "claude-opus-4-6"}

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.side_effect = [incomplete, retry_xml]
        from src.summarizer import summarize_weekly
        result = await summarize_weekly([], settings, subscription_type="finance")

    assert mock_claude.call_count == 2
    assert "Risk-on. Watchlist: Nvidia." in result


@pytest.mark.asyncio
async def test_summarize_weekly_news_type_unchanged():
    """news type returns raw Claude output."""
    settings = {"weekly_model": "claude-opus-4-6"}
    raw = "# Weekly AI News\n\nContent."

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = raw
        from src.summarizer import summarize_weekly
        result = await summarize_weekly(["d1"], settings, subscription_type="news")

    assert result == raw
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
py -m pytest tests/test_summarizer_xml.py -v -k "summarize_weekly"
```

Expected: all 3 `test_summarize_weekly_*` tests FAIL

---

## Task 8: Implement `summarize_weekly` Finance Branch

**Files:**
- Modify: `src/summarizer.py`

- [ ] **Step 1: Update `summarize_weekly` to add finance branch**

In `src/summarizer.py`, replace the existing `summarize_weekly` function with:

```python
async def summarize_weekly(daily_digests: list[str], settings: dict, prompt_focus: str = "", language: str = "Deutsch", subscription_type: str = "news") -> str:
    language = _resolve_language(language)
    weekly_data = "\n\n---\n\n".join(daily_digests)
    template = WEEKLY_PROMPT_MAP.get(subscription_type, WEEKLY_PROMPT)
    today = date.today()
    iso = today.isocalendar()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    prompt = template.format(
        weekly_data=weekly_data,
        prompt_focus=prompt_focus,
        language=language,
        week_number=iso[1],
        week_start=week_start.strftime("%d.%m.%Y"),
        week_end=week_end.strftime("%d.%m.%Y"),
    )
    raw = await _call_claude(prompt, settings["weekly_model"])

    if subscription_type == "finance":
        sections = _extract_sections(raw, WEEKLY_REQUIRED)
        missing = [t for t in WEEKLY_REQUIRED if not sections.get(t)]
        if missing:
            logger.warning(f"[finance-weekly] Missing sections after first call: {missing}")
            retry_prompt = (
                f"Folgende XML-Tags fehlen in deiner Antwort: "
                f"{', '.join(f'<{t}>' for t in missing)}. "
                f"Bitte ergänze ausschließlich die fehlenden Tags."
            )
            raw2 = await _call_claude(retry_prompt, settings["weekly_model"])
            for tag, val in _extract_sections(raw2, missing).items():
                if val:
                    sections[tag] = val
            for t in WEEKLY_REQUIRED:
                if not sections.get(t):
                    logger.warning(f"[finance-weekly] Section {t} still missing after retry, using fallback")
                    sections[t] = "[Keine Daten verfügbar]"
        return _render_finance_template(
            "wirtschafts-news-weekly.md.j2",
            {
                "sections": sections,
                "week_number": iso[1],
                "week_start": week_start.strftime("%d.%m.%Y"),
                "week_end": week_end.strftime("%d.%m.%Y"),
            },
        )

    return raw
```

- [ ] **Step 2: Run all tests**

```bash
py -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/summarizer.py tests/test_summarizer_xml.py
git commit -m "feat: add finance branch to summarize_weekly with XML extraction and retry"
```

---

## Task 9: Update `FINANCE_WEEKLY_PROMPT` to Request XML Output

**Files:**
- Modify: `src/summarizer.py`

- [ ] **Step 1: Replace the AUSGABE block in `FINANCE_WEEKLY_PROMPT`**

Find the last lines of `FINANCE_WEEKLY_PROMPT` and replace:

```python
# OLD (last 4 lines):
AUSGABE: Beginne mit „Wochenanalyse KW {week_number} | {week_start} – {week_end}", dann sofort ①.

Hier sind die Tages-Digests der vergangenen Woche:
{weekly_data}"""
```

With:

```python
# NEW:
AUSGABE: Schreibe ausschließlich XML-Tags in exakt dieser Reihenfolge. Kein Text außerhalb der Tags.

<AKTUALITAET>Inhalt für ① hier</AKTUALITAET>
<TAKEAWAY>Inhalt für ② hier</TAKEAWAY>
<MARKT>Inhalt für ③ hier</MARKT>
<TECHNIK>Inhalt für ④ hier</TECHNIK>
<MAKRO>Inhalt für ⑤ hier</MAKRO>
<SONDER>Inhalt für ⑥ hier</SONDER>
<POLITIK>Inhalt für ⑦ hier</POLITIK>
<FAZIT>Inhalt für ⑧ hier</FAZIT>

Hier sind die Tages-Digests der vergangenen Woche:
{weekly_data}"""
```

- [ ] **Step 2: Run all tests**

```bash
py -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/summarizer.py
git commit -m "feat: update FINANCE_WEEKLY_PROMPT to output XML tags"
```

---

## Task 10: Smoke Test Against Real Data + PR

**Files:** None (read-only test run)

- [ ] **Step 1: Run daily digest against existing data**

```bash
py daily_digest.py wirtschafts-news --date 2026-05-20
```

Expected: no errors. Check `output/wirtschafts-news/daily/2026-05-20.md` — should contain `## ① OVERNIGHT & VORBÖRSLICH` as the first section header.

- [ ] **Step 2: Run the same command a second time and diff the structure**

```bash
py daily_digest.py wirtschafts-news --date 2026-05-20
```

Open `output/wirtschafts-news/daily/2026-05-20.md` and verify:
- Section headers are identical to the first run (`## ①`, `## ②`, etc.)
- `**Risiko:**` and `**Chance:**` labels are present
- No stray `Morning-Briefing` line outside the expected position

- [ ] **Step 3: Verify ai-news is unaffected**

```bash
py daily_digest.py ai-news --date 2026-05-20
```

Expected: no errors. Output in `output/ai-news/daily/2026-05-20.md` is unchanged (still uses old unstructured format).

- [ ] **Step 4: Push and create PR**

```bash
git push
gh pr create --title "feat: deterministic wirtschafts-news output via XML+Jinja2" --body "$(cat <<'EOF'
## Summary

- Claude now outputs XML-tagged sections instead of free-form Markdown for finance pipeline
- Python extracts sections via regex, renders via Jinja2 template (100% structural consistency)
- Retry logic handles missing sections (1 retry, then fallback to [Keine Daten verfügbar])
- ai-news pipeline completely unaffected

## Test plan
- [ ] All unit tests pass (pytest tests/)
- [ ] Daily smoke test: wirtschafts-news --date 2026-05-20 produces consistent ## headers
- [ ] Second run produces identical structure
- [ ] ai-news run unaffected

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" --base master
```
