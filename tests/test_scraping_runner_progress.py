from models.scraping.category import Category
from services.scraping.scraping_runner import ScrapingRunner


def test_runner_keeps_image_progress_in_its_own_pipeline_phase():
    categories = [
        Category(name="A", url="https://site.test/a"),
        Category(name="B", url="https://site.test/b"),
    ]
    progress = []

    def sync_categories(_categories, callback):
        callback(1, 2)
        callback(2, 2)
        callback(1, 4)
        callback(4, 4)
        callback(1, 519)
        callback(519, 519)
        return []

    result = ScrapingRunner._execute_sync_categories(
        sync_categories,
        categories,
        lambda current, total: progress.append((current, total)),
    )

    assert result == []
    assert progress == [
        (1, 6),
        (2, 6),
        (3, 6),
        (4, 6),
        (4, 6),
        (6, 6),
        (6, 6),
    ]
    assert all(
        current <= progress[index + 1][0]
        for index, (current, _total) in enumerate(progress[:-1])
    )
