<!-- File: docs/agents/upstream-review-2026-11-03.md -->
# Upstream issue and client API review — November 3, 2026

Reviewed all 14 open items in `JamesRy96/audiobookbay-automated`: nine issues and five pull requests, including issue
comments, PR descriptions and file changes. The linked reports describe the upstream application; they are evidence
to investigate, not proof that this fork has the same fault. No upstream PR was merged or copied wholesale.

## Open-item disposition

| Upstream item | Disposition in this fork | Evidence or limitation |
| --- | --- | --- |
| [#3 Portainer/Gluetun deployment](https://github.com/JamesRy96/audiobookbay-automated/issues/3) | Compose examples validate; added shared-network and empty-ports guidance. | Client timeouts and proxy bypass are documented. Deployment-specific VPN/DNS failures remain possible. |
| [#12 Selectable mirrors](https://github.com/JamesRy96/audiobookbay-automated/pull/12) | Primary/additional mirrors and automatic verified fallback already exist. | Mirror tests cover failover and TLS-to-HTTP probing. No insecure certificate-verification override or per-search selector was added. |
| [#18 Search internal error](https://github.com/JamesRy96/audiobookbay-automated/issues/18) | Quoted single hostnames are already stripped; friendly errors already exist. Fixed a later page transport failure being cached as no results. | DNS/timeout regressions now raise; genuine empty/404 pages remain empty. Cannot repair an external DNS outage. |
| [#19 Multiple downloads](https://github.com/JamesRy96/audiobookbay-automated/issues/19) | Independent buttons and nonblocking notifications already exist. | Added a browser test holding the first request while dispatching another book; assert both exact hashes and two dispatches. |
| [#20 Logging and feedback](https://github.com/JamesRy96/audiobookbay-automated/pull/20) | Configured logging, per-button pending states and notifications already cover the reported flow. | Existing tests cover failure/retry and correct client effects. A separate Recently Added panel is not required for dispatch. |
| [#21 Catalog IP blocking](https://github.com/JamesRy96/audiobookbay-automated/issues/21) | One-page progressive search, jitter, semaphore, local route limits and failure backoff replace the old five-page burst. | These mitigate traffic; they cannot make remote IP blocks impossible. Added explicit recovery guidance. |
| [#22 Hardcoded bind](https://github.com/JamesRy96/audiobookbay-automated/issues/22) | Configurable host/port and automatic container IPv6 detection already exist. | Expanded entrypoint tests for IPv4, bracketed IPv6 and custom ports while retaining one worker. |
| [#28 Hostname/fallback fixes](https://github.com/JamesRy96/audiobookbay-automated/pull/28) | Quote handling, verified mirrors and concise errors already exist. | Existing configuration/network regressions plus new transport-failure assertions; no root-HTTP-200-only probe was adopted. |
| [#29 Deluge never starts](https://github.com/JamesRy96/audiobookbay-automated/issues/29) | New Deluge transfers explicitly request `add_paused=false`. | Real SDK serialization test verifies the option. Queue settings, peers and daemon state can still prevent progress; no live Deluge transfer was tested. |
| [#33 Deluge API 2.0](https://github.com/JamesRy96/audiobookbay-automated/issues/33) | Existing typed magnet options implement the linked PR #32's API correction. Fixed URL forwarding, core Label detection, timeout and cleanup gaps. | Real SDK JSON-RPC tests cover login, daemon plugins, magnet/options, labels, status and file-preserving removal. |
| [#34 Put.io](https://github.com/JamesRy96/audiobookbay-automated/pull/34) | Put.io adapter already exists; fixed list-response API errors appearing healthy/empty. | HTTP-boundary tests verify bearer auth, form fields, target folder, progress, errors and cancellation without file deletion. |
| [#36 Unsupported client on Unraid](https://github.com/JamesRy96/audiobookbay-automated/issues/36) | Report uses the obsolete upstream `DOWNLOAD_CLIENT` variable. This fork requires documented `DL_CLIENT=qbittorrent`. | Missing `DL_CLIENT` fails startup validation; no compatibility alias added. Correct Unraid setting is now explicit. |
| [#38 Container health](https://github.com/JamesRy96/audiobookbay-automated/issues/38) | Docker health check already uses the dedicated `/health` route. | Python health-check tests cover success/failure and configured bind/port. This is app liveness, not client/catalog health. |
| [#39 curl/healthcheck](https://github.com/JamesRy96/audiobookbay-automated/pull/39) | Equivalent health capability already exists using Python. | No extra curl package is needed. CI builds the container and checks HTTP health. |

## All four Download Clients

[The plugin guide](torrent-clients.md#api-references-and-compatibility-evidence) links the primary API references.
The reviewed locked libraries are `qbittorrent-api 2026.10.1`, `transmission-rpc 7.0.12` and
`deluge-web-client 2.1.1`. Contract tests run the real installed libraries, replacing HTTP transport rather than
accepting arbitrary SDK method arguments. Put.io uses the actual adapter with an isolated HTTP boundary.

Additional findings: qBittorrent now honors `QBITTORRENT_SCHEME` without SDK scheme guessing; Transmission now closes
its HTTP
pool. Deluge plugin observations are thread-local. Deluge and Transmission do not retry an add without labels after
an error; a label failure can occur after acceptance, so inspect the client before manually resubmitting.

The real qBittorrent v5.3.0 instance passed read-only version/list/status checks for three existing tasks using the
updated adapter. No task was added, removed or changed in this review. Live Deluge, Transmission and Put.io instances
were not available; their network reachability, daemon/account configuration and completed transfers are unverified.
Transmission's current specification retains the old RPC within version 4; future removal requires an SDK upgrade.

## Release interpretation

A passing suite establishes the exercised contracts, not absence of every bug or every possible deployment failure.
Preserve the full Python coverage, JavaScript, three-engine browser, static/type, workflow and container CI gates.
Browser retries do not turn failures green: recovered flaky tests fail the gate. Keep the test traces when diagnosing
such failures and do not change application security without a reproduced root cause.

Initial Windows and Linux WebKit runs had recovered CSRF failures; the gate correctly failed those runs. The server
received a session cookie but could not recover its CSRF token. Independent sampling measured this WSL development
clock stepping backward by about 2.47 seconds. A controlled application test reproduces rejection after a two-second
rollback and separately verifies rejection of an expired token.
A subsequent failing request explicitly logged `SignatureExpired: Signature age -1 < 0 seconds`. This confirms
clock rollback for that failure; it
is not proof that every previous failure had the same cause.

The isolated browser fixture now derives its signing timestamps from a wall-clock origin plus monotonic elapsed
time. Signatures, session validation and token expiry remain enforced; application runtime security is unchanged.
Security failure diagnostics record the reason and cookie presence, never cookie/token values. Clock stabilization
addresses the measured test-environment hazard without adding retry-until-green behavior or weakening the CI gate.

Before publishing a release, merge reviewed changes, require the hosted CI results on that commit, choose the release
version and dated changelog, and validate the published image installation. Local Docker execution was unavailable in
this review. No release or deployment was performed.

## Completed local checks

- Python 3.13 and 3.14: 489 tests passed per version, with 100% application coverage.
- JavaScript: 93 tests passed.
- Final Linux browser run: 87 checks passed across Chromium, Firefox and WebKit, with no retries.
- Full pre-commit, strict MyPy/Pyright, explicit ShellCheck-backed actionlint and Compose example validation passed.
- All 27 local Markdown links/anchors passed validation; the wheel built with all four adapters, templates and assets.
- Updated qBittorrent adapter: live read-only authentication/version/status checks passed for three existing tasks.

The failed initial runs and clock-rollback diagnosis remain part of the evidence above. These results do not claim
that unconfigured real Download Clients, every external catalog response or published-image installation were tested.
