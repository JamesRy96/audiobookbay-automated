<!-- File: tests/AGENTS.md -->

# Independent QA & Test Harness Guide (`tests/`)

## 1. Test Execution Commands

Run tests inside the active project environment (`.venv` and local `node_modules`):

~~~bash
# Execute Python test suite with mandatory 100% coverage
uv run pytest

# Execute frontend JavaScript unit tests (Jest)
npm run test:js -- --runInBand

# Execute Playwright E2E browser checks across Chromium, Firefox, and WebKit
npm run test:e2e

# Run full repository static analysis, linting, and typing checks
pre-commit run --all-files
~~~

## 2. Test Harness Architecture & Fixture Conventions

- **Pytest Fixtures (`tests/conftest.py`):**
  - Isolates tests from live external networks and live torrent clients.
  - Core fixtures: `TestConfig`, `mock_global_dependencies`, `mock_sleep`, `app`, and `client`.
  - External network calls must be mocked; never dispatch requests to real internet hosts.
- **E2E Browser Test Server (`tests/e2e/server.py`):**
  - Runs on port 5090 using `BrowserConfig`, `CatalogTransport`, `IsolatedQbitSDK`, and `IsolatedTransmissionSDK`.
  - Uses real production HTML templates, CSS stylesheets, and client-side JavaScript controllers.
  - Replaces only external integration boundaries (torrent client RPC and remote catalog scraping).

## 3. Strict 100% Coverage & Quality Gates

- **Mandatory 100% Coverage:** Pytest enforces `--cov-fail-under=100` on line and branch coverage. Any drop in
  coverage triggers an immediate build failure.
- **Strict Typing:** All test support code and mock harnesses must satisfy Basedpyright standard/strict typing.

## 4. Anti-Vaporware QA Checklist

Before certifying test passes, validators must verify:

- **Semantic Behavior Verification:** No skipped tests, empty assert stubs, or placeholder `pass` statements.
- **Authentic Routing & UI Wiring:** Validate that real routes, status codes, and browser DOM elements are exercised.
- **Zero Live Hardware Dispatch:** Automated test suites must never connect to live torrent clients or modify user data.

## 5. Artifact Output Contract

- Test results and QA summaries must be written to `.agents/reports/<TASK_ID>.md`.
- Detailed test outputs, coverage summaries, or trace logs must be stored under `.agents/reports/<TASK_ID>/`.
