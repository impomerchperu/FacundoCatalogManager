import tools.profile_detail_workers as profiler


def test_positive_int_uses_default(monkeypatch):
    monkeypatch.delenv("FCM_PROFILE_DETAIL_WORKERS", raising=False)
    assert profiler._positive_int("FCM_PROFILE_DETAIL_WORKERS", 32) == 32


def test_positive_int_reads_override(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_DETAIL_WORKERS", "28")
    assert profiler._positive_int("FCM_PROFILE_DETAIL_WORKERS", 32) == 28


def test_positive_int_rejects_non_positive(monkeypatch):
    monkeypatch.setenv("FCM_PROFILE_DETAIL_WORKERS", "0")
    try:
        profiler._positive_int("FCM_PROFILE_DETAIL_WORKERS", 32)
    except ValueError as error:
        assert "mayor que cero" in str(error)
    else:
        raise AssertionError("Se esperaba ValueError")
