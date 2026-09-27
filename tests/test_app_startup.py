import pytest


def test_app_main_shows_window_before_entering_event_loop(monkeypatch):
    import app as app_module

    events = []

    class FakeApplication:
        def __init__(self, argv):
            events.append(("application", argv))

        def setApplicationName(self, name):
            events.append(("application_name", name))

        def setApplicationVersion(self, version):
            events.append(("application_version", version))

        def setWindowIcon(self, icon):
            events.append(("icon", icon))

        def exec(self):
            events.append(("exec",))
            return 0

    class FakeWindow:
        def __init__(self):
            events.append(("window",))

        def show(self):
            events.append(("show",))

    monkeypatch.setattr(app_module, "QApplication", FakeApplication)
    monkeypatch.setattr(app_module, "MainWindow", FakeWindow)
    monkeypatch.setattr(app_module.sys, "argv", ["app.py"])

    with pytest.raises(SystemExit) as exc_info:
        app_module.main()

    assert exc_info.value.code == 0
    assert events[1] == ("application_name", "Facundo Catalog Manager")
    assert events[2][0] == "application_version"
    assert events[2][1] == app_module.APP_VERSION
    assert [entry[0] for entry in events] == [
        "application",
        "application_name",
        "application_version",
        "icon",
        "window",
        "show",
        "exec",
    ]
