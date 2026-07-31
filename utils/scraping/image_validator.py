from pathlib import Path


class ImageValidator:
    VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

    def is_valid_extension(self, filename):

        extension = Path(filename).suffix.lower()

        return extension in self.VALID_EXTENSIONS

    def is_valid_content(self, content):

        if not content:
            return False

        signatures = [
            b"\xff\xd8",  # JPG
            b"\x89PNG",  # PNG
            b"RIFF",  # WEBP
        ]

        return any(content.startswith(signature) for signature in signatures)

    def is_valid_file(self, path):

        file = Path(path)

        if not file.exists():
            return False

        if file.stat().st_size == 0:
            return False

        return self.is_valid_extension(file.name)
