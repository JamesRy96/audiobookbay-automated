<!-- File: docs/development.md -->
# Development, testing and releases

For the normal installation and daily use, start with [README.md](../README.md). This guide covers changing the app,
building from source, testing and publishing.

## Run from source

Install Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Node.js 24. From a terminal:

~~~shell
git clone https://github.com/meek2100/audiobookbay-automated.git
cd audiobookbay-automated
uv sync --frozen --all-extras --python 3.14
npm ci
~~~

Copy `examples/.env.example` to `.env` and enter your settings. Start from the repository root:

~~~shell
uv run --env-file .env python -m audiobook_automated.app
~~~

Open <http://localhost:5078>. This is Flask's development server; keep it local. Running the file as
`python audiobook_automated/app.py` does not support its package-relative imports. The Python app reads environment
variables; `uv run --env-file` loads the settings file for this command.

## Run the container from source

Docker with Compose is required. From the configured checkout above:

~~~shell
docker build -t audiobookbay-automated:local .
docker run --rm --name audiobookbay-local --env-file .env -p 5078:5078 audiobookbay-automated:local
~~~

This builds the app with locked runtime dependencies. It does not require an already published image. The normal
release image contains no test fixture server, sample browser data, development dependencies, or local `.agents` files.
The container runs Gunicorn with one worker and eight threads by default. Do not add workers; rate limits and scraper
coordination are process-local.

## Checks

~~~shell
uv run --frozen --all-extras pytest
npm run test:js -- --runInBand
uv run --frozen --all-extras pre-commit run --all-files
~~~

Python tests require 100% application coverage. CI runs Python 3.13 and 3.14. Pre-commit also checks types, shell,
Dockerfile, Compose examples, Markdown and formatting. Docker Compose must be installed for its validation hook.
The branch-protection hook rejects commits on `main`; use a working branch. CI skips only that local branch hook.

Markdown uses tilde code fences and markdownlint. Prettier handles CSS, JavaScript, TypeScript, templates and settings;
it skips Markdown to preserve the fence convention.

## Real-template browser tests

~~~shell
npx playwright install --with-deps
npm run test:e2e
~~~

Playwright starts and stops `tests/e2e/server.py` on **127.0.0.1:5090**, then checks Chrome/Chromium, Firefox and WebKit.
It serves actual application templates, styles and controllers. Only catalog data and Download Client integrations
are replaced; it does not substitute page HTML or send live downloads. Port 5090 must be free.

`E2E_SERVER_COMMAND` can override the fixture launch command for a mixed Windows/WSL development environment.
`PLAYWRIGHT_CHROMIUM_CHANNEL=chrome` selects an installed Chrome instead of Playwright's bundled Chromium. CI uses
the bundled browsers. These are development options, not Docker installation settings.

To refresh the README screenshots, start the fixture server in one terminal:

~~~shell
uv run --frozen --all-extras python tests/e2e/server.py
~~~

In another terminal, run `npm run screenshots`. Review the resulting `docs/images/` files before committing. The
screenshots show fictional example books using the default theme, not personal catalog or Download Client data.

## CI and release flow

- **CI** runs formatting/types, both Python versions, Jest, real-template browser tests, and a Docker build/HTTP smoke test.
- **Browser tests** is a reusable workflow called by CI, so it does not produce a second independent run for every push.
- **Create Release** is a manual workflow. It validates the version and default branch, runs CI on that commit, calls
  the image publishing workflow, then creates the GitHub tag and release for the checked commit.
- The image workflow publishes `ghcr.io/<repository>:<version>` and `:latest`. It is called directly rather than relying
  on a token-created tag to trigger another workflow.

Before publishing:

1. Review the working changes and screenshots. Complete any live integration/container checks that could not run locally.
2. Choose a stable version, such as `1.0.0`. Set it in `pyproject.toml`, run `uv lock`, and add a dated `CHANGELOG.md`
   section for that version. Keep a new `[Unreleased]` section for future work. The private JavaScript test package is
   not separately released.
3. Commit and push the reviewed changes to the default branch through the repository's normal review process.
4. In GitHub **Actions → Create Release → Run workflow**, select the default branch and enter the version without `v`.
5. Wait for all checks and image publishing to finish. The workflow refuses a mismatched version or existing version tag.
6. Check the new release and make the GHCR package public if anonymous pulls are intended. Verify a clean installation
   using the README and the published image.

The workflow needs permission to write repository contents for the release and packages for GHCR. A failed check does
not publish an image. If image publishing succeeds but release creation fails, inspect that run before retrying; do not
move or overwrite a released version. Publishing is separate from deploying the image to a user's server.

## Design and user-facing text

Use short errors that explain the problem and next action. For example, **Enter at least 2 characters.** Avoid reporting
the user's current character count, speculating about causes, exposing raw exceptions in normal mode, or promising
that a book will appear in an integration that is not configured. Keep technical details in logs/debug views.

For another Download Client, follow the [plugin implementation guide](agents/torrent-clients.md). It covers discovery,
configuration, methods, thread-isolated connections, status normalization and tests.

See [AGENTS.md](../AGENTS.md) and [subsystem guides](agents/architecture.md) before changing scraper behavior, concurrency
or Download Client interfaces.

Pagination uses an IntersectionObserver with a 300px viewport margin. While idle, the same next-page function can be
called by the manual button. Requests cannot overlap; an error stops automatic retries until the user retries. Browsers
without IntersectionObserver use the manual button. An empty page exhausts the search. Filters affect loaded rows only.
