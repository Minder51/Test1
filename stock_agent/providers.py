from __future__ import annotations

import time
import math
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import requests
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
HTTP_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json,text/html"}

YAHOO_HOSTS = [
    "https://query1.finance.yahoo.com",
    "https://query2.finance.yahoo.com",
]


@dataclass
class TickerSnapshot:
    ticker: str
    short_name: Optional[str]
    sector: Optional[str]
    market_cap: Optional[float]
    pe_trailing: Optional[float]
    pe_forward: Optional[float]
    dividend_yield: Optional[float]
    price: Optional[float]
    returns_6m: Optional[float]
    volatility_1y: Optional[float]
    gross_margin: Optional[float]
    revenue_cagr_3y: Optional[float]


class Universe:
    @staticmethod
    def _parse_symbols_from_wiki(url: str, symbol_header_names: List[str]) -> List[str]:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.find_all("table")
        symbols: List[str] = []
        for table in tables:
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            if not headers:
                continue
            match = None
            for name in symbol_header_names:
                for h in headers:
                    if h.lower() == name.lower():
                        match = h
                        break
                if match:
                    break
            if not match:
                continue
            # Extract rows
            for tr in table.find_all("tr"):
                tds = [td.get_text(strip=True) for td in tr.find_all("td")]
                if not tds or len(tds) < 1:
                    continue
                # find column index
                try:
                    col_idx = next(i for i, h in enumerate(headers) if h.lower() == match.lower())
                except StopIteration:
                    continue
                if col_idx >= len(tds):
                    continue
                sym = tds[col_idx]
                if not sym:
                    continue
                sym = sym.replace(".", "-")
                symbols.append(sym)
            if symbols:
                break
        if not symbols:
            raise RuntimeError(f"Could not parse symbols from {url}")
        return symbols

    @staticmethod
    def sp500() -> List[str]:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        return Universe._parse_symbols_from_wiki(url, ["Symbol"])  # type: ignore

    @staticmethod
    def nasdaq100() -> List[str]:
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        return Universe._parse_symbols_from_wiki(url, ["Ticker", "Symbol"])  # type: ignore

    @staticmethod
    def dow30() -> List[str]:
        url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
        # The constituents table often has Symbol
        return Universe._parse_symbols_from_wiki(url, ["Symbol"])  # type: ignore

    @staticmethod
    def from_csv(path: str) -> List[str]:
        # Simple CSV reader without pandas; accepts header or single column
        import csv

        symbols: List[str] = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return symbols
        header = rows[0]
        if any(h.lower() in ("symbol", "ticker") for h in header):
            # find first matching column
            col_idx = None
            for i, h in enumerate(header):
                if h.lower() in ("symbol", "ticker"):
                    col_idx = i
                    break
            if col_idx is not None:
                for r in rows[1:]:
                    if col_idx < len(r) and r[col_idx].strip():
                        symbols.append(r[col_idx].strip())
        else:
            for r in rows:
                if r and r[0].strip():
                    symbols.append(r[0].strip())
        return symbols


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    try:
        if a is None or b in (None, 0):
            return None
        return a / b
    except Exception:
        return None


def _cagr(first: Optional[float], last: Optional[float], years: int) -> Optional[float]:
    try:
        if first is None or last is None or first <= 0 or years <= 0:
            return None
        return (last / first) ** (1.0 / years) - 1.0
    except Exception:
        return None


def _http_get_json(urls: List[str], timeout: int = 20, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    import random
    backoff = 0.5
    for attempt in range(max_retries):
        for base in urls:
            try:
                r = requests.get(base + url, headers=HTTP_HEADERS, timeout=timeout)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 403, 404, 500):
                    # try next host or backoff
                    continue
            except Exception:
                continue
        time.sleep(backoff + random.uniform(0, 0.3))
        backoff *= 2
    return None


def _yahoo_quote(ticker: str) -> Dict[str, Any]:
    url = f"/v7/finance/quote?symbols={ticker}"
    data = _http_get_json(YAHOO_HOSTS, timeout=20, max_retries=4)
    if not data:
        return {}
    result = (data.get("quoteResponse", {}).get("result", []) or [{}])[0]
    return result or {}


def _yahoo_chart_close(ticker: str, range_: str = "1y", interval: str = "1d") -> List[float]:
    url = f"/v8/finance/chart/{ticker}?range={range_}&interval={interval}&events=div,splits"
    data = _http_get_json(YAHOO_HOSTS, timeout=20, max_retries=4)
    if not data:
        return []
    result = data.get("chart", {}).get("result", [])
    if not result:
        return []
    result0 = result[0]
    closes = result0.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    return [float(c) for c in closes if c is not None]


def _stooq_history_close(ticker: str) -> List[float]:
    # Stooq uses .US suffix for US tickers
    sym = ticker.upper()
    if "." not in sym and ":" not in sym:
        sym = f"{sym}.US"
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv"}, timeout=20)
        if r.status_code != 200 or not r.text:
            return []
        lines = r.text.strip().splitlines()
        if len(lines) <= 1:
            return []
        closes: List[float] = []
        for line in lines[1:]:
            parts = line.split(",")
            if len(parts) >= 5:
                try:
                    closes.append(float(parts[4]))
                except Exception:
                    continue
        return closes
    except Exception:
        return []


def _yahoo_income_statement_history(ticker: str) -> List[Dict[str, Any]]:
    modules = "incomeStatementHistory"
    url = f"/v10/finance/quoteSummary/{ticker}?modules={modules}"
    data = _http_get_json(YAHOO_HOSTS, timeout=20, max_retries=4)
    if not data:
        return []
    result = data.get("quoteSummary", {}).get("result", [])
    if not result:
        return []
    hist = result[0].get("incomeStatementHistory", {}).get("incomeStatementHistory", [])
    return hist or []


def _yahoo_asset_profile(ticker: str) -> Dict[str, Any]:
    modules = "assetProfile"
    url = f"/v10/finance/quoteSummary/{ticker}?modules={modules}"
    data = _http_get_json(YAHOO_HOSTS, timeout=20, max_retries=4)
    if not data:
        return {}
    result = data.get("quoteSummary", {}).get("result", [])
    if not result:
        return {}
    return result[0].get("assetProfile", {}) or {}


def fetch_snapshot(ticker: str) -> Optional[TickerSnapshot]:
    try:
        quote = _yahoo_quote(ticker)
        short_name = quote.get("shortName") or quote.get("longName")
        market_cap = quote.get("marketCap")
        pe_trailing = quote.get("trailingPE")
        pe_forward = quote.get("forwardPE")
        dividend_yield = quote.get("trailingAnnualDividendYield") or quote.get("dividendYield")
        price = quote.get("regularMarketPrice") or quote.get("postMarketPrice")

        # Momentum and volatility from chart
        closes = _yahoo_chart_close(ticker)
        if not closes:
            closes = _stooq_history_close(ticker)
        returns_6m = None
        volatility_1y = None
        if closes and len(closes) > 150:
            last = closes[-1]
            prev_6m = closes[max(0, len(closes) - 126)]
            if prev_6m and prev_6m > 0:
                returns_6m = float(last / prev_6m - 1.0)
            # daily returns
            daily = []
            for i in range(1, len(closes)):
                if closes[i - 1] and closes[i - 1] > 0 and closes[i] and closes[i] > 0:
                    daily.append((closes[i] / closes[i - 1]) - 1.0)
            if len(daily) > 2:
                mean = sum(daily) / len(daily)
                var = sum((x - mean) ** 2 for x in daily) / len(daily)
                volatility_1y = float(math.sqrt(var) * math.sqrt(252))

        # Financials for gross margin and revenue CAGR
        gross_margin = None
        revenue_cagr_3y = None
        try:
            incs = _yahoo_income_statement_history(ticker)
            # Each item has totalRevenue, grossProfit as dicts with 'raw'
            revenues: List[float] = []
            gross: Optional[float] = None
            for idx, it in enumerate(incs[:4]):
                tr = it.get("totalRevenue", {}).get("raw")
                gp = it.get("grossProfit", {}).get("raw")
                if tr is not None:
                    revenues.append(float(tr))
                if idx == 0 and gp is not None and tr is not None and tr > 0:
                    gross = float(gp) / float(tr)
            if revenues:
                gross_margin = gross
            if len(revenues) >= 4 and revenues[0] and revenues[3] and revenues[3] > 0:
                revenue_cagr_3y = _cagr(float(revenues[3]), float(revenues[0]), 3)
        except Exception:
            pass

        # Sector from asset profile
        sector = None
        try:
            profile = _yahoo_asset_profile(ticker)
            sector = profile.get("sector")
        except Exception:
            pass

        return TickerSnapshot(
            ticker=ticker,
            short_name=short_name,
            sector=sector,
            market_cap=float(market_cap) if market_cap is not None else None,
            pe_trailing=float(pe_trailing) if pe_trailing is not None else None,
            pe_forward=float(pe_forward) if pe_forward is not None else None,
            dividend_yield=float(dividend_yield) if dividend_yield is not None else None,
            price=float(price) if price is not None else None,
            returns_6m=returns_6m,
            volatility_1y=volatility_1y,
            gross_margin=gross_margin,
            revenue_cagr_3y=revenue_cagr_3y,
        )
    except Exception as e:
        logger.warning("Failed snapshot for %s: %s", ticker, e)
        return None


def batch_fetch_snapshots(tickers: List[str], max_per_minute: int = 180) -> List[TickerSnapshot]:
    results: List[TickerSnapshot] = []
    start = time.time()
    for i, tic in enumerate(tickers, 1):
        snap = fetch_snapshot(tic)
        if snap:
            results.append(snap)
        # basic rate limiting
        if max_per_minute > 0:
            elapsed = time.time() - start
            expected = i / (max_per_minute / 60.0)
            if expected > elapsed:
                time.sleep(min(1.0, expected - elapsed))
    return results