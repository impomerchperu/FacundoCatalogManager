from scrapers.images.image_validator import ImageValidator

validator = ImageValidator()


print("=" * 80)
print("IMAGE VALIDATOR")
print("=" * 80)


valid_image = "data/images/FB-1812.webp"


result = validator.validate(valid_image)


print("VALID:", result)


assert result is True


missing = validator.validate("data/images/no-existe.webp")


print("MISSING:", missing)


assert missing is False


print()
print("OK")
