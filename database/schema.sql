CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    price REAL,
    stock INTEGER,
    image_path TEXT
);


CREATE TABLE IF NOT EXISTS scraped_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    url TEXT UNIQUE,
    code TEXT,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    price REAL DEFAULT 0,
    image_url TEXT,
    stock INTEGER DEFAULT 0,
    price_sample REAL DEFAULT 0,
    price_hundred REAL DEFAULT 0,
    price_thousand REAL DEFAULT 0,
    image_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS sync_records (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    code TEXT UNIQUE NOT NULL,

    name TEXT,

    category TEXT,

    price REAL,

    stock INTEGER,

    image_path TEXT,

    image_url TEXT,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);