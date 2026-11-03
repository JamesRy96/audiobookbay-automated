<!-- File: tests/e2e/catalog/captured/README.md -->
# Captured AudiobookBay parser inputs

These inputs were fetched from the real mirror through an authorized HTTP proxy. `manifest.json` records the source
URLs, UTC capture time, known info hashes, tracker text and checksums for Details captures. `search-encoded.html` was
captured from the Grover Gardner search during the same audit; it contains nine listings, including five base64
`post re-ab` blocks that the mirror reveals with JavaScript. The expected links were checked against the native
browser listings. This is a real example of records missed by the previous parser.

Only parser-relevant catalog posts are retained. Scripts, forms, embedded frames and comments were removed from
Details captures; titles, descriptions, cast lists, tracker order/duplicates and encoding were not rewritten into
idealized metadata. Prettier and spelling checks exclude captured files so these source irregularities survive.

The test server consumes this HTML through the normal scraper pipeline. Its qBittorrent SDK boundary stores tasks
only in memory, and browser traffic to external hosts is blocked. No real downloads or user accounts are used.
Synthetic sibling fixtures remain for layout/screenshots and deterministic missing/error scenarios.

When refreshing a capture, use the authorized proxy, preserve the problematic source structure, update its metadata
and independently verify the expected links/hashes. Never generate expected records from the parser being tested.
Keep personal client data, credentials and browser session cookies out of captures. These snapshots establish
repeatable regressions; they do not establish current live mirror availability or complete downloader compatibility.
