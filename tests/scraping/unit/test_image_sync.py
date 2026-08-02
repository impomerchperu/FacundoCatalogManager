from scrapers.sync.image_sync import ImageSync


class FakeManager:

    def process(
        self,
        code,
        url,
    ):

        return {

            "image_path": (
                f"data/images/{code}.webp"
            ),

            "image_hash": (
                "abc123"
            )

        }



class Product:

    code = "FB-1812"

    image_url = (
        "https://site.com/FB-1812.webp"
    )



sync = ImageSync(
    image_manager=FakeManager()
)


print("=" * 80)
print("IMAGE SYNC")
print("=" * 80)


result = sync.synchronize(
    Product()
)


print(result)


assert result["image_path"] == (
    "data/images/FB-1812.webp"
)


assert result["image_hash"] == (
    "abc123"
)


print()
print("OK")