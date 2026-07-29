CREATE TABLE IF NOT EXISTS products (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    code TEXT NOT NULL UNIQUE,

    name TEXT NOT NULL,

    category TEXT,

    description TEXT,

    price REAL DEFAULT 0,

    stock INTEGER DEFAULT 0,

    image_path TEXT

);