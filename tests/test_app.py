"""End-to-end UI tests across the separate screens (AppTest): no API key, no network."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import ai_parser

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
SCREENS = {
    "overview": "views/overview.py", "supplier": "views/supplier_update.py",
    "decision": "views/decision.py", "allocation": "views/allocation.py",
    "orders": "views/orders_risk.py", "export": "views/export.py",
}


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(ai_parser, "load_dotenv", lambda: None)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    return AppTest.from_file(APP, default_timeout=30).run()


def go(at, screen):
    at.switch_page(SCREENS[screen]).run()
    assert not at.exception, at.exception
    return at


def button(at, label):
    return next(b for b in at.button if b.label == label)


def metrics(at):
    return {m.label: m.value for m in at.metric}


def test_every_screen_renders_with_sample_data(app):
    assert not app.exception
    for screen in SCREENS:
        go(app, screen)
        assert any("sp-hero" in m.value for m in app.markdown), screen


def test_overview_shows_the_scenario(app):
    m = metrics(app)
    assert (m["Stock on hand"], m["Customer demand"], m["Incoming stock"]) == ("100", "150", "50")
    assert (m["Stock gap"], m["Net shortage"]) == ("50", "0")


def test_full_flow_across_screens_without_api_key(app):
    go(app, "supplier")
    assert button(app, "Parse supplier update").disabled
    button(app, "Load offline demo extraction").click()
    app.run()
    assert not app.error  # valid proposal, nothing applied yet
    assert any("Needs confirmation" in x.value for x in app.markdown)
    assert app.session_state.revised_ships is None

    button(app, "Confirm and apply update").click()
    app.run()
    assert app.session_state.revised_ships["quantity"].tolist() == [30, 20]

    go(app, "decision")
    m = metrics(app)
    assert (m["Late units"], m["Known penalties"]) == ("10", "₹3,000")
    app.radio[0].set_value("penalty_first").run()
    m = metrics(app)
    assert (m["Known penalties"], m["Contractual late"]) == ("₹0", "1")

    go(app, "orders")  # the chosen policy carries over to other screens
    assert any("Atlas Motors" in e.value for e in app.error)
    go(app, "export")
    assert len(app.download_button) == 2


def test_invalid_edit_blocks_apply(app):
    go(app, "supplier")
    button(app, "Load offline demo extraction").click()
    app.run()
    app.text_input(key=f"sid_{app.session_state.draft_id}").set_value("SH-99").run()
    assert any("does not exist" in e.value for e in app.error)
    assert button(app, "Confirm and apply update").disabled
    assert app.session_state.revised_ships is None


def test_parse_button_locks_after_session_cap(monkeypatch):
    monkeypatch.setattr(ai_parser, "load_dotenv", lambda: None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("MAX_AI_PARSES", "2")
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.session_state["parse_count"] = 2
    go(at, "supplier")
    assert button(at, "Parse supplier update").disabled
    assert any("parse limit reached" in w.value for w in at.warning)
