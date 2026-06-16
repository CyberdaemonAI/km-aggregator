"""
Mattermost webhook delivery.

Sends digest text to a Mattermost incoming webhook.
Webhook URL is sourced from MATTERMOST_WEBHOOK_URL env var — never hardcoded.

Splits long messages into chunks (Mattermost limit: 16383 chars).
"""

import logging

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

MATTERMOST_MAX_CHARS = 16000  # stay under 16383 hard limit


async def send_digest(text: str) -> bool:
    """
    POST digest text to the configured Mattermost webhook.

    Splits into chunks if text exceeds MATTERMOST_MAX_CHARS.
    Returns True if all chunks sent successfully.
    """
    if not settings.mattermost_webhook_url:
        log.warning("MATTERMOST_WEBHOOK_URL not set — digest not sent")
        return False

    chunks = _split_message(text)
    total = len(chunks)
    success = True

    for i, chunk in enumerate(chunks, 1):
        payload: dict = {"text": chunk}
        if total > 1:
            payload["username"] = f"Daemon Intel ({i}/{total})"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(settings.mattermost_webhook_url, json=payload)
                resp.raise_for_status()
        except Exception as exc:
            log.error("Mattermost delivery failed (chunk %d/%d): %s", i, total, exc)
            success = False

    return success


async def send_alert(message: str, username: str = "Daemon Intel Alert") -> bool:
    """
    Send a one-off alert message (framework release, major discovery).
    """
    if not settings.mattermost_webhook_url:
        log.warning("MATTERMOST_WEBHOOK_URL not set — alert not sent")
        return False

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                settings.mattermost_webhook_url,
                json={"text": message, "username": username},
            )
            resp.raise_for_status()
            return True
    except Exception as exc:
        log.error("Mattermost alert failed: %s", exc)
        return False


def _split_message(text: str) -> list[str]:
    """Split text into chunks that fit within Mattermost's character limit."""
    if len(text) <= MATTERMOST_MAX_CHARS:
        return [text]

    chunks = []
    while text:
        chunk = text[:MATTERMOST_MAX_CHARS]
        # Try to split at a paragraph boundary
        split_at = chunk.rfind("\n\n")
        if split_at > MATTERMOST_MAX_CHARS // 2:
            chunk = chunk[:split_at]
        chunks.append(chunk)
        text = text[len(chunk):].lstrip()

    return chunks
