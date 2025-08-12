# Deep Stock Research Agent

A Python CLI that screens a stock universe (S&P 500, NASDAQ-100, Dow 30, or custom) using value, quality, growth, and momentum factors, then generates brief research notes using recent news and an optional LLM (OpenAI or Ollama).

## Features
- Universe loaders: `sp500`, `nasdaq100`, `dow30`, or `csv:/path/to/tickers.csv` or comma-separated list
- Data from Yahoo Finance JSON endpoints (no heavy deps)
- Factor-based screener with simple z-score normalization (pure Python)
- News gathering via Google News RSS
- Optional LLM summarization via `OPENAI` (e.g., `gpt-4o-mini`) or `Ollama` (local models)
- Markdown reports in `reports/`

## Quickstart

```bash
# Install dependencies (user site)
pip3 install --break-system-packages -r requirements.txt

# Run with S&P 500 universe, no LLM
python3 -m stock_agent.cli run --universe sp500 --min-market-cap 20000000000 --top 5 --llm none

# Run with OpenAI (requires OPENAI_API_KEY)
export OPENAI_API_KEY=sk-...
python3 -m stock_agent.cli run --universe sp500 --top 5 --llm openai:gpt-4o-mini

# Run with Ollama (ensure Ollama is running and model pulled)
export OLLAMA_HOST=http://localhost:11434
python3 -m stock_agent.cli run --universe nasdaq100 --top 5 --llm ollama:llama3.1
```

## Output
- `reports/screen_YYYYMMDD_HHMMSS.md`: Ranked table with core metrics
- `reports/<TICKER>_YYYYMMDD_HHMMSS.md`: Per-company research brief

## Notes
- Free data sources can be noisy or incomplete. The agent handles missing fields gracefully but results may vary.
- This is not financial advice. Always do your own research.