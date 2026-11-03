<!-- File: docs/agents/architecture.md -->

# Architecture & Concurrency Standards

## Core Architecture: The Single-User Constraint

- Single-user, self-hosted appliance model: Not a scalable SaaS platform.
- Gunicorn Configuration: `WORKERS=1`, `THREADS=8+`.
- In-memory rate limits (`memory://`) apply per process; never add workers without an external limiter backend.
- No internal SQL database, persistent local caches, or server-side sessions.
- Container maintains no persistent application state; torrent client manages download and file state.

## Thread Safety & State Isolation

- Stateful objects must be thread-local or isolated.
- SDK connections and HTTP sessions must never be shared across request threads. Shared plugin objects use the base
  class's thread-local `client` and `session` handles; additional transport state must also be isolated.
- Subclass `threading.local` for typed thread-local storage (e.g., `class ClientLocal(threading.local)`).
- Shared memory caches must be guarded by thread locks defined in the same module
  (`audiobook_automated/scraper/network.py`).

## Concurrency Safeguards

- Global Request Semaphore: Initialized at startup to match `SCRAPER_THREADS`.
- Must never be bypassed, removed, or modified to exceed configured concurrency.
- Background executors (e.g., mirror check workers) must register clean container shutdown handlers.

## Extension & Initialization

- Global extensions (e.g., `TorrentManager`, `ScraperEngine`) must use the Flask `init_app()` pattern.
- Load environment variables before importing the application configuration. Config reads them during module import;
  the app does not load a `.env` file itself. Use Docker `env_file` or `uv run --env-file .env`.
- `create_app()` generates a 32-byte random signing key when optional `SECRET_KEY` is empty, before CSRF/session
  initialization. Keep the key in memory for the single-worker lifetime; do not generate it per request or write it to
disk.
  An explicit key is an advanced restart-continuity option. Expired action tokens return actionable JSON without
retries.
- Configuration is loaded via typed classes in `audiobook_automated/config.py` with runtime validation in `validate()`.
- Multi-client routing: `TorrentManager` initializes individual client plugins specified by `DL_CLIENT` and
  `DL_CLIENT` (one name or a comma-separated list) and independent client-prefixed connection settings, routing
download requests to the designated client and aggregating status queries.

## Frontend Presentation

- Use shared theme, control positioning and motion rules. Keep single-column mobile layouts compact rather than
  reserving alignment space intended for adjacent cards.
- Search filters operate on loaded summaries only. Title contributor credits are conservative presentation heuristics,
  not verified bibliographic data. Keep the raw title for actions and never fetch every Details page to fill filters.
- Details extracts all structured contributor and audio metadata before sanitizing the source HTML. Remove only
  matching leading metadata lines; preserve unique description text and unmatched credits.
