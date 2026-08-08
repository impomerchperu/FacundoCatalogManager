-- ==========================================================
-- FACUNDO CATALOG MANAGER
-- Database Schema
-- ==========================================================

-- ==========================================================
-- Catálogo principal
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

    image_url TEXT,

    image_path TEXT,

    image_hash TEXT DEFAULT '',

    content_hash TEXT DEFAULT '',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- Productos obtenidos desde scraping web
-- ==========================================================

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

    image_url TEXT,

    image_path TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================================
-- Registro incremental
-- ==========================================================

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

-- ==========================================================
-- Cargas históricas completas del catálogo
-- ==========================================================

CREATE TABLE IF NOT EXISTS catalog_loads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    created_at TEXT NOT NULL,

    source TEXT NOT NULL DEFAULT 'SCRAPING',

    status TEXT NOT NULL DEFAULT 'SUCCESS',

    applied INTEGER NOT NULL DEFAULT 0,

    product_count INTEGER NOT NULL DEFAULT 0,

    message TEXT DEFAULT ''
);

-- ==========================================================
-- Productos pertenecientes a cada carga histórica
-- ==========================================================

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

    image_url TEXT,

    image_path TEXT,

    image_hash TEXT DEFAULT '',

    content_hash TEXT DEFAULT '',

    FOREIGN KEY (load_id)
        REFERENCES catalog_loads(id)
        ON DELETE CASCADE,

    UNIQUE(load_id, code)
);

-- ==========================================================
-- Historial de ejecuciones de scraping
-- ==========================================================

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

    FOREIGN KEY (load_id)
        REFERENCES catalog_loads(id)
        ON DELETE SET NULL
);

-- ==========================================================
-- Índices independientes de migraciones
--
-- El índice de scraping_history.load_id se crea desde
-- DBManager después de ejecutar las migraciones para que
-- las bases existentes puedan incorporar la columna.
-- ==========================================================

CREATE INDEX IF NOT EXISTS idx_catalog_loads_created_at
ON catalog_loads(created_at);

CREATE INDEX IF NOT EXISTS idx_catalog_loads_applied
ON catalog_loads(applied);

CREATE INDEX IF NOT EXISTS idx_catalog_load_products_load_id
ON catalog_load_products(load_id);

CREATE INDEX IF NOT EXISTS idx_scraping_history_started_at
ON scraping_history(started_at);