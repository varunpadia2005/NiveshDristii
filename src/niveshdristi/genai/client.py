"""OpenRouter client with Jinja2 deterministic fallback."""
import httpx
import os
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from niveshdristi.config import CFG


class OpenRouterClient:
    """OpenRouter API client - one key accesses DeepSeek, Claude, Nemotron, Gemini, etc."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model or CFG.genai.model
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://niveshdristi.local",
            "X-Title": "NiveshDristi",
        }

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        response_format: dict = None
    ) -> str:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")

        # Short timeout to fail fast on invalid keys
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if response_format:
                payload["response_format"] = response_format

            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]


# --- Jinja2 Template Fallback ---

TEMPLATE_DIR = Path(__file__).parent / "templates"
JINJA_ENV = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=False)


def render_template(template_name: str, **kwargs) -> str:
    """Render a Jinja2 template with given context."""
    template = JINJA_ENV.get_template(template_name)
    return template.render(**kwargs)