"""
Embedding generation via Ollama (nomic-embed-text).

All inference is local. No OpenAI, no paid API.
Ollama endpoint configured via OLLAMA_BASE_URL env var.

nomic-embed-text output dimension: 768 — matches Vector(768) in Article model.
"""

import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


async def embed_text(text: str) -> list[float] | None:
    """
    Generate a 768-dimension embedding for a text string via Ollama.

    Returns None on failure — caller stores NULL embedding and retries later.
    """
    if not text or not text.strip():
        return None

    # Truncate to ~8k chars to stay within context window
    text = text[:8000]

    url = f"{settings.ollama_base_url}/api/embed"
    payload = {"model": settings.embed_model, "input": text}

    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            embedding: list[float] = data.get("embeddings", [[]])[0]
            if len(embedding) != 768:
                log.warning(
                    "unexpected embedding dimension %d (expected 768) — model: %s",
                    len(embedding),
                    settings.embed_model,
                )
                return None
            return embedding
    except httpx.ConnectError:
        log.error(
            "cannot reach Ollama at %s — is the inference stack running?",
            settings.ollama_base_url,
        )
        return None
    except Exception as exc:
        log.warning("embed_text failed: %s", exc)
        return None


async def embed_batch(texts: list[str]) -> list[list[float] | None]:
    """Embed a batch of texts. Returns parallel list of embeddings (None on failure)."""
    results = []
    for text in texts:
        results.append(await embed_text(text))
    return results
