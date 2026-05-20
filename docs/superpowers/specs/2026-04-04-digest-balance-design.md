# AI News Digest — Ausgewogenheit & Extended Format

GitHub Issue: #2 "AI News Pipe nicht ausgewogen"

## Ziel

Das tägliche Digest ausgewogener machen: alle Quellen sollen sichtbar sein, das Format bekommt eine Extended-Sektion, und kaputte Quellen werden repariert.

## Drei Arbeitspakete

### A) Kaputte Quellen reparieren

13 von 23 konfigurierten Quellen liefern keine Daten (Stand 2026-04-03):

| Quelle                   | Typ                 | Vermutetes Problem                        |
| ------------------------ | ------------------- | ----------------------------------------- |
| Anthropic News           | RSS (GitHub-hosted) | Feed evtl. nicht aktuell                  |
| OpenAI Blog              | RSS                 | URL veraltet/umgezogen                    |
| Google DeepMind          | RSS                 | URL veraltet/umgezogen                    |
| Google AI Blog           | RSS                 | URL veraltet/umgezogen                    |
| Microsoft AI Blog        | RSS                 | URL veraltet/umgezogen                    |
| Apple ML Research        | RSS                 | URL veraltet/umgezogen                    |
| AWS AI Blog              | RSS                 | URL veraltet/umgezogen                    |
| NVIDIA AI Blog           | RSS                 | URL veraltet/umgezogen                    |
| Ars Technica             | RSS                 | URL veraltet/umgezogen                    |
| HuggingFace Blog         | RSS                 | URL veraltet/umgezogen                    |
| HuggingFace Transformers | GitHub Releases     | API-Problem oder keine Releases in 26h    |
| ArXiv cs.AI              | ArXiv API           | Nicht debuggen — zeigt sich in Diagnostik |
| ArXiv cs.CL              | ArXiv API           | Nicht debuggen — zeigt sich in Diagnostik |

**Vorgehen:**

1. Jeden Feed einzeln abrufen und Response prüfen
2. Kaputte URLs durch funktionierende ersetzen
3. ArXiv-Collector wird NICHT debuggt — zeigt sich im Diagnostik-Footer

**`max_age_hours` bleibt global bei 26h.**

### B) Neues Digest-Format (Prompt-only-Ansatz)

Nur der `DAILY_PROMPT` in `src/summarizer.py` wird geändert. Kein zweiter Claude-Call, keine Code-Vorgruppierung.

**Neue Struktur:**

```markdown
# 📊 Morning Briefing — [Datum]

## 🎯 Top 3 des Tages

(1-2 Sätze pro Punkt, wie bisher)

## ⭐ Highlights

(Wie bisher nach Themen gruppiert, aber KÜRZER:

- Anthropic/Claude: max 4-5 Zeilen statt 15+
- Andere Themen: max 2-3 Sätze pro Thema)

---

## 📖 Extended: Alle Quellen im Detail

### Anthropic & Claude

(ALLE Details: jedes Feature, jeder Bugfix, SDK-Changes ausführlich)

### OpenAI

(Alle News von OpenAI)

### Google DeepMind / Google AI

(Zusammengefasst wenn thematisch nah)

### Microsoft AI

(...)

### [Weitere Quellen mit Daten...]

### 📄 ArXiv Papers

(cs.AI + cs.CL Papers mit Abstract-Zusammenfassungen)

### 🔥 GitHub Trending

(Trending Repos mit Beschreibung)
```

**Änderungen an `summarize_daily()`:**

- `priority` aus Config an Artikel-Daten anhängen (wird aktuell nicht mitgegeben)
- `DAILY_PROMPT` bekommt neue Formatanweisung mit zwei Teilen (kurz oben, Extended unten)
- Regel: Jede Quelle die Daten geliefert hat, muss mindestens 1x im Extended-Teil vorkommen

### C) Diagnostik im Footer

Das Jinja2-Template `templates/daily.md.j2` bekommt neue Variablen:

```markdown
---

_Quellen: X Artikel aus Y von Z konfigurierten Quellen_
_Keine Daten von: [Liste fehlender Quellen]_
_Generiert am [Timestamp]_
```

**Code-Änderungen:**

- `daily_digest.py`: Tracken welche Quellen Daten geliefert haben vs. welche konfiguriert waren
- Template: Neue Variablen `total_configured_sources`, `missing_sources`

## Nicht im Scope

- ArXiv-Collector debuggen (zeigt sich in Diagnostik)
- `max_age_hours` per-Source konfigurierbar machen
- Zweiter Claude-Call für Extended-Sektion
- Weekly-Summary-Format ändern
