<!-- File: docs/agents/scraping-safety.md -->

# Scraping Safety & Filesystem Standards

## Safety Over Speed Invariants

- Mandatory Jitter: Introduce random sleep (0.5 to 1.5 seconds) prior to all external requests. Never remove or reduce.
- Network Calls: Never invoke `requests` directly; always route through `audiobook_automated/scraper/network.py`.
- Explicit Timeouts: Every blocking I/O operation must reference a named constant in `audiobook_automated/constants.py`.
- Search Query Limits: Search queries must meet minimum character length requirements (>= 2 characters) and normalize to
  lowercase.

## Mirror Probing, Dual Protocol Fallback & Negative Caching

- Dual Protocol Probing: Mirror checks probe HTTPS first; on TLS handshake failures, they cleanly fall back to HTTP
  (port 80).
- Semantic Catalog Verification: Verification validates authentic HTML structures (`postTitle`, `#content`) and ensures
  no third-party redirects or parked-domain markers exist before marking a mirror healthy.
- Latency Scoring: Active mirrors are ranked via exponential moving average (EMA) response latency
  (`Accuracy > Speed > Security`).
- Fail Fast: Probes must immediately return `None` on connection errors or timeouts.
- Negative Caching: If all external mirrors fail, cache the failure state for backoff (e.g., 30 seconds) to prevent
  retry storms. Do not purge mirror caches prematurely.

## Filesystem Safety & Path Boundaries

- Path Length Safety: Calculate maximum allowable directory length dynamically based on configured `SAVE_PATH_BASE` to
  honor OS path limits (such as 260 characters on Windows).
- Windows Reserved Names: Sanitize illegal characters and reserved words (e.g., `CON`, `PRN`, `AUX`, `NUL`), including
  compound extensions (e.g., `CON.tar.gz`).
- Cross-Platform OS Normalization: Windows drive paths, UNC shares and backslash paths are detected from the optional
  save root; paths are
  safely formatted using Windows backslash conventions without mangling POSIX paths on Linux.
- Collision Avoidance: Append short UUIDs (`uuid.uuid4().hex[:8]`) to sanitized or fallback directory names to guarantee
  uniqueness.

## Search and Description Data

- Catalog book links may be root-relative (`/abss/...`) or absolute HTTP(S) URLs. Search cards and appended rows
  preserve that value. Download validation must accept catalog-relative paths, reject network-path URLs (`//host/...`)
  and unsupported schemes, and retain the Details resolver's mirror allowlist before network access. Browser fixtures
  must include relative links and test actual Download clicks on initial and appended cards.

- Expose `category:`, `language:`, `author:` and `narrator:` in UI links. Native category/language URLs still use the
  catalog's `/type/` and `/tag/` segments. Author/narrator prefixes use supported keyword search, not invented
  archive paths; omit dotted initials to handle spelling variants. Retain explicit native paths. Do not add aliases.
- A search-page 404 means that page has no results; do not penalize or invalidate the whole mirror for it.
- Progressive search fetches one page at a time and ends when the catalog returns no further results. There is no
  `PAGE_LIMIT` application setting. Preserve request jitter and concurrency caps for every page.
- Description cleanup is local to already-fetched HTML. Collect the complete structured cast and audio fields first;
  remove only leading standalone duplicates that match fields displayed above. Do not discard synopsis content or
  issue extra metadata requests.
