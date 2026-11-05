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

## Build a test image from any branch

For a published test image, use GitHub **Actions → Build test image → Run workflow**:

1. Leave **Use workflow from** set to `main`.
2. In **Branch, tag or commit to build**, enter your source branch name, tag or full commit SHA.
3. Select **Run workflow** and wait for the build to finish.
4. Open that run's **Summary**. Copy its `docker pull` command or image reference.
5. Put that image reference in your test installation's `compose.yaml` under `image:`, then run:

~~~shell
docker compose pull
docker compose up -d
~~~

This builds the selected source without a release version, changelog entry, Git tag or GitHub Release. Test images
contain the normal app built from that source's Dockerfile; they do not add sample data or configure your Download
Client. Use your test installation's own `.env` settings.

Each build publishes a branch-specific `test-...` tag and a `test-sha-<full-commit-sha>` tag. The branch tag includes a
short suffix so similarly named branches remain distinct; rebuilding that ref updates its branch tag. The commit
tag identifies the exact source revision. Neither tag updates `latest` or a release version. All image references
appear in the run summary so you do not need to calculate the tag names.

The manual workflow must first exist on the repository's default branch. Running its definition from `main` lets it
build branches that predate this workflow. Invalid or unavailable refs fail at checkout. You need repository write
access to start a build and permission to pull the GHCR package if it is private.

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

The isolated fixture uses a monotonic advancing signing clock so VM clock corrections cannot invalidate freshly
created test sessions. It retains real CSRF/session checks; production signing behavior is unchanged. Failed runs
record security failure reasons without cookie or token values.

To refresh README screenshots, run a local app with the default branding and a real catalog connection. Configure
its proxy and Download Client using the settings in [configuration.md](configuration.md), then run in another terminal:

~~~shell
npm run screenshots
~~~

The capture script defaults to `http://127.0.0.1:5078` and a `dune` search. All three images use the same
1440 × 1100 browser viewport, without content-specific crops, and must have identical computed theme backgrounds.
It opens Search, a returned Details link and
Downloads without clicking Download or Remove. It requires decoded covers for every first-row search card and the
Details artwork; failed image loads must be corrected before using the screenshots.

Optional environment variables are `SCREENSHOT_BASE_URL`, `SCREENSHOT_QUERY`, `SCREENSHOT_DETAILS_LINK` (the app's
`/details?link=...` URL), and `SCREENSHOT_PROXY` for browser cover requests. The browser proxy bypasses localhost.
The Python app's proxy settings are separate and must also be configured. `PLAYWRIGHT_CHROMIUM_CHANNEL=chrome`
selects installed Chrome. Use default branding, review the complete `docs/images/` images, and check that no private
client information appears before committing. An empty Downloads view is valid when no matching tasks exist; do not
start a download merely to populate a documentation screenshot. Isolated fixtures remain for browser regression tests.

For the upstream issue inventory, client API references and verification limits, see the
[November 2026 upstream review](agents/upstream-review-2026-11-03.md).

## CI and release flow

- **CI** runs formatting/types, both Python versions, Jest, real-template browser tests, and a Docker build/HTTP smoke test.
- **Browser tests** is called by CI and can also be run manually from Actions. It does not create a duplicate run on
  every push.
- **Create Release** is a manual workflow. It validates the version and default branch, runs CI on that commit, calls
  the image publishing workflow, then creates the GitHub tag and release for the checked commit.
- **Build test image** publishes separate test tags from a chosen source ref, without creating a release.
- The release image workflow publishes `ghcr.io/<repository>:<version>` and `:latest`. It is called directly rather
  than relying
  on a token-created tag to trigger another workflow.

Before publishing:

1. Review the working changes and screenshots. Complete any live integration/container checks that could not run locally.
2. In GitHub **Actions → Create Release → Run workflow**, select the default branch and enter the target release
   version without `v` (for example `1.0.0`).
3. The workflow automatically stamps today's date in `CHANGELOG.md`, synchronizes `pyproject.toml` and `uv.lock`, commits
   the release preparation to the default branch, runs the full test matrix, publishes the Docker image, and creates the
   GitHub Release with generated release notes.
4. Check the new release and make the GHCR package public if anonymous pulls are intended. Verify a clean installation
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
