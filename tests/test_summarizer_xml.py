import pytest
from unittest.mock import AsyncMock, patch
from src.summarizer import _extract_sections, _render_finance_template

SAMPLE_DAILY_XML = """
<OVERNIGHT>Nikkei +0,3%. US-Futures leicht im Plus. Keine wesentlichen Overnight-Bewegungen.</OVERNIGHT>
<INDIZES>DAX: 18.450 (+0,2%). S&P 500: 5.320 (+0,1%). Nasdaq: 16.800 (unverändert).</INDIZES>
<TERMINE>14:30 – US CPI April (Erw. 3,2%). Bullish wenn darunter, bearish wenn darüber.</TERMINE>
<RISIKO>Samsung-Streik ab Donnerstag: 48.000 Beschäftigte, globale Halbleiter-Lieferketten gefährdet.</RISIKO>
<CHANCE>EU-US-Handelsdeal entschärft Zollsorgen. DAX könnte auf 18.600 steigen.</CHANCE>
<WATCHLIST>Nvidia vor Quartalszahlen nach Börsenschluss.</WATCHLIST>
"""

SAMPLE_DAILY_XML_NO_WATCHLIST = """
<OVERNIGHT>Keine wesentlichen Overnight-Bewegungen.</OVERNIGHT>
<INDIZES>DAX: 18.200 (-0,1%).</INDIZES>
<TERMINE>Kein relevanter Termin heute.</TERMINE>
<RISIKO>Inflationsdaten morgen könnten überraschen. CPI-Konsens bei 3,0%.</RISIKO>
<CHANCE>Technologiewerte nach Google I/O im Aufwind. Nasdaq +0,5% möglich.</CHANCE>
<WATCHLIST></WATCHLIST>
"""

DAILY_REQUIRED = ["OVERNIGHT", "INDIZES", "TERMINE", "RISIKO", "CHANCE"]
DAILY_OPTIONAL = ["WATCHLIST"]


# --- _extract_sections ---

def test_extract_sections_all_present():
    sections = _extract_sections(SAMPLE_DAILY_XML, DAILY_REQUIRED + DAILY_OPTIONAL)
    assert sections["OVERNIGHT"] == "Nikkei +0,3%. US-Futures leicht im Plus. Keine wesentlichen Overnight-Bewegungen."
    assert sections["INDIZES"] == "DAX: 18.450 (+0,2%). S&P 500: 5.320 (+0,1%). Nasdaq: 16.800 (unverändert)."
    assert sections["WATCHLIST"] == "Nvidia vor Quartalszahlen nach Börsenschluss."


def test_extract_sections_missing_tag_returns_none():
    sections = _extract_sections("<OVERNIGHT>text</OVERNIGHT>", ["OVERNIGHT", "INDIZES"])
    assert sections["INDIZES"] is None


def test_extract_sections_empty_tag_returns_empty_string():
    sections = _extract_sections(SAMPLE_DAILY_XML_NO_WATCHLIST, DAILY_OPTIONAL)
    assert sections["WATCHLIST"] == ""


def test_extract_sections_multiline_content():
    xml = "<TERMINE>09:30 – CPI\n14:00 – Zinsentscheid\n16:00 – Pressekonferenz</TERMINE>"
    sections = _extract_sections(xml, ["TERMINE"])
    assert "09:30 – CPI" in sections["TERMINE"]
    assert "14:00 – Zinsentscheid" in sections["TERMINE"]


# --- _render_finance_template (daily) ---

def test_render_daily_template_all_sections():
    sections = {
        "OVERNIGHT": "Keine wesentlichen Overnight-Bewegungen.",
        "INDIZES": "DAX: 18.450.",
        "TERMINE": "14:30 – CPI.",
        "RISIKO": "Streik-Risiko.",
        "CHANCE": "Handelsdeal bullish.",
        "WATCHLIST": "Nvidia watchen.",
    }
    result = _render_finance_template(
        "wirtschafts-news-daily.md.j2",
        {"sections": sections, "date": "21.05.2026"},
    )
    assert "Morning-Briefing 21.05.2026" in result
    assert "## ① OVERNIGHT & VORBÖRSLICH" in result
    assert "## ② TAGESÜBERBLICK: SCHLÜSSELINDIZES" in result
    assert "## ③ HEUTIGE TERMINE & TRIGGER" in result
    assert "**Risiko:** Streik-Risiko." in result
    assert "**Chance:** Handelsdeal bullish." in result
    assert "## ⑤ WATCHLIST-HINWEIS" in result
    assert "Nvidia watchen." in result


def test_render_daily_template_no_watchlist():
    sections = {
        "OVERNIGHT": "Ruhige Nacht.",
        "INDIZES": "DAX stabil.",
        "TERMINE": "Kein Termin.",
        "RISIKO": "Inflationsrisiko.",
        "CHANCE": "Technologie-Bounce.",
        "WATCHLIST": "",
    }
    result = _render_finance_template(
        "wirtschafts-news-daily.md.j2",
        {"sections": sections, "date": "21.05.2026"},
    )
    assert "## ⑤ WATCHLIST-HINWEIS" not in result


def test_render_daily_template_none_watchlist():
    sections = {
        "OVERNIGHT": "Ruhige Nacht.",
        "INDIZES": "DAX stabil.",
        "TERMINE": "Kein Termin.",
        "RISIKO": "Inflationsrisiko.",
        "CHANCE": "Technologie-Bounce.",
        "WATCHLIST": None,
    }
    result = _render_finance_template(
        "wirtschafts-news-daily.md.j2",
        {"sections": sections, "date": "21.05.2026"},
    )
    assert "## ⑤ WATCHLIST-HINWEIS" not in result


def test_render_weekly_template():
    sections = {t: f"Inhalt {t}" for t in
                ["AKTUALITAET", "TAKEAWAY", "MARKT", "TECHNIK", "MAKRO", "SONDER", "POLITIK", "FAZIT"]}
    result = _render_finance_template(
        "wirtschafts-news-weekly.md.j2",
        {"sections": sections, "week_number": 21, "week_start": "19.05.2026", "week_end": "25.05.2026"},
    )
    assert "Wochenanalyse KW 21 | 19.05.2026 – 25.05.2026" in result
    assert "## ① AKTUALITÄTS-CHECK" in result
    assert "## ⑧ FAZIT & HANDLUNGSMÖGLICHKEITEN" in result
    assert "Inhalt FAZIT" in result


# --- summarize_daily (finance branch) ---

@pytest.mark.asyncio
async def test_summarize_daily_finance_returns_structured_markdown():
    """finance type extracts XML and renders via template."""
    settings = {"daily_model": "claude-sonnet-4-6"}
    articles = []

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = SAMPLE_DAILY_XML
        from src.summarizer import summarize_daily
        result = await summarize_daily(articles, settings, subscription_type="finance")

    assert "Morning-Briefing" in result
    assert "## ① OVERNIGHT & VORBÖRSLICH" in result
    assert "## ② TAGESÜBERBLICK: SCHLÜSSELINDIZES" in result
    assert "**Risiko:**" in result
    assert "**Chance:**" in result
    mock_claude.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_daily_finance_retries_on_missing_section():
    """When a required section is missing, a second call is made."""
    incomplete_xml = """
<OVERNIGHT>Ruhige Nacht.</OVERNIGHT>
<INDIZES>DAX stabil.</INDIZES>
<TERMINE>Kein Termin.</TERMINE>
<RISIKO>Streik-Risiko.</RISIKO>
"""
    retry_xml = "<CHANCE>Handelsdeal ist die Chance.</CHANCE>"

    settings = {"daily_model": "claude-sonnet-4-6"}

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.side_effect = [incomplete_xml, retry_xml]
        from src.summarizer import summarize_daily
        result = await summarize_daily([], settings, subscription_type="finance")

    assert mock_claude.call_count == 2
    assert "**Chance:** Handelsdeal ist die Chance." in result


@pytest.mark.asyncio
async def test_summarize_daily_finance_fallback_after_failed_retry():
    """After retry, still-missing sections get fallback text."""
    incomplete_xml = "<OVERNIGHT>text</OVERNIGHT><INDIZES>text</INDIZES><TERMINE>text</TERMINE><RISIKO>text</RISIKO>"

    settings = {"daily_model": "claude-sonnet-4-6"}

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.side_effect = [incomplete_xml, ""]
        from src.summarizer import summarize_daily
        result = await summarize_daily([], settings, subscription_type="finance")

    assert "[Keine Daten verfügbar]" in result


@pytest.mark.asyncio
async def test_summarize_daily_news_type_unchanged():
    """news type still returns raw Claude output without XML processing."""
    settings = {"daily_model": "claude-sonnet-4-6"}
    raw_output = "# AI News\n\nSome content here."

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = raw_output
        from src.summarizer import summarize_daily
        result = await summarize_daily([], settings, subscription_type="news")

    assert result == raw_output


# --- summarize_weekly (finance branch) ---

SAMPLE_WEEKLY_XML = """
<AKTUALITAET>Keine Ereignisse der letzten 48 Stunden überholen frühere Einschätzungen.</AKTUALITAET>
<TAKEAWAY>DAX +1,2% auf Wochenbasis. S&P 500 +0,8%. Nvidia-Zahlen überzeugen.</TAKEAWAY>
<MARKT>DAX: 18.600 (+1,2%). S&P 500: 5.340 (+0,8%). Gold: 2.380 USD (+0,5%).</MARKT>
<TECHNIK>DAX RSI: 58 (neutral). 50-Tage-MA: 18.100 (Kurs darüber). Widerstand: 18.800.</TECHNIK>
<MAKRO>EZB hält Zinsen bei 3,75%. US CPI April: 3,1% (unter Erwartung). Bullish für Anleihen.</MAKRO>
<SONDER>Nvidia Q1: Umsatz +262% YoY. Commerzbank widersteht Unicredit-Übernahme.</SONDER>
<POLITIK>EU-US-Handelsdeal unterzeichnet. Ukraine-Waffenstillstandsgespräche ohne Ergebnis.</POLITIK>
<FAZIT>Risk-on-Stimmung. Chance: Tech-Sektor. Risiko: CPI-Daten nächste Woche.</FAZIT>
"""


@pytest.mark.asyncio
async def test_summarize_weekly_finance_returns_structured_markdown():
    """finance type weekly extracts XML and renders via template."""
    settings = {"weekly_model": "claude-opus-4-6"}

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = SAMPLE_WEEKLY_XML
        from src.summarizer import summarize_weekly
        result = await summarize_weekly(["digest1", "digest2"], settings, subscription_type="finance")

    assert "Wochenanalyse KW" in result
    assert "## ① AKTUALITÄTS-CHECK" in result
    assert "## ⑧ FAZIT & HANDLUNGSMÖGLICHKEITEN" in result
    mock_claude.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_weekly_finance_retries_on_missing_section():
    """Missing required section triggers a retry call."""
    incomplete = "\n".join(
        f"<{t}>Inhalt {t}</{t}>"
        for t in ["AKTUALITAET", "TAKEAWAY", "MARKT", "TECHNIK", "MAKRO", "SONDER", "POLITIK"]
        # FAZIT missing
    )
    retry_xml = "<FAZIT>Risk-on. Watchlist: Nvidia.</FAZIT>"

    settings = {"weekly_model": "claude-opus-4-6"}

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.side_effect = [incomplete, retry_xml]
        from src.summarizer import summarize_weekly
        result = await summarize_weekly([], settings, subscription_type="finance")

    assert mock_claude.call_count == 2
    assert "Risk-on. Watchlist: Nvidia." in result


@pytest.mark.asyncio
async def test_summarize_weekly_news_type_unchanged():
    """news type returns raw Claude output."""
    settings = {"weekly_model": "claude-opus-4-6"}
    raw = "# Weekly AI News\n\nContent."

    with patch("src.summarizer._call_claude", new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = raw
        from src.summarizer import summarize_weekly
        result = await summarize_weekly(["d1"], settings, subscription_type="news")

    assert result == raw
