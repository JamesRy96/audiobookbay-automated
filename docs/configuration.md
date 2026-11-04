<!-- File: docs/configuration.md -->
# Optional settings and client setup

Start with the [Docker installation steps](../README.md#install-with-docker). Change only the settings you need in
`.env`.
After changing settings, run `docker compose up -d --force-recreate` in your app folder.

## Passwords and special characters

Keep passwords in single quotes in `.env` so `$` and `#` are treated as part of the password. For example:

~~~env
QBITTORRENT_PASSWORD='my$pass#word'
~~~

If the password contains a single quote, escape that quote with a backslash, as in `QBITTORRENT_PASSWORD='Let\'s go!'`.
These are examples only; enter the password already used by your Download Client.

## Download Clients

Choose one client with `DL_CLIENT=qbittorrent`, `transmission`, `deluge`, or `putio`.
Use the matching settings below. App setting names accept uppercase, lowercase, or mixed case. Only configure clients
you actually use.
Ports have defaults, so you only need a port setting if you changed the client's normal port.

### qBittorrent

Enable qBittorrent's web interface and use the same login details you enter there:

~~~env
DL_CLIENT=qbittorrent
QBITTORRENT_HOST=192.168.1.100
QBITTORRENT_USERNAME=admin
QBITTORRENT_PASSWORD='your-web-interface-password'
~~~

The default port is `8080`; set `QBITTORRENT_PORT` if different. For HTTPS, set `QBITTORRENT_SCHEME=https`.
Compatible qBittorrent versions can use `QBITTORRENT_API_KEY` instead of username/password.

### Transmission

Use Transmission 4.x with remote/web access enabled. Allow connections from the app's container or server:

~~~env
DL_CLIENT=transmission
TRANSMISSION_HOST=192.168.1.100
TRANSMISSION_USERNAME=your-username
TRANSMISSION_PASSWORD='your-password'
~~~

The default port is `9091`; set `TRANSMISSION_PORT` if different. For HTTPS, set `TRANSMISSION_SCHEME=https`.
Labels keep app downloads visible in Downloads; a rejected label is reported as an error.

### Deluge

Enable Deluge Web and connect it to a Deluge 2.x daemon:

~~~env
DL_CLIENT=deluge
DELUGE_HOST=192.168.1.100
DELUGE_PASSWORD='your-deluge-web-password'
~~~

The default port is `8112`; set `DELUGE_PORT` if different. Deluge Web uses a password, not a username.
Enable the daemon's **Label** plugin for category-based organization. Without it, Deluge may show downloads outside
this app's category. For HTTPS, set `DELUGE_SCHEME=https`. For a reverse-proxy path, set
`DELUGE_URL=https://downloads.example/deluge/`; the SDK adds `/json` automatically.
The app requests new transfers unpaused, but queue limits, missing peers and daemon settings can still delay progress.

### Put.io

Put.io uses an OAuth token instead of a server address and password:

~~~env
DL_CLIENT=putio
PUTIO_TOKEN='your-oauth-token'
PUTIO_FOLDER_ID=0
~~~

`PUTIO_FOLDER_ID=0` saves to your cloud root folder; enter another folder ID to change the target.
Put.io does not use `SAVE_PATH_BASE` or the download category. Do not add Put.io to `DL_CLIENT` without a token.

### Several Download Clients

List the client names in **one** setting, separated by commas. The first is the default selection.
Each client keeps its own address and login details. For example:

~~~env
DL_CLIENT=qbittorrent,deluge,transmission
QBITTORRENT_HOST=192.168.1.100
QBITTORRENT_USERNAME=your-qbittorrent-username
QBITTORRENT_PASSWORD='your-qbittorrent-password'
DELUGE_HOST=192.168.1.100
DELUGE_PASSWORD='your-deluge-web-password'
TRANSMISSION_HOST=192.168.1.100
TRANSMISSION_USERNAME=your-transmission-username
TRANSMISSION_PASSWORD='your-transmission-password'
~~~

The default ports are `8080`, `8112`, and `9091`, respectively. Addresses can differ.
Choose a connected client when you select Download. The dialog checks each client's connection and disables offline
clients. With one configured client, Download sends directly without showing a client chooser.
Downloads combines tasks from all configured clients, and Remove targets the client that owns the task.
A dispatch failure is reported; the app does not silently send the book to a different client.

`DL_CATEGORY` applies to all local clients. Each client uses its own configured download folder unless you add an
optional path override.

### Download folders

**No path setting is required.** By default, the app lets each Download Client choose its configured folder and torrent
layout, including any category/label rules in that client. Put.io uses its selected cloud folder.

To have the app organize downloads into a separate folder for each book, optionally set a root:

~~~env
SAVE_PATH_BASE=/downloads/audiobooks
~~~

To use different roots for individual clients, set the matching client-specific value:

~~~env
QBITTORRENT_SAVE_PATH_BASE=/downloads/audiobooks
DELUGE_SAVE_PATH_BASE=/media/books
TRANSMISSION_SAVE_PATH_BASE=/downloads/transmission-books
~~~

A client-specific root takes priority over the shared `SAVE_PATH_BASE`. With neither set, the app sends no destination
override. With a root set, the app appends a safe book-title folder. Use paths **as seen by the Download Clients**,
not this app's container, and make sure each client can write there. Do not mount download folders into this app.

### Windows save paths

Windows drive paths and network shares are detected automatically, even when this app runs in Linux/Docker.
For an optional Windows destination override, use:

~~~env
SAVE_PATH_BASE=D:/Audiobooks
~~~

The app sends a destination path; it does not move files or change that folder's ownership.

### Optional connection settings

For clients reachable at `127.0.0.1` from inside this app, omit HOST and PORT: the app automatically uses the local
address and that client's standard port. It verifies the connection when needed. Docker containers must share one
network connection (`network_mode: service:...` or host networking) for these local defaults to reach another client.
Separate containers on the same Docker network still have their own localhost: use the client's Docker service name.
For another server, set its reachable IP address or hostname. No VPN product detection is needed.
An explicitly configured address is always preserved; the app does not scan your network or guess a replacement.

| Setting | Default / purpose |
| --- | --- |
| `<CLIENT>_HOST` | Server address; defaults automatically to `127.0.0.1` inside the app's network |
| `<CLIENT>_PORT` | Client's normal port; positive whole number up to `65535` |
| `<CLIENT>_SCHEME` | `http`; use `https` if that client serves HTTPS |
| `<CLIENT>_TIMEOUT` | Override the common timeout for that client, in positive whole seconds |
| `CLIENT_TIMEOUT` | `5` seconds; common default for Download Client requests |
| `DL_CATEGORY` | `abb-automated`; label/category used for this app's downloads |

Replace `<CLIENT>` with `QBITTORRENT`, `DELUGE`, or `TRANSMISSION`; do not enter the angle brackets.
Capitalization of app setting names does not matter: `DELUGE_PASSWORD` and `deluge_PASSWORD` mean the same setting.
Passwords, API keys, paths and other values keep their original capitalization. Set each setting once; conflicting
duplicates stop startup with a message naming the setting to fix. Use only the settings shown for your chosen client;
shared connection aliases are not supported.

Docker startup settings such as `LISTEN_PORT`, `PUID`, `PGID` and `TZ` follow the same capitalization rule. Other
containers and Docker Compose variable references follow their own rules; keep `${BASE_PATH}` and similar references
consistent with the variables defined in your Compose `.env` file.

## Appearance

The menu's Appearance setting changes the theme for the current browser. `DEFAULT_THEME` sets the starting theme for
new browsers: `purple`, `crow`, `catppuccin`, `nord`, `tokyo`, `oled`, `forest`, `ocean`, `sunset`, `dracula`,
`cyberpunk`,
`light`, `royal`, or `slate`.

| Setting | Purpose |
| --- | --- |
| `SITE_TITLE` | App name; default `AudiobookBay Automated` |
| `SITE_LOGO` | Header image URL or filename in `static/images/` |
| `SPLASH_ENABLED` | `true` by default; set `false` to skip the intro |
| `SPLASH_VIDEO` | MP4 intro URL or filename in `static/images/` |
| `SPLASH_VIDEO_WEBM` | Optional WebM version |
| `SPLASH_TITLE`, `SPLASH_MESSAGE` | Text used when the intro needs a fallback |
| `SPLASH_DURATION` | Fallback intro duration in milliseconds; default `3500` |
| `NAV_LINK_NAME`, `NAV_LINK_URL` | Optional link in the menu; set both |

For local custom artwork, mount individual files read-only in Compose. For example, add this under the service:

~~~yaml
volumes:
  - ./my-banner.jpg:/app/audiobook_automated/static/images/my-banner.jpg:ro
  - ./my-intro.mp4:/app/audiobook_automated/static/images/my-intro.mp4:ro
~~~

Then set `SITE_LOGO=my-banner.jpg` and `SPLASH_VIDEO=my-intro.mp4` in `.env`. Keep those image/video files next to
`compose.yaml`. Mount individual files so the app's other images remain available.

## Audiobookshelf

The optional **Reload Library** action asks Audiobookshelf to scan for new files. It does not transfer files from your
Download Client into your library, so those programs must already use compatible folder mappings.

Set all three values to enable the action:

- `ABS_URL`: your Audiobookshelf server address.
- `ABS_KEY`: an API token created in your Audiobookshelf account/settings.
- `ABS_LIB`: the library ID, visible in its library page URL.

## Diagnostics and network

Set `ENABLE_DIAGNOSTICS=true` to enable Diagnostics in the menu. Mirror observations distinguish verified availability
from candidates that have not been checked. An available mirror's latency and previous observations help choose it;
a response code alone does not prove that a mirror serves the catalog.

| Setting | Default / purpose |
| --- | --- |
| `ABB_HOSTNAME` | `audiobookbay.lu`; primary catalog mirror |
| `ABB_MIRRORS` | Optional comma-separated additional mirrors |
| `ABB_MIRRORS_REMOTE_URL` | Optional source for an additional mirror list |
| `LOG_LEVEL` | `INFO`; use `DEBUG` only while investigating a problem |
| `LISTEN_HOST`, `LISTEN_PORT` | Container detects IPv6 (`[::]`) or IPv4 (`0.0.0.0`); port `5078` |
| `THREADS` | `8`; keep the container's single Gunicorn worker |
| `SCRAPER_THREADS` | `3`; bounded concurrent catalog requests |
| `SCRAPER_TIMEOUT` | `10` seconds per catalog request attempt |
| `SCRAPER_JITTER_MIN` | `0.3` seconds minimum request jitter spacing |
| `SCRAPER_JITTER_MAX` | `0.8` seconds maximum request jitter spacing |
| `TZ` | Container timezone; for example `America/Los_Angeles` |

The app does not provide a VPN. Configure your own VPN/proxy if required. Local browser and Download Client traffic
must bypass a remote proxy. For example:

~~~env
HTTP_PROXY=http://gluetun:8888
HTTPS_PROXY=http://gluetun:8888
NO_PROXY=localhost,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
~~~

Configure the Download Client's network separately; sending it a magnet link does not change how it connects.

If the app shares Gluetun's network with `network_mode: service:gluetun`, publish the app's port on the Gluetun service.
Omit the app's `ports` key entirely; an empty `ports:` value is invalid Compose. When the Download Client shares that
same network, use `QBITTORRENT_HOST=127.0.0.1` (or the matching client-specific host setting) and its actual Web UI
port. A separate client needs an address reachable from
the app's network. LAN addresses are supported; the VPN and Docker firewall must allow that route. If a client cannot
be reached, its connection check logs the client name and the settings to check. Requests use a five-second timeout
by default; qBittorrent may make a second attempt. Increase `CLIENT_TIMEOUT` only for a genuinely slow connection.
Unraid users should enter the documented `DL_CLIENT=qbittorrent` setting; `DOWNLOAD_CLIENT` is
not an app setting.

Search loads one catalog page at a time, with request delays and bounded concurrency. These controls reduce traffic;
they cannot guarantee the catalog will never block an IP. If blocked, stop retrying and allow the site's restriction
to expire. Changing mirror names may still reach the same server/IP.

The container health check uses Python and `/health`; curl is not required. It checks the app's HTTP availability,
not catalog reachability, Download Client connectivity or completed transfers. Startup also makes no Download Client
connections. A loaded plugin is not a confirmed connection: open **Status** to check each client. Missing login
settings produce warnings naming the setting to add, without showing passwords or tokens. After changing settings,
recreate the app container with `docker compose up -d` from the folder containing your Compose file.
Connection help also appears in the page banner, Download Client picker and Status page, so you do not need to read
logs for basic setup corrections. A client that is unavailable cannot be selected; working clients remain usable.

## Reverse proxy and HTTPS

For ordinary local access, leave `PUBLIC_URL` unset and open `http://SERVER-IP:5078`. No security flags are required.
Direct HTTPS connections automatically receive Secure session cookies.

If you use a reverse proxy, set the full public address you open in your browser:

~~~env
PUBLIC_URL=https://myaudiobooks.com
~~~

This declares the address used through your reverse proxy. Requests naming this public host use its configured
protocol for links, session cookies and HTTPS origin checks, even when the proxy connects over HTTP. Direct access
at `http://SERVER-IP:5078` continues to work independently, with its own browser session. The internal HTTP `/health`
check also stays available. Include a custom public port if needed, and have the proxy preserve the browser's Host
header, including that port.
The address must start with `http://` or `https://`; do not include a login, subpath, query or fragment.

For **Nginx Proxy Manager**:

1. Add a Proxy Host for your domain, forwarding with scheme **http** to the app's server and port **5078**.
2. In **SSL**, select/request the certificate and enable **Force SSL** if you want HTTPS-only browser access.
3. Set `PUBLIC_URL` to that HTTPS address in the app's settings and recreate the app container.

No Custom Nginx Configuration snippet is needed for this normal setup. The proxy handles certificates and redirects;
the app does not redirect its internal HTTP connection back through the proxy. HSTS is also a deliberate proxy-side
choice; it is not automatically enabled by the app. Restrict direct access to the backend to your private network.

### Advanced: forwarded client details

`PUBLIC_URL` does not establish that a request came from a trusted proxy. Forwarded headers are ignored by default.
For normal NPM use, leave `TRUSTED_PROXIES` unset. Rate limiting and logs will identify the connecting proxy.

If you need forwarded client addresses or routing details, list only the proxy addresses/networks that actually
connect to the app:

~~~env
TRUSTED_PROXIES=172.20.0.5
~~~

Replace this example with your proxy's actual backend-facing address. Comma-separated IP addresses or CIDR networks
are accepted; do not trust every address or all private networks. One forwarding hop is trusted from allowlisted
peers. Your proxy must correctly set or sanitize forwarded headers. More complex proxy chains require separate review.
The configured `PUBLIC_URL` always takes priority over forwarded host/protocol values.

## Custom trackers

`MAGNET_TRACKERS` accepts a comma-separated list of tracker URLs. Alternatively, mount a JSON file at
`/app/trackers.json`; [the example](../examples/trackers.json) shows the supported format.

## Browser session protection

The app generates its own secret signing key at startup. No setup or extra storage is needed. It protects browser
sessions and action requests; it is not your Download Client password. After an app restart, refresh any page that
was already open before using Download, Remove or library scan controls.

For advanced setups that need open pages to remain valid across restarts, optionally set `SECRET_KEY` to a long random
value (at least 32 letters/numbers) and keep it private and unchanged. Leave it unset for normal installation.
A fixed key preserves signing continuity; it does not disable token expiry or other request checks.

If freshly opened pages repeatedly show a page-expired message, check that the app server's clock is synchronized.
A clock moving backward can invalidate a newly signed session. Refresh after correcting the server time.

Diagnostics returns the last completed observations while checking Download Clients in the background. Its regular
refresh does not repeat catalog probes or fetch a new mirror list. Manual checks are limited to once every 30
seconds. A mirror request waits at most 2.5 seconds per probe attempt; catalog requests use `SCRAPER_TIMEOUT`.
Transient connection failures can retry once, with the same request spacing and concurrency limit as other requests.
