<!-- File: CHANGELOG.md -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Manual branch/tag/commit test-image builds with separate GHCR tags and copyable image references.

- Shared search filters, session-scoped recent searches, explicit pagination retry/end states, and recognizable
  contributor credits with a loaded-results filter.
- Theme-aware cover placeholders, keyboard-safe dialogs and synchronized floating controls.
- End-user Docker setup, configuration/troubleshooting guides, isolated browser fixtures and release instructions.

- **Multi-Client Routing:** Added support for aggregating and dispatching to multiple download clients simultaneously
  using `DL_CLIENTS` (comma-separated list).
- **API Key Authentication:** Added `DL_API_KEY` support for modern qBittorrent and Put.io setups.
- **Cross-Platform Path Normalization:** Added `DL_CLIENT_OS=windows` configuration to safely format paths for Windows
  torrent client hosts without mangling POSIX paths on Linux.
- **Dual Protocol Fallback & Latency Scoring:** Search scrapers now probe HTTPS first and gracefully fall back to HTTP
  (port 80), ranking mirrors via exponential moving average (EMA) response latency.
- **Live Diagnostics Suite:** Added comprehensive health dashboard and scraper inspector at `/diagnostics` (toggleable
  via `ENABLE_DIAGNOSTICS`).
- **14 Modern Themes:** Expanded theme switcher with 14 polished palettes (`purple`, `crow`, `catppuccin`, `nord`,
  `tokyo`, `oled`, `forest`, `ocean`, `sunset`, `dracula`, `cyberpunk`, `light`, `royal`, `slate`).
- **Put.io Cloud Client:** Integrated Put.io cloud torrent downloader (`DL_CLIENT=putio`) with Bearer token
  authentication and customizable target folder ID (`PUTIO_FOLDER_ID`).
- **UI Customization & Theming:** Added `DEFAULT_THEME`, customizable `SITE_TITLE`, and `SITE_LOGO`.
- **Animated Splash Screen Morph:** Added video splash screen with smooth transition that shrinks and fades into the
  header banner.
- **Custom Trackers Example:** Added `examples/trackers.json` demonstrating custom tracker override formats.
- **Auto-Refresh Controls:** Added toggleable auto-refresh switches and 5-second countdown timer buttons across both
  Active Downloads (`/status`) and System Diagnostics (`/diagnostics`), allowing users to pause polling anytime while
  retaining on-demand manual refresh.
- **Diagnostics Test Suite:** Added comprehensive Jest test suite (`tests/js/diagnostics.test.js`) verifying dashboard
  polling, metric rendering, and log filtering.

### Changed

- Generate session/CSRF signing keys automatically; normal installation no longer requires a manual secret.
- Explain page expiry with a refresh instruction after restarts, while retaining optional signing-key configuration.

- Standardized filled covers, card/metadata/action alignment and a compact banner/menu arrangement across screen sizes.
- Grouped Details metadata and Download information; moved search posting dates to a quiet footer.
- Simplified refresh controls and mirror availability/ranking presentation across all 14 themes.
- Standardized category/language/author/narrator search prefixes and concise, actionable user messages.
- Docker now installs locked runtime dependencies without development tools. Build context excludes local audit data.
- Release creation runs quality gates and explicitly publishes the versioned/latest image before creating the release.
- Added an accessible search-box clear control and moved filter reset into the Filters panel.
- Placed posting dates beneath metadata in list view while retaining the grid footer.
- Removed obsolete credential/timeout aliases, the unused `PAGE_LIMIT` setting and compatibility behavior before
  the first release.

- **User-Centric Client Terminology:** Replaced developer jargon "Strategy" across the codebase, tests, docstrings, and
  documentation with clear Download Client plugin names (`TorrentClientPlugin`, `QBittorrentClient`, `DelugeClient`,
  `TransmissionClient`, `PutioClient`, `CustomClient`), removing obsolete backwards-compatibility aliases prior to 1.0.
- **Diagnostics Mobile Interface:** Upgraded `/diagnostics` with responsive glass hero headers, fluid metric cards, and
  touch-friendly controls that adapt seamlessly to phone screens.
- **Layman-Friendly Documentation:** Completely updated `README.md` with clear, accessible guides for non-technical
  users, including deep dives into path mapping (`SAVE_PATH_BASE`), download client setups, and Audiobookshelf
  integration.
- **Architectural Reference Refresh:** Updated `AGENTS.md` and all guides in `docs/agents/` to reflect current
  configuration structures and invariants.
- **Responsive Design:** Optimized layout breakpoints for mobile devices (iPhone 13 mini through iPad Pro and desktops)
  ensuring stacked cards on small screens and fluid navigation.
- **CI / Workflows:** Configured `uv sync --all-extras` across GitHub Actions workflows to ensure development tools
  (`pre-commit`, `mypy`, `pytest`) are available on all runners.

### Fixed

- Accept catalog-relative book links when downloading from search results, including newly loaded grid/list cards.

- Connect Download Clients in each request thread and close their handles at request teardown; reject dispatch when
  no client is configured.
- Show qBittorrent stopped transfers as Paused and unavailable metadata sizes as Unknown.
- Normalize Diagnostics Inspector searches and enforce their minimum length; clamp log limits to the buffer capacity.
- Apply the existing scraper semaphore and request jitter to uncached Details requests.

- Use working catalog keyword searches for authors/narrators; normalize dotted initials and retain healthy mirrors
  when a search page returns 404.
- Show one inline loading indicator during pagination, and split narrator lists that include a full-cast credit.

- Isolated Download Client connections per request thread so cleanup cannot close another request's session.
- Corrected the default client host when its setting is empty, including Put.io cloud setup.

- Preserved every structured narrator/author and audio field before removing duplicate description headers.
- Corrected initial Status recovery, selected-client removal, refresh focus preservation and filter cancellation.
- Corrected theme contrast, search loading geometry/timers, mobile history layout and intro-to-banner handoff.
- Corrected repository/image links, Python module startup instructions, browser test server ports and release triggers.

- Replaced mock-page E2E checks with actual-template browser tests and responsive layout assertions.
- Fixed notification toast DOM class assignment and download button data attribute fallbacks.
