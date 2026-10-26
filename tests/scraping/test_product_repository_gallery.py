from models.product import Product


def test_product_repository_round_trips_gallery_images(repository):
    product = Product(
        code="FB-4010",
        name="Gota Antiestrés",
        image_url="https://site.test/one.webp",
        image_path="data/images/products/FB-4010.webp",
        gallery_images=[
            {
                "url": "https://site.test/one.webp",
                "image_path": "data/images/gallery/FB-4010/FB-4010-01.webp",
                "image_hash": "hash-one",
                "position": 1,
                "source": "woocommerce-gallery",
            },
            {
                "url": "https://site.test/two.webp",
                "image_path": "data/images/gallery/FB-4010/FB-4010-02.webp",
                "image_hash": "hash-two",
                "position": 2,
                "source": "woocommerce-gallery",
            },
        ],
    )

    repository.create(product)
    loaded = repository.get_by_code("FB-4010")

    assert loaded is not None
    assert loaded.gallery_images == product.gallery_images
