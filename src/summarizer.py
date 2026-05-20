# src/summarizer.py
import asyncio
import json
import logging

from src.models import Article

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "de": "Deutsch",
    "en": "English",
    "fr": "Français",
    "es": "Español",
}


def _resolve_language(code: str) -> str:
    """Map ISO 639-1 codes to full language names for prompts."""
    return LANGUAGE_MAP.get(code, code)


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

TOP3_PROMPT = """Fasse die drei wichtigsten News des Tages in maximal 500 Zeichen zusammen. Nur Fließtext, keine Markdown-Formatierung. {language}.

{digest_markdown}"""

NOTIFICATION_PROMPT = """Du bist ein News-Redakteur. Erstelle aus dem folgenden Tages-Digest eine kompakte aber vollständige Zusammenfassung für eine Push-Notification.

Regeln:
- Maximal 3900 Zeichen (harte Grenze!)
- Verwende Markdown-Formatierung (fett, Aufzählungen, Überschriften mit ##)
- Alle relevanten News und Highlights müssen enthalten sein
- Verlinke auf Originalquellen wo möglich mit [Text](URL)
- Sprache: {language}
- Kein Meta-Kommentar, nur der Inhalt

{prompt_focus}

{digest_markdown}"""

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

WEEKLY_PROMPT = """Du bist ein Senior News-Analyst. Hier sind die 7 täglichen Digests der vergangenen Woche.

Erstelle einen umfassenden Wochenrückblick auf {language}:

1. **Top 10 der Woche** — Die 10 wichtigsten Entwicklungen, gerankt nach Impact
2. **Trend-Analyse** — Welche übergeordneten Trends zeichnen sich ab?
3. **Ausblick** — Was kommt nächste Woche? Worauf sollte man achten?
4. **Action Items** — Konkrete Dinge, die ich mir diese Woche anschauen/ausprobieren sollte
5. **Wochenstatistik** — Anzahl neue Tools, Papers, Major Releases etc.

{prompt_focus}

Hier sind die 7 Tages-Digests:
{weekly_data}"""


async def _call_claude(prompt: str, model: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "claude", "-p",
        "--model", model,
        "--output-format", "text",
        "--no-session-persistence",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(input=prompt.encode())
    if proc.returncode != 0:
        detail = stderr.decode().strip() or stdout.decode().strip()
        raise RuntimeError(f"Claude CLI failed (exit {proc.returncode}): {detail}")
    return stdout.decode().strip()


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


async def summarize_top3(digest_markdown: str, settings: dict, language: str = "Deutsch", subscription_type: str = "news") -> str:
    language = _resolve_language(language)
    prompts = PROMPT_MAP.get(subscription_type, PROMPT_MAP["news"])
    prompt = prompts["top3"].format(digest_markdown=digest_markdown, language=language)
    result = await _call_claude(prompt, settings["daily_model"])
    return result[:500]


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


async def summarize_weekly(daily_digests: list[str], settings: dict, prompt_focus: str = "", language: str = "Deutsch") -> str:
    language = _resolve_language(language)
    weekly_data = "\n\n---\n\n".join(daily_digests)
    prompt = WEEKLY_PROMPT.format(
        weekly_data=weekly_data,
        prompt_focus=prompt_focus,
        language=language,
    )
    return await _call_claude(prompt, settings["weekly_model"])
