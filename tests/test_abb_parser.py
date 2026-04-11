from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "app")

from adapters.abb.parser import parse_magnet_link, parse_search_results

SEARCH_HTML = """
<div class="post">
  <div class="postTitle"><h2><a href="/book/example">Example Book</a></h2></div>
  <img src="https://covers.example/book.jpg" />
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

DETAILS_HTML = """
<table>
  <tr><td>Info Hash</td><td>ABC123HASH</td></tr>
  <tr><td>udp://tracker.example:80</td></tr>
</table>
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
        self.assertEqual(result.language, "English")
        self.assertEqual(result.format, "MP3")
        self.assertEqual(result.file_size, "500 MB")

    def test_parse_magnet_link_returns_magnet(self):
        magnet_link = parse_magnet_link(DETAILS_HTML)

        self.assertIsNotNone(magnet_link)
        self.assertIn("magnet:?xt=urn:btih:ABC123HASH", magnet_link)
        self.assertIn("tracker.example", magnet_link)


if __name__ == "__main__":
    unittest.main()
