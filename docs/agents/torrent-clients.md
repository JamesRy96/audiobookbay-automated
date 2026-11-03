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

The manager supplies `host`, `port`, `username`, `password`, `scheme` and `timeout`. If `DL_PORT` is unset, it uses the
plugin's `DEFAULT_PORT`. Current extra keyword arguments are `api_key`, `token` and `folder_id`. Accept unused keyword
arguments so the common constructor works for every client, and call `super().__init__()`.

If a client needs a new setting, add a typed parser in `Config`, pass its value through the common construction path,
and document it in the configuration guide and settings example. An arbitrary new `.env` name is not automatically
forwarded to plugins. Keep client-specific API behavior in the plugin, not in `TorrentManager` or Flask routes.

`DL_CLIENTS` can enable several clients. They currently share the host, credentials and common connection settings;
an unset port permits each plugin's default. Different hosts/credentials require separate app instances.

## Implement the interface

| Method | Required behavior |
| --- | --- |
| `connect() -> None` | Establish or reuse this thread's authenticated connection. Apply the configured scheme and timeout. Raise on failure. |
| `close() -> None` | Release this thread's handles and set them to `None`. Be safe when called repeatedly or after a partial connection failure. |
| `add_magnet(magnet_link, save_path, category) -> None` | Send the URI, destination and category/label to the client. Raise if rejected; returning `False` does not report a failed dispatch. |
| `remove_torrent(torrent_id) -> None` | Remove the download task without deleting its files. Raise if it cannot be removed. |
| `get_status(category) -> list[TorrentStatus]` | Return normalized records for the requested category/label. Filter locally if the API cannot filter on the server. |

The inherited `verify_credentials()` calls `connect()` and returns a boolean. Override it only if a lighter check can
prove that the configured credentials work. An unreachable or unauthenticated client must not report success.
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

`SAVE_PATH_BASE` belongs to the Download Client. The plugin sends that destination; the web container must not create,
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
`PUTIO_TOKEN`, `DL_API_KEY` or `DL_PASSWORD` and an optional target folder ID.

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
