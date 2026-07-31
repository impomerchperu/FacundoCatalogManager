from dataclasses import dataclass


@dataclass
class ImageRecord:

    code: str
    image_url: str
    image_path: str
    checksum: str