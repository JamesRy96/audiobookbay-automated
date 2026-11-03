<!-- File: AGENTS.md -->

# Developer & AI Agent Guide

## 1. Project Overview & Intent

- **What:** A single-user, self-hosted web appliance automating audiobook search, scraping, and torrent client dispatch.
- **Architecture:** Python 3.13/3.14 Flask backend with Gunicorn (`WORKERS=1`, `THREADS=8+`), plain ES6 browser
  frontend, and pluggable torrent download client plugins.
- **Appliance Philosophy:** Zero SQL databases, zero local persistent application caches, and zero external queues (no
  Redis/Celery). Torrent clients hold download state; proxy scrapers protect user privacy.

## 2. Essential Commands

~~~bash
# Install package with development dependencies (using uv or pip)
uv sync --frozen --all-extras
# or: pip install -e ".[dev]"

# Run development server
uv run --env-file .env python -m audiobook_automated.app

# Execute full Python test suite with 100% coverage
pytest

# Execute frontend JavaScript unit tests
npm run test:js -- --runInBand

# Real-template browser checks (isolated server; no live catalog or downloads)
npm ci
npx playwright install --with-deps
npm run test:e2e

# Run all static analysis, linting, formatting, and type checks
pre-commit run --all-files
~~~

## 3. Core Invariants (Non-Negotiable)

- **Safety Over Speed:** Mandatory random jitter sleeps (0.5–1.5s) on external requests must never be removed or
  reduced.
- **Concurrency Caps:** Scraper concurrency is bounded by `GLOBAL_REQUEST_SEMAPHORE` (matching `SCRAPER_THREADS`). Never
  bypass or increase.
- **Worker Limits:** Gunicorn must run with `WORKERS=1`. Never scale worker processes without an external rate-limit
  backend.
- **Zero Raw Network/Print:** Never call `requests` directly (use `audiobook_automated/scraper/network.py`). Never use
  `print()` (use configured logger).
- **Code Block Formatting:** Always format Markdown code blocks using triple tildes (`~~~`) rather than triple
  backticks.
- **First-Line File Headers:** The first line of every source file must comment the relative file path prefixed with
  `File:` (e.g., `# File: audiobook_automated/app.py` or `<!-- File: README.md -->`).
- **User-Centric Terminology:** Always use clear end-user terminology (e.g. `Download Client`, plugin name like
  `qBittorrent`) rather than developer jargon like `Strategy` across codebase, documentation, logs, and UI.
- **Proxy Environment Safety:** When routing through a remote VPN/proxy (such as Gluetun), `NO_PROXY` must explicitly
  bypass local and internal RFC-1918 subnets (`localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`) to prevent
  client connectivity and local Gunicorn bindings from timing out through the external proxy.
- **Semantic Catalog Verification:** Mirror health checks must verify authentic catalog HTML structures (`postTitle`,
  `#content`, and no third-party domain redirects) rather than relying only on HTTP 200/root index responses.
- **Dual Protocol Fallback & Latency Ranking:** Scrapers must probe HTTPS first, falling back to HTTP (port 80) if TLS
  handshake fails, ranking active mirrors via exponential moving average (EMA) response latency.
- **Catalog Routing:** UI/search prefixes are `category:`, `language:`, `author:`, and `narrator:`. Category/language
  map to verified native `/audio-books/type/<category>/` and `/audio-books/tag/<language>/` feeds. Author/narrator
  use catalog keyword search with dotted-initial normalization; do not fabricate contributor archives. Preserve
  explicit native `/audio-books/...` paths when supplied. Do not fetch Details per search result for enrichment.
- **Multi-Client Aggregation:** Support concurrent multi-client setups via `DL_CLIENTS` (comma-separated), unifying
  download status reporting across all active clients.

## 4. Operating Protocol & Reasoning Framework

- **Sandbox Protocol:**
  - `.agents/docs/`: Architectural documentation, research, and `plan.md`.
  - `.agents/scratchpad/`: Working drafts, isolated verification tests, and experiments.
  - `.agents/logs/`: Step-by-step reasoning and audit logs.
  - Changes must be staged and validated in `.agents/` before modifying source files.
- **Reasoning Framework:**
  - Apply Sequential Thinking and the Hermeneutic Circle against overall architecture.
  - Follow ReAct (Thought -> Action -> Observation) and Chain of Verification (CoVe).
  - Negative constraints: No placeholders, no unprompted apologies, no conversational summaries unless requested.
- **Definition of Done:** Plan documented in `.agents/docs/plan.md`, code validated in `.agents/scratchpad/`, required checks
  completed, and readiness evidence/limitations reported. Stay within the authorized scope. Ask for deployment approval
  only when deployment is the next requested step and has not already been authorized.

## 5. Progressive Disclosure Guides

Consult specialized documentation for subsystem implementation details:

- [Architecture & Concurrency](docs/agents/architecture.md): Single-user constraints, thread-local sessions, shutdown
  signals.
- [Scraping Safety & Filesystem](docs/agents/scraping-safety.md): Mirror probes, fail-fast rules, negative caching, path
  length safety.
- [Download Clients & Plugins](docs/agents/torrent-clients.md): Download client interface, progress normalization,
  client quirks, plugin creation.
- [Testing & Quality Standards](docs/agents/testing-quality.md): 100% coverage enforcement, MyPy/Pyright strict typing,
  fixture conventions.

## 6. End-User Experience and Release Maintenance

- The public README is the normal prebuilt Docker installation and usage guide. Keep commands copyable, explain where
  to run them, and describe Download Client paths from the client's perspective. Put advanced settings in
  `docs/configuration.md` and developer/debug/test/release instructions in `docs/development.md`.
- User-facing errors state the problem and correction briefly. Use "Enter at least 2 characters." rather than echoing
  the current count. Keep raw exceptions and troubleshooting detail in logs or explicit debug views.
- This project is preparing its first release. Replace superseded code, settings and tests rather than adding
  compatibility aliases by default. Retain upstream protocol names only where the remote catalog requires them.
- Canonical repository, issue links and image examples use `meek2100/audiobookbay-automated`. Image publishing derives
  its owner/name from the GitHub repository context.
- Browser checks must use the real templates, CSS and controllers. `tests/e2e/server.py` replaces only integration
  boundaries and runs on port 5090. Never point automated Download Client actions at production clients.
- CI checks Python 3.13/3.14, full coverage, Jest, three browser engines, static/types and a container HTTP smoke test.
  Release publishing explicitly calls CI and the image workflow; it does not rely on token-created tag events.
- Do not claim Docker, GitHub-hosted checks, published-image installation or real Download Client compatibility has
  been verified unless those checks actually ran. Keep pending release actions separate from completed local evidence.
