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
    colors TEXT DEFAULT '[]',
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
    colors TEXT DEFAULT '[]',
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
    image_url TEXT DEFAULT '',
    image_path TEXT DEFAULT '',
    content_hash TEXT DEFAULT '',
    image_hash TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS download_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    processed INTEGER NOT NULL DEFAULT 0,
    new_products INTEGER NOT NULL DEFAULT 0,
    updated_products INTEGER NOT NULL DEFAULT 0,
    unchanged_products INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'SUCCESS',
    message TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS download_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    history_id INTEGER NOT NULL,
    change_type TEXT NOT NULL,
    code TEXT NOT NULL,
    product_name TEXT NOT NULL DEFAULT '',
    field_name TEXT,
    field_label TEXT,
    old_value TEXT,
    new_value TEXT,
    FOREIGN KEY (history_id) REFERENCES download_history(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_products_code
ON products(code);

CREATE INDEX IF NOT EXISTS idx_products_category
ON products(category);

CREATE INDEX IF NOT EXISTS idx_download_history_created_at
ON download_history(created_at);

CREATE INDEX IF NOT EXISTS idx_download_changes_history_id
ON download_changes(history_id);

CREATE INDEX IF NOT EXISTS idx_download_changes_code
ON download_changes(code);

-- Legacy tables are intentionally retained for existing databases.
-- They are no longer used by the active catalog/history workflow.
CREATE TABLE IF NOT EXISTS catalog_loads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'SCRAPING',
    status TEXT NOT NULL DEFAULT 'SUCCESS',
    applied INTEGER NOT NULL DEFAULT 0,
    applied_at TEXT,
    product_count INTEGER NOT NULL DEFAULT 0,
    message TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS catalog_load_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    load_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    price REAL DEFAULT 0,
    price_sample REAL DEFAULT 0,
    price_hundred REAL DEFAULT 0,
    price_thousand REAL DEFAULT 0,
    stock INTEGER DEFAULT 0,
    colors TEXT DEFAULT '[]',
    color_stock TEXT DEFAULT '{}',
    image_url TEXT,
    image_path TEXT,
    image_hash TEXT DEFAULT '',
    content_hash TEXT DEFAULT '',
    FOREIGN KEY (load_id) REFERENCES catalog_loads(id) ON DELETE CASCADE,
    UNIQUE(load_id, code)
);

CREATE TABLE IF NOT EXISTS scraping_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    load_id INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    created INTEGER DEFAULT 0,
    updated INTEGER DEFAULT 0,
    unchanged INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    status TEXT DEFAULT 'SUCCESS',
    message TEXT DEFAULT '',
    FOREIGN KEY (load_id) REFERENCES catalog_loads(id) ON DELETE SET NULL
);
