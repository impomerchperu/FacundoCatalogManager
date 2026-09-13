import os
from pathlib import Path

import pytest

from scrapers.images.image_downloader import ImageDownloader

URL = "https://stock.importacionesfacundo.com/wp-content/uploads/2026/04/FB-1812.webp"


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REAL_SITE_TESTS") != "1",
    reason="real-site tests require RUN_REAL_SITE_TESTS=1",
)


def test_image_downloader_real() -> None:
    downloader = ImageDownloader()
    path = downloader.download(
        "FB-1812",
        URL,
    )

    assert path

    file = Path(path)
    assert file.exists()
    assert file.stat().st_size > 0
