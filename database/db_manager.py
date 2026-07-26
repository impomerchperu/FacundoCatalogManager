import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).parent / "catalog.db"


def get_connection():
    """
    Crea y devuelve una conexión a la base de datos.
    """
    return sqlite3.connect(DATABASE_PATH)


def initialize_database():
    """
    Crea la tabla products si no existe.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category TEXT,
            description TEXT,
            price REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()
    connection.close()


def add_product(product):
    """
    Inserta un producto en la base de datos.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
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
            product.code,
            product.name,
            product.category,
            product.description,
            product.price,
            product.stock,
            product.image_path,
        ),
    )

    connection.commit()
    connection.close()


def get_products():
    """
    Devuelve todos los productos registrados.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            code,
            name,
            category,
            description,
            price,
            stock,
            image_path
        FROM products
        ORDER BY id DESC
        """
    )

    products = cursor.fetchall()

    connection.close()

    return products


def delete_product(product_id):
    """
    Elimina un producto por ID.
    """
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM products WHERE id = ?",
        (product_id,),
    )

    connection.commit()
    connection.close()