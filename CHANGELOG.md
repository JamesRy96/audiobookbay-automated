<!-- File: CHANGELOG.md -->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-04

### Added

- **Multi-Client Routing & Management:** Simultaneous support for qBittorrent, Deluge, Transmission, and Put.io cloud
  downloads via `DL_CLIENT` (comma-separated list), with unified cross-client status aggregation and independent
  uppercase connection configurations.
- **Modern Responsive Web Interface:** Completely redesigned, mobile-first responsive frontend featuring:
  - Both Grid View and List View result displays with high-resolution responsive covers.
  - 14 user-selectable modern color themes (`purple`, `crow`, `catppuccin`, `nord`, `tokyo`, `oled`, `forest`,
    `ocean`, `sunset`, `dracula`, `cyberpunk`, `light`, `royal`, `slate`).
  - Animated introductory splash screen that transitions seamlessly into the header banner.
  - Dedicated book Details view with rich metadata, chapter/cast breakdowns, and technical tracker inspectors.
  - Floating controls, auto-refresh toggles, and countdown controls for active downloads.
  - Contributor search and filtering across author, narrator, category, and language taxonomy feeds.
- **Live System Diagnostics Suite:** Built-in health dashboard and scraper inspector at `/diagnostics` (enabled via
  `ENABLE_DIAGNOSTICS=true` or debug mode) with memory, process, mirror latency, and client connection analytics.
- **Robust Scraper & Mirror Engine:**
  - Automated mirror failover probing HTTPS first and HTTP fallback with Exponential Moving Average (EMA) latency
    ranking.
  - Shared concurrency rate-limiting (`GLOBAL_REQUEST_SEMAPHORE`) and configurable jitter delays (0.3–0.8s
    default, tuned via `SCRAPER_JITTER_MIN` / `SCRAPER_JITTER_MAX`) on all external catalog requests.
  - Support for dynamic mirror synchronisation via remote catalog lists and customizable tracker overrides
    (`examples/trackers.json`).
- **Network Security & Reverse Proxy Architecture:**
  - Optional `PUBLIC_URL` setting for single public browser origin deployments with automatic HTTPS cookie handling.
  - Strict proxy header validation via `TRUSTED_PROXIES` allowlisting.
  - Automatic cryptographic session and CSRF key generation with zero setup overhead.
  - Client-independent startup ensuring web service availability even when torrent daemons are offline.
- **Comprehensive Quality & Testing Infrastructure:**
  - 100% Python test coverage enforced on Python 3.13 and 3.14 (`pytest`, `mypy`, `pyright`, `ruff`).
  - Frontend JavaScript unit test suite (`jest`).
  - Multi-browser end-to-end integration test suite (`playwright` covering Chromium, Firefox, and WebKit) using real
    templates.
  - Automated GitHub Actions CI, dependabot schedules, and multi-architecture Docker build workflows.

### Changed

- Re-architected application package structure from legacy monolithic `app/app.py` into modular package
  `audiobook_automated/` with clean separation of clients, scraper network/parser, web security, and route blueprints.
- Migrated dependency management to `uv` and `pyproject.toml` with frozen lockfile support.
- Replaced legacy hardcoded credentials with case-insensitive environment variable lookup and client-prefixed settings.
- Defaulted client target save paths to client daemon configurations with optional cross-platform path normalization
  (supporting Windows drives and SMB network paths inside Linux containers).
- Removed raw network calls and unconfigured printing in favor of structured logging and centralized request
  management.

### Removed

- Removed legacy single-file scripts and unmaintained vendor JS/CSS dependencies.
- Removed hardcoded mirror lists and deprecated monolithic routes.
