from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from models import BookResult

DEFAULT_COVER_PATH = "/static/images/default_cover.jpg"
DEFAULT_TRACKERS = [
    "udp://tracker.openbittorrent.com:80",
    "udp://opentor.org:2710",
    "udp://tracker.ccc.de:80",
    "udp://tracker.blackunicorn.xyz:6969",
    "udp://tracker.coppersurfer.tk:6969",
    "udp://tracker.leechers-paradise.org:6969",
]


def parse_search_results(
    html: str,
    hostname: str,
    cover_validator,
) -> list[BookResult]:
    soup = BeautifulSoup(html, "html.parser")
    posts = soup.select(".post")
    return [
        parsed_post
        for post in posts
        if (parsed_post := parse_post(post, hostname, cover_validator)) is not None
    ]


def parse_post(
    post: Tag,
    hostname: str,
    cover_validator,
) -> BookResult | None:
    title_element = post.select_one(".postTitle > h2 > a")
    if not title_element:
        return None

    title = title_element.text.strip()
    link = f"https://{hostname}{title_element['href']}"
    cover = resolve_cover(post, cover_validator)

    post_info = post.select_one(".postInfo")
    post_info_text = post_info.get_text(separator=" ", strip=True) if post_info else ""
    language_match = re.search(
        r"Language:\s*(.*?)(?:\s*Keywords:|$)", post_info_text, re.DOTALL
    )
    language = language_match.group(1).strip() if language_match else "N/A"

    details_paragraph = post.select_one(".postContent p[style*='text-align:center']")
    details = parse_post_details(str(details_paragraph) if details_paragraph else "")

    return BookResult(
        title=title,
        link=link,
        cover=cover,
        language=language,
        post_date=details["post_date"],
        format=details["format"],
        bitrate=details["bitrate"],
        file_size=details["file_size"],
    )


def resolve_cover(post: Tag, cover_validator) -> str:
    cover_image = post.select_one("img")
    cover_url = cover_image["src"] if cover_image else None
    if cover_url and cover_validator(cover_url):
        return cover_url
    return DEFAULT_COVER_PATH


def parse_post_details(details_html: str) -> dict[str, str]:
    details = {
        "post_date": "N/A",
        "format": "N/A",
        "bitrate": "N/A",
        "file_size": "N/A",
    }

    if not details_html:
        return details

    post_date_match = re.search(r"Posted:\s*([^<]+)", details_html)
    if post_date_match:
        details["post_date"] = post_date_match.group(1).strip()

    format_match = re.search(r"Format:\s*<span[^>]*>([^<]+)</span>", details_html)
    if format_match:
        details["format"] = format_match.group(1).strip()

    bitrate_match = re.search(r"Bitrate:\s*<span[^>]*>([^<]+)</span>", details_html)
    if bitrate_match:
        details["bitrate"] = bitrate_match.group(1).strip()

    file_size_match = re.search(
        r"File Size:\s*<span[^>]*>([^<]+)</span>\s*([^<]+)",
        details_html,
    )
    if file_size_match:
        details["file_size"] = (
            f"{file_size_match.group(1).strip()} {file_size_match.group(2).strip()}"
        )

    return details


def parse_magnet_link(details_html: str) -> str | None:
    soup = BeautifulSoup(details_html, "html.parser")

    info_hash_row = soup.find("td", string=re.compile(r"Info Hash", re.IGNORECASE))
    if not info_hash_row:
        return None

    info_hash = info_hash_row.find_next_sibling("td").text.strip()
    tracker_rows = soup.find_all("td", string=re.compile(r"udp://|http://", re.IGNORECASE))
    trackers = [row.text.strip() for row in tracker_rows] or DEFAULT_TRACKERS
    trackers_query = "&".join(
        f"tr={requests.utils.quote(tracker)}" for tracker in trackers
    )
    return f"magnet:?xt=urn:btih:{info_hash}&{trackers_query}"
