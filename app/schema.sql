CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    details_url TEXT NOT NULL,
    magnet_link TEXT,
    client TEXT,
    external_id TEXT,
    state TEXT NOT NULL DEFAULT 'queued',
    progress REAL NOT NULL DEFAULT 0,
    error TEXT,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS import_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    download_id INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    source_path TEXT,
    target_path TEXT,
    mode TEXT,
    error TEXT,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY(download_id) REFERENCES downloads(id)
);
