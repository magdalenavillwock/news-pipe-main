# Flight Search Collector — Design Spec

**Date:** 2026-04-04
**Status:** Approved

## Problem

The bali-flights pipe monitors RSS deal sites (Urlaubspiraten, Travel-Dealz, etc.) for flight deals. These sites rarely post Bali-specific flight offers, resulting in mostly empty digests. Users need actual flight price data for specific routes and date ranges.

## Solution

A new `flight_search` collector type that queries the Kiwi.com Tequila API for real flight prices. Integrates into the existing collector architecture — same base class, same Article output, same config pattern.

## Architecture

### New File: `src/collectors/flights.py`

`FlightSearchCollector(BaseCollector)` with a single `collect()` method that:

1. Reads route/date parameters from source config
2. Sends GET request to `https://api.tequila.kiwi.com/v2/search`
3. Maps each flight result to an `Article` object
4. Returns sorted by price (cheapest first)

### Registration

Add `"flight_search": FlightSearchCollector` to `COLLECTOR_MAP` in `src/collectors/__init__.py`.

### API Authentication

- Environment variable: `KIWI_API_KEY`
- Sent as `apikey` HTTP header
- Added as GitHub Actions secret

## Config Schema

```yaml
- name: Bali Fluege
  type: flight_search
  fly_from: FRA,MUC,BER,DUS,HAM,STR # IATA codes, comma-separated
  fly_to: DPS # IATA destination
  date_from: "18/07/2026" # Earliest departure (DD/MM/YYYY)
  date_to: "01/08/2026" # Latest departure
  return_from: "20/07/2026" # Earliest return
  return_to: "01/08/2026" # Latest return
  max_fly_duration: 22 # Max hours per leg (incl. layovers)
  flight_type: round # round or oneway
  max_results: 10 # Limit results
  curr: EUR # Currency
  priority: high
```

All fields except `name` and `type` have sensible defaults (no dates = next 30 days, max_results = 10, curr = EUR, flight_type = round).

## API Response Mapping

Each element in `response["data"]` becomes an `Article`:

| Article field | Source                                                                                    |
| ------------- | ----------------------------------------------------------------------------------------- | -------------- | ---------- | ------------ |
| `title`       | `"{fly_from} -> {fly_to}                                                                  | {price} {curr} | {airlines} | {duration}"` |
| `url`         | `data[i]["deep_link"]` (Kiwi.com booking link)                                            |
| `source`      | Collector name from config                                                                |
| `summary`     | Formatted details: layover cities, departure/arrival times, baggage info, number of stops |
| `published`   | Current UTC timestamp (flight prices have no publication date)                            |
| `priority`    | From config                                                                               |
| `content`     | None                                                                                      |

### Summary Format

```
Hin: FRA 08:15 -> DOH 16:30 -> DPS 23:45 (1 Stopp, 18h 30m)
Rueck: DPS 01:20 -> DOH 06:45 -> FRA 12:10 (1 Stopp, 16h 50m)
Gepaeck: 23kg Aufgabegepaeck inklusive
Airline: Qatar Airways
```

## Error Handling

Following existing collector patterns:

- **No API key:** Log warning, return empty list (no crash)
- **HTTP error (4xx/5xx):** Log error, return empty list
- **No results:** Return empty list (summarizer handles "nothing found")
- **Timeout:** Respects global `request_timeout` setting

## Testing

`tests/test_flight_collector.py`:

1. **Happy path:** Mock API response, verify Article creation with correct fields
2. **Missing API key:** Verify warning logged, empty list returned
3. **API error:** Mock 500 response, verify graceful handling
4. **Parameter mapping:** Verify config fields map correctly to API query params

## Updated bali-flights Config

Replace or supplement existing RSS sources with:

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

The flight_search source becomes high priority; RSS deal sources drop to low priority as supplementary.

## GitHub Actions Changes

Add `KIWI_API_KEY` as a repository secret and pass it to the workflow environment. No workflow file changes needed — the reusable workflow already passes `secrets: inherit`.
