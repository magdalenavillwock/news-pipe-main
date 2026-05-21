# src/summarizer.py
import asyncio
import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

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

FINANCE_DAILY_PROMPT = """Du bist ein präziser Finanzanalyst. Erstelle ein strukturiertes Morning-Briefing für den heutigen Handelstag {date}.

Führe zunächst eine Websuche durch. Relevante Quellen: Handelsblatt, Reuters, Bloomberg, CNBC, finanzen.net, Yahoo Finance, Wall Street Journal. Suche gezielt nach:
- Overnight-Bewegungen an Asien- und US-Märkten
- Vorbörslichen Kursveränderungen DAX, S&P 500, Nasdaq
- Makroterminkalendern für heute
- Relevanten Unternehmens- oder Sektornachrichten seit gestern 18:00 Uhr

Quellenregel: Belege faktische Aussagen mit Quelle und Datum, sofern aus der Websuche verfügbar. Wenn keine verifizierbare Quelle vorliegt, kennzeichne die Aussage explizit als Einschätzung. Widersprüchliche Analystenmeinungen werden gegenübergestellt, nicht harmonisiert.

Sprache: Deutscher Satzbau durchgehend. Englische Börsenfachbegriffe (bullish, bearish, RSI, Futures etc.) sind zulässig, englische Satzstrukturen nicht.

Fachbegriffe gemäß Deutscher Börse.

─────────────────────────────────────────
STRUKTUR (Pflicht, diese Reihenfolge):
─────────────────────────────────────────

① OVERNIGHT & VORBÖRSLICH [max. 200 Wörter]
Was bewegte die Märkte seit gestern Abend? Asien-Schluss, US-Schluss, US Futures, relevante Ereignisse nach Börsenschluss. Nur wenn wirklich bewegt – sonst: „Keine wesentlichen Overnight-Bewegungen."

② TAGESÜBERBLICK: SCHLÜSSELINDIZES [max. 150 Wörter]
DAX, S&P 500, Nasdaq – Vortagsschluss, vorbörsliche Tendenz. Einzelwerte nur bei Bewegungen >3 % oder konkretem Nachrichtentreiber.

③ HEUTIGE TERMINE & TRIGGER [max. 200 Wörter]
Makrodaten (z. B. CPI, Arbeitsmarkt, BIP-Revision), Zinsentscheide, Earnings-Berichte, politische Ereignisse. Format pro Termin:
Uhrzeit – Ereignis – erwartete Marktreaktion (bullish / bearish / neutral, mit Begründung).

④ EIN RISIKO, EINE CHANCE [je max. 100 Wörter]
Das konkreteste Abwärtsrisiko heute. Die konkreteste Aufwärtschance heute.
Keine allgemeinen Aussagen wie „Märkte könnten steigen."
Jede Aussage enthält mindestens eine konkrete Zahl (Kurs, %, Schwellenwert oder Datum).

⑤ WATCHLIST-HINWEIS [optional, nur wenn relevant]
Maximal 3 Werte oder Sektoren mit auffälliger Lage. Nur aufnehmen, wenn ein konkreter Grund vorliegt — kein Auffüllen.

─────────────────────────────────────────
REGELN:
─────────────────────────────────────────
- Gesamtlänge: 450-750 Wörter
- Kein Abschnitt wird künstlich befüllt
- Rohstoffe nur erwähnen, wenn sie heute direkten Markteinfluss haben
- Kein 3-Monats-Ausblick, keine Strategieempfehlung — das ist Aufgabe des Weekly
- Kein Meta-Kommentar, keine Einleitung, keine Schlusszusammenfassung

AUSGABE: Schreibe ausschließlich XML-Tags in exakt dieser Reihenfolge. Kein Text außerhalb der Tags.

<OVERNIGHT>Inhalt für Abschnitt ① hier</OVERNIGHT>
<INDIZES>Inhalt für Abschnitt ② hier</INDIZES>
<TERMINE>Inhalt für Abschnitt ③ hier</TERMINE>
<RISIKO>Nur den Risiko-Text für Abschnitt ④ hier (ohne das Wort „Risiko:")</RISIKO>
<CHANCE>Nur den Chance-Text für Abschnitt ④ hier (ohne das Wort „Chance:")</CHANCE>
<WATCHLIST>Inhalt für ⑤ hier — leer lassen wenn kein konkreter Hinweis vorliegt: <WATCHLIST></WATCHLIST></WATCHLIST>

Hier sind die gesammelten Nachrichtendaten des heutigen Tages:
{collected_data}"""

FINANCE_TOP3_PROMPT = """Fasse die drei wichtigsten Marktnews des heutigen Tages {date} in maximal 600 Zeichen zusammen. Priorisiere nach direktem Kurseinfluss. Nur Fließtext, keine Markdown-Formatierung. Sprache: Deutsch.

{digest_markdown}"""

FINANCE_NOTIFICATION_PROMPT = """Du bist ein Finanzredakteur. Erstelle aus den wichtigsten Marktnews des heutigen Tages {date} eine kompakte Zusammenfassung für eine Push-Notification.

Führe eine Websuche nach den relevantesten Finanznachrichten des heutigen Tages durch.

Regeln:
- Harte Zeichengrenze: 3900 Zeichen — wird diese überschritten, kürze ohne Rückfrage
- Priorisiere nach direktem Kurseinfluss; Themen ohne Marktbewegung werden weggelassen
- Markdown-Formatierung: fett, Aufzählungen, ## Überschriften
- Verlinke auf Originalquellen wo aus der Websuche verfügbar: [Text](URL)
- Sprache: Deutsch
- Kein Meta-Kommentar, nur Inhalt

{prompt_focus}

{digest_markdown}"""

FINANCE_WEEKLY_PROMPT = """Du bist ein erfahrener Finanzanalyst. Erstelle eine vollständige Wochenanalyse für KW {week_number}, Zeitraum {week_start} bis {week_end}.

Führe eine umfassende Websuche durch. Quellen: TradingView, Handelsblatt, Reuters, Bloomberg, CNBC, finanzen.net, Yahoo Finance, Wall Street Journal, SeekingAlpha, Deutsche Börse. Suche gezielt nach:
- Wochenperformance der Hauptindizes (DAX, S&P 500, Nasdaq, EuroStoxx 50, Nikkei, Hang Seng)
- Rohstoffpreisen (WTI, Brent, Gold, Silber) für den Zeitraum {week_start}–{week_end}
- Relevanten Makrodaten und Notenbankentscheidungen der Woche
- Bedeutenden Quartalszahlen, M&A-Ereignissen, geopolitischen Entwicklungen

Quellenregel: Belege faktische Aussagen mit Quelle und Veröffentlichungsdatum, sofern aus der Websuche verfügbar. Nicht verifizierbare Einschätzungen werden als solche gekennzeichnet. Widersprüchliche Analysteneinschätzungen werden explizit gegenübergestellt, nicht harmonisiert.

Detailgrad: Jeder Abschnitt enthält mindestens eine konkrete Zahl (Kurs, %, Basispunkte oder Datum). Keine Aussage ohne quantitativen Anker.

Sprache: Deutscher Satzbau durchgehend. Englische Börsenfachbegriffe (bullish, bearish, RSI, Spread etc.) sind zulässig, englische Satzstrukturen nicht.

Fachbegriffe nach Deutscher Börse.

─────────────────────────────────────────
STRUKTUR:
─────────────────────────────────────────

① AKTUALITÄTS-CHECK
Gab es in den letzten 48 Stunden Ereignisse, die frühere Wocheneinschätzungen überholen?
Falls nein: explizit bestätigen.

② ONE-MINUTE-TAKEAWAY
3–5 Sätze. Die wichtigsten Erkenntnisse der Woche. Keine Phrasen.
Konkrete Zahlen und Treiber — jede Aussage mit quantitativem Anker.

③ MARKTÜBERBLICK: INDIZES & EINZELWERTE
Wochenperformance: DAX, S&P 500, Dow Jones, Nasdaq, EuroStoxx 50, Nikkei, Hang Seng.
Währungen: EUR/USD, ggf. USD/JPY, DXY.
Rohstoffe (Pflicht): Öl (WTI & Brent), Gold, Silber — je mit konkretem Wochenverlauf.
Einzelwerte: nur bei Bewegungen >5 % oder klarem Nachrichtentreiber.

④ TECHNISCHE ANALYSE
DAX und S&P 500 verpflichtend: RSI (aktueller Wert), gleitende Durchschnitte (50/200-Tage, aktuelle Kursnähe), Trendstruktur, konkrete Unterstützungs- und Widerstandsmarken mit Niveaus in Punkten.

⑤ MAKROÖKONOMISCHER KONTEXT
Geldpolitik: FED, EZB, BOJ — konkrete Aussagen oder Entscheidungen der Woche.
Konjunkturdaten: Inflation, Arbeitsmarkt, BIP — nur veröffentlichte Zahlen dieser Woche.
Rohstoffmärkte und direkter Einfluss auf Aktienmärkte (Pflicht).

⑥ SONDERSITUATIONEN & MIKROÖKONOMIE
Quartalszahlen, M&A, IPOs, Rating-Änderungen, regulatorische Eingriffe.
Pro Sondersituation: Beobachtung → Auswirkung → Bedeutung.

⑦ WELTPOLITISCHE & FINANZPOLITISCHE LAGE [Pflicht]
Geopolitik: Ukraine, Taiwan, Nahost, Handelskonflikte, Wahlen.
Einfluss auf Kapitalflüsse und Risikobereitschaft konkret benennen — keine allgemeinen Formulierungen.

⑧ FAZIT & HANDLUNGSMÖGLICHKEITEN [Pflicht]
Marktstimmung: Risk-on oder Risk-off? Begründet mit konkreten Indikatoren.
Chancen und Risiken der kommenden Woche: je 2–3 konkrete Punkte mit Zahlen.
Wichtige Termine nächste Woche: Datum, Ereignis, erwartete Marktrelevanz.
Watchlist: max. 5 Werte oder Sektoren mit kurzem Grund und aktuellem Kursniveau.
3-Monats-Einschätzung: Konkrete These mit Richtung und Bedingung — keine Absicherung nach allen Seiten.

─────────────────────────────────────────
REGELN:
─────────────────────────────────────────
- Kein Abschnitt wird mit Platzhaltern oder Phrasen befüllt
- Fehlen Daten trotz Websuche: explizit benennen statt erfinden
- Kein Meta-Kommentar, keine Einleitung, keine Schlusszusammenfassung

AUSGABE: Beginne mit „Wochenanalyse KW {week_number} | {week_start} – {week_end}", dann sofort ①.

Hier sind die Tages-Digests der vergangenen Woche:
{weekly_data}"""

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

PROMPT_MAP = {
    "news": {
        "daily": DAILY_PROMPT,
        "top3": TOP3_PROMPT,
        "notification": NOTIFICATION_PROMPT,
    },
    "finance": {
        "daily": FINANCE_DAILY_PROMPT,
        "top3": FINANCE_TOP3_PROMPT,
        "notification": FINANCE_NOTIFICATION_PROMPT,
    },
}

WEEKLY_PROMPT_MAP = {
    "finance": FINANCE_WEEKLY_PROMPT,
}


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


async def summarize_top3(digest_markdown: str, settings: dict, language: str = "Deutsch", subscription_type: str = "news") -> str:
    language = _resolve_language(language)
    prompts = PROMPT_MAP.get(subscription_type, PROMPT_MAP["news"])
    today = date.today()
    prompt = prompts["top3"].format(
        digest_markdown=digest_markdown,
        language=language,
        date=today.strftime("%d.%m.%Y"),
    )
    result = await _call_claude(prompt, settings["daily_model"])
    return result[:600]


async def summarize_notification(digest_markdown: str, settings: dict, prompt_focus: str = "", language: str = "Deutsch", subscription_type: str = "news") -> str:
    language = _resolve_language(language)
    prompts = PROMPT_MAP.get(subscription_type, PROMPT_MAP["news"])
    today = date.today()
    prompt = prompts["notification"].format(
        digest_markdown=digest_markdown,
        prompt_focus=prompt_focus,
        language=language,
        date=today.strftime("%d.%m.%Y"),
    )
    result = await _call_claude(prompt, settings["daily_model"])
    return result[:3900]


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
    return await _call_claude(prompt, settings["weekly_model"])
