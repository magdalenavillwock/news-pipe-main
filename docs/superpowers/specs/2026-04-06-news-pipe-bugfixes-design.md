# news-pipe Bug Fixes — Design Spec

**Datum:** 2026-04-06
**Scope:** 5 Bugs fixen, kein neues Feature

## Kontext

Die news-pipe hat 2 Subscriptions: `ai-news` (RSS/GitHub/ArXiv → AI-News-Digest) und `bali-flights` (SerpApi + RSS → Flug-Deals). Beide nutzen denselben Summarizer-Prompt, was zu fehlerhafter Ausgabe führt.

## Bug-Übersicht

| #   | Severity | Bug                                      | Ursache                                                                 |
| --- | -------- | ---------------------------------------- | ----------------------------------------------------------------------- |
| 1   | KRITISCH | Bali-Pipe erzeugt AI-News-Format         | `DAILY_PROMPT` hardcoded für AI-News                                    |
| 2   | HOCH     | Flüge mit 30-35h trotz max 22h           | `max_duration` Unit-Mismatch (Stunden vs. Minuten) + kein Client-Filter |
| 3   | MITTEL   | Irrelevante RSS-Artikel in Bali-Pipe     | Urlaubspiraten/Travel-Dealz liefern generische Reise-Deals              |
| 4   | MITTEL   | Prompt sagt "auf de" statt "auf Deutsch" | Config nutzt ISO-Codes, Prompts erwarten Sprachnamen                    |
| 5   | MINOR    | "ueblich" statt "üblich"                 | ASCII-Ersatz in flights.py                                              |

## Fix 1: Subscription-spezifische Prompts

### Entscheidung

Eigener Prompt pro Subscription-Typ statt generischem Base-Prompt.

### Änderungen

**`config.yaml`:**

- Neues Feld `type` pro Subscription (`news` | `flight_deals`)
- Default: `news` (abwärtskompatibel)

```yaml
subscriptions:
  ai-news:
    type: news
    ...
  bali-flights:
    type: flight_deals
    ...
```

**`src/summarizer.py`:**

- Bestehenden `DAILY_PROMPT` behalten (nur für `type: news`)
- Neuer `FLIGHT_DEALS_PROMPT` mit Fokus auf:
  - Top 5 Flüge sortiert nach Preis
  - Tabellarische Darstellung (Abflughafen, Preis, Airline, Dauer, Stopps)
  - Preisbewertung (Schnäppchen vs. über Budget)
  - Buchungslinks
  - Kein "Top 3 des Tages", keine "Highlights", kein "Extended"-Teil
- `PROMPT_MAP` dict: `{"news": DAILY_PROMPT, "flight_deals": FLIGHT_DEALS_PROMPT}`
- `summarize_daily()` bekommt neuen Parameter `subscription_type: str = "news"`
- Flight-spezifische Varianten:
  - `FLIGHT_TOP3_PROMPT`: "Fasse die Top 3 günstigsten Flüge in max 500 Zeichen zusammen."
  - `FLIGHT_NOTIFICATION_PROMPT`: Kompakte Flug-Deal-Liste für Push (max 3900 Zeichen)

**`daily_digest.py`:**

- `subscription_type = sub_config.get("type", "news")` auslesen
- An `summarize_daily()`, `summarize_top3()`, `summarize_notification()` durchreichen

### Prompt-Inhalt FLIGHT_DEALS_PROMPT

```
Du bist ein Flug-Deal-Analyst. Hier sind aktuelle Flugsuchergebnisse.

Erstelle eine übersichtliche Flug-Deal-Liste auf {language}.

{prompt_focus}

Regeln:
- Sortiere nach Preis (günstigster zuerst)
- Zeige pro Flug: Abflughafen, Preis, Airline, Stopps, Gesamtdauer, Buchungslink
- Verlinke auf Buchungsseiten wo möglich
- Antworte nur mit der formatierten Liste, kein Meta-Kommentar

Hier sind die gesammelten Daten:
{collected_data}
```

## Fix 2: max_duration Filter

### Änderungen in `src/collectors/flights.py`

1. **API-Parameter:** `max_duration` in Minuten umrechnen vor dem SerpApi-Request:

   ```python
   if max_duration:
       params["max_duration"] = max_duration * 60  # API erwartet Minuten
   ```

2. **Client-seitiger Fallback:** Nach API-Response filtern:
   ```python
   if max_duration:
       max_minutes = max_duration * 60
       all_flights = [f for f in all_flights if f.get("total_duration", 0) <= max_minutes]
   ```

## Fix 3: RSS-Feeds aus bali-flights entfernen

### Änderung in `config.yaml`

Die komplette `deals`-Sektion unter `bali-flights.sources` löschen:

```yaml
# ENTFERNEN:
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

Begründung: Die SerpApi liefert echte, strukturierte Flugdaten. Die RSS-Feeds liefern 12 von 22 Artikeln die nichts mit Bali zu tun haben (Mykonos, Gardasee, Kreuzfahrten).

## Fix 4: Language-Mapping

### Änderungen in `src/summarizer.py`

```python
LANGUAGE_MAP = {
    "de": "Deutsch",
    "en": "English",
    "fr": "Français",
    "es": "Español",
}

def _resolve_language(code: str) -> str:
    return LANGUAGE_MAP.get(code, code)
```

In allen `summarize_*`-Funktionen: `language = _resolve_language(language)` vor dem Prompt-Formatting.

## Fix 5: Umlaut

### Änderung in `src/collectors/flights.py:145`

```python
# Vorher:
lines.append(f"CO2: {abs(diff)}% weniger als ueblich")
# Nachher:
lines.append(f"CO2: {abs(diff)}% weniger als üblich")
```

## Test-Strategie

- Bestehende Tests anpassen: Language-Parameter in Mocks aktualisieren
- Neuer Test: `subscription_type` wird korrekt an Summarizer durchgereicht
- Neuer Test: `max_duration` Client-Filter in FlightSearchCollector
- Neuer Test: `_resolve_language()` Mapping

## Dateien die geändert werden

1. `config.yaml` — type-Feld + deals-Sektion entfernen
2. `src/summarizer.py` — FLIGHT_DEALS_PROMPT, PROMPT_MAP, Language-Mapping
3. `src/collectors/flights.py` — max_duration Fix + Umlaut
4. `daily_digest.py` — subscription_type durchreichen
5. `weekly_summary.py` — Language-Bug Fix (Zeile 29, 40-42), gleicher Fix wie daily_digest.py
6. `tests/` — Tests anpassen und erweitern
