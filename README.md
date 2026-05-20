# News Push

Automatisierte News-Digests mit teilbaren Abos. Sammelt News aus RSS, GitHub und ArXiv, fasst sie mit Claude zusammen und pusht sie per Ntfy.sh auf dein Handy.

## Features

- **Multi-Abo:** Beliebig viele Abos mit eigenen Quellen und Ntfy-Topics
- **Teilbar:** Andere subscriben einfach deinen Ntfy-Topic — fertig
- **Täglicher Digest:** News gesammelt und zusammengefasst von Claude Sonnet
- **Wochenrückblick:** Trend-Analyse und Top-10 von Claude Opus
- **Push Notifications:** Vollständiger Digest mit Markdown direkt auf dein Handy
- **GitHub Actions:** Voll automatisiert, kein Server nötig
- **Custom Prompt-Focus:** Jedes Abo kann eigene Schwerpunkte setzen

## Abo subscriben

Jedes Abo hat einen eigenen Ntfy-Topic. So abonnierst du:

1. Installiere die [Ntfy App](https://ntfy.sh) (iOS/Android/Web)
2. Subscribiere den Topic, z.B. `news-push-ai`
3. Fertig — du bekommst automatisch Push-Notifications

### Verfügbare Abos

| Abo          | Topic          | Beschreibung                                  |
| ------------ | -------------- | --------------------------------------------- |
| AI & ML News | `news-push-ai` | Tägliche AI/ML News mit Fokus auf Claude Code |

## Setup (eigene Instanz)

### 1. Fork & Clone

```bash
git clone https://github.com/ahlerjam/news-pipe.git
cd news-pipe
```

### 2. GitHub Secrets

```bash
claude setup-token
```

Go to Settings → Secrets → Actions, add:

| Secret                    | Value                                 |
| ------------------------- | ------------------------------------- |
| `CLAUDE_CODE_OAUTH_TOKEN` | OAuth token from `claude setup-token` |

### 3. Eigenes Abo hinzufügen

Füge in `config.yaml` unter `subscriptions` ein neues Abo hinzu:

```yaml
subscriptions:
  mein-abo:
    name: "Mein News Abo"
    description: "Beschreibung"
    language: de
    ntfy:
      enabled: true
      server: https://ntfy.sh
      topic: news-push-mein-abo # <-- Diesen Topic teilen
    prompt_focus: |
      Optionaler Fokus für die Zusammenfassung.
    sources:
      kategorie:
        - name: Quelle
          type: rss
          url: https://example.com/feed.xml
          priority: high
```

### 4. Einzelnes Abo ausführen

```bash
python daily_digest.py mein-abo      # nur ein Abo
python daily_digest.py               # alle Abos
```

### 5. iOS Shortcut

```
URL: https://api.github.com/repos/ahlerjam/news-pipe/actions/workflows/daily-digest.yml/dispatches
Method: POST
Headers: Authorization: Bearer YOUR_GITHUB_PAT
Body: {"ref": "main"}
```

## Architektur

```
config.yaml (Subscriptions)
    ↓
┌─────────────────────────┐
│ Subscription: ai-news   │  ← Abo 1
│   RSS / GitHub / ArXiv  │
│   → Claude Summarize    │
│   → output/ai-news/     │
│   → ntfy.sh/news-push-ai│
└─────────────────────────┘
┌─────────────────────────┐
│ Subscription: security  │  ← Abo 2
│   RSS / CVE Feeds       │
│   → Claude Summarize    │
│   → output/security/    │
│   → ntfy.sh/news-push-security│
└─────────────────────────┘
```

## Kosten

Nutzt dein Claude Pro/Max Abo — keine zusätzlichen API-Kosten.
