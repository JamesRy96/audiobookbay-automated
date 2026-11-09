<!-- File: audiobook_automated/AGENTS.md -->

# Backend Architecture & Subsystem Guide (`audiobook_automated/`)

## 1. Directory Layout & Module Boundaries

- `app.py`: CLI and Flask WSGI application entrypoint (`create_app`, `main`). Enforces Gunicorn `WORKERS=1`.
- `config.py`: Environment configuration parsing, case-insensitive settings, and RFC-1918 `NO_PROXY` validation.
- `clients/`: Pluggable Download Client plugins.
  - `base.py`: Defines the `TorrentClientPlugin` ABC and `TorrentClientError`.
  - `qbittorrent.py`, `transmission.py`: Concrete client plugins using thread-local sessions (`threading.local`).
- `scraper/`: Catalog scraping, network resilience, and HTML parsing pipeline.
  - `network.py`: Jittered outbound HTTP requests, health probes, latency ranking, and `ScraperError`.
  - `models.py`: Structured dataclasses for search results and audiobooks.
  - `parser.py`: BeautifulSoup HTML parsing and metadata extraction.
- `static/`: Plain vanilla ES6 JavaScript client assets, custom CSS, and `normalize.css`. Zero frontend frameworks.
- `templates/`: Server-rendered Jinja2 HTML templates (`index.html`, `details.html`).

## 2. Canonical Shared Helper Registry

Reuse existing implementations via clean imports; never duplicate utility logic:

- `request_external(url, timeout, ...)` in `audiobook_automated.scraper.network`:
  Executes jittered (`0.3–0.8s`), semaphore-bounded (`GLOBAL_REQUEST_SEMAPHORE`) requests. Never call `requests`
  directly.
- `check_mirror(url, timeout)` in `audiobook_automated.scraper.network`:
  Probes mirror health via HTTPS with HTTP (port 80) fallback, verifying authentic HTML (`postTitle`, `#content`).
- `find_best_mirror(mirrors, ...)` in `audiobook_automated.scraper.network`:
  Dynamically selects active mirrors ranked by exponential moving average (EMA) response latency.
- `TorrentClientPlugin` in `audiobook_automated.clients.base`:
  Abstract base class for all download client implementations. Maintains thread-isolated sessions.
- `Config` in `audiobook_automated.config`:
  Validates application configuration and multi-client connection settings (`DL_CLIENT`, uppercase prefixes).
- `validate_safe_subpath(base, path)` in `audiobook_automated.config`:
  Enforces path traversal safety and filesystem length boundaries.

## 3. Typing, Error Handling & Security Invariants

- **Strict Typing:** Must satisfy Basedpyright strict typing without untyped definitions or ignored type errors.
- **Decentralized Domain Exceptions:** Use domain exceptions (`TorrentClientError`, `ScraperError`, `ConfigError`).
- **Zero Raw Network/Print:** Never call `requests` directly; never use `print()`. Use `logging.getLogger(__name__)`.
- **User-Centric Terminology:** Always use `Download Client` and concrete plugin names, never `Strategy`.
- **Proxy Environment Safety:** Ensure `NO_PROXY` explicitly bypasses local/RFC-1918 subnets
  (`localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16`).
- **Concurrency & Workers:** Gunicorn must run with `WORKERS=1` and `THREADS=8+`. Never scale worker processes.

## 4. Local Subsystem Verification Commands

~~~bash
# Run backend unit and integration tests with 100% coverage
uv run pytest tests/unit/ tests/integration/

# Execute static analysis and strict type checks
pre-commit run --all-files
~~~
