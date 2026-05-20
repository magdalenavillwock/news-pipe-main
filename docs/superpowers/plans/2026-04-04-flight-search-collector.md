# Flight Search Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `flight_search` collector that queries the Kiwi.com Tequila API for real flight prices on configurable routes.

**Architecture:** New `FlightSearchCollector` class inheriting `BaseCollector`, registered in `COLLECTOR_MAP`. Queries `https://api.tequila.kiwi.com/v2/search` with route/date params from config, maps JSON results to `Article` objects. API key via `KIWI_API_KEY` env var.

**Tech Stack:** Python 3.12, httpx (async HTTP), pytest + unittest.mock for tests.

---

### Task 1: Write FlightSearchCollector with Tests (TDD)

**Files:**

- Create: `src/collectors/flights.py`
- Create: `tests/test_flight_collector.py`

- [ ] **Step 1: Write the test file with all test cases**

```python
# tests/test_flight_collector.py
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

import httpx

from src.collectors.flights import FlightSearchCollector
from src.models import Article


@pytest.fixture
def flight_config():
    return {
        "name": "Test Flights",
        "type": "flight_search",
        "category": "flights",
        "fly_from": "FRA,MUC",
        "fly_to": "DPS",
        "date_from": "18/07/2026",
        "date_to": "01/08/2026",
        "return_from": "20/07/2026",
        "return_to": "01/08/2026",
        "max_fly_duration": 22,
        "flight_type": "round",
        "max_results": 5,
        "curr": "EUR",
        "priority": "high",
    }


@pytest.fixture
def settings():
    return {
        "max_articles_per_source": 10,
        "max_age_hours": 26,
        "request_timeout": 30,
        "max_retries": 3,
    }


SAMPLE_KIWI_RESPONSE = {
    "data": [
        {
            "price": 487,
            "deep_link": "https://www.kiwi.com/booking?token=abc123",
            "fly_duration": 66600,
            "return_duration": 60600,
            "airlines": ["QR"],
            "route": [
                {
                    "flyFrom": "FRA",
                    "flyTo": "DOH",
                    "local_departure": "2026-07-18T08:15:00.000Z",
                    "local_arrival": "2026-07-18T16:30:00.000Z",
                    "airline": "QR",
                    "return": 0,
                },
                {
                    "flyFrom": "DOH",
                    "flyTo": "DPS",
                    "local_departure": "2026-07-18T19:00:00.000Z",
                    "local_arrival": "2026-07-19T11:45:00.000Z",
                    "airline": "QR",
                    "return": 0,
                },
                {
                    "flyFrom": "DPS",
                    "flyTo": "DOH",
                    "local_departure": "2026-08-01T01:20:00.000Z",
                    "local_arrival": "2026-08-01T06:45:00.000Z",
                    "airline": "QR",
                    "return": 1,
                },
                {
                    "flyFrom": "DOH",
                    "flyTo": "FRA",
                    "local_departure": "2026-08-01T08:00:00.000Z",
                    "local_arrival": "2026-08-01T12:10:00.000Z",
                    "airline": "QR",
                    "return": 1,
                },
            ],
            "bags_price": {"1": 0, "2": 60},
            "availability": {"seats": 5},
        },
        {
            "price": 623,
            "deep_link": "https://www.kiwi.com/booking?token=def456",
            "fly_duration": 54000,
            "return_duration": 50400,
            "airlines": ["SQ"],
            "route": [
                {
                    "flyFrom": "MUC",
                    "flyTo": "SIN",
                    "local_departure": "2026-07-20T22:00:00.000Z",
                    "local_arrival": "2026-07-21T16:00:00.000Z",
                    "airline": "SQ",
                    "return": 0,
                },
                {
                    "flyFrom": "SIN",
                    "flyTo": "DPS",
                    "local_departure": "2026-07-21T18:30:00.000Z",
                    "local_arrival": "2026-07-21T21:15:00.000Z",
                    "airline": "SQ",
                    "return": 0,
                },
                {
                    "flyFrom": "DPS",
                    "flyTo": "SIN",
                    "local_departure": "2026-07-31T08:00:00.000Z",
                    "local_arrival": "2026-07-31T10:45:00.000Z",
                    "airline": "SQ",
                    "return": 1,
                },
                {
                    "flyFrom": "SIN",
                    "flyTo": "MUC",
                    "local_departure": "2026-07-31T13:00:00.000Z",
                    "local_arrival": "2026-07-31T19:00:00.000Z",
                    "airline": "SQ",
                    "return": 1,
                },
            ],
            "bags_price": {"1": 0, "2": 80},
            "availability": {"seats": 3},
        },
    ],
    "currency": "EUR",
}


@pytest.mark.asyncio
async def test_flight_collector_returns_articles(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json=SAMPLE_KIWI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"KIWI_API_KEY": "test-key"}):
            articles = await collector.collect(client)

    assert len(articles) == 2
    assert all(isinstance(a, Article) for a in articles)
    assert articles[0].priority == "high"
    assert articles[0].source == "Test Flights"
    assert articles[0].category == "flights"
    # Sorted by price — cheapest first
    assert "487" in articles[0].title
    assert "623" in articles[1].title


@pytest.mark.asyncio
async def test_flight_collector_title_format(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json=SAMPLE_KIWI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"KIWI_API_KEY": "test-key"}):
            articles = await collector.collect(client)

    # Title should contain: origin, destination, price, airline
    title = articles[0].title
    assert "FRA" in title
    assert "DPS" in title
    assert "487" in title
    assert "EUR" in title


@pytest.mark.asyncio
async def test_flight_collector_summary_contains_route(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json=SAMPLE_KIWI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"KIWI_API_KEY": "test-key"}):
            articles = await collector.collect(client)

    summary = articles[0].summary
    assert "DOH" in summary  # Layover city
    assert "Hin:" in summary
    assert "Rueck:" in summary


@pytest.mark.asyncio
async def test_flight_collector_url_is_deep_link(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json=SAMPLE_KIWI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"KIWI_API_KEY": "test-key"}):
            articles = await collector.collect(client)

    assert articles[0].url == "https://www.kiwi.com/booking?token=abc123"


@pytest.mark.asyncio
async def test_flight_collector_missing_api_key(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    async with httpx.AsyncClient() as client:
        with patch.dict("os.environ", {}, clear=True):
            articles = await collector.collect(client)

    assert articles == []


@pytest.mark.asyncio
async def test_flight_collector_http_error(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(500, text="Internal Server Error")
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"KIWI_API_KEY": "test-key"}):
            articles = await collector.collect(client)

    assert articles == []


@pytest.mark.asyncio
async def test_flight_collector_passes_correct_params(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json={"data": []})
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response) as mock_get, \
             patch.dict("os.environ", {"KIWI_API_KEY": "test-key"}):
            await collector.collect(client)

    call_kwargs = mock_get.call_args
    params = call_kwargs.kwargs["params"]
    assert params["fly_from"] == "FRA,MUC"
    assert params["fly_to"] == "DPS"
    assert params["date_from"] == "18/07/2026"
    assert params["max_fly_duration"] == 22
    assert params["flight_type"] == "round"
    assert params["curr"] == "EUR"
    headers = call_kwargs.kwargs["headers"]
    assert headers["apikey"] == "test-key"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_flight_collector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.collectors.flights'`

- [ ] **Step 3: Write the FlightSearchCollector implementation**

```python
# src/collectors/flights.py
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx

from src.collectors.base import BaseCollector
from src.models import Article

logger = logging.getLogger(__name__)

KIWI_API_URL = "https://api.tequila.kiwi.com/v2/search"


class FlightSearchCollector(BaseCollector):
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        api_key = os.environ.get("KIWI_API_KEY")
        if not api_key:
            logger.warning(f"[{self.name}] KIWI_API_KEY not set, skipping flight search")
            return []

        params = {
            "fly_from": self.config.get("fly_from", ""),
            "fly_to": self.config.get("fly_to", ""),
            "date_from": self.config.get("date_from", ""),
            "date_to": self.config.get("date_to", ""),
            "return_from": self.config.get("return_from", ""),
            "return_to": self.config.get("return_to", ""),
            "flight_type": self.config.get("flight_type", "round"),
            "max_fly_duration": self.config.get("max_fly_duration", 24),
            "curr": self.config.get("curr", "EUR"),
            "limit": self.config.get("max_results", 10),
            "sort": "price",
            "asc": 1,
        }
        # Remove empty string params
        params = {k: v for k, v in params.items() if v != ""}

        try:
            response = await client.get(
                KIWI_API_URL,
                params=params,
                headers={"apikey": api_key},
            )
            if response.status_code >= 400:
                logger.error(f"[{self.name}] Kiwi API returned HTTP {response.status_code}: {response.text[:200]}")
                return []
        except httpx.HTTPError as e:
            logger.error(f"[{self.name}] Kiwi API request failed: {e}")
            return []

        data = response.json().get("data", [])
        currency = response.json().get("currency", "EUR")

        articles = []
        for flight in data:
            articles.append(self._flight_to_article(flight, currency))

        return articles

    def _flight_to_article(self, flight: dict, currency: str) -> Article:
        route = flight.get("route", [])
        outbound = [s for s in route if s.get("return") == 0]
        inbound = [s for s in route if s.get("return") == 1]

        origin = outbound[0]["flyFrom"] if outbound else "?"
        destination = outbound[-1]["flyTo"] if outbound else "?"
        price = flight["price"]
        airlines = ", ".join(sorted(set(flight.get("airlines", []))))
        fly_h = flight.get("fly_duration", 0) // 3600
        fly_m = (flight.get("fly_duration", 0) % 3600) // 60

        title = f"{origin} -> {destination} | {price} {currency} | {airlines} | {fly_h}h {fly_m}m"

        summary = self._format_route_summary(outbound, inbound, flight)

        return Article(
            title=title,
            url=flight.get("deep_link", ""),
            source=self.name,
            category=self.category,
            published=datetime.now(timezone.utc),
            summary=summary,
            content=None,
            priority=self.priority,
        )

    def _format_route_summary(self, outbound: list, inbound: list, flight: dict) -> str:
        lines = []

        if outbound:
            stops = len(outbound) - 1
            stop_label = f"{stops} Stopp" if stops == 1 else f"{stops} Stopps"
            if stops == 0:
                stop_label = "Direktflug"
            segments = " -> ".join(
                f"{s['flyFrom']} {s['local_departure'][11:16]}" for s in outbound
            )
            segments += f" -> {outbound[-1]['flyTo']} {outbound[-1]['local_arrival'][11:16]}"
            fly_h = flight.get("fly_duration", 0) // 3600
            fly_m = (flight.get("fly_duration", 0) % 3600) // 60
            lines.append(f"Hin: {segments} ({stop_label}, {fly_h}h {fly_m}m)")

        if inbound:
            stops = len(inbound) - 1
            stop_label = f"{stops} Stopp" if stops == 1 else f"{stops} Stopps"
            if stops == 0:
                stop_label = "Direktflug"
            segments = " -> ".join(
                f"{s['flyFrom']} {s['local_departure'][11:16]}" for s in inbound
            )
            segments += f" -> {inbound[-1]['flyTo']} {inbound[-1]['local_arrival'][11:16]}"
            ret_h = flight.get("return_duration", 0) // 3600
            ret_m = (flight.get("return_duration", 0) % 3600) // 60
            lines.append(f"Rueck: {segments} ({stop_label}, {ret_h}h {ret_m}m)")

        bags = flight.get("bags_price", {})
        if bags.get("1") == 0:
            lines.append("Gepaeck: Aufgabegepaeck inklusive")
        elif bags.get("1"):
            lines.append(f"Gepaeck: Aufgabegepaeck +{bags['1']} EUR")
        else:
            lines.append("Gepaeck: Nur Handgepaeck")

        airlines = ", ".join(sorted(set(flight.get("airlines", []))))
        if airlines:
            lines.append(f"Airline: {airlines}")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_flight_collector.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/collectors/flights.py tests/test_flight_collector.py
git commit -m "feat: add FlightSearchCollector with Kiwi.com API integration"
```

---

### Task 2: Register Collector and Update Config

**Files:**

- Modify: `src/collectors/__init__.py`
- Modify: `config.yaml` (bali-flights sources section)
- Modify: `.github/workflows/run-subscription.yml` (add KIWI_API_KEY env)

- [ ] **Step 1: Register FlightSearchCollector in COLLECTOR_MAP**

In `src/collectors/__init__.py`, add the import and map entry:

```python
from src.collectors.base import BaseCollector
from src.collectors.rss import RSSCollector
from src.collectors.github import GitHubCollector
from src.collectors.arxiv import ArxivCollector
from src.collectors.flights import FlightSearchCollector

COLLECTOR_MAP: dict[str, type[BaseCollector]] = {
    "rss": RSSCollector,
    "github_releases": GitHubCollector,
    "github_trending": GitHubCollector,
    "arxiv": ArxivCollector,
    "flight_search": FlightSearchCollector,
}
```

- [ ] **Step 2: Update bali-flights config in config.yaml**

Replace the bali-flights `sources:` block with:

```yaml
sources:
  flights:
    - name: Bali Fluege
      type: flight_search
      fly_from: FRA,MUC,BER,DUS,HAM,STR
      fly_to: DPS
      date_from: "18/07/2026"
      date_to: "01/08/2026"
      return_from: "20/07/2026"
      return_to: "01/08/2026"
      max_fly_duration: 22
      flight_type: round
      max_results: 10
      curr: EUR
      priority: high
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

- [ ] **Step 3: Add KIWI_API_KEY to workflow env**

In `.github/workflows/run-subscription.yml`, add `KIWI_API_KEY` to the env block of the digest step:

```yaml
- run: python daily_digest.py ${{ inputs.subscription }}
  env:
    CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    KIWI_API_KEY: ${{ secrets.KIWI_API_KEY }}
```

- [ ] **Step 4: Run all tests to verify nothing is broken**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 5: Commit**

```bash
git add src/collectors/__init__.py config.yaml .github/workflows/run-subscription.yml
git commit -m "feat: register flight_search collector and update bali-flights config"
```

---

### Task 3: Set GitHub Secret and Test Run

- [ ] **Step 1: Prompt user to create Kiwi.com API key**

The user needs to:

1. Go to https://tequila.kiwi.com/ and create a free account
2. Create a solution and get the API key
3. Set it as GitHub secret: `gh secret set KIWI_API_KEY`

- [ ] **Step 2: Push to remote**

```bash
git push origin main
```

- [ ] **Step 3: Trigger test run**

```bash
gh workflow run "Bali Flug-Deals" --ref main
```

- [ ] **Step 4: Watch run and verify success**

```bash
gh run list --workflow="Bali Flug-Deals" --limit 1 --json databaseId --jq '.[0].databaseId' | xargs gh run watch --exit-status
```

Expected: All steps green. If it fails, check logs with `gh run view <id> --log-failed`.

- [ ] **Step 5: Verify digest output contains flight data**

```bash
git pull origin main
cat output/bali-flights/daily/$(date +%Y-%m-%d).md
```

Expected: Digest contains flight listings with prices, airlines, and booking links.
