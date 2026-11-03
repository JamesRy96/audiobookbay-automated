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

## Browser and Release Checks

- `npm run test:e2e` starts the isolated Flask fixture through Playwright on 127.0.0.1:5090. Tests render the actual
  templates, styles and JavaScript in Chromium, Firefox and WebKit. Mock integration boundaries, not page HTML.
- Cover missing credits, pagination/filter state, concise validation, metadata cleanup, equal actions, responsive
  header alignment, menu focus and refresh controls. Keep failure screenshots/traces as CI artifacts.
- Run `npm run screenshots` against the isolated fixture to refresh default-theme documentation images. Never use
  personal Download Client data in checked-in screenshots.
- Pre-commit checks Markdown with markdownlint and tilde fences; Prettier handles code/templates including TypeScript.
- For release changes, validate workflow syntax, the lockfile, Compose examples, the built wheel and the container's
  HTTP health endpoint. GitHub publishing/deployment remain explicit actions; local checks do not prove a remote run.

- Workflow validation must include embedded shell scripts. Ensure ShellCheck is installed, then run
  `actionlint -shellcheck shellcheck`. A local actionlint run without ShellCheck does not match CI's container check.
