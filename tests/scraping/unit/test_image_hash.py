from scrapers.images.image_hash import ImageHash

hasher = ImageHash()


IMAGE = "data/images/FB-1812.webp"


print("=" * 80)
print("IMAGE HASH")
print("=" * 80)


hash_value = hasher.calculate(IMAGE)


print("HASH:", hash_value)


assert hash_value

assert len(hash_value) == 64


missing = hasher.calculate("data/images/no-existe.webp")


print("MISSING:", missing)


assert missing == ""


print()
print("OK")
