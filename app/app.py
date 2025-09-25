import os, re, requests
from flask import Flask, request, render_template, jsonify
from bs4 import BeautifulSoup
from qbittorrentapi import Client
from transmission_rpc import Client as transmissionrpc
from deluge_web_client import DelugeWebClient as delugewebclient
from dotenv import load_dotenv
from urllib.parse import urlparse
app = Flask(__name__)

#Load environment variables
load_dotenv()

# Get hostname and strip any quotes that may have been included in the environment variable
ABB_HOSTNAME = os.getenv("ABB_HOSTNAME", "audiobookbay.lu").strip("'\"")

# Define fallback hostnames to try if the primary one fails
ABB_FALLBACK_HOSTNAMES = [
    ABB_HOSTNAME,
    "audiobookbay.se",
    "audiobookbay.li", 
    "audiobookbay.ws",
    "audiobookbay.la",
    "audiobookbay.me",
    "audiobookbay.fi",
    "theaudiobookbay.com",
    "audiobookbay.is"
]

# Remove duplicates while preserving order
seen = set()
ABB_FALLBACK_HOSTNAMES = [x for x in ABB_FALLBACK_HOSTNAMES if not (x in seen or seen.add(x))]

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

#Print configuration
print(f"ABB_HOSTNAME: {ABB_HOSTNAME}")
print(f"ABB_FALLBACK_HOSTNAMES: {ABB_FALLBACK_HOSTNAMES}")
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


@app.context_processor
def inject_nav_link():
    return {
        'nav_link_name': os.getenv('NAV_LINK_NAME'),
        'nav_link_url': os.getenv('NAV_LINK_URL')
    }



# Helper function to find a working hostname
def get_working_hostname(test_query="test"):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    for hostname in ABB_FALLBACK_HOSTNAMES:
        try:
            # Test with a simple request to the homepage first
            test_url = f"https://{hostname}"
            print(f"[INFO] Testing hostname: {hostname}")
            response = requests.get(test_url, headers=headers, timeout=10)
            if response.status_code == 200:
                print(f"[INFO] Successfully connected to {hostname}")
                return hostname
        except Exception as e:
            print(f"[ERROR] Failed to connect to {hostname}: {e}")
            continue
    
    # If no hostname works, return the primary one and let the search function handle the error
    print(f"[WARNING] No working hostname found, using primary: {ABB_HOSTNAME}")
    return ABB_HOSTNAME

# Helper function to search AudiobookBay
def search_audiobookbay(query, max_pages=PAGE_LIMIT):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    results = []
    
    # Get a working hostname
    working_hostname = get_working_hostname()
    
    for page in range(1, max_pages + 1):
        url = f"https://{working_hostname}/page/{page}/?s={query.replace(' ', '+')}&cat=undefined%2Cundefined"
        print(f"[INFO] Fetching: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"[ERROR] Failed to fetch page {page}. Status Code: {response.status_code}")
                break
        except Exception as e:
            print(f"[ERROR] Request failed for page {page}: {e}")
            # Try to find another working hostname
            if page == 1:  # Only retry hostname finding on first page failure
                print(f"[INFO] Trying to find alternative hostname...")
                for alternative_hostname in ABB_FALLBACK_HOSTNAMES:
                    if alternative_hostname != working_hostname:
                        try:
                            alt_url = f"https://{alternative_hostname}/page/{page}/?s={query.replace(' ', '+')}&cat=undefined%2Cundefined"
                            print(f"[INFO] Trying alternative: {alt_url}")
                            response = requests.get(alt_url, headers=headers, timeout=15)
                            if response.status_code == 200:
                                working_hostname = alternative_hostname
                                print(f"[INFO] Successfully switched to {working_hostname}")
                                url = alt_url
                                break
                        except Exception as alt_e:
                            print(f"[ERROR] Alternative {alternative_hostname} also failed: {alt_e}")
                            continue
                else:
                    print(f"[ERROR] All hostnames failed for page {page}")
                    break
            else:
                break

        soup = BeautifulSoup(response.text, 'html.parser')
        for post in soup.select('.post'):
            try:
                title = post.select_one('.postTitle > h2 > a').text.strip()
                link = f"https://{working_hostname}{post.select_one('.postTitle > h2 > a')['href']}"
                cover = post.select_one('img')['src'] if post.select_one('img') else "/static/images/default-cover.jpg"
                results.append({'title': title, 'link': link, 'cover': cover})
            except Exception as e:
                print(f"[ERROR] Skipping post due to error: {e}")
                continue
    return results

# Helper function to extract magnet link from details page
def extract_magnet_link(details_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(details_url, headers=headers)
        if response.status_code != 200:
            print(f"[ERROR] Failed to fetch details page. Status Code: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract Info Hash
        info_hash_row = soup.find('td', string=re.compile(r'Info Hash', re.IGNORECASE))
        if not info_hash_row:
            print("[ERROR] Info Hash not found on the page.")
            return None
        info_hash = info_hash_row.find_next_sibling('td').text.strip()

        # Extract Trackers
        tracker_rows = soup.find_all('td', string=re.compile(r'udp://|http://', re.IGNORECASE))
        trackers = [row.text.strip() for row in tracker_rows]

        if not trackers:
            print("[WARNING] No trackers found on the page. Using default trackers.")
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

        print(f"[DEBUG] Generated Magnet Link: {magnet_link}")
        return magnet_link

    except Exception as e:
        print(f"[ERROR] Failed to extract magnet link: {e}")
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
                if len(books) == 0:
                    # Check if this might be a connectivity issue
                    error_msg = ("No results found. This could be due to:\n"
                               "1. No matching audiobooks found for your search\n"
                               "2. AudiobookBay website connectivity issues\n"
                               "3. All AudiobookBay domains are currently down\n\n"
                               "Please try again later or check your network connection.")
                    return render_template('search.html', books=books, error=error_msg)
        return render_template('search.html', books=books)
    except Exception as e:
        print(f"[ERROR] Failed to search: {e}")
        
        # Provide a more user-friendly error message
        error_msg = ("Unable to connect to AudiobookBay. This could be due to:\n"
                   "1. AudiobookBay domains are temporarily down\n"
                   "2. Network connectivity issues\n"
                   "3. DNS resolution problems\n\n"
                   "Please try again later or check if AudiobookBay has moved to a new domain.")
        return render_template('search.html', books=books, error=error_msg)




# Endpoint to send magnet link to qBittorrent
@app.route('/send', methods=['POST'])
def send():
    data = request.json
    details_url = data.get('link')
    title = data.get('title')
    if not details_url or not title:
        return jsonify({'message': 'Invalid request'}), 400

    try:
        magnet_link = extract_magnet_link(details_url)
        if not magnet_link:
            return jsonify({'message': 'Failed to extract magnet link'}), 500

        save_path = f"{SAVE_PATH_BASE}/{sanitize_title(title)}"
        
        if DOWNLOAD_CLIENT == 'qbittorrent':
            qb = Client(host=DL_HOST, port=DL_PORT, username=DL_USERNAME, password=DL_PASSWORD)
            qb.auth_log_in()
            qb.torrents_add(urls=magnet_link, save_path=save_path, category=DL_CATEGORY)
        elif DOWNLOAD_CLIENT == 'transmission':
            transmission = transmissionrpc(host=DL_HOST, port=DL_PORT, protocol=DL_SCHEME, username=DL_USERNAME, password=DL_PASSWORD)
            transmission.add_torrent(magnet_link, download_dir=save_path)
        elif DOWNLOAD_CLIENT == "delugeweb":
            delugeweb = delugewebclient(url=DL_URL, password=DL_PASSWORD)
            delugeweb.login()
            delugeweb.add_torrent_magnet(magnet_link, save_directory=save_path, label=DL_CATEGORY)
        else:
            return jsonify({'message': 'Unsupported download client'}), 400

        return jsonify({'message': f'Download added successfully! This may take some time, the download will show in Audiobookshelf when completed.'})
    except Exception as e:
        return jsonify({'message': str(e)}), 500
@app.route('/status')
def status():
    try:
        if DOWNLOAD_CLIENT == 'transmission':
            transmission = transmissionrpc(host=DL_HOST, port=DL_PORT, username=DL_USERNAME, password=DL_PASSWORD)
            torrents = transmission.get_torrents()
            torrent_list = [
                {
                    'name': torrent.name,
                    'progress': round(torrent.progress, 2),
                    'state': torrent.status,
                    'size': f"{torrent.total_size / (1024 * 1024):.2f} MB"
                }
                for torrent in torrents
            ]
            return render_template('status.html', torrents=torrent_list)
        elif DOWNLOAD_CLIENT == 'qbittorrent':
            qb = Client(host=DL_HOST, port=DL_PORT, username=DL_USERNAME, password=DL_PASSWORD)
            qb.auth_log_in()
            torrents = qb.torrents_info(category=DL_CATEGORY)
            torrent_list = [
                {
                    'name': torrent.name,
                    'progress': round(torrent.progress * 100, 2),
                    'state': torrent.state,
                    'size': f"{torrent.total_size / (1024 * 1024):.2f} MB"
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
            return jsonify({'message': 'Unsupported download client'}), 400
        return render_template('status.html', torrents=torrent_list)
    except Exception as e:
        return jsonify({'message': f"Failed to fetch torrent status: {e}"}), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5078)
