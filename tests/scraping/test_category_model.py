from models.scraping.category import Category


def test_category_model():

    category = Category(name="Jarros Mug", url="https://example.com/jarros")

    assert category.name == "Jarros Mug"
    assert category.url.endswith("/jarros")
