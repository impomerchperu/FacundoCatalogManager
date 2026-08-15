-- ==========================================================
-- FACUNDO CATALOG MANAGER
-- Database Schema
-- ==========================================================

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    price REAL DEFAULT 0,
    price_sample REAL DEFAULT 0,
    price_hundred REAL DEFAULT 0,
    price_thousand REAL DEFAULT 0,
    stock INTEGER DEFAULT 0,
    color_stock TEXT DEFAULT '{}',
    image_url TEXT,
    image_path TEXT,
    image_hash TEXT DEFAULT '',
    content_hash TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scraped_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    code TEXT,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    stock INTEGER DEFAULT 0,
    price REAL DEFAULT 0,
    price_sample REAL DEFAULT 0,
    price_hundred REAL DEFAULT 0,
    price_thousand REAL DEFAULT 0,
    color_stock TEXT DEFAULT '{}',
    image_url TEXT,
    image_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    url TEXT DEFAULT '',
    name TEXT,
    category TEXT,
    description TEXT DEFAULT '',
    price REAL DEFAULT 0,
    price_sample REAL DEFAULT 0,
    price_hundred REAL DEFAULT 0,
    price_thousand REAL DEFAULT 0,
    stock INTEGER DEFAULT 0,
    color_stock TEXT DEFAULT '{}',
    image_url TEXT DEFAULT '',
    image_path TEXT DEFAULT '',
    content_hash TEXT DEFAULT '',
    image_hash TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scraping_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    created INTEGER DEFAULT 0,
    updated INTEGER DEFAULT 0,
    unchanged INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    status TEXT DEFAULT 'SUCCESS',
    message TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS download_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id INTEGER NOT NULL,
    change_type TEXT NOT NULL,
    code TEXT NOT NULL,
    product_name TEXT NOT NULL,
    field_name TEXT,
    field_label TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    FOREIGN KEY (history_id) REFERENCES scraping_history(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS catalog_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scraping_history_finished_at
ON scraping_history(finished_at);

CREATE INDEX IF NOT EXISTS idx_download_changes_history_id
ON download_changes(history_id);

CREATE INDEX IF NOT EXISTS idx_download_changes_code
ON download_changes(code);
