from __future__ import annotations

import argparse
import os
import sys
import datetime as dt
from typing import List

from .providers import Universe, batch_fetch_snapshots
from .screener import rank_tickers
from .llm import LLMClient
from .research import summarize_company_news
from .report import generate_screen_report, generate_company_brief


def _load_universe(spec: str) -> List[str]:
    spec = spec.lower()
    if spec == "sp500":
        return Universe.sp500()
    if spec == "nasdaq100":
        return Universe.nasdaq100()
    if spec == "dow30":
        return Universe.dow30()
    if spec.startswith("csv:"):
        path = spec.split(":", 1)[1]
        return Universe.from_csv(path)
    # comma-separated tickers
    return [t.strip().upper() for t in spec.split(",") if t.strip()]


def run():
    parser = argparse.ArgumentParser(description="Deep Stock Research Agent")
    sub = parser.add_subparsers(dest="cmd")

    runp = sub.add_parser("run", help="Screen universe and generate research report")
    runp.add_argument("--universe", default="sp500", help="Universe: sp500|nasdaq100|dow30|csv:/path|comma,list")
    runp.add_argument("--min-market-cap", type=float, default=5e9, help="Minimum market cap filter (e.g., 2e10 for $20B)")
    runp.add_argument("--top", type=int, default=10, help="How many top names to include")
    runp.add_argument("--llm", default=os.getenv("LLM_MODEL", "none"), help="LLM backend model spec: none|openai:<model>|ollama:<model>")
    runp.add_argument("--out", default="reports", help="Output folder for markdown reports")

    args = parser.parse_args()

    if args.cmd != "run":
        parser.print_help()
        sys.exit(0)

    tickers = _load_universe(args.universe)
    print(f"Loaded universe: {len(tickers)} tickers")

    snaps = batch_fetch_snapshots(tickers)
    print(f"Fetched snapshots: {len(snaps)}")

    ranked = rank_tickers(snaps, min_market_cap=args.min_market_cap)

    title = f"Screen — {args.universe} — min_mcap={args.min_market_cap:,.0f}"
    screen_md = generate_screen_report(ranked, title=title, top_n=args.top)

    os.makedirs(args.out, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    screen_path = os.path.join(args.out, f"screen_{ts}.md")
    with open(screen_path, "w", encoding="utf-8") as f:
        f.write(screen_md)
    print(f"Wrote screen report: {screen_path}")

    llm = LLMClient(args.llm)

    top = ranked[: args.top]
    for st in top:
        s = st.snapshot
        name = s.short_name or s.ticker
        thesis = summarize_company_news(name, s.ticker, llm)
        brief_md = generate_company_brief(s.ticker, thesis)
        brief_path = os.path.join(args.out, f"{s.ticker}_{ts}.md")
        with open(brief_path, "w", encoding="utf-8") as f:
            f.write(brief_md)
        print(f"Wrote brief: {brief_path}")


if __name__ == "__main__":
    run()