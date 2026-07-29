from database.db_manager import DBManager


def test_database_connection():

    db = DBManager(":memory:")

    db.initialize_database()


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
        """
        SELECT *
        FROM products
        WHERE code=?
        """,

        (
            "TEST001",
        )
    )


    assert len(products) == 1

    assert products[0]["code"] == "TEST001"


    db.close()