import main
from main import JarvisApp
from tests.test_main_ui_more import make_headless_app, DummyScrolled, patch_ctk


def test_build_console_runs_with_dummy_scrolled(monkeypatch):
    patch_ctk(monkeypatch)
    app = make_headless_app()
    # ensure scrolledtext.ScrolledText is DummyScrolled via patch_ctk
    app._build_console(DummyScrolled())
    # console should be set and implement tag_config
    assert hasattr(app.console, 'tag_config')
