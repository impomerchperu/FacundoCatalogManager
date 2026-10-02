from tools.benchmark_images_real_site import _worker_count


def test_worker_count_reads_category_override(monkeypatch):
    monkeypatch.setenv("FCM_BENCH_CATEGORY_WORKERS", "12")

    assert _worker_count("FCM_BENCH_CATEGORY_WORKERS", 8) == 12


def test_worker_count_uses_default_when_override_is_absent(monkeypatch):
    monkeypatch.delenv("FCM_BENCH_CATEGORY_WORKERS", raising=False)

    assert _worker_count("FCM_BENCH_CATEGORY_WORKERS", 8) == 8
