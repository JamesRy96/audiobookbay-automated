<!-- File: docs/agents/torrent-clients.md -->
# Download Client plugins

This guide is for developers adding another Download Client. Users of the prebuilt image should follow the
[normal client setup](../configuration.md#download-clients). A new plugin becomes available to those users after it is
included in a rebuilt/released image; copying a Python file beside `.env` does not install a plugin.

## How discovery works

1. Copy [client_template.py](../../audiobook_automated/clients/client_template.py) into the same directory with a
   lowercase module name, such as `rtorrent.py`. Update its `File:` header, class name and real `DEFAULT_PORT`.
2. Implement the API using a concrete subclass of `TorrentClientPlugin`. Keep one concrete plugin class per module;
   do not import another concrete plugin into it, because discovery scans the module's classes.
3. Set `DL_CLIENT=rtorrent` in the development `.env`. `TorrentManager` imports
   `audiobook_automated.clients.rtorrent` automatically; no plugin registration list is required.
4. Add any SDK dependency to `pyproject.toml` and update `uv.lock`. Rebuild the image after the plugin and tests pass.

Use the existing qBittorrent, Transmission, Deluge and Put.io modules as working API adapters. The template is a
starting scaffold and deliberately cannot connect or send downloads until its API methods are implemented.

## Configuration contract

The manager supplies `host`, `port`, `username`, `password`, `scheme` and `timeout` from the client's entry in
`Config.CLIENT_CONNECTIONS`. Document environment names with the uppercase plugin name, such as `RTORRENT_HOST` and
`RTORRENT_PASSWORD`. Name lookup is case-insensitive through `environment.get_env`; values retain their case, and
conflicting duplicate spellings fail without revealing values. If the client's port is unset, it uses the plugin's
`DEFAULT_PORT`. Current extra keyword
arguments are `api_key`, `token` and `folder_id`. Accept unused keyword
arguments so the common constructor works for every client, and call `super().__init__()`.

If a client needs a new setting, add a typed parser in `Config`, pass its value through the common construction path,
and document it in the configuration guide and settings example. An arbitrary new `.env` name is not automatically
forwarded to plugins. Keep client-specific API behavior in the plugin, not in `TorrentManager` or Flask routes.
The common construction path also forwards `DELUGE_URL` as the optional Deluge `dl_url` argument.
The parser accepts the standard suffixes `HOST`, `PORT`, `USERNAME`, `PASSWORD`, `SCHEME`, `TIMEOUT`, `API_KEY`,
`TOKEN`, `FOLDER_ID`, `SAVE_PATH_BASE` and `URL` for configured plugins; new suffixes require an explicit
parser/manager change.

`DL_CLIENT` accepts one plugin name or comma-separated names; the first is the default. Each plugin has independent
connection settings. There are no shared credential aliases or implicit password-to-token conversions. The chooser
checks each client separately; an explicitly selected unknown/offline client must never fall back to another client.

## Implement the interface

| Method | Required behavior |
| --- | --- |
| `connect() -> None` | Establish or reuse this thread's authenticated connection. Apply the configured scheme and timeout. Raise on failure. |
| `close() -> None` | Release this thread's handles and set them to `None`. Be safe when called repeatedly or after a partial connection failure. |
| `add_magnet(magnet_link, save_path, category) -> None` | Send the URI, optional destination and category/label to the client. Omit the destination from the remote request when `save_path` is `None`. Raise if rejected; returning `False` does not report a failed dispatch. |
| `remove_torrent(torrent_id) -> None` | Remove the download task without deleting its files. Raise if it cannot be removed. |
| `get_status(category) -> list[TorrentStatus]` | Return normalized records for the requested category/label. Filter locally if the API cannot filter on the server. |

The inherited `verify_credentials()` calls `connect()` and returns a boolean. Override it only if a lighter check can
prove that the configured credentials work. An unreachable or unauthenticated client must not report success.
Before dispatch, status or removal, the manager connects the current thread when both transport handles are absent.
It registers application-context teardown to release that thread's connection at the end of the request. Repeated
operations within one request reuse the handle; startup verification does not connect future request threads.
The inherited `teardown()` calls `close()` after a web request. Override it only for a documented, thread-isolated
connection lifecycle. Never close or log out another request's connection.

## Thread and network safety

`TorrentManager` holds shared plugin objects, but their inherited **client** and **session** properties store connection
handles separately for each thread. Put SDK connections in `self.client` and HTTP sessions in `self.session`; the base
class supplies their isolation. Do not replace those properties with class attributes or a shared global session.
Any additional mutable transport state also needs thread-local storage or synchronization. Keep configuration values
immutable while requests run.

Use explicit timeouts and close resources. Do not add unrestricted background pools or bypass scraper concurrency.
Catalog traffic must continue through the scraper network layer with its jitter and semaphore. Tests must mock SDK
and network boundaries; never use a real account, live download, or user directory in automated tests.

`SAVE_PATH_BASE` is optional; client-prefixed roots override it. Without either, preserve the client's own default
folder. An explicit root belongs to the Download Client. The plugin sends that destination; the web container must not
create,
mount, or change ownership of the client's download folder. Removal must preserve the files.

## Normalize status records

Use the actual ID needed by the client's removal API. Progress is a percentage from `0.0` to `100.0`, not a fraction.
Use `format_size` for byte counts and a canonical `TorrentState` where possible:

~~~python
# File: status_mapping_example.py
from audiobook_automated.clients.base import TorrentState, TorrentStatus
from audiobook_automated.utils import format_size

status = TorrentStatus(
    id="client-task-42",
    name="An Example Audiobook",
    progress=42.0,
    state=TorrentState.DOWNLOADING,
    size=format_size(104857600),
    category="abb-automated",
)
~~~

`TorrentStatus` also normalizes known client state strings. Use a clear state for unknown or metadata-only transfers.
The manager assigns the configured client identifier during aggregation; the UI uses it to route removal correctly.
Do not confuse an uploader/category label with the human author of the book.

Existing adapters convert progress as follows: qBittorrent fractions are multiplied by 100; Transmission, Deluge and
Put.io already provide percentages. qBittorrent can return string or JSON responses to an add request. Deluge's Label
plugin is optional, so absence of the plugin must be handled explicitly. Put.io accepts an OAuth token from
`PUTIO_TOKEN` and an optional target folder ID.

## Test and ship the plugin

Add tests beside the existing adapters in `tests/unit/clients/`. Mock the SDK constructor and responses. Cover:

- Successful connection, bad credentials, timeout/unavailable server and safe repeated cleanup.
- Correct magnet, destination, category and timeout arguments; failed dispatch raises an error.
- Task removal with file deletion disabled, including an invalid or unknown task ID.
- Progress units, size formatting, state mapping, empty results and category filtering.
- Overlapping requests: cleanup in one thread must leave the other thread's connection usable.
- Automatic discovery, default-port selection and any additional settings in the manager/configuration tests.

Run the full Python suite with 100% coverage, strict type checks and pre-commit. Add an isolated browser fixture if the
new client changes UI behavior. Test a rebuilt container against a disposable client account before publishing, and
update the supported-client list, setup notes and changelog once the integration is verified.

The success message should say the book was sent to the Download Client. An optional Audiobookshelf scan does not
prove that a file has been downloaded or imported into that library.

## API references and compatibility evidence

Review these primary sources when changing an adapter, and validate serialization through the real installed SDK
at its HTTP boundary. A mock accepting a Python method call does not establish the remote API contract.

| Client | Primary API reference | Contract to preserve |
| --- | --- | --- |
| qBittorrent | [Web API 5.x](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-%28qBittorrent-5.0%29), [API keys](https://github.com/qbittorrent/qBittorrent/wiki/API-Key-Authentication-%28%E2%89%A5v5.2.0%29) | `urls`, `savepath`, category; fractional progress; delete with `deleteFiles=false`; configured HTTP/HTTPS |
| Transmission | [4.0.6 RPC](https://github.com/transmission/transmission/blob/4.0.6/docs/rpc-spec.md), [current RPC](https://github.com/transmission/transmission/blob/main/docs/rpc-spec.md) | Session-ID negotiation; labels; destination; percentage conversion; removal without local data |
| Deluge | [2.x Web JSON-RPC](https://deluge.readthedocs.io/en/deluge-2.0.5/reference/webapi.html), [core RPC](https://deluge.readthedocs.io/en/deluge-2.0.5/reference/api.html) | Magnet plus options; daemon `core.get_enabled_plugins`; Label assignment; `remove_data=false` |
| Put.io | [API](https://api.put.io/v2/docs), [vendor transfer implementation](https://github.com/putdotio/go-putio/blob/master/transfers.go) | Bearer authentication; form `url`/`save_parent_id`; `percent_done`; transfer cancellation without file deletion |

Transmission 4.1 introduces JSON-RPC 2.0 and snake_case, while its specification retains the older protocol within
Transmission 4. The pinned Python SDK currently uses that older protocol; do not claim compatibility with a future
server that removes it. Keep protocol upgrades in the adapter/SDK rather than adding URL/field aliases in UI code.

Deluge's `web.get_plugins` reports Web UI plugins, not the daemon's enabled plugins. Query the core list for Label
support. Store that observation per thread, pass `CLIENT_TIMEOUT` to every SDK request, and close the SDK session
without disconnecting other Web UI users from their daemon.

Put.io's HTML API guide was not retrievable during the November 3, 2026 review; the vendor-maintained transfer client
provided the endpoint and form-field reference. HTTP-boundary tests are not substitutes for a live account test.
See [the upstream review](upstream-review-2026-11-03.md) for the issue inventory and remaining live-verification limits.
