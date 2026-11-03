<!-- File: docs/configuration.md -->
# Optional settings and client setup

Start with the [Docker installation steps](../README.md#install-with-docker). Change only the settings you need in `.env`.
After changing settings, run `docker compose up -d --force-recreate` in your app folder.

## Passwords and special characters

Keep passwords in single quotes in `.env` so `$` and `#` are treated as part of the password. For example:

~~~env
DL_PASSWORD='my$pass#word'
~~~

If the password contains a single quote, escape that quote with a backslash, as in `DL_PASSWORD='Let\'s go!'`.
These are examples only; enter the password already used by your Download Client.

## Download Clients

### qBittorrent

Enable its web interface, then use its address, port, username and password. The usual port is `8080`.
`DL_API_KEY` is also supported by compatible qBittorrent versions.

### Transmission

Enable remote/web access and use `DL_CLIENT=transmission`. The usual port is `9091`.
Its access rules must allow connections from the app's container or server.

### Deluge

Enable Deluge Web, use `DL_CLIENT=deluge`, and set `DL_PORT=8112` unless you changed it.
`DL_PASSWORD` is your Deluge Web password. Enable the **Label** plugin for category-based organization.
Without it, Deluge may show downloads outside this app's category.

### Put.io

Use these settings for Put.io's cloud service. Replace the token with your Put.io OAuth token and remove any
`DL_HOST` value left over from another Download Client.

~~~env
DL_CLIENT=putio
DL_HOST=
PUTIO_TOKEN='your-token'
PUTIO_FOLDER_ID=0
~~~

An empty `DL_HOST` selects the normal Put.io API automatically. `PUTIO_FOLDER_ID=0` saves to your cloud root folder;
enter another folder ID to change the target. Put.io does not use `SAVE_PATH_BASE` or the download category.

### Windows save paths

If the Download Client runs on Windows, use:

~~~env
SAVE_PATH_BASE=D:/Audiobooks
DL_CLIENT_OS=windows
~~~

Use a folder that the Download Client can write to. The app sends a destination path; it does not move files or change
that folder's ownership.

### Several Download Clients

`DL_CLIENT` chooses the primary client. `DL_CLIENTS` can list additional supported clients, separated by commas.
The current setup shares host, credentials and connection settings across those clients. Leave `DL_PORT` unset to use
each client's default port. For different hosts or credentials, use separate app instances.

| Setting | Default / purpose |
| --- | --- |
| `DL_SCHEME` | `http`; use `https` if the Download Client serves HTTPS |
| `DL_CATEGORY` | `abb-automated`; label/category used for this app's downloads |
| `CLIENT_TIMEOUT` | `30` seconds for Download Client requests |
| `DL_URL` | Optional full Deluge Web URL |
| `DL_CLIENT_OS` | `posix`; use `windows` for Windows path conventions |

## Appearance

The menu's Appearance setting changes the theme for the current browser. `DEFAULT_THEME` sets the starting theme for
new browsers: `purple`, `crow`, `catppuccin`, `nord`, `tokyo`, `oled`, `forest`, `ocean`, `sunset`, `dracula`, `cyberpunk`,
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
| `LISTEN_HOST`, `LISTEN_PORT` | `0.0.0.0`, `5078`; app listening address/port |
| `THREADS` | `8`; keep the container's single Gunicorn worker |
| `SCRAPER_THREADS` | `3`; bounded concurrent catalog requests |
| `SCRAPER_TIMEOUT` | `30` seconds |
| `TZ` | Container timezone; for example `America/Los_Angeles` |
| `FORCE_HTTPS` | `false`; enable only with a correctly configured HTTPS deployment |

The app does not provide a VPN. Configure your own VPN/proxy if required. Local browser and Download Client traffic
must bypass a remote proxy. For example:

~~~env
HTTP_PROXY=http://gluetun:8888
HTTPS_PROXY=http://gluetun:8888
NO_PROXY=localhost,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
~~~

Configure the Download Client's network separately; sending it a magnet link does not change how it connects.

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
