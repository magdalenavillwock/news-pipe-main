# Design: Deterministische Ausgabe für Wirtschafts-News (XML + Jinja2)

**Datum:** 2026-05-21  
**Pipeline:** `wirtschafts-news` (type: finance)  
**Scope:** Nur `finance`-Typ — `ai-news` bleibt unberührt

---

## Problem

Claude generiert Finanz-Reports strukturell inkonsistent: Überschriften-Format, Abschnittstiefe und Markdown-Stil variieren von Run zu Run, obwohl der Prompt eine feste Struktur vorgibt. Ursache ist die inhärente Nicht-Determinismus des LLMs; das Claude Code CLI unterstützt kein Temperature-Flag.

## Lösung

Strukturkontrolle von Claude auf Python übertragen:

- Claude schreibt **nur Fließtext**, eingewickelt in XML-Tags (einen Tag pro Sektion)
- Python extrahiert die Sektionen per Regex
- Ein Jinja2-Template rendert das finale Markdown — vollständig deterministisch

**Vorher:** `Prompt → Claude → Markdown`  
**Nachher:** `Prompt → Claude → XML → Python-Extraktion → Jinja2 → Markdown`

---

## Komponenten

### 1. Geänderte Prompts (`src/summarizer.py`)

`FINANCE_DAILY_PROMPT` und `FINANCE_WEEKLY_PROMPT` werden so umgebaut, dass Claude ausschließlich XML-Tags ausgibt. Der gesamte inhaltliche Teil der Prompts (Quellenregeln, Sprache, Detailgrad) bleibt erhalten — nur der AUSGABE-Block ändert sich.

**Daily — XML-Tags (6):**

| Tag | Pflicht | Entspricht |
|---|---|---|
| `<OVERNIGHT>` | ja | ① Overnight & Vorbörslich |
| `<INDIZES>` | ja | ② Tagesüberblick Schlüsselindizes |
| `<TERMINE>` | ja | ③ Heutige Termine & Trigger |
| `<RISIKO>` | ja | ④ Risiko-Teil |
| `<CHANCE>` | ja | ④ Chance-Teil |
| `<WATCHLIST>` | nein | ⑤ Watchlist-Hinweis (leer wenn nicht relevant) |

**Weekly — XML-Tags (8):**

| Tag | Pflicht | Entspricht |
|---|---|---|
| `<AKTUALITAET>` | ja | ① Aktualitäts-Check |
| `<TAKEAWAY>` | ja | ② One-Minute-Takeaway |
| `<MARKT>` | ja | ③ Marktüberblick |
| `<TECHNIK>` | ja | ④ Technische Analyse |
| `<MAKRO>` | ja | ⑤ Makroökonomischer Kontext |
| `<SONDER>` | ja | ⑥ Sondersituationen |
| `<POLITIK>` | ja | ⑦ Weltpolitische Lage |
| `<FAZIT>` | ja | ⑧ Fazit & Handlungsmöglichkeiten |

Prompt-Ausgabeanweisung (ersetzt bisherigen AUSGABE-Block):

```
AUSGABE: Schreibe ausschließlich XML-Tags. Kein Text außerhalb der Tags.
Reihenfolge: <OVERNIGHT>, <INDIZES>, <TERMINE>, <RISIKO>, <CHANCE>, <WATCHLIST>
Für WATCHLIST: Tag leer lassen (<WATCHLIST></WATCHLIST>) wenn kein Hinweis relevant ist.
```

### 2. Extraktions-Funktion (`src/summarizer.py`)

```python
import re

def _extract_sections(xml: str, tags: list[str]) -> dict[str, str | None]:
    return {
        tag: m.group(1).strip()
        if (m := re.search(f'<{tag}>(.*?)</{tag}>', xml, re.DOTALL))
        else None
        for tag in tags
    }
```

Robuster als JSON-Parsing: fehlendes Escaping oder ein Sonderzeichen wirft keinen Fehler.

### 3. Retry-Logik

Wenn nach dem ersten Call Pflicht-Tags fehlen:

1. Einmaliger Retry: Prompt enthält die Liste der fehlenden Tags
2. Nach Retry: vorhandene Sektionen nutzen, fehlende als `[Keine Daten verfügbar]` markieren
3. Warning ins Log

```python
DAILY_REQUIRED = ["OVERNIGHT", "INDIZES", "TERMINE", "RISIKO", "CHANCE"]
DAILY_OPTIONAL = ["WATCHLIST"]

WEEKLY_REQUIRED = ["AKTUALITAET", "TAKEAWAY", "MARKT", "TECHNIK", "MAKRO", "SONDER", "POLITIK", "FAZIT"]
```

### 4. Jinja2-Templates (2 neue Dateien)

**`templates/wirtschafts-news-daily.md.j2`:**

```jinja
# Morning-Briefing {{ date }}

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

**`templates/wirtschafts-news-weekly.md.j2`:**

```jinja
# Wochenanalyse KW {{ week_number }} | {{ week_start }} – {{ week_end }}

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

### 5. Rendering-Helfer in `src/summarizer.py`

```python
def _render_finance_template(template_name: str, context: dict) -> str:
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    return env.get_template(template_name).render(**context)
```

---

## Datenfluss

```
summarize_daily(articles, settings, ..., subscription_type="finance")
  │
  ├─ _call_claude(FINANCE_DAILY_PROMPT)  →  raw XML string
  │
  ├─ _extract_sections(xml, DAILY_REQUIRED + DAILY_OPTIONAL)  →  dict
  │
  ├─ missing = [t for t in DAILY_REQUIRED if sections[t] is None]
  │   └─ if missing: _call_claude(retry_prompt)  →  re-extract  →  merge
  │
  └─ _render_finance_template("wirtschafts-news-daily.md.j2", sections, date)
       →  str (konsistentes Markdown)
```

---

## Fehlerbehandlung

| Szenario | Verhalten |
|---|---|
| Pflicht-Tag fehlt nach erstem Call | Einmaliger Retry |
| Pflicht-Tag fehlt nach Retry | `[Keine Daten verfügbar]`, Warning geloggt |
| Claude gibt gar kein XML aus | Alle Sektionen als `[Keine Daten verfügbar]` |
| Template-Datei fehlt | `FileNotFoundError` → Pipeline-Fehler geloggt |

---

## Dateien die sich ändern

| Datei | Art |
|---|---|
| `src/summarizer.py` | Prompts + Extraktion + Rendering-Logik |
| `templates/wirtschafts-news-daily.md.j2` | Neu |
| `templates/wirtschafts-news-weekly.md.j2` | Neu |

## Dateien die sich **nicht** ändern

`daily_digest.py`, `weekly_summary.py`, alle Workflows, `config.yaml`, `notifier.py`, `models.py`, `ai-news`-Prompts — keinerlei Änderungen.

---

## Verifikation

1. Lokaler Test: `py daily_digest.py wirtschafts-news --date 2026-05-20` gegen vorhandene `data/wirtschafts-news/2026-05-20.json`
2. Output `output/wirtschafts-news/daily/2026-05-20.md` prüfen: alle 5 Sektionen mit konsistenten `##`-Überschriften
3. Zweiter Run mit identischen Daten: Strukturvergleich — Überschriften und Reihenfolge müssen identisch sein
4. `ai-news`-Run: muss unverändert funktionieren
