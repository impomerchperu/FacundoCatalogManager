import pytest

from database.db_manager import DBManager
from repositories.product_repository import ProductRepository


@pytest.fixture
def database():

    db = DBManager(":memory:")

    db.initialize_database()

    yield db

    db.close()



@pytest.fixture
def repository(database):

    return ProductRepository(database)