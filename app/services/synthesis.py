"""
LLM-based synthesis service.

Uses Ollama on the inference stack (llama3.3:70b) — no paid API.
Generates:
  - Per-cluster theme + digest from representative article summaries
  - Framework release detection scan
  - Daily digest assembly for Mattermost delivery

Synthesis prompt style: claim-based, not summary-based.
What changed. Why it matters. Bridge to practitioner context.
"""

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.feeds_config import FRAMEWORK_KEYWORDS, RELEASE_TRIGGER_WORDS
from app.models.article import Article
from app.models.synthesis import Synthesis

log = logging.getLogger(__name__)
settings = get_settings()

SYNTHESIS_SYSTEM_PROMPT = """\
You are an intelligence synthesizer for a cybersecurity practitioner. \
Your output style: direct, claim-first, no filler. \
Focus on what changed, why it matters, and what a practitioner in identity/ZTA/AI security should do with this information. \
Never write "in conclusion" or "in summary." \
Never hedge with "it seems" or "it appears." \
State the claim, then the weight.
"""

CLUSTER_PROMPT_TEMPLATE = """\
The following {n} articles have been grouped by semantic similarity into a single cluster.
Category: {category}

Article summaries:
{summaries}

Write:
1. THEME (one sentence): what this cluster is actually about
2. SYNTHESIS (3-5 sentences): what happened across these sources, why it matters for practitioners \
in {category}, and what the delta is from the baseline

Keep total output under 300 words. Do not list sources. Synthesize, do not enumerate.
"""


async def synthesize_cluster(
    cluster: Synthesis,
    articles: list[Article],
    db: AsyncSession,
) -> bool:
    """
    Generate theme + digest for a cluster.

    Pulls summaries (or titles as fallback) from member articles,
    sends to Ollama, writes result back to Synthesis row.

    Returns True on success.
    """
    summaries = []
    for art in articles:
        text = art.summary or art.title
        if text:
            summaries.append(f"- {text.strip()}")

    if not summaries:
        log.warning("cluster %d has no content to synthesize", cluster.id)
        return False

    prompt = CLUSTER_PROMPT_TEMPLATE.format(
        n=len(articles),
        category=cluster.category or "security",
        summaries="\n".join(summaries),
    )

    result = await _call_ollama(prompt)
    if not result:
        return False

    # Parse THEME / SYNTHESIS lines
    theme = _extract_field(result, "THEME") or cluster.theme
    digest = _extract_field(result, "SYNTHESIS") or result.strip()

    cluster.theme = theme
    cluster.digest_text = digest
    cluster.article_count = len(articles)
    await db.commit()

    log.info("synthesized cluster %d: %s", cluster.id, theme[:60])
    return True


async def scan_for_framework_releases(db: AsyncSession) -> list[int]:
    """
    Scan unprocessed articles for framework/standard release signals.

    Keywords: FRAMEWORK_KEYWORDS x RELEASE_TRIGGER_WORDS (from feeds_config.py).
    Flags matching articles with is_framework_release=True and writes prom-memory.

    Returns list of flagged article IDs.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    result = await db.execute(
        select(Article).where(
            Article.ingested_at >= cutoff,
            Article.is_framework_release.is_(False),
        )
    )
    articles = list(result.scalars().all())

    flagged_ids: list[int] = []
    for art in articles:
        text = f"{art.title} {art.summary or art.content or ''}".lower()
        has_framework = any(kw.lower() in text for kw in FRAMEWORK_KEYWORDS)
        has_release = any(trigger.lower() in text for trigger in RELEASE_TRIGGER_WORDS)

        if has_framework and has_release:
            art.is_framework_release = True
            art.framework_release_flagged_at = datetime.now(timezone.utc)
            flagged_ids.append(art.id)
            log.info("framework release detected: %s", art.title[:80])

    if flagged_ids:
        await db.commit()

    return flagged_ids


async def build_daily_digest(db: AsyncSession, hours: int = 24) -> str:
    """
    Assemble Mattermost-formatted daily digest from clusters in the last N hours.

    Format:
      ## Daemon Intel — {date}
      ### {category}
      **{theme}** ({n} sources)
      {digest_text}

    Returns the full digest string.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(Synthesis).where(
            Synthesis.created_at >= cutoff,
            Synthesis.mattermost_sent.is_(False),
        ).order_by(Synthesis.created_at.desc())
    )
    clusters = list(result.scalars().all())

    if not clusters:
        return ""

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"## Daemon Intel — {date_str}", ""]

    by_category: dict[str, list[Synthesis]] = {}
    for c in clusters:
        key = c.category or "uncategorized"
        by_category.setdefault(key, []).append(c)

    for category, items in sorted(by_category.items()):
        lines.append(f"### {category.upper()}")
        for item in items:
            tag = " :rotating_light: FRAMEWORK RELEASE" if item.is_framework_release else ""
            lines.append(f"**{item.theme}** ({item.article_count} sources){tag}")
            lines.append(item.digest_text.strip())
            lines.append("")

    return "\n".join(lines)


async def _call_ollama(prompt: str) -> str | None:
    """POST to Ollama chat/generate endpoint. Returns response text or None."""
    url = f"{settings.ollama_base_url}/api/generate"
    payload = {
        "model": settings.synthesis_model,
        "prompt": prompt,
        "system": SYNTHESIS_SYSTEM_PROMPT,
        "stream": False,
        "options": {"num_predict": 512, "temperature": 0.3},
    }
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except Exception as exc:
        log.warning("Ollama synthesis call failed: %s", exc)
        return None


def _extract_field(text: str, field: str) -> str | None:
    """Extract FIELD: value from numbered output."""
    pattern = rf"(?:^|\n)\d?\s*{field}[:\s]+(.+?)(?:\n\d|\n[A-Z]{{3,}}:|\Z)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
