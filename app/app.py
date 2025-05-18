import os, re, requests
from flask import Flask, request, render_template, jsonify
from bs4 import BeautifulSoup
from qbittorrentapi import Client
from transmission_rpc import Client as transmissionrpc
from deluge_web_client import DelugeWebClient as delugewebclient
from dotenv import load_dotenv
from urllib.parse import urlparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

#Load environment variables
load_dotenv()
logger.debug("Environment variables loaded")

ABB_HOSTNAME = os.getenv("ABB_HOSTNAME", "audiobookbay.lu")

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

#Print configuration
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


@app.context_processor
def inject_nav_link():
    return {
        'nav_link_name': os.getenv('NAV_LINK_NAME'),
        'nav_link_url': os.getenv('NAV_LINK_URL')
    }



# Helper function to search AudiobookBay
def search_audiobookbay(query, max_pages=5):
    logger.debug(f"Searching AudiobookBay for query: {query} with max_pages={max_pages}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    results = []
    for page in range(1, max_pages + 1):
        url = f"https://{ABB_HOSTNAME}/page/{page}/?s={query.replace(' ', '+')}&cat=undefined%2Cundefined"
        logger.debug(f"Fetching page {page} from URL: {url}")
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch page {page}. Status Code: {response.status_code}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        for post in soup.select('.post'):
            try:
                title = post.select_one('.postTitle > h2 > a').text.strip()
                link = f"https://{ABB_HOSTNAME}{post.select_one('.postTitle > h2 > a')['href']}"
                cover = post.select_one('img')['src'] if post.select_one('img') else "/static/images/default-cover.jpg"
                results.append({'title': title, 'link': link, 'cover': cover})
                logger.debug(f"Found book: {title}")
            except Exception as e:
                logger.error(f"Skipping post due to error: {e}")
                continue
    logger.debug(f"Search completed. Found {len(results)} results")
    return results

# Helper function to extract magnet link from details page
def extract_magnet_link(details_url):
    logger.debug(f"Extracting magnet link from: {details_url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(details_url, headers=headers)
        if response.status_code != 200:
            logger.error(f"Failed to fetch details page. Status Code: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract Info Hash
        info_hash_row = soup.find('td', string=re.compile(r'Info Hash', re.IGNORECASE))
        if not info_hash_row:
            logger.error("Info Hash not found on the page")
            return None
        info_hash = info_hash_row.find_next_sibling('td').text.strip()
        logger.debug(f"Found info hash: {info_hash}")

        # Extract Trackers
        tracker_rows = soup.find_all('td', string=re.compile(r'udp://|http://', re.IGNORECASE))
        trackers = [row.text.strip() for row in tracker_rows]

        if not trackers:
            logger.warning("No trackers found on the page. Using default trackers")
            trackers = [
                "udp://tracker.openbittorrent.com:80",
                "udp://opentor.org:2710",
                "udp://tracker.ccc.de:80",
                "udp://tracker.blackunicorn.xyz:6969",
                "udp://tracker.coppersurfer.tk:6969",
                "udp://tracker.leechers-paradise.org:6969"
            ]

        # Construct the magnet link
        trackers_query = "&".join(f"tr={requests.utils.quote(tracker)}" for tracker in trackers)
        magnet_link = f"magnet:?xt=urn:btih:{info_hash}&{trackers_query}"

        logger.debug(f"Generated magnet link: {magnet_link}")
        return magnet_link

    except Exception as e:
        logger.error(f"Failed to extract magnet link: {e}")
        return None

# Helper function to sanitize titles
def sanitize_title(title):
    return re.sub(r'[<>:"/\\|?*]', '', title).strip()

# Endpoint for search page
@app.route('/', methods=['GET', 'POST'])
def search():
    books = []
    try:
        if request.method == 'POST':  # Form submitted
            query = request.form['query']
            #Convert to all lowercase
            query = query.lower()
            if query:  # Only search if the query is not empty
                books = search_audiobookbay(query)
        return render_template('search.html', books=books)
    except Exception as e:
        print(f"[ERROR] Failed to search: {e}")
        return render_template('search.html', books=books, error=f"Failed to search. { str(e) }")




# Endpoint to send magnet link to qBittorrent
@app.route('/send', methods=['POST'])
def send():
    data = request.json
    details_url = data.get('link')
    title = data.get('title')
    logger.debug(f"Received download request for title: {title}")
    
    if not details_url or not title:
        logger.error("Invalid request: missing link or title")
        return jsonify({'message': 'Invalid request'}), 400

    try:
        magnet_link = extract_magnet_link(details_url)
        if not magnet_link:
            logger.error("Failed to extract magnet link")
            return jsonify({'message': 'Failed to extract magnet link'}), 500

        save_path = f"{SAVE_PATH_BASE}/{sanitize_title(title)}"
        logger.debug(f"Save path: {save_path}")
        
        if DOWNLOAD_CLIENT == 'qbittorrent':
            logger.debug("Using qBittorrent client")
            qb = Client(host=DL_HOST, port=DL_PORT, username=DL_USERNAME, password=DL_PASSWORD)
            qb.auth_log_in()
            qb.torrents_add(urls=magnet_link, save_path=save_path, category=DL_CATEGORY)
        elif DOWNLOAD_CLIENT == 'transmission':
            logger.debug("Using Transmission client")
            transmission = transmissionrpc(host=DL_HOST, port=DL_PORT, protocol=DL_SCHEME, username=DL_USERNAME, password=DL_PASSWORD)
            transmission.add_torrent(magnet_link, download_dir=save_path)
        elif DOWNLOAD_CLIENT == "delugeweb":
            logger.debug("Using Deluge Web client")
            delugeweb = delugewebclient(url=DL_URL, password=DL_PASSWORD)
            delugeweb.login()
            delugeweb.add_torrent_magnet(magnet_link, save_directory=save_path, label=DL_CATEGORY)
        else:
            logger.error(f"Unsupported download client: {DOWNLOAD_CLIENT}")
            return jsonify({'message': 'Unsupported download client'}), 400

        logger.info(f"Successfully added torrent: {title}")
        return jsonify({
            'success': True,
            'title': title,
            'message': f'Added to download queue: {title}'
        })
    except Exception as e:
        logger.error(f"Error adding torrent: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500
@app.route('/status')
def status():
    logger.debug("Fetching torrent status")
    try:
        if DOWNLOAD_CLIENT == 'transmission':
            logger.debug("Fetching status from Transmission")
            transmission = transmissionrpc(host=DL_HOST, port=DL_PORT, username=DL_USERNAME, password=DL_PASSWORD)
            torrents = transmission.get_torrents()
            torrent_list = [
                {
                    'name': torrent.name,
                    'progress': round(torrent.progress, 2),
                    'state': torrent.status,
                    'size': f"{torrent.total_size / (1024 * 1024):.2f} MB",
                    'date_added': torrent.added_date
                }
                for torrent in torrents
            ]
            # Sort by date_added in descending order
            torrent_list.sort(key=lambda x: x['date_added'], reverse=True)
            logger.debug(f"Found {len(torrent_list)} torrents in Transmission")
            return render_template('status.html', torrents=torrent_list)
        elif DOWNLOAD_CLIENT == 'qbittorrent':
            logger.debug("Fetching status from qBittorrent")
            qb = Client(host=DL_HOST, port=DL_PORT, username=DL_USERNAME, password=DL_PASSWORD)
            qb.auth_log_in()
            torrents = qb.torrents_info(category=DL_CATEGORY)
            torrent_list = [
                {
                    'name': torrent.name,
                    'progress': round(torrent.progress * 100, 2),
                    'state': torrent.state,
                    'size': f"{torrent.total_size / (1024 * 1024):.2f} MB",
                    'date_added': torrent.added_on
                }
                for torrent in torrents
            ]
            # Sort by date_added in descending order
            torrent_list.sort(key=lambda x: x['date_added'], reverse=True)
            logger.debug(f"Found {len(torrent_list)} torrents in qBittorrent")
        elif DOWNLOAD_CLIENT == "delugeweb":
            logger.debug("Fetching status from Deluge Web")
            delugeweb = delugewebclient(url=DL_URL, password=DL_PASSWORD)
            delugeweb.login()
            torrents = delugeweb.get_torrents_status(
                filter_dict={"label": DL_CATEGORY},
                keys=["name", "state", "progress", "total_size", "time_added"],
            )
            torrent_list = [
                {
                    "name": torrent["name"],
                    "progress": round(torrent["progress"], 2),
                    "state": torrent["state"],
                    "size": f"{torrent['total_size'] / (1024 * 1024):.2f} MB",
                    "date_added": torrent["time_added"]
                }
                for k, torrent in torrents.result.items()
            ]
            # Sort by date_added in descending order
            torrent_list.sort(key=lambda x: x['date_added'], reverse=True)
            logger.debug(f"Found {len(torrent_list)} torrents in Deluge")
        else:
            logger.error(f"Unsupported download client: {DOWNLOAD_CLIENT}")
            return jsonify({'message': 'Unsupported download client'}), 400
        return render_template('status.html', torrents=torrent_list)
    except Exception as e:
        logger.error(f"Failed to fetch torrent status: {e}")
        return jsonify({'message': f"Failed to fetch torrent status: {e}"}), 500



if __name__ == '__main__':
    logger.info("Starting AudiobookBay Automated application")
    app.run(host='0.0.0.0', port=5078)
