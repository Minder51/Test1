from __future__ import annotations

import datetime as dt
import html
import re
from dataclasses import dataclass
from typing import List, Optional, Dict

import requests
import feedparser

from .llm import LLMClient


GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


@dataclass
class NewsItem:
    title: str
    url: str
    published: Optional[str]
    source: Optional[str]


def fetch_google_news(query: str, max_items: int = 10) -> List[NewsItem]:
    url = GOOGLE_NEWS_RSS.format(query=requests.utils.quote(query))
    feed = feedparser.parse(url)
    items: List[NewsItem] = []
    for e in feed.entries[:max_items]:
        title = html.unescape(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        published = getattr(e, "published", None)
        source = None
        if hasattr(e, "source") and getattr(e, "source") is not None:
            source = getattr(e.source, "title", None)
        items.append(NewsItem(title=title, url=link, published=published, source=source))
    return items


def summarize_company_news(company_name: str, ticker: str, llm: LLMClient, max_articles: int = 8) -> str:
    items = fetch_google_news(f"{company_name} {ticker}", max_items=max_articles)
    if not items:
        return "No recent news found."

    bullets = []
    for it in items:
        when = it.published or ""
        src = f"[{it.source}]" if it.source else ""
        bullets.append(f"- {when} {src} {it.title} — {it.url}")

    prompt = (
        "You are an equity research analyst. Given these recent headlines and links about a company, "
        "identify key catalysts, risks, and themes. Be concise with bullet points, then provide a 1-paragraph thesis.\n\n"
        + "\n".join(bullets)
    )

    system = (
        "Write like a professional buy-side analyst. "
        "Avoid hype. Use evidence. Include both positives and negatives."
    )

    return llm.summarize(prompt=prompt, system=system)