from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from config import AppSettings

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
)
DEFAULT_COVER_PATH = "/static/images/default_cover.jpg"


def is_url_valid(url: str) -> bool:
    try:
        response = requests.head(url, timeout=3, allow_redirects=True, stream=True)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def search_audiobookbay(
    query: str, settings: AppSettings, max_pages: int | None = None
) -> list[dict[str, str]]:
    headers = {"User-Agent": USER_AGENT}
    results = []
    max_pages = max_pages or settings.page_limit

    print(f"Searching for '{query}' on https://{settings.abb_hostname}...")

    for page in range(1, max_pages + 1):
        url = f"https://{settings.abb_hostname}/page/{page}/?s={query.lower().replace(' ', '+')}"
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            print(f"[ERROR] Failed to fetch page {page}. Reason: {exc}")
            break

        soup = BeautifulSoup(response.text, "html.parser")
        posts = soup.select(".post")

        if not posts:
            print(f"No more results found on page {page}.")
            break

        print(f"Processing {len(posts)} posts on page {page}...")

        for post in posts:
            try:
                title_element = post.select_one(".postTitle > h2 > a")
                if not title_element:
                    continue

                title = title_element.text.strip()
                link = f"https://{settings.abb_hostname}{title_element['href']}"

                cover_url = (
                    post.select_one("img")["src"] if post.select_one("img") else None
                )
                cover = (
                    cover_url
                    if cover_url and is_url_valid(cover_url)
                    else DEFAULT_COVER_PATH
                )

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
                        file_size = (
                            f"{file_size_match.group(1).strip()} "
                            f"{file_size_match.group(2).strip()}"
                        )

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
            except Exception as exc:
                print(f"[ERROR] Could not process a post. Details: {exc}")
                continue

    return results


def extract_magnet_link(details_url: str) -> str | None:
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(details_url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(
                f"[ERROR] Failed to fetch details page. Status Code: {response.status_code}"
            )
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        info_hash_row = soup.find("td", string=re.compile(r"Info Hash", re.IGNORECASE))
        if not info_hash_row:
            print("[ERROR] Info Hash not found on the page.")
            return None

        info_hash = info_hash_row.find_next_sibling("td").text.strip()

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

        trackers_query = "&".join(
            f"tr={requests.utils.quote(tracker)}" for tracker in trackers
        )
        magnet_link = f"magnet:?xt=urn:btih:{info_hash}&{trackers_query}"

        print(f"[DEBUG] Generated Magnet Link: {magnet_link}")
        return magnet_link
    except Exception as exc:
        print(f"[ERROR] Failed to extract magnet link: {exc}")
        return None
