import os
import requests
from typing import List, Dict, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class LLMClient:
    """Minimal wrapper to support OpenAI and Ollama backends for summarization."""

    def __init__(self, model_spec: Optional[str] = None):
        self.model_spec = model_spec or os.getenv("LLM_MODEL", "none")
        self.backend, self.model = self._parse_model_spec(self.model_spec)

        self.openai_client = None
        if self.backend == "openai":
            if OpenAI is None:
                raise RuntimeError("openai package not available. Install and set OPENAI_API_KEY.")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is required for OpenAI backend")
            self.openai_client = OpenAI()

        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    @staticmethod
    def _parse_model_spec(model_spec: str):
        # formats: "none", "openai:gpt-4o-mini", "ollama:llama3.1:8b"
        if not model_spec or model_spec.lower() == "none":
            return ("none", "none")
        if ":" in model_spec:
            backend, model = model_spec.split(":", 1)
            return backend.strip().lower(), model.strip()
        # default to openai if only a model name is given
        return ("openai", model_spec.strip())

    def summarize(self, prompt: str, system: Optional[str] = None, max_tokens: int = 800) -> str:
        if self.backend == "none":
            return "[LLM disabled]"  # no-op

        if self.backend == "openai":
            assert self.openai_client is not None
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                temperature=0.2,
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or "").strip()

        if self.backend == "ollama":
            url = f"{self.ollama_host}/api/chat"
            payload = {
                "model": self.model,
                "messages": ([{"role": "system", "content": system}] if system else []) +
                            [{"role": "user", "content": prompt}],
                "stream": False,
            }
            r = requests.post(url, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
            return data.get("message", {}).get("content", "").strip()

        raise ValueError(f"Unsupported LLM backend: {self.backend}")