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
-- Historial de actualizaciones manuales
-- ==========================================================

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