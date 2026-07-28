from database.db_manager import DBManager


def test_database_connection():

    db = DBManager()

    db.execute_query(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT,
            category TEXT,
            description TEXT,
            price REAL,
            stock INTEGER,
            image TEXT
        )
        """
    )

    db.execute_query(
        "DELETE FROM products"
    )

    db.execute_query(
        """
        INSERT INTO products
        (
            code,
            name,
            category,
            description,
            price,
            stock,
            image_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "TEST001",
            "Producto de prueba",
            "General",
            "Primer registro del catálogo",
            25.50,
            10,
            ""
        )
    )

    products = db.fetch_all(
        "SELECT * FROM products WHERE code=?",
        ("TEST001",)
    )

    assert len(products) == 1
    assert products[0][1] == "TEST001"

    db.close()