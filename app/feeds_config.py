"""
Hardcoded feed list for km-aggregator.
Source: knowledge-monitor planning / km_config.yaml (as of 2026-06-16).

To add feeds: append to FEEDS or YOUTUBE_CHANNELS and restart workers.
For a UI-based add, POST /feeds/add (see routers/feeds.py).
"""

from typing import Literal

FeedType = Literal["rss", "youtube", "github"]
Category = Literal[
    "ai-security",
    "identity-iam",
    "threat-intel",
    "ai-llm",
    "architecture",
    "standards",
    "tools",
]

FEEDS: list[dict] = [
    # ── AI Security ────────────────────────────────────────────────────────────
    {
        "name": "Palo Alto Unit 42",
        "url": "https://unit42.paloaltonetworks.com/feed/",
        "type": "rss",
        "category": "ai-security",
    },
    {
        "name": "Mandiant Threat Intelligence",
        "url": "https://cloudblog.withgoogle.com/topics/threat-intelligence/rss/",
        "type": "rss",
        "category": "ai-security",
    },
    {
        "name": "OWASP GenAI Blog",
        "url": "https://genai.owasp.org/blog/feed/",
        "type": "rss",
        "category": "ai-security",
    },
    {
        "name": "Lee Hanchung Blog",
        "url": "https://leehanchung.github.io/feed.xml",
        "type": "rss",
        "category": "ai-security",
    },
    {
        "name": "CrowdStrike Blog",
        "url": "https://www.crowdstrike.com/blog/feed/",
        "type": "rss",
        "category": "ai-security",
    },
    {
        "name": "Wiz Blog",
        "url": "https://www.wiz.io/blog/rss.xml",
        "type": "rss",
        "category": "ai-security",
    },
    {
        "name": "Schneier on Security",
        "url": "https://www.schneier.com/blog/atom.xml",
        "type": "rss",
        "category": "ai-security",
    },
    {
        "name": "NVIDIA Generative AI Blog",
        "url": "https://developer.nvidia.com/blog/category/generative-ai/feed/",
        "type": "rss",
        "category": "ai-security",
    },
    # ── Identity / IAM ─────────────────────────────────────────────────────────
    {
        "name": "Control Plane (Karl McGuinness)",
        "url": "https://notes.karlmcguinness.com/index.xml",
        "type": "rss",
        "category": "identity-iam",
    },
    {
        "name": "Microsoft Entra Blog",
        "url": "https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board.id=microsoft-entra-blog&size=10",
        "type": "rss",
        "category": "identity-iam",
    },
    {
        "name": "Delinea Blog",
        "url": "https://delinea.com/blog/rss.xml",
        "type": "rss",
        "category": "identity-iam",
    },
    {
        "name": "One Identity Blog",
        "url": "https://www.oneidentity.com/community/blogs/rss",
        "type": "rss",
        "category": "identity-iam",
    },
    {
        "name": "Auth0 Blog",
        "url": "https://auth0.com/blog/rss.xml",
        "type": "rss",
        "category": "identity-iam",
    },
    {
        "name": "Saviynt Blog",
        "url": "https://www.saviynt.com/blog/feed/",
        "type": "rss",
        "category": "identity-iam",
    },
    # ── Threat Intel ───────────────────────────────────────────────────────────
    {
        "name": "CISA News",
        "url": "https://www.cisa.gov/news.xml",
        "type": "rss",
        "category": "threat-intel",
    },
    {
        "name": "Krebs on Security",
        "url": "https://krebsonsecurity.com/feed/",
        "type": "rss",
        "category": "threat-intel",
    },
    {
        "name": "BleepingComputer",
        "url": "https://www.bleepingcomputer.com/feed/",
        "type": "rss",
        "category": "threat-intel",
    },
    {
        "name": "The Hacker News",
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "type": "rss",
        "category": "threat-intel",
    },
    {
        "name": "Dark Reading",
        "url": "https://www.darkreading.com/rss.xml",
        "type": "rss",
        "category": "threat-intel",
    },
    {
        "name": "Graham Cluley",
        "url": "http://feeds.feedburner.com/GrahamCluleysBlog",
        "type": "rss",
        "category": "threat-intel",
    },
    {
        "name": "The Register (Security)",
        "url": "http://www.theregister.co.uk/security/headlines.atom",
        "type": "rss",
        "category": "threat-intel",
    },
    # ── AI / LLM ───────────────────────────────────────────────────────────────
    {
        "name": "Anthropic News",
        # Community-maintained scraper — monitor for breaks
        "url": "https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml",
        "type": "rss",
        "category": "ai-llm",
    },
    {
        "name": "OpenAI News",
        "url": "https://openai.com/news/rss.xml",
        "type": "rss",
        "category": "ai-llm",
    },
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "type": "rss",
        "category": "ai-llm",
    },
    {
        "name": "Daniel Miessler (Unsupervised Learning)",
        "url": "https://danielmiessler.com/feed/podcast/",
        "type": "rss",
        "category": "ai-llm",
    },
    # ── Architecture / Infrastructure ──────────────────────────────────────────
    {
        "name": "AWS Architecture Blog",
        "url": "https://aws.amazon.com/blogs/architecture/feed/",
        "type": "rss",
        "category": "architecture",
    },
    {
        "name": "CNCF Blog",
        "url": "https://www.cncf.io/blog/feed/",
        "type": "rss",
        "category": "architecture",
    },
    {
        "name": "Kubernetes Blog",
        "url": "https://kubernetes.io/feed.xml",
        "type": "rss",
        "category": "architecture",
    },
    # ── Standards ──────────────────────────────────────────────────────────────
    {
        "name": "NIST News",
        "url": "https://www.nist.gov/news-events/news/rss.xml",
        "type": "rss",
        "category": "standards",
    },
    # ── Tools / Releases ───────────────────────────────────────────────────────
    {
        "name": "Ollama Releases",
        "url": "https://github.com/ollama/ollama/releases.atom",
        "type": "rss",
        "category": "tools",
    },
    {
        "name": "llama.cpp Releases",
        "url": "https://github.com/ggml-org/llama.cpp/releases.atom",
        "type": "rss",
        "category": "tools",
    },
    {
        "name": "MCP Python SDK Releases",
        "url": "https://github.com/modelcontextprotocol/python-sdk/releases.atom",
        "type": "rss",
        "category": "tools",
    },
    {
        "name": "markitdown Releases",
        "url": "https://github.com/microsoft/markitdown/releases.atom",
        "type": "rss",
        "category": "tools",
    },
    # ── NHI / Agent Identity ───────────────────────────────────────────────────
    {
        "name": "SPIFFE Spec Releases",
        "url": "https://github.com/spiffe/spiffe/releases.atom",
        "type": "rss",
        "category": "standards",
    },
    {
        "name": "SPIRE Project Releases",
        "url": "https://github.com/spiffe/spire/releases.atom",
        "type": "rss",
        "category": "standards",
    },
    {
        "name": "OWASP LLM Top 10 Releases",
        "url": "https://github.com/OWASP/www-project-top-10-for-large-language-model-applications/releases.atom",
        "type": "rss",
        "category": "standards",
    },
]

# YouTube channels — fetched via YouTube RSS API (no API key required)
# URL pattern: https://www.youtube.com/feeds/videos.xml?channel_id=<ID>
YOUTUBE_CHANNELS: list[dict] = [
    # ── Threat Intel ───────────────────────────────────────────────────────────
    {
        "name": "Risky Business Media",
        "channel_id": "UCZzIaWixWHa96R7K4c40_Dg",
        "category": "threat-intel",
    },
    {
        "name": "Darknet Diaries",
        "channel_id": "UCziVakKilxo8Gjn7_Rs5RLw",
        "category": "threat-intel",
    },
    {
        "name": "SANS Institute",
        "channel_id": "UCnUYZLuoy1rq1aVMwx4aTzw",
        "category": "threat-intel",
    },
    {
        "name": "CISO Series",
        "channel_id": "UC9ksdhUaDEEyltTxBc2AzfQ",
        "category": "threat-intel",
    },
    {
        "name": "Down the Security Rabbithole",
        "channel_id": "UCeLgLsw08zJk-XczD7v38mw",
        "category": "threat-intel",
    },
    {
        "name": "N2K Networks",
        "channel_id": "UCIC1L2vbbyotqEF0ZLhaOdw",
        "category": "threat-intel",
    },
    # ── AI Security ────────────────────────────────────────────────────────────
    {
        "name": "fwd:cloudsec",
        "channel_id": "UCjfghTrOeq5Qu0WdKjxBpBA",
        "category": "ai-security",
    },
    {
        "name": "Unsupervised Learning (Daniel Miessler)",
        "channel_id": "UCnCikd0s4i9KoDtaHPlK-JA",
        "category": "ai-security",
    },
    {
        "name": "Security Visionaries",
        "channel_id": "UCZrwON-Dvv4B58r0XRvB27w",
        "category": "ai-security",
    },
    {
        "name": "The Weekly Purple Team",
        "channel_id": "UCfB_ox83jMXoQ8i_4zVNBWw",
        "category": "ai-security",
    },
    {
        "name": "IBM Technology",
        "channel_id": "UC8cc4pVKVHG7A9fbNsRNrLQ",
        "category": "ai-security",
    },
    {
        "name": "AI Security Podcast",
        "channel_id": "UC8jQKdbAHbv7LuIQOxN_mqQ",
        "category": "ai-security",
    },
    {
        "name": "Cloud Security Podcast",
        "channel_id": "UCRrWf6aQnFbdS7WRlv_o0Tw",
        "category": "ai-security",
    },
    # ── Identity / IAM ─────────────────────────────────────────────────────────
    {
        "name": "Identity at the Center",
        "channel_id": "UC-m5vJ8FHUxhZnbRiOxSOpQ",
        "category": "identity-iam",
    },
    # ── Architecture ───────────────────────────────────────────────────────────
    {
        "name": "Packet Pushers",
        "channel_id": "UC7vAUu1TQAwzuq8wajJw4kA",
        "category": "architecture",
    },
]

# Watched URLs (change detection, not RSS)
WATCHED_URLS: list[dict] = [
    {
        "name": "A2A Protocol Specification",
        "url": "https://a2a-protocol.org/latest/specification/",
        "category": "architecture",
        "check_frequency": "weekly",
    },
    {
        "name": "Agentic JWT IETF Draft",
        "url": "https://datatracker.ietf.org/doc/draft-goswami-agentic-jwt/",
        "category": "standards",
        "check_frequency": "weekly",
    },
    {
        "name": "Capsule Security Blog",
        "url": "https://capsulesecurity.io/blog",
        "category": "ai-security",
        "check_frequency": "weekly",
    },
    {
        "name": "Microsoft Entra Identity Docs",
        "url": "https://learn.microsoft.com/en-us/entra/identity/",
        "category": "identity-iam",
        "check_frequency": "weekly",
    },
]

# Framework names used for release detection scanning
FRAMEWORK_KEYWORDS: list[str] = [
    "NIST",
    "OWASP",
    "CISA",
    "ISO",
    "MITRE",
    "SPIFFE",
    "SPIRE",
    "MCP",
    "A2A",
    "IETF",
    "FIDO",
    "OAuth",
    "OpenID",
    "SAML",
]

RELEASE_TRIGGER_WORDS: list[str] = [
    "released",
    "updated",
    "new version",
    "v2",
    "v3",
    "2025",
    "2026",
    "final",
    "published",
    "announced",
]
