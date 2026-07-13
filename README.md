
# AudiobookBay Automated

AudiobookBay Automated is a lightweight web application designed to simplify audiobook management. It allows users to search [**AudioBook Bay**](https://audiobookbay.lu/) for audiobooks and send magnet links directly to a designated **Deludge, qBittorrent or Transmission** client.

## How It Works
- **Search Results**: Users search for audiobooks. The app grabs results from AudioBook Bay and displays results with the **title** and **cover image**, along with two action links:
  1. **More Details**: Opens the audiobook's page on AudioBook Bay for additional information.
  2. **Download to Server**: Sends the audiobook to your configured torrent client for downloading.

- **Magnet Link Generation**: When a user selects "Download to Server," the app generates a magnet link from the infohash displayed on AudioBook Bay and sends it to the torrent client. Along with the magnet link, the app assigns:
  - A **category label** for organizational purposes.
  - A **save location** for downloaded files.


> **Note**: This app does not download or move any material itself (including torrent files). It only searches AudioBook Bay and facilitates magnet link generation for torrent.


## Features
- **Search Audiobook Bay**: Easily search for audiobooks by title or keywords.
- **View Details**: Displays book titles and covers with quickly links to the full details on AudioBook Bay.
- **Basic Download Status Page**: Monitor the download status of items in your torrent client that share the specified category assigned.
- **No AudioBook Bay Account Needed**: The app automatically generates magnet links from the displayed infohashes and push them to your torrent client for downloading.
- **Automatic Folder Organization**: Once the download is complete, torrent will automatically move the downloaded audiobook files to your save location. Audiobooks are organized into subfolders named after the AudioBook Bay title, making it easy for [**Audiobookshelf**](https://www.audiobookshelf.org/) to automatically add completed downloads to its library.



## Why Use This?
AudiobookBay Downloader provides a simple and user-friendly interface for users to download audiobooks without on their own and import them into your libary. 

---

## Installation

### Prerequisites
- **Deluge, qBittorrent or Transmission** (with the WebUI enabled)
- **Docker** (optional, for containerized deployments)

### Environment Variables
The app uses environment variables to configure its behavior. Below are the required variables:

# For some unknown reason some users have issues if the hostname is quoted, if it doesn't work try removing the quotes. I have no idea why this happens and can only assume it depends on the host system and how it handles envs/DNS lookup.

```env
DOWNLOAD_CLIENT=qbittorrent      # qbittorrent, transmission, or delugeweb
DL_SCHEME=http
DL_HOST=192.168.xxx.xxx        # IP or hostname of your qBittorrent or Transmission instance
DL_PORT=8080                   # torrent WebUI port
DL_USERNAME=YOUR_USER          # torrent username (not needed when using DL_API_KEY)
DL_PASSWORD=YOUR_PASSWORD      # torrent password (not needed when using DL_API_KEY)
DL_API_KEY=                    # qBittorrent v5.2+ API key (optional; takes precedence)
DL_CATEGORY=abb-downloader     # torrent category for downloads
SAVE_PATH_BASE=/audiobooks     # Root path for audiobook downloads (relative to torrent)
ABB_HOSTNAME='audiobookbay.is' # Default
PAGE_LIMIT=5                   # Maximum result pages per query; only page 1 loads initially.
SEARCH_COOLDOWN_SECONDS=5      # Wait time before another uncached upstream search.
SEARCH_CACHE_TTL_SECONDS=900   # Reuse matching query/page results for 15 minutes.
FLASK_PORT=5078                # Port used by docker container
```

### Docker Compose and 1Password

Docker Compose reads the application configuration from `.env`; it does not need
an `environment:` list in `docker-compose.yaml`. For secrets stored in
1Password, replace the value in `.env` with its secret-reference path, for
example:

```env
DL_PASSWORD=op://Private/qBittorrent/password
```

Start the stack through the supplied wrapper, which uses `op inject` to resolve
the references into a temporary file before Docker Compose starts the container:

```bash
./scripts/compose-with-op.sh up -d
```

Install and sign in to the 1Password CLI on the Docker host first. The resolved
secret is not written to `.env`, committed to Git, or passed to the container as
a 1Password credential.
The following optional variables add an additional entry to the navigation bar. This is useful for linking to your audiobook player or another related service:

```
NAV_LINK_NAME=Open Audiobook Player
NAV_LINK_URL=https://audiobooks.yourdomain.com/
```

### Using Docker

1. Build the image locally:

   ```bash
   docker build -t audiobookbay-automated .
   ```

2. Copy `.env.example` to `.env` and set the application values. Use this
   `docker-compose.yml` for quick deployment:

   ```yaml
   services:
     audiobookbay-downloader:
       image: ghcr.io/jamesry96/audiobookbay-automated:latest
       ports:
         - "5078:5078"
       container_name: audiobookbay-downloader
       env_file:
         - .env
   ```

3. **Start the Application**:
   ```bash
   ./scripts/compose-with-op.sh up -d
   ```

### Running Locally
1. **Install Dependencies**:
   Ensure you have Python installed, then install the required dependencies:
   ```bash
   pip install -r requirements.txt
   
2. Create a .env file in the project directory to configure your application. Below is an  example of the required variables:
    ```
    # Torrent Client Configuration
    DOWNLOAD_CLIENT=transmission # Change to delugeweb, transmission or qbittorrent
    DL_SCHEME=http
    DL_HOST=192.168.1.123
    DL_PORT=8080
    DL_USERNAME=admin
    DL_PASSWORD=pass
    # Or, for qBittorrent v5.2+, use an API key instead:
    # DL_API_KEY=qbt_your_api_key
    DL_CATEGORY=abb-downloader
    SAVE_PATH_BASE=/audiobooks
    
    # AudiobookBar Hostname
    ABB_HOSTNAME='audiobookbay.is' #Default
    # ABB_HOSTNAME='audiobookbay.lu' #Alternative

    PAGE_LIMIT=5 # Maximum result pages per query; only page 1 loads initially
    SEARCH_COOLDOWN_SECONDS=5 # Default
    SEARCH_CACHE_TTL_SECONDS=900 # Default (15 minutes)
    FLASK_PORT=5078 #Default

    # Optional Navigation Bar Entry
    NAV_LINK_NAME=Open Audiobook Player
    NAV_LINK_URL=https://audiobooks.yourdomain.com/
    ```

3. Start the app:
   ```bash
   python app.py
   ```

---

## Notes
- **This app does NOT download any material**: It simply generates magnet links and sends them to your qBittorrent client for handling.

- **Folder Mapping**: __The `SAVE_PATH_BASE` is based on the perspective of your torrent client__, not this app. This app does not move any files; all file handling and organization are managed by the torrent client. Ensure that the `SAVE_PATH_BASE` in your torrent client aligns with your audiobook library (e.g., for Audiobookshelf). Using a path relative to where this app is running, instead of the torrent client, will cause issues.


---

## Feedback and Contributions
This project is a work in progress, and your feedback is welcome! Feel free to open issues or contribute by submitting pull requests.

---

## Screenshots
### Search Results
![screenshot-2025-01-13-19-59-03](https://github.com/user-attachments/assets/8a30fd4e-a289-49d0-83ab-67a3bcfc9745)

### Download Status
![screenshot-2025-01-13-19-59-25](https://github.com/user-attachments/assets/19cc74de-51fc-422f-9cab-fe69e30c74b9)

---
