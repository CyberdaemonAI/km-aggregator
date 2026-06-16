<div align="center">

# km-aggregator

**AI security news aggregator with semantic clustering, framework release detection, and daily digest delivery**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![pgvector](https://img.shields.io/badge/pgvector-PostgreSQL-blue.svg)](https://github.com/pgvector/pgvector)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

> km-aggregator monitors AI security, identity, and governance content across RSS feeds and YouTube channels, clusters related articles by semantic similarity, detects when standards bodies release new versions, and delivers a synthesized daily digest to Mattermost. No paid API required — all inference runs locally via Ollama.

---

## What it does

km-aggregator is a three-worker pipeline that runs continuously:

1. **Ingest** — polls 35+ RSS feeds and 15 YouTube channels every two hours. Fetches YouTube transcripts via yt-dlp (no audio download). Deduplicates by normalized URL and content hash.

2. **Embed** — generates 768-dimension embeddings for every article using `nomic-embed-text` via Ollama. Stores vectors in PostgreSQL with pgvector.

3. **Synthesize** — clusters embedded articles by cosine similarity, generates a theme and digest for each cluster using `llama3.3:70b` via Ollama, scans for framework release signals, and delivers a formatted daily digest to Mattermost.

---

## What it does differently

Most news aggregators give you a list. km-aggregator gives you a briefing.

Five things that distinguish it from a standard RSS reader:

**1. Cross-article cluster synthesis.** When five sources all cover the same story, they become one cluster with one synthesized theme. You get the signal, not the noise.

**2. YouTube transcript ingestion.** Podcast content on YouTube is treated as a first-class source. yt-dlp fetches auto-generated VTT transcripts (no audio downloaded, no Whisper required). Same pipeline as RSS.

**3. Framework release detection.** After synthesis, every cluster is scanned for signals that a standard was updated: NIST, OWASP, CISA, MITRE, SPIFFE, OAuth, OpenID. Positive signals get flagged, sent as an immediate Mattermost alert, and written to prom-memory if configured.

**4. prom-memory integration.** Major discoveries (framework releases, large clusters) can be written to a prom-memory instance as structured memory entries. Optional — disabled by default, activated with an env var.

**5. No paid inference.** Everything runs against a local Ollama instance. Default models: `nomic-embed-text` for embeddings, `llama3.3:70b` for synthesis. Swap models by changing two env vars.

---

## Stack

- **FastAPI** — async web framework, REST API, health endpoint
- **PostgreSQL + pgvector** — article storage with native vector similarity search
- **APScheduler** — async background workers (ingest, embed, synthesize)
- **httpx** — async HTTP client for feed fetching and Ollama API calls
- **feedparser** — RSS/Atom parsing
- **yt-dlp** — YouTube transcript fetching (VTT, no audio)
- **Ollama** — local inference for embeddings (`nomic-embed-text`) and synthesis (`llama3.3:70b`)
- **Mattermost incoming webhook** — daily digest delivery
- **Alembic** — database migrations

---

## Local dev setup

**Prerequisites:**
- Docker and Docker Compose
- Ollama running locally with `nomic-embed-text` and `llama3.3:70b` pulled

```bash
# Pull required Ollama models
ollama pull nomic-embed-text
ollama pull llama3.3:70b

# Clone and configure
git clone https://github.com/CyberdaemonAI/km-aggregator
cd km-aggregator
cp .env.example .env
# Edit .env — add MATTERMOST_WEBHOOK_URL at minimum

# Start database and app
docker compose up -d

# Check health
curl http://localhost:8000/health
```

The ingest worker fires immediately on startup, then every 2 hours. First digest runs at 07:00 UTC.

**Manual trigger:**
```bash
curl -X POST http://localhost:8000/digest/trigger
```

---

## Configuration

All configuration is via environment variables. See `.env.example` for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://km:km@localhost:5432/km` | PostgreSQL connection string |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama inference endpoint |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model (768-dim output required) |
| `SYNTHESIS_MODEL` | `llama3.3:70b` | Synthesis and theme generation model |
| `MATTERMOST_WEBHOOK_URL` | _(empty)_ | Mattermost incoming webhook URL for digest delivery |
| `PROM_MEMORY_URL` | _(empty)_ | prom-memory REST endpoint (optional) |
| `PROM_MEMORY_ENABLED` | `false` | Set to `true` to enable prom-memory writes |
| `CLUSTER_SIMILARITY_THRESHOLD` | `0.85` | Cosine similarity threshold for clustering |
| `DIGEST_SCHEDULE_UTC` | `07:00` | Daily digest time (HH:MM, UTC) |
| `INGEST_INTERVAL_MINUTES` | `120` | RSS + YouTube poll interval |

---

## Feed configuration

Feeds are hardcoded in `app/feeds_config.py` as Python lists. The file ships with 35 RSS feeds and 15 YouTube channels across six categories: `ai-security`, `identity-iam`, `threat-intel`, `ai-llm`, `architecture`, `standards`.

**To add a feed via API:**

```bash
curl -X POST http://localhost:8000/feeds/add \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Feed",
    "url": "https://example.com/feed.xml",
    "feed_type": "rss",
    "category": "ai-security"
  }'
```

**To add permanently:** edit `app/feeds_config.py` and append to `FEEDS` or `YOUTUBE_CHANNELS`.

**Feed categories:**

| Category | What it covers |
|----------|---------------|
| `ai-security` | AI security research, red team, adversarial ML |
| `identity-iam` | IAM, NHI, OAuth, zero trust identity |
| `threat-intel` | CVEs, active exploits, threat actor campaigns |
| `ai-llm` | LLM releases, safety research, model news |
| `architecture` | Cloud architecture, Kubernetes, CNCF |
| `standards` | NIST, OWASP, CISA, IETF, SPIFFE, ISO |

---

## API reference

Full interactive docs at `/docs` when running locally.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check + scheduler status |
| `/feeds/` | GET | List all feeds with poll status |
| `/feeds/add` | POST | Add a new feed |
| `/feeds/{id}/toggle` | POST | Enable/disable a feed |
| `/articles/` | GET | Paginated article list (filter by category, hours) |
| `/articles/search` | GET | Semantic search via pgvector |
| `/articles/frameworks` | GET | Framework release flagged articles |
| `/digest/latest` | GET | Most recent synthesis clusters |
| `/digest/trigger` | POST | Manually trigger full synthesis pipeline |
| `/digest/status` | GET | Last run stats |

---

## K8s deployment

Internal deployment configs are not included. See `k8s/README.md` for the manifest structure and setup guide.

---

## Framework release detection

km-aggregator scans every cluster for co-occurrence of framework names (NIST, OWASP, CISA, MITRE, SPIFFE, OAuth, OpenID, etc.) and release signals ("released", "updated", "new version", "final"). Positive hits trigger:

1. `is_framework_release = true` on the article and its cluster
2. An immediate Mattermost alert (not queued for the daily digest)
3. A prom-memory write if `PROM_MEMORY_ENABLED=true`

The keyword lists are in `app/feeds_config.py` — `FRAMEWORK_KEYWORDS` and `RELEASE_TRIGGER_WORDS`.

---

## License

MIT

---

<div align="center">

Built for [cyberdaemon.ai](https://cyberdaemon.ai)

</div>
