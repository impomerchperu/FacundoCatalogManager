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
    url TEXT UNIQUE NOT NULL,
    code TEXT,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    price REAL,
    image_url TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);