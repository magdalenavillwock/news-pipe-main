# src/collectors/flights.py
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import httpx

from src.collectors.base import BaseCollector
from src.models import Article

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"


class FlightSearchCollector(BaseCollector):
    async def collect(self, client: httpx.AsyncClient) -> list[Article]:
        api_key = os.environ.get("SERPAPI_KEY")
        if not api_key:
            logger.warning(f"[{self.name}] SERPAPI_KEY not set, skipping flight search")
            return []

        params = {
            "engine": "google_flights",
            "departure_id": self.config.get("origin", ""),
            "arrival_id": self.config.get("destination", ""),
            "outbound_date": self.config.get("departure_date", ""),
            "type": 1,  # Round trip
            "currency": self.config.get("curr", "EUR"),
            "adults": self.config.get("adults", 1),
            "gl": self.config.get("gl", "de"),
            "hl": self.config.get("hl", "de"),
            "api_key": api_key,
        }
        return_date = self.config.get("return_date", "")
        if return_date:
            params["return_date"] = return_date

        max_duration = self.config.get("max_duration")
        if max_duration:
            params["max_duration"] = max_duration * 60  # API expects minutes

        max_price = self.config.get("max_price")
        if max_price:
            params["max_price"] = max_price

        try:
            response = await client.get(SERPAPI_URL, params=params)
            if response.status_code >= 400:
                logger.error(f"[{self.name}] SerpApi returned HTTP {response.status_code}: {response.text[:200]}")
                return []
        except httpx.HTTPError as e:
            logger.error(f"[{self.name}] SerpApi request failed: {e}")
            return []

        data = response.json()
        best = data.get("best_flights", [])
        other = data.get("other_flights", [])
        all_flights = best + other

        max_results = self.config.get("max_results", 10)
        if max_duration:
            max_minutes = max_duration * 60
            all_flights = [f for f in all_flights if f.get("total_duration", 0) <= max_minutes]
        all_flights = all_flights[:max_results]

        return [self._flight_to_article(f) for f in all_flights]

    def _flight_to_article(self, flight: dict) -> Article:
        segments = flight.get("flights", [])
        price = flight.get("price", 0)
        total_duration = flight.get("total_duration", 0)
        currency = self.config.get("curr", "EUR")

        origin = segments[0]["departure_airport"]["id"] if segments else "?"
        destination = segments[-1]["arrival_airport"]["id"] if segments else "?"

        carriers = set()
        for seg in segments:
            carriers.add(seg.get("airline", ""))
        airlines = ", ".join(sorted(carriers - {""}))

        dur_h = total_duration // 60
        dur_m = total_duration % 60

        title = f"{origin} -> {destination} | {price} {currency} | {airlines} | {dur_h}h {dur_m}m"

        summary = self._format_summary(flight)

        return Article(
            title=title,
            url=f"https://www.google.com/travel/flights?q={origin}+to+{destination}",
            source=self.name,
            category=self.category,
            published=datetime.now(timezone.utc),
            summary=summary,
            content=None,
            priority=self.priority,
        )

    def _format_summary(self, flight: dict) -> str:
        lines = []
        segments = flight.get("flights", [])
        layovers = flight.get("layovers", [])

        # Route segments
        parts = []
        for seg in segments:
            dep = seg["departure_airport"]
            dep_time = dep.get("time", "?")[11:16] if len(dep.get("time", "")) > 11 else dep.get("time", "?")
            parts.append(f"{dep['id']} {dep_time}")

        if segments:
            last_arr = segments[-1]["arrival_airport"]
            arr_time = last_arr.get("time", "?")[11:16] if len(last_arr.get("time", "")) > 11 else last_arr.get("time", "?")
            parts.append(f"{last_arr['id']} {arr_time}")

        stops = len(segments) - 1
        stop_label = f"{stops} Stopp" if stops == 1 else f"{stops} Stopps"
        if stops == 0:
            stop_label = "Direktflug"

        total_dur = flight.get("total_duration", 0)
        lines.append(f"Route: {' -> '.join(parts)} ({stop_label}, {total_dur // 60}h {total_dur % 60}m)")

        # Layover details
        for lay in layovers:
            lay_dur = lay.get("duration", 0)
            lines.append(f"Umstieg: {lay.get('name', '?')} ({lay_dur // 60}h {lay_dur % 60}m)")

        # Airlines
        carriers = set()
        for seg in segments:
            airline = seg.get("airline", "")
            flight_no = seg.get("flight_number", "")
            if airline:
                carriers.add(f"{airline} {flight_no}".strip())
        if carriers:
            lines.append(f"Airline: {', '.join(sorted(carriers))}")

        # Carbon emissions
        emissions = flight.get("carbon_emissions", {})
        if emissions.get("difference_percent"):
            diff = emissions["difference_percent"]
            if diff < 0:
                lines.append(f"CO2: {abs(diff)}% weniger als üblich")

        return "\n".join(lines)
