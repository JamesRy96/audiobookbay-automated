# File: tests/scraper/test_parser.py
# pyright: reportPrivateUsage=false
"""Tests for the parser module."""

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from audiobook_automated.scraper.parser import (
    RE_CATEGORY,
    RE_HASH_STRING,
    RE_LABEL_FORMAT,
    RE_LABEL_SIZE,
    RE_LANGUAGE,
    BookDetails,
    BookMetadata,
    _extract_table_data,
    _normalize_metadata,
    _parse_categories_from_info,
    _sanitize_description,
    get_text_after_label,
    normalize_cover_url,
    parse_book_details,
    parse_post_content,
)


def test_parse_post_content_integration() -> None:
    """Integration test for parsing post content using a local fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_page.html"
    html_content = fixture_path.read_text(encoding="utf-8")

    soup = BeautifulSoup(html_content, "lxml")
    post = soup.select_one(".post")
    assert post is not None
    content_div = post.select_one(".postContent")
    assert content_div is not None
    post_info = post.select_one(".postInfo")
    assert post_info is not None

    meta = parse_post_content(content_div, post_info)

    assert meta.language == "English"
    assert meta.format == "MP3"
    assert meta.bitrate == "128 Kbps"


# --- Merged Coverage Tests from test_parser_coverage.py ---

HTML_STANDARD_DETAILS = """
<div class="post">
    <div class="postTitle"><h1>Valid Book Title</h1></div>
    <div class="desc">
        <p>Description line 1.</p>
        <script>alert('xss')</script>
        <p style="color:red">Bad Style</p>
    </div>
    <div class="postContent">
        <img itemprop="image" src="/images/cover.jpg">
        <p>Posted: 01 Jan 2024</p>
        <p>Format: MP3</p>
    </div>
    <div class="postInfo">Category: Sci-Fi Language: English</div>
    <span class="author" itemprop="author">Isaac Asimov</span>
    <span class="narrator" itemprop="author">John Doe</span>
    <table class="torrent_info">
        <tr><td>Tracker:</td><td>udp://tracker.opentrackr.org:1337</td></tr>
        <tr><td>Info Hash:</td><td>aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa</td></tr>
        <tr><td>File Size:</td><td>1.2 GB</td></tr>
    </table>
</div>
"""

HTML_MISSING_HASH_TABLE = """
<div class="post">
    <div class="postTitle"><h1>No Hash Table</h1></div>
    <div class="postContent">Content</div>
    <table>
        <tr><td>Info Hash</td><td>bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb</td></tr>
    </table>
</div>
"""

HTML_REGEX_FALLBACK = """
<div class="post">
    <div class="postTitle"><h1>Regex Fallback</h1></div>
    <div class="postContent">
        Some content with hash embedded: cccccccccccccccccccccccccccccccccccccccc
    </div>
</div>
"""


def test_parse_standard_details() -> None:
    """Test standard details page parsing including trackers and sanitization."""
    soup = BeautifulSoup(HTML_STANDARD_DETAILS, "lxml")
    result: BookDetails = parse_book_details(soup, "http://test.com/book")

    assert result["title"] == "Valid Book Title"
    assert result["info_hash"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert result["file_size"] == "1.2 GB"
    assert result["author"] == "Isaac Asimov"
    assert "udp://tracker.opentrackr.org:1337" in result["trackers"]

    # Check Description Sanitization
    assert "<script>" not in result["description"]
    assert 'style="color:red"' not in result["description"]
    assert "<p>Description line 1.</p>" in result["description"]


def test_parse_fallback_hash_footer() -> None:
    """Test info hash extraction from footer when missing from table."""
    soup = BeautifulSoup(HTML_MISSING_HASH_TABLE, "lxml")
    result: BookDetails = parse_book_details(soup, "http://test.com/book")
    assert result["info_hash"] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def test_parse_fallback_hash_regex() -> None:
    """Test info hash extraction via regex when missing from DOM."""
    soup = BeautifulSoup(HTML_REGEX_FALLBACK, "lxml")
    result: BookDetails = parse_book_details(soup, "http://test.com/book")
    assert result["info_hash"] == "cccccccccccccccccccccccccccccccccccccccc"


def test_language_parsing_multi_word() -> None:
    """Test parsing of multi-word languages."""
    # Mock HTML snippet
    html = """
    <div class="postInfo">
        Category: Audiobooks Language: English (UK) Format: MP3
    </div>
    <div class="postContent">
        <p>Some content</p>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    post_info = soup.select_one(".postInfo")
    content_div = soup.select_one(".postContent")

    # Cast to Tag for MyPy
    assert isinstance(post_info, Tag)
    assert isinstance(content_div, Tag)

    meta = parse_post_content(content_div, post_info)
    assert meta.language == "English (UK)"


def test_language_parsing_multi_word_end_of_string() -> None:
    """Test parsing of multi-word languages at end of string."""
    html = """
    <div class="postInfo">
        Category: Audiobooks Language: English (US)
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    post_info = soup.select_one(".postInfo")

    # Cast to Tag for MyPy
    assert isinstance(post_info, Tag)

    meta = parse_post_content(None, post_info)
    assert meta.language == "English (US)"


def test_parse_book_details_cover_normalization() -> None:
    """Test cover URL normalization integration within parse_book_details."""
    soup = BeautifulSoup(HTML_STANDARD_DETAILS, "lxml")
    result: BookDetails = parse_book_details(soup, "http://base.com/page/")
    assert result["cover"] == "http://base.com/images/cover.jpg"


def test_parse_book_details_robustness() -> None:
    """Test robustness against missing elements (title, content, etc)."""
    minimal_html = "<html><body>Nothing here</body></html>"
    soup = BeautifulSoup(minimal_html, "lxml")
    result: BookDetails = parse_book_details(soup, "http://test.com")

    assert result["title"] == "Unknown Title"
    assert result["info_hash"] == "Unknown"
    assert result["description"] == "No description available."


def test_tracker_label_case_insensitive() -> None:
    """Test that tracker extraction works with mixed-case labels (e.g. TRACKER:)."""
    html = """
    <table class="torrent_info">
        <tr><td>TRACKER:</td><td>udp://tracker.TEST:1337</td></tr>
        <tr><td>Announce URL:</td><td>udp://announce.TEST:80</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    assert isinstance(table, Tag)
    trackers, _, _ = _extract_table_data(table, "Unknown")

    assert "udp://tracker.TEST:1337" in trackers
    assert "udp://announce.TEST:80" in trackers


def test_fallback_hash_in_script_ignored() -> None:
    """Test that fallback hash search ignores script tags (searches .postContent only)."""
    # 40-char hash in a script tag (should be ignored)
    fake_hash = "1111111111111111111111111111111111111111"
    # 40-char hash in postContent (should be found)
    real_hash = "2222222222222222222222222222222222222222"

    html = f"""
    <html>
        <script>var x = "{fake_hash}";</script>
        <body>
            <div class="postContent">
                Hash: {real_hash}
            </div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")

    # We call parse_book_details which invokes _find_info_hash_fallback
    # Since table is missing, it goes to fallback.
    details = parse_book_details(soup, "http://test")

    assert details["info_hash"] == real_hash
    assert details["info_hash"] != fake_hash


def test_fallback_hash_no_post_content() -> None:
    """Test fallback behavior when .postContent is missing (should be robust)."""
    fake_hash = "1111111111111111111111111111111111111111"
    html = f"""
    <html>
        <body>
            <script>var x = "{fake_hash}";</script>
            <div>No Post Content</div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "lxml")
    details = parse_book_details(soup, "http://test")

    # Should not find the fake hash in script because we only search .postContent
    # And .postContent is missing.
    assert details["info_hash"] == "Unknown"


def test_normalize_metadata_complex_cases() -> None:
    """Test explicit normalization logic for tricky strings (starting with '? ')."""
    meta = BookMetadata(file_size="? 100 MB", bitrate="  ?  ")
    _normalize_metadata(meta)
    assert meta.file_size == "Unknown"
    assert meta.bitrate == "Unknown"


def test_sanitize_description_merging() -> None:
    """Test that sanitization doesn't merge words when unwrapping tags."""
    html = "<div><div class='custom'>Hello</div><div class='custom'>World</div></div>"
    soup = BeautifulSoup(html, "lxml").find("div")
    assert isinstance(soup, Tag)
    res = _sanitize_description(soup, BookMetadata())
    assert "Hello World" in res


def test_extract_table_data_empty_values() -> None:
    """Test that '?' or empty strings in table data become 'Unknown'."""
    html = """
    <table class="torrent_info">
        <tr><td>Tracker:</td><td>?</td></tr>
        <tr><td>Info Hash:</td><td></td></tr>
        <tr><td>File Size:</td><td>   </td></tr>
    </table>
    """
    table = BeautifulSoup(html, "lxml").find("table")
    assert isinstance(table, Tag)
    trackers, size, info_hash = _extract_table_data(table, "Fallback")
    assert trackers == ["Unknown"]
    assert info_hash == "Unknown"
    assert size == "Fallback"


def test_get_text_after_label_simple() -> None:
    """Test simple case: Label: Value in text node."""
    html = "<p>Format: MP3</p>"
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("p")
    # Cast to Tag for type checker safety (soup.find returns Tag | NavigableString | None)
    assert isinstance(container, Tag)

    pattern = re.compile(r"Format:")
    assert get_text_after_label(container, pattern) == "MP3"


def test_get_text_after_label_with_span() -> None:
    """Test case where value is in a sibling span."""
    html = "<p>Format: <span>MP3</span></p>"
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("p")
    assert isinstance(container, Tag)
    assert isinstance(container, Tag)

    pattern = re.compile(r"Format:")
    assert get_text_after_label(container, pattern) == "MP3"


def test_get_text_after_label_nested_label() -> None:
    """Test case where label is nested in a bold tag."""
    html = "<p><b>Format:</b> <span>MP3</span></p>"
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("p")
    assert isinstance(container, Tag)

    pattern = re.compile(r"Format:")
    assert get_text_after_label(container, pattern) == "MP3"


def test_get_text_after_label_file_size() -> None:
    """Test file size extraction with unit."""
    html = "<p>File Size: <span>100</span> MB</p>"
    # Note: unit is a text sibling of span
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("p")
    assert isinstance(container, Tag)

    pattern = re.compile(r"File Size:")
    # The logic `is_file_size=True` handles `next_elem.next_sibling`.
    assert get_text_after_label(container, pattern, is_file_size=True) == "100 MB"


def test_regex_language() -> None:
    """Test language regex against various formats."""
    assert RE_LANGUAGE.search("Language: English")
    assert RE_LANGUAGE.search("Language:   English")
    match = RE_LANGUAGE.search("Category: Sci-Fi Language: English")
    assert match and match.group(1) == "English"


def test_regex_category() -> None:
    """Test category regex against various formats."""
    # Standard format
    match = RE_CATEGORY.search("Category: Sci-Fi Language: English")
    assert match and match.group(1).strip() == "Sci-Fi"

    # Missing language (end of string)
    match = RE_CATEGORY.search("Category: Fantasy")
    assert match and match.group(1).strip() == "Fantasy"

    # Multiple categories
    match = RE_CATEGORY.search("Category: Sci-Fi, Action Language: English")
    assert match and match.group(1).strip() == "Sci-Fi, Action"


def test_regex_hash() -> None:
    """Test hash regex supports SHA-1 and SHA-256 (BitTorrent v2)."""
    # SHA-1 (40 hex chars)
    sha1 = "a" * 40
    assert RE_HASH_STRING.search(f"Info Hash: {sha1}")

    # SHA-256 (64 hex chars)
    sha256 = "b" * 64
    assert RE_HASH_STRING.search(f"Info Hash: {sha256}")

    # Invalid length
    assert not RE_HASH_STRING.search("Info Hash: " + "c" * 39)
    assert not RE_HASH_STRING.search("Info Hash: " + "d" * 65)


def test_metadata_normalization_explicit() -> None:
    """Test metadata normalization logic explicitly."""
    meta = BookMetadata(
        category=["Sci-Fi", "", "?", "Unknown"],
        file_size="? ",
        bitrate="?",
        language=" English ",
    )
    _normalize_metadata(meta)

    assert meta.category == ["Sci-Fi", "Unknown", "Unknown", "Unknown"]
    assert meta.file_size == "Unknown"
    assert meta.bitrate == "Unknown"
    assert meta.language == "English"


def test_get_text_after_label_nested_sibling() -> None:
    """Test get_text_after_label where the value is in a sibling of the parent (recursive check)."""
    # The current logic only checks:
    # 1. next_sibling
    # 2. parent.next_sibling (if parent name not in block tags)
    # In "<div><p><strong>Format:</strong></p><span>MP3</span></div>":
    # - "Format:" is in <strong>.
    # - <strong> next sibling is None (inside <p>).
    # - <strong> parent is <p>. <p> IS in ["div", "p", "td", "li"].
    # - So it STOPS recursion and returns "Unknown".
    #
    # To test the recursion success, we need a parent that is NOT in the block list.
    # E.g. <span><strong>Format:</strong></span><span>MP3</span>

    html = "<div><span><strong>Format:</strong></span><span>MP3</span></div>"
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div")
    assert isinstance(container, Tag)
    assert get_text_after_label(container, RE_LABEL_FORMAT) == "MP3"


def test_get_text_after_label_file_size_unit() -> None:
    """Test get_text_after_label for file size where unit is in next sibling text node."""
    html = """
    <div>
        <span>File Size:</span>
        <span>123</span> MB
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div")
    assert isinstance(container, Tag)
    assert get_text_after_label(container, RE_LABEL_SIZE, is_file_size=True) == "123 MB"


def test_normalize_metadata_category_list() -> None:
    """Test normalization of category list."""
    meta = BookMetadata(category=["A", "?", " ", ""])
    _normalize_metadata(meta)
    assert meta.category == ["A", "Unknown", "Unknown", "Unknown"]


def test_normalize_metadata_category_empty_list() -> None:
    """Test normalization of empty category list."""
    meta = BookMetadata(category=[])
    _normalize_metadata(meta)
    assert meta.category == ["Unknown"]


def test_parse_post_content_category_splitting() -> None:
    """Test that parse_post_content splits categories with non-breaking spaces and commas."""
    # HTML with non-breaking spaces
    html_nbsp = """
    <div class="postInfo">
        Category: Adults&nbsp; Bestsellers&nbsp; LitRPG&nbsp; Sci-Fi&nbsp; Language: Spanish
    </div>
    """
    soup_nbsp = BeautifulSoup(html_nbsp, "lxml")
    post_info_nbsp = soup_nbsp.select_one(".postInfo")
    assert isinstance(post_info_nbsp, Tag)
    meta_nbsp = parse_post_content(None, post_info_nbsp)
    assert meta_nbsp.category == ["Adults", "Bestsellers", "LitRPG", "Sci-Fi"]

    # HTML with comma separation
    html_comma = """
    <div class="postInfo">
        Category: Sci-Fi, Action, Fantasy Language: English
    </div>
    """
    soup_comma = BeautifulSoup(html_comma, "lxml")
    post_info_comma = soup_comma.select_one(".postInfo")
    assert isinstance(post_info_comma, Tag)
    meta_comma = parse_post_content(None, post_info_comma)
    assert meta_comma.category == ["Sci-Fi", "Action", "Fantasy"]

    # Multi-word categories with non-breaking spaces (e.g. Teens & Young Adults)
    html_multiword = """
    <div class="postInfo">
        Category: Teens & Young Adults&nbsp; Sci-Fi & Fantasy&nbsp; True Crime&nbsp; Language: English
    </div>
    """
    soup_multiword = BeautifulSoup(html_multiword, "lxml")
    post_info_multiword = soup_multiword.select_one(".postInfo")
    assert isinstance(post_info_multiword, Tag)
    meta_multiword = parse_post_content(None, post_info_multiword)
    assert meta_multiword.category == ["Teens & Young Adults", "Sci-Fi & Fantasy", "True Crime"]

    # Categories from anchor tags
    html_anchors = """
    <div class="postInfo">
        Category: <a href="/category/teens-young-adults/">Teens & Young Adults</a> <a href="/category/sci-fi/">Sci-Fi</a> Language: English
    </div>
    """
    soup_anchors = BeautifulSoup(html_anchors, "lxml")
    post_info_anchors = soup_anchors.select_one(".postInfo")
    assert isinstance(post_info_anchors, Tag)
    meta_anchors = parse_post_content(None, post_info_anchors)
    assert meta_anchors.category == ["Teens & Young Adults", "Sci-Fi"]


def test_normalize_metadata_strings() -> None:
    """Test normalization of string fields."""
    meta = BookMetadata(format="? ", bitrate="")
    _normalize_metadata(meta)
    assert meta.format == "Unknown"
    assert meta.bitrate == "Unknown"


def test_get_text_after_label_not_found() -> None:
    """Test when the label pattern is not found in the container."""
    html = "<div><p>Other Content</p></div>"
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div")
    assert isinstance(container, Tag)
    # Pattern that doesn't exist
    assert get_text_after_label(container, re.compile(r"Missing:")) == "Unknown"


def test_get_text_after_label_method2_fallback() -> None:
    """Test method 2 (text split) fallbacks."""
    # Case 1: No colon
    html_no_colon = "<p>Format MP3</p>"
    soup = BeautifulSoup(html_no_colon, "lxml")
    container = soup.find("p")
    assert isinstance(container, Tag)
    assert get_text_after_label(container, re.compile(r"Format")) == "Unknown"

    # Case 2: Colon but empty value
    html_empty = "<p>Format: </p>"
    soup = BeautifulSoup(html_empty, "lxml")
    container = soup.find("p")
    assert isinstance(container, Tag)
    assert get_text_after_label(container, re.compile(r"Format")) == "Unknown"


def test_get_text_after_label_exception() -> None:
    """Test exception handling in get_text_after_label."""
    # Pass a Mock that raises an exception when .find() is called
    mock_container = Tag(name="div")
    # We can't easily mock BeautifulSoup Tag methods directly without side effects,
    # but we can pass something that is NOT a tag but acts like one until it breaks.
    # Or rely on the fact that `container.find` might raise if container is None (but type hint says Tag).
    # Easier: Mock the find method of a real tag instance.
    from unittest.mock import MagicMock

    mock_container.find = MagicMock(side_effect=Exception("Boom"))  # type: ignore

    assert get_text_after_label(mock_container, RE_LABEL_FORMAT) == "Unknown"


def test_normalize_cover_url_empty() -> None:
    """Test normalize_cover_url with empty input."""
    assert normalize_cover_url("http://base.com", "") is None
    assert normalize_cover_url("http://base.com", None) is None  # type: ignore


def test_parse_details_format_in_desc() -> None:
    """Test parsing Format and Bitrate when they appear in the description div."""
    html = """
    <div class="post">
        <div class="postTitle"><h1>Desc Format Book</h1></div>
        <div class="desc">
            <p>Description line.</p>
            <p>Format: M4B</p>
            <p>Bitrate: 64 Kbps</p>
        </div>
        <div class="postContent">
            <p>Posted: 01 Jan 2024</p>
        </div>
        <div class="postInfo">Category: Audiobooks Language: English</div>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    result: BookDetails = parse_book_details(soup, "http://test.com/book")

    assert result["format"] == "M4B"
    assert result["bitrate"] == "64 Kbps"


def test_parse_categories_empty_match() -> None:
    """Test category parsing when category match is whitespace only."""
    html = """
    <div class="postInfo">
        Category:    Language: English
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    post_info = soup.select_one(".postInfo")
    assert isinstance(post_info, Tag)
    cats = _parse_categories_from_info(post_info)
    assert cats == ["Unknown"]


def test_garbage_html_parsing() -> None:
    """Test robustness against completely garbage HTML."""
    from bs4 import BeautifulSoup

    from audiobook_automated.scraper.parser import parse_book_details

    html = "<div><p>Random Text</p> @#%*&^ </div>"
    soup = BeautifulSoup(html, "lxml")
    result = parse_book_details(soup, "http://test.com")

    assert result["title"] == "Unknown Title"
    assert result["info_hash"] == "Unknown"
    assert result["description"] == "No description available."


def test_details_size_from_unclassified_table_and_lowercase_label() -> None:
    """Recognize catalog size rows without requiring one table class or case."""
    soup = BeautifulSoup(
        '<div class="postContent"><table><tr><td>file size:</td><td>531.35 MB</td></tr></table></div>', "html.parser"
    )
    assert parse_book_details(soup, "https://example.com/book")["file_size"] == "531.35 MB"


def test_details_size_in_description_with_known_audio_format() -> None:
    """Parse a description size even when format and bitrate are already known."""
    soup = BeautifulSoup(
        '<div class="postContent"><p>Format: MP3</p><p>Bitrate: 128 Kbps</p><div class="desc"><p>File Size: 42 MB</p></div></div>',
        "html.parser",
    )
    assert parse_book_details(soup, "https://example.com/book")["file_size"] == "42 MB"


def test_description_metadata_header_keeps_all_contributors_and_audio_fields() -> None:
    """Read raw header spans before cleanup and retain the entire cast."""
    soup = BeautifulSoup(
        '<div class="desc"><p>Written by <span class="author" itemprop="author">Jane Doe</span>, '
        '<span class="author" itemprop="author">John Smith</span><br>'
        'Read by <span class="narrator" itemprop="author">Jeff Hays</span>, '
        '<span class="narrator" itemprop="author">Annie Ellicott</span>, '
        '<span class="narrator" itemprop="author">Jeff Hays</span><br>'
        "Format: <span>M4B</span><br>Bitrate: <span>Variable</span><br>Dramatization</p>"
        "<p>A <b>richly told</b> story.</p></div>",
        "html.parser",
    )
    result = parse_book_details(soup, "https://example.com/book")
    assert result["author"] == "Jane Doe, John Smith"
    assert result["narrator"] == "Jeff Hays, Annie Ellicott"
    # A repeated credit in the original header is not identical to the deduplicated field.
    assert "Read by" in result["description"]
    assert result["format"] == "M4B"
    assert result["bitrate"] == "Variable"
    assert "<b>richly told</b>" in result["description"]


def test_description_removes_matching_prefix_but_keeps_unique_notes_and_synopsis() -> None:
    """Remove BR-separated duplicates, stopping at the first unique line."""
    soup = BeautifulSoup(
        "<div><p>Written by <b>Matt Dinniman</b><br>Read by Jeff Hays , Annie Ellicott<br>Format:M4B<br>Bitrate: Variable<br>Dramatization</p><p>A <i>real</i> synopsis.</p></div>",
        "html.parser",
    ).div
    assert isinstance(soup, Tag)
    result = _sanitize_description(
        soup,
        BookMetadata(author="Matt Dinniman", narrator="Jeff Hays, Annie Ellicott", format="M4B", bitrate="Variable"),
    )
    assert "Written by" not in result
    assert "Read by" not in result
    assert "Format:" not in result
    assert "Bitrate:" not in result
    assert "<p>Dramatization</p>" in result
    assert "<i>real</i>" in result


def test_description_does_not_remove_missing_metadata_or_prose() -> None:
    """Preserve unmatched credits and label-like sentences in the synopsis."""
    for html in [
        "<p>Written by Someone Else</p><p>Format: M4B</p>",
        "<p>Written by the victor, the account is unreliable.</p>",
        "<p>A synopsis.</p><p>Format: M4B</p>",
        "A synopsis.<p>Format: M4B</p>",
        "A synopsis.<br>Format: M4B",
    ]:
        soup = BeautifulSoup("<div>" + html + "</div>", "html.parser").div
        assert isinstance(soup, Tag)
        result = _sanitize_description(soup, BookMetadata(format="M4B"))
        assert BeautifulSoup(result, "html.parser").get_text() == BeautifulSoup(html, "html.parser").get_text()


def test_description_metadata_only_and_plain_root_lines() -> None:
    """Handle complete duplicate blocks and direct BR lines without empty shells."""
    for html in [
        "<p>Author: Jane Doe</p><p>Narrator: John Smith</p><p>Format: M4B</p>",
        "Written by Jane Doe<br>Read by John Smith<br>Format: M4B<br>",
        "<p>Language: English</p><p>Category: Fantasy</p><p>Total Size: 42 MB</p>",
    ]:
        soup = BeautifulSoup("<div>" + html + "</div>", "html.parser").div
        assert isinstance(soup, Tag)
        assert (
            _sanitize_description(
                soup,
                BookMetadata(
                    author="Jane Doe",
                    narrator="John Smith",
                    format="M4B",
                    language="English",
                    category=["Fantasy"],
                    file_size="42 MB",
                ),
            )
            == "No description available."
        )
    soup = BeautifulSoup("<div>Format: M4B<br><p>Synopsis.</p></div>", "html.parser").div
    assert isinstance(soup, Tag)
    assert _sanitize_description(soup, BookMetadata(format="M4B")) == "<p>Synopsis.</p>"


def test_description_unknown_structured_credit_is_retained() -> None:
    """Do not hide an unrepresented credit merely because its label matches."""
    soup = BeautifulSoup("<div><p>Read by Jane Doe</p><p>Synopsis.</p></div>", "html.parser").div
    assert isinstance(soup, Tag)
    assert "Read by Jane Doe" in _sanitize_description(soup, BookMetadata())
