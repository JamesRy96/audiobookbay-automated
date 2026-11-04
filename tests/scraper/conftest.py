# File: tests/scraper/conftest.py
"""Fixtures specifically for the scraper test package.

Includes cache clearing mechanisms to ensure test isolation.
"""

from collections.abc import Generator

import pytest

# Import caches from network directly — they are defined there and re-exported via __init__
# to avoid mypy re-export errors when imported from the package root
from audiobook_automated.scraper import network
from audiobook_automated.scraper.network import details_cache, mirror_cache, search_cache


@pytest.fixture(autouse=True)
def clear_caches() -> Generator[None]:
    """Isolate caches, mirror observations and thread-local transports between test cases."""
    network._local.session = None  # pyright: ignore[reportPrivateUsage]
    network._local.ping_session = None  # pyright: ignore[reportPrivateUsage]
    network._mirror_stats.clear()  # pyright: ignore[reportPrivateUsage]
    network.failure_cache.clear()
    # Clear cache in network (used by low-level tests)
    mirror_cache.clear()
    search_cache.clear()
    details_cache.clear()

    yield

    # Cleanup after test
    mirror_cache.clear()
    search_cache.clear()
    details_cache.clear()


@pytest.fixture
def real_world_html() -> str:
    """Returns a real HTML snippet from Audiobook Bay for testing."""
    return """
<div class="post">
    <div class="postTitle">
        <h2><a href="/abss/a-game-of-thrones-chapterized/" rel="bookmark">A Game of Thrones (A Song of Ice and Fire, Book 1) (Chapterized) - George R. R. Martin</a></h2>
    </div>
    <div class="postInfo">
        Category: Adults&nbsp; Bestsellers&nbsp; Fantasy&nbsp; Literature&nbsp; <br>
        Language: English<span style="margin-left:100px;">Keywords: A Game of Thrones&nbsp; </span><br>
    </div>
    <div class="postContent">
        <div class="center">
            <p class="center">Shared by:<a href="#">jason444555</a></p>
            <p class="center">
                <a href="/abss/a-game-of-thrones-chapterized/">
                    <img src="/images/cover.jpg" alt="A Game of Thrones" width="250">
                </a>
            </p>
        </div>
        <p style="text-align:center;">
            Posted: 14 Sep 2021<br>
            Format: <span style="color:#a00;">M4B</span> / Bitrate: <span style="color:#a00;">96 Kbps</span><br>
            File Size: <span style="color:#00f;">1.37</span> GBs
        </p>
    </div>
</div>
"""


@pytest.fixture
def details_html() -> str:
    """Return a mock Details page HTML.

    Updated to include Category and Posted fields to ensure full coverage of regex parsers.
    """
    return """
<div class="post">
    <div class="postTitle"><h1>A Game of Thrones</h1></div>
    <div class="postInfo">
        Language: English
        Category: Fantasy
    </div>
    <div class="postContent">
        <img itemprop="image" src="/cover.jpg">
        <p>Format: <span>M4B</span> / Bitrate: <span>96 Kbps</span></p>
        <p>Posted: 10 Jan 2024</p>
        <span class="author" itemprop="author">George R.R. Martin</span>
        <span class="narrator" itemprop="author">Roy Dotrice</span>
        <div class="desc">
            <p>This is a great book.</p>
            <a href="https://example.com/spam">Spam Link</a>
        </div>
    </div>
    <table class="torrent_info">
        <tr><td>Tracker:</td><td>udp://tracker.opentrackr.org:1337/announce</td></tr>
        <tr><td>File Size:</td><td>1.37 GBs</td></tr>
        <tr><td>Info Hash:</td><td>eb154ac7886539c4d01eae14908586e336cdb550</td></tr>
    </table>
</div>
"""
