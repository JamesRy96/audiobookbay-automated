import os
import re
import requests
from flask import Flask, request, render_template, jsonify
from bs4 import BeautifulSoup
from qbittorrentapi import Client
from transmission_rpc import Client as transmissionrpc
from deluge_web_client import DelugeWebClient as delugewebclient
from deluge_web_client import TorrentOptions as delugetorrentoptions
from dotenv import load_dotenv
from urllib.parse import urlparse

app = Flask(__name__)

# Load environment variables
load_dotenv()

ABB_HOSTNAME = os.getenv("ABB_HOSTNAME", "audiobookbay.lu")

PAGE_LIMIT = int(os.getenv("PAGE_LIMIT", 5))

DOWNLOAD_CLIENT = os.getenv("DOWNLOAD_CLIENT")
DL_URL = os.getenv("DL_URL")
if DL_URL:
    parsed_url = urlparse(DL_URL)
    DL_SCHEME = parsed_url.scheme
    DL_HOST = parsed_url.hostname
    DL_PORT = parsed_url.port
else:
    DL_SCHEME = os.getenv("DL_SCHEME", "http")
    DL_HOST = os.getenv("DL_HOST")
    DL_PORT = os.getenv("DL_PORT")

    # Make a DL_URL for Deluge if one was not specified
    if DL_HOST and DL_PORT:
        DL_URL = f"{DL_SCHEME}://{DL_HOST}:{DL_PORT}"

DL_USERNAME = os.getenv("DL_USERNAME")
DL_PASSWORD = os.getenv("DL_PASSWORD")
DL_CATEGORY = os.getenv("DL_CATEGORY", "Audiobookbay-Audiobooks")
SAVE_PATH_BASE = os.getenv("SAVE_PATH_BASE")

# Custom Nav Link Variables
NAV_LINK_NAME = os.getenv("NAV_LINK_NAME")
NAV_LINK_URL = os.getenv("NAV_LINK_URL")

# Define the port to be used
FLASK_PORT = int(os.getenv("PORT", 5078))

# Print configuration
print(f"ABB_HOSTNAME: {ABB_HOSTNAME}")
print(f"DOWNLOAD_CLIENT: {DOWNLOAD_CLIENT}")
print(f"DL_HOST: {DL_HOST}")
print(f"DL_PORT: {DL_PORT}")
print(f"DL_URL: {DL_URL}")
print(f"DL_USERNAME: {DL_USERNAME}")
print(f"DL_CATEGORY: {DL_CATEGORY}")
print(f"SAVE_PATH_BASE: {SAVE_PATH_BASE}")
print(f"NAV_LINK_NAME: {NAV_LINK_NAME}")
print(f"NAV_LINK_URL: {NAV_LINK_URL}")
print(f"PAGE_LIMIT: {PAGE_LIMIT}")
print(f"PORT: {FLASK_PORT}")


@app.context_processor
def inject_nav_link():
    return {
        "nav_link_name": os.getenv("NAV_LINK_NAME"),
        "nav_link_url": os.getenv("NAV_LINK_URL"),
    }


def is_url_valid(url):
    """
    Checks if URL is valid and returns a 200 status code. Primarily used to check if cover images are accessible.

    Args:
        url (str): The URL to check.
    """
    try:
        # Use a HEAD request with a short timeout and stream parameter
        response = requests.head(url, timeout=3, allow_redirects=True, stream=True)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


# Helper function to search AudiobookBay
def search_audiobookbay(query, max_pages=PAGE_LIMIT):
    """
    Searches AudiobookBay for a given query and scrapes the results.

    Args:
        query (str): The search term.
        max_pages (int): The maximum number of pages to scrape.

    Returns:
        list: A list of dictionaries, where each dictionary represents a book
              and contains its details.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    results = []

    print(f"Searching for '{query}' on https://{ABB_HOSTNAME}...")

    for page in range(1, max_pages + 1):
        url = f"https://{ABB_HOSTNAME}/page/{page}/?s={query.lower().replace(' ', '+')}"
        try:
            response = requests.get(url, headers=headers, timeout=15)
            # Raise an exception for bad status codes (4xx or 5xx)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to fetch page {page}. Reason: {e}")
            break

        soup = BeautifulSoup(response.text, "html.parser")
        posts = soup.select(".post")

        # If no posts are found on the page, stop paginating
        if not posts:
            print(f"No more results found on page {page}.")
            break

        print(f"Processing {len(posts)} posts on page {page}...")

        for post in posts:
            try:
                title_element = post.select_one(".postTitle > h2 > a")
                if not title_element:
                    continue  # Skip post if title is not found

                title = title_element.text.strip()
                link = f"https://{ABB_HOSTNAME}{title_element['href']}"

                # Check if the cover URL is valid, otherwise use the default
                cover_url = (
                    post.select_one("img")["src"] if post.select_one("img") else None
                )
                if cover_url and is_url_valid(cover_url):
                    cover = cover_url
                else:
                    cover = "/static/images/default_cover.jpg"

                post_info = post.select_one(".postInfo")
                post_info_text = (
                    post_info.get_text(separator=" ", strip=True) if post_info else ""
                )

                language_match = re.search(
                    r"Language:\s*(.*?)(?:\s*Keywords:|$)", post_info_text, re.DOTALL
                )
                language = language_match.group(1).strip() if language_match else "N/A"

                details_paragraph = post.select_one(
                    ".postContent p[style*='text-align:center']"
                )

                post_date, book_format, bitrate, file_size = "N/A", "N/A", "N/A", "N/A"

                if details_paragraph:
                    details_html = str(details_paragraph)

                    post_date_match = re.search(r"Posted:\s*([^<]+)", details_html)
                    post_date = (
                        post_date_match.group(1).strip() if post_date_match else "N/A"
                    )

                    format_match = re.search(
                        r"Format:\s*<span[^>]*>([^<]+)</span>", details_html
                    )
                    book_format = (
                        format_match.group(1).strip() if format_match else "N/A"
                    )

                    bitrate_match = re.search(
                        r"Bitrate:\s*<span[^>]*>([^<]+)</span>", details_html
                    )
                    bitrate = bitrate_match.group(1).strip() if bitrate_match else "N/A"

                    file_size_match = re.search(
                        r"File Size:\s*<span[^>]*>([^<]+)</span>\s*([^<]+)",
                        details_html,
                    )
                    if file_size_match:
                        file_size = f"{file_size_match.group(1).strip()} {file_size_match.group(2).strip()}"

                results.append(
                    {
                        "title": title,
                        "link": link,
                        "cover": cover,
                        "language": language,
                        "post_date": post_date,
                        "format": book_format,
                        "bitrate": bitrate,
                        "file_size": file_size,
                    }
                )
            except Exception as e:
                print(f"[ERROR] Could not process a post. Details: {e}")
                continue
    return results


# Helper function to extract magnet link from details page
def extract_magnet_link(details_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(details_url, headers=headers)
        if response.status_code != 200:
            print(
                f"[ERROR] Failed to fetch details page. Status Code: {response.status_code}"
            )
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract Info Hash
        info_hash_row = soup.find("td", string=re.compile(r"Info Hash", re.IGNORECASE))
        if not info_hash_row:
            print("[ERROR] Info Hash not found on the page.")
            return None
        info_hash = info_hash_row.find_next_sibling("td").text.strip()

        # Extract Trackers
        tracker_rows = soup.find_all(
            "td", string=re.compile(r"udp://|http://", re.IGNORECASE)
        )
        trackers = [row.text.strip() for row in tracker_rows]

        if not trackers:
            print("[WARNING] No trackers found on the page. Using default trackers.")
            trackers = [
                "udp://tracker.openbittorrent.com:80",
                "udp://opentor.org:2710",
                "udp://tracker.ccc.de:80",
                "udp://tracker.blackunicorn.xyz:6969",
                "udp://tracker.coppersurfer.tk:6969",
                "udp://tracker.leechers-paradise.org:6969",
            ]

        # Construct the magnet link
        trackers_query = "&".join(
            f"tr={requests.utils.quote(tracker)}" for tracker in trackers
        )
        magnet_link = f"magnet:?xt=urn:btih:{info_hash}&{trackers_query}"

        print(f"[DEBUG] Generated Magnet Link: {magnet_link}")
        return magnet_link

    except Exception as e:
        print(f"[ERROR] Failed to extract magnet link: {e}")
        return None


# Helper function to sanitize titles
def sanitize_title(title):
    return re.sub(r'[<>:"/\\|?*]', "", title).strip()


# Endpoint for search page
@app.route("/", methods=["GET", "POST"])
def search():
    books = []
    query = ""
    try:
        if request.method == "POST":  # Form submitted
            query = request.form["query"]
            if query:  # Only search if the query is not empty
                books = search_audiobookbay(query)
        return render_template("search.html", books=books, query=query)
    except Exception as e:
        print(f"[ERROR] Failed to search: {e}")
        return render_template(
            "search.html", books=books, error=f"Failed to search. {str(e)}", query=query
        )


# Endpoint to send magnet link to qBittorrent
@app.route("/send", methods=["POST"])
def send():
    data = request.json
    details_url = data.get("link")
    title = data.get("title")
    if not details_url or not title:
        return jsonify({"message": "Invalid request"}), 400

    try:
        magnet_link = extract_magnet_link(details_url)
        if not magnet_link:
            return jsonify({"message": "Failed to extract magnet link"}), 500

        save_path = f"{SAVE_PATH_BASE}/{sanitize_title(title)}"

        if DOWNLOAD_CLIENT == "qbittorrent":
            qb = Client(
                host=DL_HOST, port=DL_PORT, username=DL_USERNAME, password=DL_PASSWORD
            )
            qb.auth_log_in()
            qb.torrents_add(urls=magnet_link, save_path=save_path, category=DL_CATEGORY)
        elif DOWNLOAD_CLIENT == "transmission":
            transmission = transmissionrpc(
                host=DL_HOST,
                port=DL_PORT,
                protocol=DL_SCHEME,
                username=DL_USERNAME,
                password=DL_PASSWORD,
            )
            transmission.add_torrent(magnet_link, download_dir=save_path)
        elif DOWNLOAD_CLIENT == "delugeweb":
            delugeweb = delugewebclient(url=DL_URL, password=DL_PASSWORD)
            delugeweb.login()
            torrent_options = delugetorrentoptions(
                download_location=save_path, label=DL_CATEGORY
            )
            delugeweb.add_torrent_magnet(magnet_link, torrent_options=torrent_options)
        else:
            return jsonify({"message": "Unsupported download client"}), 400

        return jsonify(
            {
                "message": "Download added successfully! This may take some time, the download will show in Audiobookshelf when completed."
            }
        )
    except Exception as e:
        return jsonify({"message": str(e)}), 500


@app.route("/status")
def status():
    try:
        if DOWNLOAD_CLIENT == "transmission":
            transmission = transmissionrpc(
                host=DL_HOST, port=DL_PORT, username=DL_USERNAME, password=DL_PASSWORD
            )
            torrents = transmission.get_torrents()
            torrent_list = [
                {
                    "name": torrent.name,
                    "progress": round(torrent.progress, 2),
                    "state": torrent.status,
                    "size": f"{torrent.total_size / (1024 * 1024):.2f} MB",
                }
                for torrent in torrents
            ]
            return render_template("status.html", torrents=torrent_list)
        elif DOWNLOAD_CLIENT == "qbittorrent":
            qb = Client(
                host=DL_HOST, port=DL_PORT, username=DL_USERNAME, password=DL_PASSWORD
            )
            qb.auth_log_in()
            torrents = qb.torrents_info(category=DL_CATEGORY)
            torrent_list = [
                {
                    "name": torrent.name,
                    "progress": round(torrent.progress * 100, 2),
                    "state": torrent.state,
                    "size": f"{torrent.total_size / (1024 * 1024):.2f} MB",
                }
                for torrent in torrents
            ]
        elif DOWNLOAD_CLIENT == "delugeweb":
            delugeweb = delugewebclient(url=DL_URL, password=DL_PASSWORD)
            delugeweb.login()
            torrents = delugeweb.get_torrents_status(
                filter_dict={"label": DL_CATEGORY},
                keys=["name", "state", "progress", "total_size"],
            )
            torrent_list = [
                {
                    "name": torrent["name"],
                    "progress": round(torrent["progress"], 2),
                    "state": torrent["state"],
                    "size": f"{torrent['total_size'] / (1024 * 1024):.2f} MB",
                }
                for k, torrent in torrents.result.items()
            ]
        else:
            return jsonify({"message": "Unsupported download client"}), 400
        return render_template("status.html", torrents=torrent_list)
    except Exception as e:
        return jsonify({"message": f"Failed to fetch torrent status: {e}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=FLASK_PORT)
