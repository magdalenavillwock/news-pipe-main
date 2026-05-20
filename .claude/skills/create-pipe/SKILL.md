---
name: create-pipe
description: This skill should be used when the user asks to "create a pipe", "neue pipe erstellen", "neues abo anlegen", "add subscription", "create subscription", "find sources", "recherchiere quellen", "finde feeds", or wants to set up a new notification pipeline with custom sources, schedule and push notifications.
---

# Create Pipe

Create a new News Pipe subscription — research sources, validate them, configure everything, and set up the GitHub Actions workflow. Fully automated.

## Overview

A "Pipe" is a subscription in the News Pipe system. Each pipe has:

- **Sources** (RSS feeds, GitHub releases, ArXiv categories)
- **Schedule** (Cron-based via GitHub Actions)
- **Ntfy Topic** (push notifications to phone)
- **Prompt Focus** (instructions for Claude's summarization)

## Workflow

### Step 1: Understand What the User Wants

Use AskUserQuestion to collect:

1. **Thema / Use Case** — z.B. "AI News", "Flug-Deals ab Frankfurt", "Crypto", "Security Alerts"
2. **Pipe-ID** — lowercase with hyphens (e.g. `flight-deals`, `tech-security`)
3. **Display Name** (e.g. "Guenstige Fluege")
4. **Language** — `de` or `en`
5. **Schedule** — when and how often (e.g. "daily at 8:00", "twice daily at 8 and 18")
6. **Prompt Focus** — what to emphasize (e.g. "Only deals under 100 EUR, sorted by price")

### Step 2: Research and Validate Sources

Use WebSearch to find sources for the topic.

**Search strategies:**

- RSS: `"{topic}" RSS feed`, `"{topic}" atom feed`, `site:reddit.com/r/ "{topic}"`
- Common RSS patterns: `/feed/`, `/rss/`, `/rss.xml`, `/atom.xml`, `/feed.xml`
- GitHub: actively maintained repos with regular releases
- ArXiv: categories like `cs.AI`, `cs.CL`, `cs.CV`, `cs.LG`, `cs.CR`

**Creative sources for special use cases:**

| Use Case          | Source Ideas                                                    |
| ----------------- | --------------------------------------------------------------- |
| Flight Deals      | Secret Flying RSS, Urlaubspiraten RSS, The Points Guy, Fly4Free |
| Price Alerts      | Deal sites RSS, Reddit r/deals (.rss), Mydealz RSS              |
| Person Monitoring | Personal blog RSS, GitHub profile, ArXiv author feed            |
| Social Media      | RSS bridges (Nitter for X/Twitter), Mastodon feeds (.rss)       |
| Sports            | ESPN RSS, Kicker RSS, Transfermarkt News                        |
| Crypto            | CoinDesk RSS, The Block RSS, CryptoSlate RSS                    |
| Security          | CISA Alerts XML, NVD feeds, Hacker News RSS                     |
| Science           | Nature RSS, Science Daily RSS, Phys.org RSS                     |

**Validate each source:**

1. Reachable? `curl -sI {url}` — check for HTTP 200
2. Valid feed? `curl -s {url} | head -30` — check for RSS/Atom XML
3. Fresh? Check dates in feed entries — skip feeds with no posts in 30+ days

Present findings as table with Status, Last Post, Priority recommendation.

### Step 3: Add to config.yaml

Supported source types:

| Type              | Required Fields                             | Example              |
| ----------------- | ------------------------------------------- | -------------------- |
| `rss`             | name, url, priority                         | RSS/Atom feed        |
| `github_releases` | name, repo, priority                        | GitHub repo releases |
| `github_trending` | name, query, min_stars, priority            | Trending repos       |
| `arxiv`           | name, arxiv_category, max_results, priority | Academic papers      |

Insert new block under `subscriptions:` in `config.yaml`:

```yaml
{ pipe-id }:
  name: "{name}"
  description: "{description}"
  language: { language }
  ntfy:
    enabled: true
    server: https://ntfy.sh
    topic: news-pipe-{pipe-id}
  prompt_focus: |
    {prompt_focus}
  sources:
    { category }:
      - name: { source-name }
        type: { type }
        url: { url }
        priority: { priority }
```

### Step 4: Create Workflow Files

**Daily workflow:** `.github/workflows/{pipe-id}.yml`

```yaml
name: "{name}"
on:
  schedule:
    - cron: "{cron-expression}"
  workflow_dispatch:
permissions:
  contents: write
jobs:
  run:
    uses: ./.github/workflows/run-subscription.yml
    with:
      subscription: { pipe-id }
    secrets: inherit
```

Convert user times to UTC cron (Berlin = UTC+2 summer, UTC+1 winter).
For multiple daily runs, add multiple cron lines under `schedule:`.

**Weekly workflow (optional):** `.github/workflows/{pipe-id}-weekly.yml`

```yaml
name: "{name} - Wochenrueckblick"
on:
  schedule:
    - cron: "{weekly-cron}"
  workflow_dispatch:
permissions:
  contents: write
jobs:
  run:
    uses: ./.github/workflows/run-weekly.yml
    with:
      subscription: { pipe-id }
    secrets: inherit
```

### Step 5: Commit, Push and Test Run

Commit with: `feat: add {pipe-id} subscription`

Push to remote, then trigger a test run via GitHub Actions:

```bash
gh workflow run "{name}" --ref main
```

Watch the run until completion:

```bash
gh run list --workflow="{name}" --limit 1 --json databaseId --jq '.[0].databaseId' | xargs gh run watch --exit-status
```

If the run fails, check logs with `gh run view <id> --log-failed` and fix the issue before reporting success.

Report to user:

- Ntfy topic to subscribe: `news-pipe-{pipe-id}`
- Manual trigger: `gh workflow run "{name}"`
- Test run result (pass/fail)

## Known Pitfalls

- **Workflow permissions**: Caller workflows MUST include `permissions: contents: write`. Without it, the commit/push step fails with HTTP 403. Reusable workflows (`workflow_call`) inherit permissions from the caller, NOT from their own top-level block.
- **ASCII-only in HTTP headers**: The ntfy Title header is encoded as ASCII. Never use Unicode characters (em-dash `—`, umlauts, etc.) in workflow names or ntfy display names that end up in HTTP headers. Use ASCII alternatives (`-` instead of `—`, `ae/oe/ue` instead of umlauts).
- **Anthropic RSS feeds**: Several Anthropic RSS URLs return 404 (engineering, research, news subpaths). Always validate feeds before adding.

## Reference

### Output Structure

Each pipe stores its digests in a separate directory:

```
output/{pipe-id}/daily/YYYY-MM-DD.md    # daily digests
output/{pipe-id}/weekly/YYYY-MM-DD.md   # weekly summaries
data/{pipe-id}/YYYY-MM-DD.json          # raw article data
```

Files older than 90 days are automatically cleaned up by the workflow.

### Reusable Workflows

- `run-subscription.yml` — daily digest pipeline (collect, summarize, notify, commit)
- `run-weekly.yml` — weekly summary pipeline

### Entry Points

- `daily_digest.py {pipe-id}` — run single subscription
- `weekly_summary.py {pipe-id}` — run single subscription weekly
- Without argument: runs all subscriptions
