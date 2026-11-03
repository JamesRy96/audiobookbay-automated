<!-- File: docs/agents/testing-quality.md -->

# Testing & Code Quality Standards

## Quality Gates & Tooling

- 100% Test Coverage: Strictly enforced with `--cov-fail-under=100`.
- Type Checking: Dual validation via MyPy and Pyright in strict mode. Use Python 3.12+ generic syntax
  (`def fn[T](x: T) -> T`).
- Linting & Security: Enforced via Ruff (`ruff check`, `ruff format`).
- Docstrings: Google style conventions strictly checked with `pydocstyle`. All test functions and classes require
  docstrings.

## Test Suite Principles

- Fixtures and contexts: Shared fixtures reside in `tests/conftest.py`. App context is pushed automatically.
- No redundant test files: Consolidate new test cases into existing domain suites (`tests/functional/test_api.py`,
  `tests/scraper/test_network.py`) rather than introducing one-off files.
- Mocking: Always mock network calls and `time.sleep`.
- Frontend Tests: Executed with Jest and JSDOM (`npx jest`). Load scripts via `eval()` in `jest.setup.js`.
- Fake-timer tests must use awaited `jest.advanceTimersByTimeAsync` to settle asynchronous work; do not flush promises
  using real timers. Check immediate refresh, exact poll boundaries, pending requests, pause/resume and retries, and
  clear scheduled work in teardown even when assertions fail.

## Browser and Release Checks

- `npm run test:e2e` starts the isolated Flask fixture through Playwright on 127.0.0.1:5090. Tests render the actual
  templates, styles and JavaScript in Chromium, Firefox and WebKit. For Download contracts, replace only catalog HTTP
  transport and Download Client SDKs. Run the real parser, core search/Details/magnet extraction, routes, manager and
  client adapter. Never replace those steps with unconditional successful return values.
- Multi-client cases must verify per-client connectivity, disabled offline choices, correct dispatch/removal routing,
  single-client direct dispatch and optional destination settings.
- Client unit contracts must also execute the installed SDK against an isolated HTTP boundary, using documented
  request/response shapes. Browser SDK doubles alone cannot prove API arguments, authentication or serialization.
- The isolated browser fixture uses advancing monotonic signing time to avoid development-VM clock rollback.
  Keep application signatures and expiration enabled; separately test rejection of expired and future-dated tokens.
- Captured catalog inputs live under `tests/e2e/catalog/captured/`, with source URLs and capture metadata. Preserve
  encoded `post re-ab` listings, duplicate/list trackers, punctuation, cast and description markup. Synthetic pages
  remain for deterministic layout/screenshots and deliberate errors. Unknown fixture URLs must fail, never select
  a default book. Keep captured corpus content outside spelling/formatting rewrites.
- A successful toast or HTTP 200 is insufficient for Download tests: assert the selected task's actual hash, title,
  destination/category and dispatch count at the isolated SDK boundary, then observe it through Downloads. Verify
  cancellation has no effects and removal preserves files. Include initial/appended grid/list cards, absolute and
  relative paths, Details, rejection/retry, missing hash, expired CSRF and exact external navigation after confirmation.
- CI fails on recovered flaky browser tests as well as final failures; retries retain diagnostic evidence without
  turning an unstable run green.
- Reset isolated client/cache state before each browser case. Fail on JavaScript exceptions and attach isolated client
  effects/security failure reasons to failed tests without logging tokens or cookies. External browser traffic is
  blocked except a test's explicit intercepted destination; CI never uses live user credentials.
- Reproduce the defect before fixing it and verify a regression rejects the faulty implementation. Negative controls
  belong in an isolated checkout, not application flags that bypass validation. Passing coverage alone does not prove
  URL/data contracts or integration success.
- Cover missing credits, pagination/filter state, concise validation, metadata cleanup, equal actions, responsive
  header alignment, menu focus and refresh controls. Keep failure screenshots/traces as CI artifacts.
- Refresh default-theme README images with real catalog results and loaded covers using `npm run screenshots`;
  follow `docs/development.md`. Review client data for privacy and never submit downloads just to populate images.
- Pre-commit checks Markdown with markdownlint and tilde fences; Prettier handles code/templates including TypeScript.
- For release changes, validate workflow syntax, the lockfile, Compose examples, the built wheel and the container's
  HTTP health endpoint. GitHub publishing/deployment remain explicit actions; local checks do not prove a remote run.

- Workflow validation must include embedded shell scripts. Ensure ShellCheck is installed, then run
  `actionlint -shellcheck shellcheck`. A local actionlint run without ShellCheck does not match CI's container check.

## Live verification and readiness claims

Record simulated-boundary checks separately from real integrations. A live search HTTP 200 with an empty list only
proves the application returned that shape. Before claiming source parity, compare independently observed native
mirror listings with parsed results, record the exact query/URL and compare distinct book links. Account for the
mirror form's query truncation/rewriting and JavaScript-decoded posts. Retry isolated transport failures in a bounded
way and report unresolved cases. Do not classify an empty response as catalog absence without source evidence.

For authorized live Download tests, click the actual initial/appended search card and Details controls, observe the
new task in the real client, and record hash, destination, category, cancellation/removal effects and cleanup state.
Inspecting a button or testing a manually constructed absolute link does not prove the search-card flow. Do not
claim full transfer completion, other client compatibility or absence of all defects without that evidence.
