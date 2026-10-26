import json
import sqlite3

from tools.clean_unused_images import find_unused_images


def test_gallery_images_are_protected_from_cleanup(tmp_path):
    project_root = tmp_path
    db_path = project_root / "catalog.db"
    gallery_path = project_root / "data" / "images" / "gallery" / "FB-4010" / "FB-4010-02.webp"
    gallery_path.parent.mkdir(parents=True)
    gallery_path.write_bytes(b"gallery")

    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "CREATE TABLE products (image_path TEXT, gallery_images TEXT)"
        )
        connection.execute(
            "INSERT INTO products VALUES (?, ?)",
            (
                "",
                json.dumps(
                    [
                        {
                            "url": "https://site.test/two.webp",
                            "image_path": "data/images/gallery/FB-4010/FB-4010-02.webp",
                        }
                    ]
                ),
            ),
        )
        connection.commit()
    finally:
        connection.close()

    unused = find_unused_images(
        project_root=project_root,
        db_path=db_path,
        roots=[project_root / "data" / "images"],
    )

    assert unused == []
