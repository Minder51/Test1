from __future__ import annotations

import datetime as dt
from typing import List

from .screener import ScoredTicker


def _fmt_pct(x):
    return "-" if x is None else f"{x*100:.1f}%"


def _fmt_float(x):
    return "-" if x is None else f"{x:.2f}"


def _fmt_int(x):
    return "-" if x is None else f"{int(x):,}"


def generate_screen_report(scored: List[ScoredTicker], title: str, top_n: int = 20) -> str:
    lines = []
    lines.append(f"# {title}")
    lines.append(f"Generated: {dt.datetime.utcnow().isoformat()}Z\n")
    lines.append("| Rank | Ticker | Name | Sector | Score | Mkt Cap | P/E | 6m Ret | 1y Vol | GM | Rev CAGR |")
    lines.append("|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for i, st in enumerate(scored[:top_n], 1):
        s = st.snapshot
        lines.append(
            f"| {i} | {s.ticker} | {s.short_name or ''} | {s.sector or ''} | "
            f"{st.score_total:.2f} | {_fmt_int(s.market_cap)} | {_fmt_float(s.pe_trailing)} | "
            f"{_fmt_pct(s.returns_6m)} | {_fmt_pct(s.volatility_1y)} | {_fmt_pct(s.gross_margin)} | {_fmt_pct(s.revenue_cagr_3y)} |"
        )
    return "\n".join(lines)


def generate_company_brief(ticker: str, thesis_markdown: str) -> str:
    return f"## {ticker} — Research Brief\n\n{thesis_markdown}\n"