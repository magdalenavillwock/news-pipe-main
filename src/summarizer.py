# src/summarizer.py
import asyncio
import json
import logging
from datetime import date, timedelta

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

FINANCE_DAILY_PROMPT = """Gib ausschließlich das fertige Morning-Briefing aus – vollständig, abschnittweise, ohne Einleitung, ohne Meta-Kommentar, ohne Zusammenfassung am Ende. Kein Satz wie „Das Briefing umfasst X Wörter" oder „Die Struktur wurde eingehalten." Beginne direkt mit ①.

Du bist ein präziser Finanzanalyst. Erstelle ein strukturiertes Morning-Briefing für den heutigen Handelstag {date}.

Nutze Websuche und beziehe dich auf aktuelle Quellen (Handelsblatt, Reuters, Bloomberg, CNBC, finanzen.net, Yahoo Finance, Wall Street Journal). Jede faktische Aussage erhält Quelle und Datum. Bei widersprüchlichen Einschätzungen: beide Positionen nennen, nicht glätten.

Sprache: Deutscher Satzbau durchgehend. Keine englischen Satzstrukturen. Fachbegriffe gemäß Deutscher Börse.

─────────────────────────────────────────
STRUKTUR (Pflicht, diese Reihenfolge):
─────────────────────────────────────────

① OVERNIGHT & VORBÖRSLICH [max. 150 Wörter]
Was bewegte die Märkte seit gestern Abend? Asien-Schluss, US-Futures, relevante Ereignisse nach Börsenschluss. Nur wenn wirklich bewegt – sonst: „Keine wesentlichen Overnight-Bewegungen."

② TAGESÜBERBLICK: SCHLÜSSELINDIZES [max. 100 Wörter]
DAX, S&P 500, Nasdaq – Vortagsschluss, vorbörsliche Tendenz. Einzelwerte nur bei Bewegungen >3 % oder konkretem Nachrichtentreiber.

③ HEUTIGE TERMINE & TRIGGER [max. 150 Wörter]
Makrodaten (z. B. CPI, Arbeitsmarkt, BIP-Revision), Zinsentscheide, Earnings-Berichte, politische Ereignisse. Format pro Termin: Uhrzeit – Ereignis – erwartete Marktreaktion (bullish / bearish / neutral, mit Begründung).

④ EIN RISIKO, EINE CHANCE [je max. 3 Sätze]
Das konkreteste Abwärtsrisiko heute. Die konkreteste Aufwärtschance heute. Keine allgemeinen Aussagen wie „Märkte könnten steigen."

⑤ WATCHLIST-HINWEIS [optional, nur wenn relevant]
Maximal 2 Werte oder Sektoren mit auffälliger Lage. Nur aufnehmen, wenn ein konkreter Grund vorliegt.

─────────────────────────────────────────
REGELN:
─────────────────────────────────────────
- Gesamtlänge: 400–600 Wörter
- Kein Abschnitt wird künstlich befüllt
- Rohstoffe nur erwähnen, wenn sie heute direkten Markteinfluss haben
- Kein 3-Monats-Ausblick, keine Strategieempfehlung – das ist Aufgabe des Weekly

AUSGABEFORMAT: Beginne deine Antwort mit der Zeile „Morning-Briefing {date}" und danach sofort mit Abschnitt ①. Nichts davor, nichts danach.

Hier sind die gesammelten Nachrichtendaten des heutigen Tages:
{collected_data}"""

FINANCE_WEEKLY_PROMPT = """Du bist ein erfahrener Finanzanalyst. Erstelle eine vollständige Wochenanalyse für KW {week_number}, Zeitraum {week_start} bis {week_end}.

Nutze Websuche. Quellen: TradingView, Handelsblatt, Reuters, Bloomberg, CNBC, finanzen.net, Yahoo Finance, Wall Street Journal, SeekingAlpha, Deutsche Börse, ggf. X/Twitter bei Marktrelevanz. Jede faktische Aussage: Quelle + Veröffentlichungsdatum. Widersprüchliche Analysteneinschätzungen werden explizit gegenübergestellt, nicht harmonisiert.

Sprache: Deutscher Satzbau durchgehend. Fachbegriffe nach Deutscher Börse und Coachingunterlagen. Detailgrad: +20 % gegenüber Standardanalysen – das bedeutet konkrete Zahlen, keine Phrasen.

─────────────────────────────────────────
VOLLSTÄNDIGKEITSBEDINGUNG:
─────────────────────────────────────────
Die Analyse gilt erst als vollständig, wenn alle 8 Abschnitte mit Quellenangaben ausgefüllt sind UND Abschnitt 7 (Weltpolitik) sowie Abschnitt 8 (Fazit & Strategie) substanziell befüllt sind – nicht mit Platzhaltern.

─────────────────────────────────────────
STRUKTUR:
─────────────────────────────────────────

① AKTUALITÄTS-CHECK
Gab es in den letzten 48 Stunden Ereignisse, die frühere Wocheneinschätzungen überholen? (Zinsentscheide, Überraschungsdaten, geopolitische Eskalation, Großereignisse) Falls nein: explizit bestätigen.

② ONE-MINUTE-TAKEAWAY
3–5 Sätze. Die wichtigsten Erkenntnisse der Woche für jemanden, der nur diesen Abschnitt liest. Keine Phrasen. Konkrete Zahlen und Treiber.

③ MARKTÜBERBLICK: INDIZES & EINZELWERTE
Wochenperformance: DAX, S&P 500, Dow Jones, Nasdaq, EuroStoxx 50, Nikkei, Hang Seng – prozentuale Veränderung, Kontext. Währungen: EUR/USD, ggf. USD/JPY, DXY. Rohstoffe (Pflicht): Öl (WTI & Brent), Gold, Silber; weitere (Kupfer, Erdgas) nur bei auffälliger Bewegung. Einzelwerte: nur bei Bewegungen >5 % oder klarem Nachrichtentreiber. Pro Wert: Beobachtung → Auswirkung → Bedeutung.

④ TECHNISCHE ANALYSE
Für DAX und S&P 500 verpflichtend: RSI (überkauft/überverkauft?), gleitende Durchschnitte (50-Tage, 200-Tage – Lage dazu?), dominante Trendstruktur, Unterstützung/Widerstand. Fibonacci und Volatilität (VIX, VDAX) nur bei auffälligen Konstellationen – nicht standardmäßig. Für andere Indizes/Rohstoffe: nur wenn technisch eine besondere Lage vorliegt.

⑤ MAKROÖKONOMISCHER KONTEXT
Geldpolitik: FED, EZB, BOJ – Entscheidungen, Protokolle, Signale. Was hat sich verändert? Konjunkturdaten: Inflation, Arbeitsmarkt, BIP – nur veröffentlichte Daten dieser Woche, mit Vergleich zu Erwartung und Vorperiode. Rohstoffmärkte und deren direkter Einfluss auf Aktienmärkte (Pflicht, auch wenn knapp).

⑥ SONDERSITUATIONEN & MIKROÖKONOMIE
Quartalszahlen, Gewinnwarnungen, M&A, IPOs, Dividenden, Rückkaufprogramme, Rating-Änderungen, regulatorische Eingriffe, Branchennews. Dividenden, ETF-Flows, Insider-Trades, Short Interest: nur aufnehmen, wenn in dieser Woche wirklich markant – kein Standardbefüllen. Sektorrotation und Fondsbewegungen: nur bei auffälligen Signalen. Pro Sondersituation: Beobachtung → Auswirkung → Bedeutung.

⑦ WELTPOLITISCHE & FINANZPOLITISCHE LAGE [Pflicht]
Geopolitik: Ukraine, Taiwan, Nahost, Handelskonflikte, Sanktionen, Wahlen – nur laufende oder neue Entwicklungen dieser Woche. Einfluss auf Kapitalflüsse und Risikobereitschaft konkret benennen, nicht abstrakt beschreiben.

⑧ FAZIT & HANDLUNGSMÖGLICHKEITEN [Pflicht]
Marktstimmung: Risk-on oder Risk-off? Begründet mit konkreten Indikatoren. Chancen und Risiken der kommenden Woche: je 2–3 konkrete Punkte, keine Allgemeinplätze. Wichtige Termine nächste Woche: Zinsentscheide, Makrodaten, Earnings, politische Ereignisse – mit Datum und erwarteter Marktrelevanz. Watchlist: max. 5 Werte oder Sektoren, ohne Value/Growth-Kategorisierung, mit kurzem Grund pro Eintrag. 3-Monats-Einschätzung: Wohin tendiert der Markt strukturell? Konkrete These, keine Absicherung nach allen Seiten.

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
    "flight_deals": {
        "daily": FLIGHT_DEALS_PROMPT,
        "top3": FLIGHT_TOP3_PROMPT,
        "notification": FLIGHT_NOTIFICATION_PROMPT,
    },
    "finance": {
        "daily": FINANCE_DAILY_PROMPT,
        "top3": TOP3_PROMPT,
        "notification": NOTIFICATION_PROMPT,
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
