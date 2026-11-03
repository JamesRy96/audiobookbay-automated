# File: audiobook_automated/scraper/parser.py
"""Parser module for BeautifulSoup HTML processing.

This module contains regex patterns and helper functions to extract
structured data from the raw HTML of AudiobookBay pages.
It encapsulates parsing strategies to keep core.py focused on networking and flow control.
"""

import re
from dataclasses import dataclass, field, fields
from typing import Any, TypedDict
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from bs4.element import PageElement

from audiobook_automated.constants import DEFAULT_COVER_FILENAME

# Constants
MIN_TABLE_CELLS = 2

# --- Regex Patterns ---
RE_INFO_HASH = re.compile(r"Info Hash", re.IGNORECASE)
RE_HASH_STRING = re.compile(r"\b([a-fA-F0-9]{40}|[a-fA-F0-9]{64})\b")
RE_LANGUAGE = re.compile(r"Language:\s*(.+?)(?:\s*$|\s+Format:|\s+Bitrate:|\s+Keywords:)", re.IGNORECASE)
RE_CATEGORY = re.compile(
    r"Category:\s*(?:(?=(?:Language|Format|Bitrate|Keywords):)|(.*?)(?:\s+(?:Language|Format|Bitrate|Keywords):|\s*$))",
    re.IGNORECASE,
)
RE_LABEL_POSTED = re.compile(r"Posted:", re.IGNORECASE)
RE_LABEL_FORMAT = re.compile(r"Format:", re.IGNORECASE)
RE_LABEL_BITRATE = re.compile(r"Bitrate:", re.IGNORECASE)
RE_LABEL_SIZE = re.compile(r"(?:File|Total)\s*Size:", re.IGNORECASE)
RE_DESCRIPTION_METADATA = re.compile(
    r"(written by|read by|narrated by|authors?|narrators?|format|bitrate|file size|total size|size|language|category)(?:\s*:\s*|\s+)(.+)",
    re.IGNORECASE,
)


class BookSummary(TypedDict):
    """TypedDict representing the structure of a search result (summary)."""

    title: str
    link: str
    cover: str | None
    language: str
    category: list[str]
    post_date: str
    format: str
    bitrate: str
    file_size: str


class BookDetails(BookSummary):
    """TypedDict representing the full details of a book."""

    description: str
    trackers: list[str]
    info_hash: str
    author: str
    narrator: str


@dataclass
class BookMetadata:
    """Data class representing standard audiobook metadata extracted from the page."""

    language: str = "Unknown"
    category: list[str] = field(default_factory=lambda: ["Unknown"])
    post_date: str = "Unknown"
    format: str = "Unknown"
    bitrate: str = "Unknown"
    file_size: str = "Unknown"
    author: str = "Unknown"
    narrator: str = "Unknown"


def get_text_after_label(container: Tag, label_pattern: re.Pattern[str], is_file_size: bool = False) -> str:
    """Robustly find values based on a label within a BS4 container using a compiled regex."""
    try:
        label_node = container.find(string=label_pattern)
        if not label_node:
            return "Unknown"

        current_node: Tag | Any = label_node
        next_elem = current_node.find_next_sibling()

        for _ in range(3):
            if next_elem:
                break
            if current_node.parent and current_node.parent.name not in ["div", "p", "td", "li"]:
                current_node = current_node.parent
                next_elem = current_node.find_next_sibling()
            else:
                break

        if next_elem and isinstance(next_elem, Tag) and next_elem.name == "span":
            val = next_elem.get_text(strip=True)
            if is_file_size:
                unit_node = next_elem.next_sibling
                if unit_node and isinstance(unit_node, str):
                    val += f" {unit_node.strip()}"
            return str(val)

        label_str = str(label_node)
        if ":" in label_str:
            parts = label_str.split(":", 1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()

        return "Unknown"
    except Exception:
        return "Unknown"


def normalize_cover_url(base_url: str, relative_url: str) -> str | None:
    """Normalize a cover image URL and handle default placeholders."""
    if not relative_url:
        return None

    extracted_cover = urljoin(base_url, relative_url)
    if extracted_cover.endswith(DEFAULT_COVER_FILENAME):
        return None

    return extracted_cover


def _normalize_metadata(meta: BookMetadata) -> None:
    """Normalize metadata fields in place, handling unknown values."""
    for f in fields(meta):
        value = getattr(meta, f.name)
        if f.name == "category":
            if not value:
                setattr(meta, f.name, ["Unknown"])
            else:
                normalized_list = []
                for item in value:
                    if not item or item.strip() in ["?", ""]:
                        normalized_list.append("Unknown")
                    else:
                        normalized_list.append(item)
                setattr(meta, f.name, normalized_list)
            continue

        if isinstance(value, str):
            clean_val = value.strip()
            if not clean_val or clean_val == "?" or clean_val.startswith("? "):
                setattr(meta, f.name, "Unknown")
            else:
                setattr(meta, f.name, clean_val)


def _parse_body_content(content_div: Tag, meta: BookMetadata) -> None:
    """Extract metadata from the body paragraphs."""
    for p in content_div.find_all("p"):
        p_text = p.get_text()
        if RE_LABEL_POSTED.search(p_text):
            meta.post_date = get_text_after_label(p, RE_LABEL_POSTED)
        if RE_LABEL_FORMAT.search(p_text):
            meta.format = get_text_after_label(p, RE_LABEL_FORMAT)
        if RE_LABEL_BITRATE.search(p_text):
            meta.bitrate = get_text_after_label(p, RE_LABEL_BITRATE)
        if RE_LABEL_SIZE.search(p_text):
            meta.file_size = get_text_after_label(p, RE_LABEL_SIZE, is_file_size=True)


def _parse_categories_from_info(post_info: Tag) -> list[str]:
    """Extract and split categories cleanly from post_info."""
    category_anchors = post_info.select('a[href*="/category/"], a[rel*="category"]')
    if category_anchors:
        parsed_cats = [a.get_text(strip=True) for a in category_anchors if a.get_text(strip=True)]
        if parsed_cats:
            return parsed_cats

    info_text = post_info.get_text(" ", strip=True)
    info_raw_text = post_info.get_text("\xa0", strip=True)
    cat_match = RE_CATEGORY.search(info_raw_text) or RE_CATEGORY.search(info_text)
    if not cat_match:
        return ["Unknown"]

    raw_cat = (cat_match.group(1) or "").strip()
    if not raw_cat:
        return ["Unknown"]

    if "," in raw_cat:
        return [c.strip() for c in raw_cat.split(",") if c.strip()]
    if "\xa0" in raw_cat or "\t" in raw_cat or re.search(r"\s{2,}", raw_cat):
        return [c.strip() for c in re.split(r"(?:\xa0|\t|\s{2,})+", raw_cat) if c.strip()]
    return [raw_cat]


def parse_post_content(
    content_div: Tag | None,
    post_info: Tag | None,
    author_tag: Tag | None = None,
    narrator_tag: Tag | None = None,
) -> BookMetadata:
    """Parse the post content and info sections to extract normalized metadata."""
    meta = BookMetadata()

    if post_info:
        meta.category = _parse_categories_from_info(post_info)

        info_text = post_info.get_text(" ", strip=True)
        lang_match = RE_LANGUAGE.search(info_text)
        if lang_match:
            meta.language = lang_match.group(1)

    if content_div:
        _parse_body_content(content_div, meta)

    if author_tag:
        meta.author = author_tag.get_text(strip=True)
    if narrator_tag:
        meta.narrator = narrator_tag.get_text(strip=True)

    _normalize_metadata(meta)

    return meta


def _description_value(value: str) -> str:
    """Normalize spacing and list separators for duplicate comparisons only."""
    return re.sub(r"\s*[,;]\s*", ",", " ".join(value.split())).casefold()


def _remove_metadata_line(nodes: list[PageElement], metadata: dict[str, str]) -> bool:
    """Remove a standalone line only when its value is already represented."""
    text = " ".join(node.get_text(" ", strip=True) if isinstance(node, Tag) else str(node) for node in nodes)
    normalized = " ".join(text.split())
    match = RE_DESCRIPTION_METADATA.fullmatch(normalized)
    redundant = not normalized
    if match:
        expected = metadata[match[1].casefold()]
        redundant = expected != "Unknown" and _description_value(match[2]) == _description_value(expected)
    if redundant:
        for node in nodes:
            node.extract()
    return redundant


def _strip_description_prefix(container: Tag, metadata: dict[str, str]) -> bool:
    """Stop at the first nonduplicate line, preserving the remaining synopsis."""
    pending: list[PageElement] = []
    for node in list(container.contents):
        if isinstance(node, Tag) and node.name == "p":
            if not _remove_metadata_line(pending, metadata):
                return False
            pending = []
            if not _strip_description_prefix(node, metadata):
                return False
            node.decompose()
        elif isinstance(node, Tag) and node.name == "br":
            if not _remove_metadata_line(pending, metadata):
                return False
            pending = []
            node.decompose()
        else:
            pending.append(node)
    return _remove_metadata_line(pending, metadata)


def _sanitize_description(desc_tag: Tag | None, meta: BookMetadata) -> str:
    """Extract and sanitize the description."""
    if not desc_tag:
        return "No description available."

    allowed_tags = ["p", "br", "b", "i", "em", "strong", "ul", "li"]
    for tag in list(desc_tag.find_all(True)):
        if tag.name not in allowed_tags:
            tag.insert_after(" ")
            tag.unwrap()
        else:
            tag.attrs = {}
    metadata = {
        "written by": meta.author,
        "author": meta.author,
        "authors": meta.author,
        "read by": meta.narrator,
        "narrated by": meta.narrator,
        "narrator": meta.narrator,
        "narrators": meta.narrator,
        "format": meta.format,
        "bitrate": meta.bitrate,
        "file size": meta.file_size,
        "total size": meta.file_size,
        "size": meta.file_size,
        "language": meta.language,
        "category": ", ".join(meta.category),
    }
    _strip_description_prefix(desc_tag, metadata)
    return str(desc_tag.decode_contents()).strip() or "No description available."


def _extract_table_data(info_table: Tag | None, file_size_fallback: str) -> tuple[list[str], str, str]:
    """Extract trackers, file size, and info hash from the torrent info table."""
    trackers: list[str] = []
    file_size = file_size_fallback
    info_hash = "Unknown"

    if info_table:
        for row in info_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= MIN_TABLE_CELLS:
                label = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)

                if value == "?" or not value:
                    value = "Unknown"

                label_lower = label.lower()
                if "tracker:" in label_lower or "announce url:" in label_lower:
                    trackers.append(value)
                elif RE_LABEL_SIZE.search(label) and file_size == "Unknown":
                    file_size = value
                elif "Info Hash:" in label:
                    info_hash = value
    return trackers, file_size, info_hash


def _find_info_hash_fallback(soup: BeautifulSoup, current_hash: str) -> str:
    """Find the info hash using fallback strategies."""
    if current_hash != "Unknown":
        return current_hash

    info_hash_row = soup.find(lambda tag: tag.name == "td" and bool(RE_INFO_HASH.search(tag.get_text())))
    if info_hash_row:
        sibling = info_hash_row.find_next_sibling("td")
        if sibling:
            return str(sibling.text.strip())

    post_content_div = soup.select_one(".postContent")
    search_text = post_content_div.get_text() if post_content_div else ""

    hash_match = RE_HASH_STRING.search(search_text)
    if hash_match:
        return hash_match.group(1)

    return "Unknown"


def parse_book_details(soup: BeautifulSoup, url: str) -> BookDetails:
    """Extract full book details from the BeautifulSoup object of a details page."""
    title = "Unknown Title"
    title_tag = soup.select_one(".postTitle h1")
    if title_tag:
        title = title_tag.get_text(strip=True)

    cover = None
    cover_tag = soup.select_one('.postContent img[itemprop="image"]')
    if cover_tag and cover_tag.has_attr("src"):
        cover = normalize_cover_url(url, str(cover_tag["src"]))

    post_info = soup.select_one(".postInfo")
    content_div = soup.select_one(".postContent")
    author_tag = soup.select_one('span.author[itemprop="author"]')
    narrator_tag = soup.select_one('span.narrator[itemprop="author"]')

    meta = parse_post_content(content_div, post_info, author_tag, narrator_tag)
    for contributor_field in ("author", "narrator"):
        credits = [
            tag.get_text(strip=True)
            for tag in soup.select(f'span.{contributor_field}[itemprop="author"]')
            if tag.get_text(strip=True) not in {"", "?", "Unknown"}
        ]
        if credits:
            setattr(meta, contributor_field, ", ".join(dict.fromkeys(credits)))

    desc_tag = soup.select_one("div.desc")

    if desc_tag and (meta.format == "Unknown" or meta.bitrate == "Unknown" or meta.file_size == "Unknown"):
        _parse_body_content(desc_tag, meta)
    _normalize_metadata(meta)

    trackers, file_size, info_hash = _extract_table_data(
        soup.select_one("table.torrent_info") or soup.select_one(".postContent"),
        meta.file_size,
    )

    info_hash = _find_info_hash_fallback(soup, info_hash)
    meta.file_size = file_size
    description = _sanitize_description(desc_tag, meta)

    return {
        "title": title,
        "cover": cover,
        "description": description,
        "trackers": trackers,
        "file_size": file_size,
        "info_hash": info_hash,
        "link": url,
        "language": meta.language,
        "category": meta.category,
        "post_date": meta.post_date,
        "format": meta.format,
        "bitrate": meta.bitrate,
        "author": meta.author,
        "narrator": meta.narrator,
    }


def parse_html(html: str) -> BeautifulSoup:
    """Parse raw HTML string into a BeautifulSoup object."""
    return BeautifulSoup(html, "html.parser")


def parse_search_results(soup: BeautifulSoup, base_url: str) -> list[BookSummary]:
    """Parse search results from the main page soup.

    Args:
        soup: The parsed HTML soup object.
        base_url: The URL of the search page (used for relative links/covers).

    Returns:
        list[BookSummary]: A list of book summaries.
    """
    results: list[BookSummary] = []

    for post in soup.select(".post"):
        title_tag = post.select_one(".postTitle h2 a")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = title_tag.get("href", "")
        if not link:
            continue

        # Use urljoin if link is relative? Usually search links are relative in some contexts
        # But core.py fetch_page_results doesn't need it normalized to absolute yet?
        # Actually BookSummary has 'link'. The app usually handles it.
        # But cover definitely needs normalization.

        cover = None
        cover_tag = post.select_one(".postContent img")
        if cover_tag and cover_tag.has_attr("src"):
            cover = normalize_cover_url(base_url, str(cover_tag["src"]))

        post_info = post.select_one(".postInfo")
        content_div = post.select_one(".postContent")

        if not content_div:
            # Skip invalid/empty posts (satisfies test_fetch_and_parse_page_missing_content_div)
            continue

        meta = parse_post_content(content_div, post_info)

        results.append(
            {
                "title": title,
                "link": str(link),
                "cover": cover,
                "language": meta.language,
                "category": meta.category,
                "post_date": meta.post_date,
                "format": meta.format,
                "bitrate": meta.bitrate,
                "file_size": meta.file_size,
            }
        )

    return results
