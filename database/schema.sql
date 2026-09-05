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

-- Fuente histórica/compatibilidad. El scraper normalizado no depende de esta tabla.
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

-- Fuente histórica/compatibilidad. Las nuevas ejecuciones no dependen de esta tabla.
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

-- Categorías descubiertas por el scraper. canonical_url es la identidad estable.
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    canonical_url TEXT NOT NULL UNIQUE,
    expected_count INTEGER DEFAULT 0,
    last_scraped_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Relación normalizada producto <-> categoría. Sustituye products.category como fuente de verdad.
CREATE TABLE IF NOT EXISTS product_categories (
    product_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    first_seen_at TEXT,
    last_seen_at TEXT,
    PRIMARY KEY (product_id, category_id),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

-- Una ejecución de scraping representa una observación completa o dirigida del sitio.
CREATE TABLE IF NOT EXISTS scraping_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    mode TEXT NOT NULL DEFAULT 'directed',
    status TEXT NOT NULL DEFAULT 'RUNNING',
    categories_requested INTEGER DEFAULT 0,
    expected_category_occurrences INTEGER DEFAULT 0,
    actual_category_occurrences INTEGER DEFAULT 0,
    products_found INTEGER DEFAULT 0,
    products_unique INTEGER DEFAULT 0,
    products_multiple_categories INTEGER DEFAULT 0,
    duplicate_occurrences INTEGER DEFAULT 0,
    coverage_complete INTEGER DEFAULT 0,
    coverage_gap INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    message TEXT DEFAULT ''
);

-- Ocurrencia real encontrada por el scraper: una fila por producto dentro de una categoría.
-- Se conserva aunque el SKU aparezca en más de una categoría.
CREATE TABLE IF NOT EXISTS scraping_product_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    product_id INTEGER,
    code TEXT NOT NULL,
    product_url TEXT NOT NULL,
    page_number INTEGER DEFAULT 0,
    position INTEGER DEFAULT 0,
    name TEXT DEFAULT '',
    discovered_at TEXT,
    UNIQUE (run_id, category_id, code),
    FOREIGN KEY (run_id) REFERENCES scraping_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS scraping_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    created INTEGER DEFAULT 0,
    updated INTEGER DEFAULT 0,
    unchanged INTEGER DEFAULT 0,
    deleted INTEGER DEFAULT 0,
    generated INTEGER DEFAULT 0,
    products_expected INTEGER DEFAULT 0,
    products_found INTEGER DEFAULT 0,
    products_unique INTEGER DEFAULT 0,
    products_multiple_categories INTEGER DEFAULT 0,
    duplicate_occurrences INTEGER DEFAULT 0,
    category_summary TEXT DEFAULT '[]',
    multiple_category_products TEXT DEFAULT '[]',
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

CREATE INDEX IF NOT EXISTS idx_categories_name
ON categories(name);

CREATE INDEX IF NOT EXISTS idx_product_categories_category_id
ON product_categories(category_id);

CREATE INDEX IF NOT EXISTS idx_product_categories_product_id
ON product_categories(product_id);

CREATE INDEX IF NOT EXISTS idx_scraping_runs_started_at
ON scraping_runs(started_at);

CREATE INDEX IF NOT EXISTS idx_scraping_runs_status
ON scraping_runs(status);

CREATE INDEX IF NOT EXISTS idx_scraping_occurrences_run_id
ON scraping_product_occurrences(run_id);

CREATE INDEX IF NOT EXISTS idx_scraping_occurrences_category_id
ON scraping_product_occurrences(category_id);

CREATE INDEX IF NOT EXISTS idx_scraping_occurrences_code
ON scraping_product_occurrences(code);
