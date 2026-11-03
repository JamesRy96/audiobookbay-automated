<!-- File: README.md -->
# AudiobookBay Automated

Find audiobooks on AudioBook Bay and send them to **qBittorrent, Transmission, Deluge, or Put.io**. Your Download Client
downloads and stores the files; this app provides search, book details, and download progress.

## Install with Docker

This is the recommended setup. Install [Docker](https://docs.docker.com/get-started/get-docker/) with Compose 2.24 or
newer, and have one supported Download Client running.
For qBittorrent, Transmission, or Deluge, make sure you can open that client's web interface and sign in.

### 1. Create a folder for the app

Save these two files in the same folder:

- [Download the Compose example](https://raw.githubusercontent.com/meek2100/audiobookbay-automated/main/examples/docker-compose.env.yaml)
  and save it as **compose.yaml**.
- [Download the settings example](https://raw.githubusercontent.com/meek2100/audiobookbay-automated/main/examples/.env.example)
  and save it as **.env**.

If you use Windows, turn on **File name extensions** in File Explorer and check that neither filename ends in `.txt`.

### 2. Enter your connection settings

Open `.env` in a text editor. Set these values for your Download Client:

| Setting | What to enter |
| --- | --- |
| `DL_CLIENT` | `qbittorrent`, `transmission`, `deluge`, or `putio` |
| `DL_HOST` | The address of the server running your Download Client, such as `192.168.1.100` |
| `DL_PORT` | Its web-interface port: usually `8080`, `9091`, or `8112`, respectively |
| `DL_USERNAME` | The username you use to sign in to that web interface |
| `DL_PASSWORD` | Its password; keep the surrounding single quotes |
| `SAVE_PATH_BASE` | The audiobook folder **as your Download Client sees it** |

For example, if qBittorrent saves books under `/downloads/audiobooks` inside its own container, use that path for
`SAVE_PATH_BASE`. Do not use the folder path from this app's container. **You do not need to mount the download folder
into this app.**

For Put.io or a Windows Download Client, follow the short [client setup notes](docs/configuration.md#download-clients).
Deluge users should enable the **Label** plugin so downloads can be organized by category.

### 3. Start the app

Open Terminal or PowerShell **in the folder containing compose.yaml**, then run:

~~~shell
docker compose up -d
~~~

Open **<http://localhost:5078>** if Docker runs on this computer. If it runs on a home server, replace `localhost` with
that server's address, for example **<http://192.168.1.100:5078>**.

The prebuilt image is `ghcr.io/meek2100/audiobookbay-automated:latest`. It becomes available when a release is published.
Before the first release, use the [source-build instructions](docs/development.md#run-the-container-from-source).

### 4. Check the connection

Open **Downloads** in the menu. If the app reports that your Download Client is disconnected, check its address, port,
username, and password in `.env`. Then apply the settings:

~~~shell
docker compose up -d --force-recreate
~~~

Keep the app on your private network. For access over the internet, use an authenticated reverse proxy; the app has
no sign-in screen of its own.

## Find and download a book

1. Enter a title, author, or keyword and select **Search**. Searches need at least two characters.
2. Open **Details** to read about a book, or choose **Download** to send it to your Download Client.
3. Open **Downloads** to follow its progress. Your Download Client controls where files are stored and when they finish.

Near the bottom, more results load automatically. **Load more audiobooks** also lets you request the next page manually.
While a request is running, the button shows **Loading audiobooks…** and is disabled. If it fails, select **Retry loading
audiobooks**. An end message confirms when there are no more results, and the button disappears.

The **×** at the end of the search box clears its text and returns focus so you can type another search. It does not
submit a request or discard the results already on screen. To clear filters, open **Filters → Reset filters**.

**Filters apply only to results already loaded.** The Author / contributor filter uses recognizable credits in titles,
so some listings may have no credit. Narrator details appear on the Details page when the catalog supplies them.

Click a category, language, author, or narrator link to browse related books. You can also enter these searches directly:

| Browse by | Example |
| --- | --- |
| Category | `category:Fantasy` |
| Language | `language:German` |
| Author | `author:J.R.R. Tolkien` |
| Narrator | `narrator:Gert Heidenreich` |

Recent searches appear inside the search panel and are kept in your browser tab. The trash icon beside
**Recent searches** clears that history. The menu also lets you choose a color theme.

## Update or stop the app

Run these commands in your app folder to install the latest published image. Your `.env` settings and Download Client
files stay in place:

~~~shell
docker compose pull
docker compose up -d
~~~

To stop the app:

~~~shell
docker compose down
~~~

## Troubleshooting

| What you see | What to check |
| --- | --- |
| The image cannot be downloaded | Check your internet connection and the image name. A first release must be published before `latest` exists. |
| The app will not start | Check `.env` for `DL_CLIENT` and `SAVE_PATH_BASE`. Run `docker compose logs --tail=50` to see the reason. |
| The browser cannot open the app | Check that Docker is running, port `5078` is available, and you used the correct server address. |
| Download Client disconnected | Check its web interface, address, port, and credentials. In this container, `localhost` refers to this app, not your other server or container. |
| Search is unavailable | Wait a moment and retry. If it continues, check your internet/VPN connection. Enable [Diagnostics](docs/configuration.md#diagnostics-and-network) to see mirror availability. |
| A book does not appear in Downloads | Check the Download Client itself and its `abb-automated` category/label. Some clients take time to retrieve torrent information. |
| Files are saved in the wrong folder | Correct `SAVE_PATH_BASE` using the path visible inside your Download Client, then recreate the app container. |

Optional guides: [appearance, Download Clients and networking](docs/configuration.md),
[Audiobookshelf scans](docs/configuration.md#audiobookshelf), and [development/testing](docs/development.md).

## Screenshots

These show the default theme with fictional example books and isolated Download Client data.

![Search results with filters and matching card layouts](docs/images/search.png)

![Book details with contributor links and a clean description](docs/images/details.png)

![Download progress and compact refresh controls](docs/images/status.png)

## Help and contributions

[Report a problem](https://github.com/meek2100/audiobookbay-automated/issues) with what you tried and what happened.
Remove passwords, tokens, and private addresses from any logs you share.

Developers: start with [the development guide](docs/development.md) and [AGENTS.md](AGENTS.md).
