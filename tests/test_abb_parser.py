from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "app")

from adapters.abb.parser import (
    parse_details_author,
    parse_magnet_link,
    parse_search_results,
)

SEARCH_HTML = """
<div class="post">
  <div class="postTitle"><h2><a href="/book/example">Example Book - Example Author</a></h2></div>
  <img src="https://covers.example/book.jpg" />
  <div class="postInfo">Author: Example Author Language: English Keywords: fiction</div>
  <div class="postContent">
    <p style="text-align:center">
      Posted: 10 Jan 2026
      Format: <span>MP3</span>
      Bitrate: <span>128Kbps</span>
      File Size: <span>500</span> MB
    </p>
  </div>
</div>
"""

DETAILS_HTML = """
<table>
  <tr><td>Info Hash</td><td>ABC123HASH</td></tr>
  <tr><td>udp://tracker.example:80</td></tr>
</table>
<div>
  Written by Andy Weir
  Read by Ray Porter
  Format: MP3
</div>
"""

DETAILS_HTML_AUTHOR = """
<div>
  Author: Andy Weir
  Language: English
</div>
"""

DETAILS_HTML_BY = """
<div>
  By: Andy Weir
  Category: Sci-Fi
</div>
"""


class AbbParserTests(unittest.TestCase):
    def test_parse_search_results_returns_book_result(self):
        results = parse_search_results(
            SEARCH_HTML,
            "audiobookbay.lu",
            lambda _url: True,
        )

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result.title, "Example Book")
        self.assertEqual(result.author, "Example Author")
        self.assertEqual(result.language, "English")
        self.assertEqual(result.format, "MP3")
        self.assertEqual(result.file_size, "500 MB")

    def test_parse_search_results_infers_author_from_title(self):
        html = """
        <div class="post">
          <div class="postTitle"><h2><a href="/book/example">Example Book - Example Author</a></h2></div>
          <div class="postInfo">Language: English Keywords: fiction</div>
          <div class="postContent">
            <p style="text-align:center">
              Posted: 10 Jan 2026
              Format: <span>MP3</span>
              Bitrate: <span>128Kbps</span>
              File Size: <span>500</span> MB
            </p>
          </div>
        </div>
        """

        results = parse_search_results(html, "audiobookbay.lu", lambda _url: True)

        self.assertEqual(results[0].author, "Example Author")
        self.assertEqual(results[0].title, "Example Book")

    def test_parse_search_results_uses_last_title_separator_for_author(self):
        html = """
        <div class="post">
          <div class="postTitle"><h2><a href="/book/example">Harry Potter - Order of the Phoenix - J.K. Rowling</a></h2></div>
          <div class="postInfo">Language: English Keywords: fiction</div>
          <div class="postContent">
            <p style="text-align:center">
              Posted: 10 Jan 2026
              Format: <span>MP3</span>
              Bitrate: <span>128Kbps</span>
              File Size: <span>500</span> MB
            </p>
          </div>
        </div>
        """

        results = parse_search_results(html, "audiobookbay.lu", lambda _url: True)

        self.assertEqual(results[0].author, "J.K. Rowling")
        self.assertEqual(results[0].title, "Harry Potter - Order of the Phoenix")

    def test_parse_magnet_link_returns_magnet(self):
        magnet_link = parse_magnet_link(DETAILS_HTML)

        self.assertIsNotNone(magnet_link)
        self.assertIn("magnet:?xt=urn:btih:ABC123HASH", magnet_link)
        self.assertIn("tracker.example", magnet_link)

    def test_parse_details_author_returns_written_by_value(self):
        author = parse_details_author(DETAILS_HTML)

        self.assertEqual(author, "Andy Weir")

    def test_parse_details_author_accepts_author_label(self):
        author = parse_details_author(DETAILS_HTML_AUTHOR)

        self.assertEqual(author, "Andy Weir")

    def test_parse_details_author_accepts_by_label(self):
        author = parse_details_author(DETAILS_HTML_BY)

        self.assertEqual(author, "Andy Weir")


if __name__ == "__main__":
    unittest.main()
