"""FI BICS wiring uses synthetic labels; production taxonomy is user supplied."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from shared.bics import FI_BICS_FILTERS
from shared.models import BondSearchQuery
from server.bql_compiler import compile_query
from server.prompts import build_system_prompt


@pytest.fixture
def configured_bics(monkeypatch):
    for level, options in [(2, ("Test Industry A", "Test Issuer's Industry"))]:
        field = f"fi_bics_level_{level}"
        monkeypatch.setitem(FI_BICS_FILTERS, field, {
            "label": f"FI BICS Level {level}",
            "bql_field": f"TEST_FI_BICS_{level}",
            "options": options,
        })


def make_query(sectors=None):
    return BondSearchQuery.model_validate({"filters": [
        {"field": "fi_bics_level_2", "operator": "in", "value": sectors},
    ]})


def test_unconfigured_levels_do_not_filter_or_allow_invented_options(monkeypatch):
    for field in FI_BICS_FILTERS:
        monkeypatch.setitem(FI_BICS_FILTERS, field, {
            "label": field, "bql_field": None, "options": (),
        })
    assert compile_query(make_query()) == compile_query(BondSearchQuery(filters=[]))
    with pytest.raises(ValueError, match="Unknown or unconfigured"):
        make_query(["Invented Sector"])
    assert '"fi_bics_level_2": []' in build_system_prompt()
    app = QApplication.instance() or QApplication([])
    from desktop.main_window import MainWindow
    window = MainWindow()
    try:
        for field in FI_BICS_FILTERS:
            dropdown = window.categorical_dropdowns[field]
            assert not dropdown.isEnabled()
            assert dropdown.placeholderText() == "Options not configured"
    finally:
        window.close()
        app.processEvents()


def test_bics_compiles_level_2_with_multiple_choices(configured_bics):
    query = make_query([" test industry a ", "Test Issuer's Industry", "Test Industry A"])
    universe = compile_query(query).split(" FOR(", 1)[1]
    assert "TEST_FI_BICS_2 IN ['Test Industry A', 'Test Issuer''s Industry']" in universe
    with pytest.raises(ValueError, match="requires IN"):
        BondSearchQuery.model_validate({"filters": [{
            "field": "fi_bics_level_2", "operator": "equals", "value": ["Test Industry A"],
        }]})
    with pytest.raises(ValueError, match="Unknown or unconfigured"):
        make_query(["Unknown sector"])


def test_ai_options_round_trip_through_controls_and_reset(configured_bics):
    from server.ai_interpreter import parse_ai_query
    from desktop.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    prompt = build_system_prompt()
    assert "fi_bics_level_1" not in prompt
    assert '"fi_bics_level_2": ["Test Industry A", "Test Issuer\'s Industry"]' in prompt
    query = parse_ai_query(make_query(["Test Industry A", "Test Issuer's Industry"]).model_dump_json())
    window = MainWindow()
    try:
        window.display_query_in_controls(query)
        assert "fi_bics_level_2" in window.categorical_dropdowns
        assert "fi_bics_level_1" not in window.categorical_dropdowns
        assert all(item.checkState() == Qt.CheckState.Checked
                   for item in window.categorical_items["fi_bics_level_2"].values())
        assert window.categorical_dropdowns["fi_bics_level_2"].placeholderText() == "Test Industry A, Test Issuer's Industry"
        compiled = compile_query(window.query_from_controls())
        assert "TEST_FI_BICS_2 IN ['Test Industry A', 'Test Issuer''s Industry']" in compiled
        window.reset_filters()
        assert "TEST_FI_BICS" not in compile_query(window.query_from_controls())
        assert window.categorical_dropdowns["fi_bics_level_2"].placeholderText() == "All (no filter)"
    finally:
        window.close()
        app.processEvents()


def test_csv_matches_any_selected_sector(configured_bics, monkeypatch):
    import server.csv_provider as provider
    dataframe = pd.DataFrame({
        "bond_name": ["first sector", "second sector", "wrong sector", "missing"],
        "rating": ["BBB"] * 4, "price": [100] * 4,
        "fi_bics_level_2": ["Test Industry A", "Test Issuer's Industry", "Other", None],
    })
    monkeypatch.setattr(provider, "_read_bond_data", lambda _: dataframe)
    assert provider.load_bond_data(make_query(["Test Industry A", "Test Issuer's Industry"]))["bond_name"].tolist() == ["first sector", "second sector"]


def test_level_1_is_no_longer_a_supported_search_field():
    with pytest.raises(ValueError):
        BondSearchQuery.model_validate({"filters": [{
            "field": "fi_bics_level_1", "operator": "in", "value": None,
        }]})


def test_configured_sectors_compile_to_bloomberg_classification():
    from shared.bics import BICS_LEVEL_2_VALUES
    assert len(BICS_LEVEL_2_VALUES) == 23
    query = make_query(["Banking", "Insurance", "Software & Tech Services"])
    assert "CLASSIFICATION_NAME(BICS,2) IN ['Banking', 'Insurance', 'Software & Tech Services']" in compile_query(query)
    assert '"Banking"' in build_system_prompt()
