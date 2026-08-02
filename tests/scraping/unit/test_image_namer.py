from scrapers.images.image_namer import ImageNamer


namer = ImageNamer()


tests = [

    (
        "FB-1812",
        "https://site.com/images/FB-1812.webp",
        "data/images/FB-1812.webp",
    ),

    (
        "FB-1800-AZ",
        "https://site.com/a/b/c.png",
        "data/images/FB-1800-AZ.png",
    ),

    (
        "ABC123",
        "https://site.com/img/test.jpg",
        "data/images/ABC123.jpg",
    ),

    (
        "ABC123",
        "https://site.com/img/test.jpeg",
        "data/images/ABC123.jpeg",
    ),

    (
        "ABC123",
        "",
        "data/images/ABC123.bin",
    ),

]


print("=" * 80)
print("IMAGE NAMER")
print("=" * 80)

for code, url, expected in tests:

    result = namer.build(
        code,
        url,
    )

    print(result)

    assert result == expected

print()
print("OK")