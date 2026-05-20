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
        "origin": "FRA",
        "destination": "DPS",
        "departure_date": "2026-07-18",
        "return_date": "2026-08-01",
        "adults": 1,
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


SAMPLE_SERPAPI_RESPONSE = {
    "best_flights": [
        {
            "flights": [
                {
                    "departure_airport": {"name": "Frankfurt Airport", "id": "FRA", "time": "2026-07-18 08:15"},
                    "arrival_airport": {"name": "Hamad International", "id": "DOH", "time": "2026-07-18 16:30"},
                    "duration": 375,
                    "airline": "Qatar Airways",
                    "flight_number": "QR 68",
                    "travel_class": "Economy",
                    "legroom": "31 in",
                },
                {
                    "departure_airport": {"name": "Hamad International", "id": "DOH", "time": "2026-07-18 19:00"},
                    "arrival_airport": {"name": "Ngurah Rai", "id": "DPS", "time": "2026-07-19 11:45"},
                    "duration": 525,
                    "airline": "Qatar Airways",
                    "flight_number": "QR 962",
                    "travel_class": "Economy",
                    "legroom": "31 in",
                },
            ],
            "layovers": [
                {"duration": 150, "name": "Hamad International Airport", "id": "DOH", "overnight": False},
            ],
            "total_duration": 1110,
            "carbon_emissions": {
                "this_flight": 450000,
                "typical_for_this_route": 500000,
                "difference_percent": -10,
            },
            "price": 487,
            "type": "Round trip",
        },
    ],
    "other_flights": [
        {
            "flights": [
                {
                    "departure_airport": {"name": "Frankfurt Airport", "id": "FRA", "time": "2026-07-18 22:00"},
                    "arrival_airport": {"name": "Singapore Changi", "id": "SIN", "time": "2026-07-19 16:00"},
                    "duration": 720,
                    "airline": "Singapore Airlines",
                    "flight_number": "SQ 25",
                    "travel_class": "Economy",
                },
                {
                    "departure_airport": {"name": "Singapore Changi", "id": "SIN", "time": "2026-07-19 18:30"},
                    "arrival_airport": {"name": "Ngurah Rai", "id": "DPS", "time": "2026-07-19 21:15"},
                    "duration": 165,
                    "airline": "Singapore Airlines",
                    "flight_number": "SQ 946",
                    "travel_class": "Economy",
                },
            ],
            "layovers": [
                {"duration": 150, "name": "Singapore Changi Airport", "id": "SIN", "overnight": False},
            ],
            "total_duration": 1035,
            "carbon_emissions": {
                "this_flight": 480000,
                "typical_for_this_route": 500000,
                "difference_percent": -4,
            },
            "price": 623,
            "type": "Round trip",
        },
    ],
}


@pytest.mark.asyncio
async def test_flight_collector_returns_articles(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json=SAMPLE_SERPAPI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            articles = await collector.collect(client)

    assert len(articles) == 2
    assert all(isinstance(a, Article) for a in articles)
    assert articles[0].priority == "high"
    assert articles[0].source == "Test Flights"
    assert articles[0].category == "flights"


@pytest.mark.asyncio
async def test_flight_collector_title_format(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json=SAMPLE_SERPAPI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            articles = await collector.collect(client)

    title = articles[0].title
    assert "FRA" in title
    assert "DPS" in title
    assert "487" in title
    assert "EUR" in title
    assert "Qatar Airways" in title


@pytest.mark.asyncio
async def test_flight_collector_summary_contains_route(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json=SAMPLE_SERPAPI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            articles = await collector.collect(client)

    summary = articles[0].summary
    assert "DOH" in summary
    assert "Route:" in summary
    assert "Umstieg:" in summary
    assert "1 Stopp" in summary


@pytest.mark.asyncio
async def test_flight_collector_co2_info(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json=SAMPLE_SERPAPI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            articles = await collector.collect(client)

    summary = articles[0].summary
    assert "10% weniger als üblich" in summary


@pytest.mark.asyncio
async def test_flight_collector_best_flights_first(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json=SAMPLE_SERPAPI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            articles = await collector.collect(client)

    # best_flights (487) should come before other_flights (623)
    assert "487" in articles[0].title
    assert "623" in articles[1].title


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
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            articles = await collector.collect(client)

    assert articles == []


@pytest.mark.asyncio
async def test_flight_collector_passes_correct_params(flight_config, settings):
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json={"best_flights": [], "other_flights": []})
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response) as mock_get, \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            await collector.collect(client)

    call_kwargs = mock_get.call_args
    params = call_kwargs.kwargs["params"]
    assert params["engine"] == "google_flights"
    assert params["departure_id"] == "FRA"
    assert params["arrival_id"] == "DPS"
    assert params["outbound_date"] == "2026-07-18"
    assert params["return_date"] == "2026-08-01"
    assert params["currency"] == "EUR"
    assert params["api_key"] == "test-key"


@pytest.mark.asyncio
async def test_flight_collector_respects_max_results(flight_config, settings):
    flight_config["max_results"] = 1
    collector = FlightSearchCollector(flight_config, settings)

    response = httpx.Response(200, json=SAMPLE_SERPAPI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            articles = await collector.collect(client)

    assert len(articles) == 1


@pytest.mark.asyncio
async def test_flight_collector_filters_by_max_duration(flight_config, settings):
    """Flights exceeding max_duration should be filtered out client-side."""
    flight_config["max_duration"] = 18  # 18 hours = 1080 minutes

    # SAMPLE_SERPAPI_RESPONSE has flights with total_duration 1110 and 1035
    # 1110 min = 18.5h → should be filtered OUT (exceeds 18h)
    # 1035 min = 17.25h → should pass
    response = httpx.Response(200, json=SAMPLE_SERPAPI_RESPONSE)
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response), \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            articles = await FlightSearchCollector(flight_config, settings).collect(client)

    assert len(articles) == 1
    assert "623" in articles[0].title  # only the 1035-min flight survives


@pytest.mark.asyncio
async def test_flight_collector_sends_max_duration_in_minutes(flight_config, settings):
    """max_duration config is in hours, SerpApi expects minutes."""
    flight_config["max_duration"] = 22

    response = httpx.Response(200, json={"best_flights": [], "other_flights": []})
    async with httpx.AsyncClient() as client:
        with patch.object(client, "get", return_value=response) as mock_get, \
             patch.dict("os.environ", {"SERPAPI_KEY": "test-key"}):
            await FlightSearchCollector(flight_config, settings).collect(client)

    params = mock_get.call_args.kwargs["params"]
    assert params["max_duration"] == 1320  # 22 * 60
