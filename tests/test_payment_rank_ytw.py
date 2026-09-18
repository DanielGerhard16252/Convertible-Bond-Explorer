import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from shared.models import BondSearchQuery
from shared.search_choices import PAYMENT_RANK_VALUES
from server.bql_compiler import compile_query, get_result_columns
from desktop.results import select_display_columns, display_column_labels, format_table_value


def query_for(universe, minimum=0, maximum=8):
    return BondSearchQuery.model_validate({"filters": [
        {"field": "bond_universe", "operator": "equals", "value": universe},
        {"field": "payment_rank", "operator": "in", "value": ["Sr Unsecured", "1st lien"]},
        {"field": "yield_to_worst", "operator": "between",
         "value": {"minimum": minimum, "maximum": maximum}},
    ]})


@pytest.mark.parametrize("universe", ["high_yield", "convertible"])
@pytest.mark.parametrize("minimum,maximum", [(0, 8), (None, 8), (3, None)])
def test_rank_and_ytw_filters_and_return_columns(universe, minimum, maximum):
    query = query_for(universe, minimum, maximum)
    bql = compile_query(query)
    condition = bql.split(" FOR(", 1)[1]
    assert "PAYMENT_RANK IN ['Sr Unsecured', '1st lien']" in condition
    assert ("YIELD(YIELD_TYPE=YTW) >=" in condition) == (minimum is not None)
    assert ("YIELD(YIELD_TYPE=YTW) <=" in condition) == (maximum is not None)
    if minimum is not None:
        assert f"YIELD(YIELD_TYPE=YTW) >= {minimum}" in condition
    if maximum is not None:
        assert f"YIELD(YIELD_TYPE=YTW) <= {maximum}" in condition
    assert "YIELD(YIELD_TYPE=YTM) >=" not in condition
    columns = get_result_columns(query)
    assert "INDUSTRY_SECTOR" not in columns
    assert {"CLASSIFICATION_NAME(BICS,2)", "PAYMENT_RANK", "YIELD(YIELD_TYPE=YTW)"} <= set(columns)
    dataframe = pd.DataFrame({"CLASSIFICATION_NAME(BICS,2)": ["Banking"],
                              "PAYMENT_RANK": ["Sr Unsecured"],
                              "YIELD(YIELD_TYPE=YTW)": [5.12345]})
    dataframe.attrs["bond_universe"] = universe
    displayed = select_display_columns(dataframe)
    assert displayed.shape == (1, 3)
    assert display_column_labels(displayed)["classification_name(bics,2)"] == "Sector"
    assert format_table_value("YIELD(YIELD_TYPE=YTW)", 5.12345) == "5.123"


@pytest.mark.parametrize("universe", ["high_yield", "convertible"])
def test_ai_controls_and_reset(universe):
    from desktop.main_window import MainWindow
    from server.ai_interpreter import parse_ai_query
    from server.prompts import build_system_prompt
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.display_query_in_controls(parse_ai_query(query_for(universe).model_dump_json()))
        assert window.analytics_inputs["yield_to_worst"][0].isEnabled()
        assert window.categorical_dropdowns["payment_rank"].isEnabled()
        restored = window.query_from_controls()
        assert restored.find_filter("payment_rank").value == ["1st lien", "Sr Unsecured"]
        assert restored.find_filter("yield_to_worst").value.maximum == 8
        assert "Sr Unsecured" in build_system_prompt()
        assert "yield_to_worst" in build_system_prompt()
        window.reset_filters()
        assert window.query_from_controls().find_filter("payment_rank") is None
        assert window.query_from_controls().find_filter("yield_to_worst") is None
    finally:
        window.close()
        app.processEvents()


def test_payment_rank_validation():
    assert len(PAYMENT_RANK_VALUES) == len(set(PAYMENT_RANK_VALUES)) == 11
    with pytest.raises(ValueError, match="Unknown or unconfigured"):
        BondSearchQuery.model_validate({"filters": [
            {"field": "payment_rank", "operator": "in", "value": ["invented"]},
        ]})


def test_csv_rank_and_ytw(monkeypatch):
    import server.csv_provider as provider
    dataframe = pd.DataFrame({
        "bond_name": ["match", "wrong rank", "wrong yield"],
        "rating": ["BB"] * 3, "price": [100] * 3,
        "asset_class": ["Corporates"] * 3, "convertible": ["Y"] * 3,
        "payment_rank": ["Sr Unsecured", "Secured", "1st lien"],
        "yield_to_worst": [5, 5, 10],
    })
    monkeypatch.setattr(provider, "_read_bond_data", lambda _: dataframe)
    assert provider.load_bond_data(query_for("high_yield"))["bond_name"].tolist() == ["match"]
