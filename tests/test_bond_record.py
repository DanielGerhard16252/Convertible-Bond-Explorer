import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from desktop.results import configure_results_table, populate_results_table, ResultsWindow


def test_double_click_keeps_exact_sorted_source_record_and_snapshot():
    app = QApplication.instance() or QApplication([])
    table = QTableWidget()
    configure_results_table(table)
    source = pd.DataFrame({
        "ID": ["bond-a", "bond-b"], "PX_LAST": [90.123456789, 110.987654321],
        "EXTRA_FIELD": [None, "unshown value"],
        "MATURITY": [pd.Timestamp("2030-01-01"), pd.Timestamp("2031-02-03")],
    }, index=[7, 7])
    source.attrs["bond_universe"] = "high_yield"
    populate_results_table(table, source)
    price_column = next(i for i in range(table.columnCount())
                        if table.horizontalHeaderItem(i).text() == "Price")
    table.sortItems(price_column, Qt.SortOrder.DescendingOrder)
    table.cellDoubleClicked.emit(0, price_column)
    details = table.record_windows[0]
    try:
        pd.testing.assert_frame_equal(details.record, source.iloc[[1]])
        assert details.table.item(0, 2).text() == "unshown value"
        assert details.table.item(0, 1).text() == "110.987654321"
        assert details.windowTitle() == "bond-b"
        expected = details.record.copy(deep=True)
        source.iloc[1, 1] = 0
        populate_results_table(table, pd.DataFrame())
        pd.testing.assert_frame_equal(details.record, expected)
    finally:
        details.close()
        assert table.record_windows == []
        table.close()
        app.processEvents()


def test_detached_results_window_opens_record_details():
    app = QApplication.instance() or QApplication([])
    source = pd.DataFrame({"ID": ["bond-a"], "PX_LAST": [101.123456],
                           "SECURITY_DES": ["Example 5% 2030"], "CRNCY": ["USD"]})
    window = ResultsWindow(source)
    table = window.findChild(QTableWidget)
    table.cellDoubleClicked.emit(0, 0)
    try:
        pd.testing.assert_frame_equal(table.record_windows[0].record, source)
        details = table.record_windows[0]
        assert details.windowTitle() == "Example 5% 2030"
        assert details.heading.text() == "Example 5% 2030"
        assert details.table.rowCount() == 1
        assert details.table.columnCount() == len(source.columns)
        assert details.table.horizontalHeaderItem(1).text() == "Price"
    finally:
        table.record_windows[0].close()
        window.close()
        app.processEvents()


def test_record_interest_rate_uses_own_currency(monkeypatch):
    import desktop.bond_record as module
    from types import SimpleNamespace
    app = QApplication.instance() or QApplication([])
    submitted = []
    monkeypatch.setattr(module.QThreadPool, "globalInstance", lambda: SimpleNamespace(start=submitted.append))
    calls = []
    monkeypatch.setattr(module.BondRecordWindow, "get_interest_rate", staticmethod(
        lambda currency, maturity: calls.append((currency, maturity)) or 3.5))
    window = module.BondRecordWindow(pd.DataFrame({"ID": ["b"], "CRNCY": ["EUR"],
                                                  "MATURITY": [pd.Timestamp("2030-01-01")]}))
    try:
        window.lgd_input.setText("60")
        window.interest_rate_button.click()
        assert len(submitted) == 1
        assert not window.interest_rate_button.isEnabled()
        submitted[0].run()
        assert calls == [("EUR", pd.Timestamp("2030-01-01"))]
        assert window.interest_rate_button.isEnabled()
        assert window.interest_rate == 3.5
        assert window.interest_rate_label.text() == "Estimated risk-free interest rate (EUR): 3.5000%"
        assert window.interest_rate_button.text() == "Get interest rate"
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("maturity, expected", [
    ("2030-01-06", 3.0),
    ("2030-01-11", 4.0),
    ("2029-01-01", 2.0),
    ("2031-01-01", 8.0),
])
def test_interest_rate_interpolation_and_endpoints(monkeypatch, maturity, expected):
    import desktop.bond_record as module
    curve = pd.DataFrame({
        "maturity": ["2030-01-21", "2030-01-01", "2030-01-11", None, "2030-01-04"],
        "PX_LAST": [8.0, 2.0, 4.0, 99.0, None],
    })
    monkeypatch.setattr(module, "execute_bql", lambda *args, **kwargs: curve.copy())
    assert module.BondRecordWindow.get_interest_rate("EUR", maturity) == pytest.approx(expected)


def test_interest_rate_single_point_and_empty_curve(monkeypatch):
    import desktop.bond_record as module
    curve = pd.DataFrame({"maturity": ["2030-01-01"], "PX_LAST": [3.5]})
    monkeypatch.setattr(module, "execute_bql", lambda *args, **kwargs: curve.copy())
    assert module.BondRecordWindow.get_interest_rate("USD", "2031-01-01") == 3.5
    curve["PX_LAST"] = None
    with pytest.raises(ValueError, match="No valid swap rates"):
        module.BondRecordWindow.get_interest_rate("USD", "2031-01-01")


def test_record_interest_rate_missing_maturity_does_not_start_job(monkeypatch):
    import desktop.bond_record as module
    app = QApplication.instance() or QApplication([])
    warnings = []
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    window = module.BondRecordWindow(pd.DataFrame({"ID": ["a"], "CRNCY": ["XXX"]}))
    try:
        window.lgd_input.setText("60")
        window.interest_rate_button.click()
        assert warnings == ["Bond maturity is missing"]
        assert window._interest_rate_job is None
    finally:
        window.close()
        app.processEvents()


def test_interest_rate_uses_currency_curve_and_rejects_unknown_currency(monkeypatch):
    import desktop.bond_record as module
    calls = []
    def execute(query, **kwargs):
        calls.append((query, kwargs))
        return pd.DataFrame({"maturity": ["2030-01-01"], "PX_LAST": [3.5]})
    monkeypatch.setattr(module, "execute_bql", execute)
    for currency in ("USD", "EUR", "GBP"):
        assert module.BondRecordWindow.get_interest_rate(currency, "2031-01-01") == 3.5
        assert module.OIS_LOOKUP[currency] in calls[-1][0]
        assert calls[-1][1]["field_values_only"] is True
    with pytest.raises(ValueError, match="not configured"):
        module.BondRecordWindow.get_interest_rate("XXX", "2030-01-06")
    assert len(calls) == 3


@pytest.mark.parametrize("field, ytm, expected", [
    ("YIELD(YIELD_TYPE=YTM)", 5.0, 1.5),
    ("yield_to_maturity", "2.5", -1.0),
    ("yield_to_maturity", None, None),
])
def test_credit_spread_display(field, ytm, expected):
    from desktop.bond_record import BondRecordWindow
    app = QApplication.instance() or QApplication([])
    window = BondRecordWindow(pd.DataFrame({field: [ytm]}))
    window._interest_rate_currency = "USD"
    try:
        window._interest_rate_finished(3.5, None)
        assert window.credit_spread == expected
        if expected is None:
            assert "unavailable" in window.credit_spread_label.text()
        else:
            assert f"{expected:.4f} percentage points" in window.credit_spread_label.text()
            assert f"{expected * 100:.2f} bps" in window.credit_spread_label.text()
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("days", [100, 1000, 3000])
def test_option_query_expires_at_least_10_days_from_today(monkeypatch, capsys, days):
    import desktop.bond_record as module
    calls = []
    expected = pd.DataFrame({"PX_ASK": [0.12], "STRIKE_PX": [10]})
    monkeypatch.setattr(module, "execute_bql", lambda query, **kwargs: calls.append((query, kwargs)) or expected)
    today = pd.Timestamp("2026-01-01")
    maturity = today + pd.Timedelta(days=days)
    results = module.BondRecordWindow.get_options("DEMO US Equity", maturity, today=today)
    queries = [capsys.readouterr().out]
    pd.testing.assert_frame_equal(results[expected.columns], expected)
    assert len(calls) == 2
    assert calls[0][0].strip() == queries[0].strip()
    assert "PX_ASK" in calls[0][1]["requested_columns"]
    get_fields = calls[0][0].split("get(", 1)[1].split("\n)", 1)[0]
    returned_fields = {field.strip().removesuffix("()").casefold()
                       for field in get_fields.split(",")}
    assert returned_fields == {field.casefold() for field in calls[0][1]["requested_columns"]}
    assert "options('DEMO US Equity')" in queries[0]
    assert "expire_dt() >= 2026-01-11" in queries[0]
    assert "expire_dt() > " not in queries[0]
    assert "expire_dt() <=" not in queries[0]


@pytest.mark.parametrize("parent, expected", [("PARENT US Equity", "PARENT US Equity"), (None, "CV US Equity")])
def test_button_starts_option_query(monkeypatch, parent, expected):
    import desktop.bond_record as module
    from types import SimpleNamespace
    app = QApplication.instance() or QApplication([])
    jobs = []
    monkeypatch.setattr(module.QThreadPool, "globalInstance", lambda: SimpleNamespace(start=jobs.append))
    window = module.BondRecordWindow(pd.DataFrame({
        "CRNCY": ["USD"], "MATURITY": ["2030-01-01"],
        "CAST_PARENT_EQUITY_TICKER": [parent], "CV_COMMON_TICKER_EXCH": ["CV US Equity"],
    }))
    try:
        window.lgd_input.setText("60")
        window.interest_rate_button.click()
        assert len(jobs) == 2
        assert jobs[1].function == module.BondRecordWindow.get_options
        assert jobs[1].args == (expected, "2030-01-01")
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("put_days", [180, 365, 730])
def test_approximate_spread_formula(put_days):
    import math
    from desktop.bond_record import BondRecordWindow
    years = put_days / 365
    q = 0.1 * 1.04 ** years / 7.5
    expected = (1 - (1 - q) ** (1 / years)) * 0.6
    assert BondRecordWindow.calculate_approximate_spread(
        0.1, 4, pd.Timestamp("2026-01-01") + pd.Timedelta(days=put_days),
        0.6, 7.5, today="2026-01-01"
    ) == pytest.approx(expected)
    with pytest.raises(ValueError, match="formula requires"):
        BondRecordWindow.calculate_approximate_spread(2, 4, "2027-01-01", 0.6, 1, today="2026-01-01")


def test_continuous_rate_calculation_displays():
    import math
    from desktop.bond_record import BondRecordWindow
    app = QApplication.instance() or QApplication([])
    window = BondRecordWindow(pd.DataFrame())
    try:
        window.interest_rate = 4.0
        window.loss_given_default = 0.6
        expiry = pd.Timestamp.now(tz="UTC").normalize() + pd.Timedelta(days=365)
        window.option_results = pd.DataFrame({"PX_ASK": [0.1], "STRIKE_PX": [7.5],
                                              "EXPIRE_DT": [expiry]})
        window._update_approximate_spread()
        expected = 0.1 * 1.04 / 7.5 * 0.6
        assert window.approximate_credit_spread == pytest.approx(expected)
        assert window.default_probability == pytest.approx(0.1 * 1.04 / 7.5)
        assert "One-year default probability:" in window.approximate_spread_label.text()
        assert not hasattr(window, "calculation_label")
        assert "Merton:" in window.merton_spread_label.text()
        assert f"{expected * 100:.4f}%" in window.approximate_spread_label.text()
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("rate", [-100, -101])
def test_continuous_rate_rejects_invalid_log_domain(rate):
    from desktop.bond_record import BondRecordWindow
    with pytest.raises(ValueError, match="greater than -100%"):
        BondRecordWindow.calculate_approximate_spread(
            0.1, rate, "2027-01-01", 0.6, 7.5, today="2026-01-01")


def test_lgd_required():
    from desktop.bond_record import BondRecordWindow
    app = QApplication.instance() or QApplication([])
    window = BondRecordWindow(pd.DataFrame())
    try:
        for value in ("", "abc", "-1", "101", "nan"):
            window.lgd_input.setText(value)
            assert not window.interest_rate_button.isEnabled()
        window.lgd_input.setText("60")
        assert window.interest_rate_button.isEnabled()
        assert window._lgd_value() == 0.6
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("q, put_years, bond_years, expected", [
    (0.2, 2, 2, 0.2), (0.2, 2, 4, 0.36),
    (0.2, 2, 0, 0), (0, 1, 10, 0),
])
def test_default_probability_horizons(q, put_years, bond_years, expected):
    from desktop.bond_record import BondRecordWindow
    assert BondRecordWindow.calculate_default_probability(q, put_years, bond_years) == pytest.approx(expected)


def test_default_probability_defaults_to_one_year():
    from desktop.bond_record import BondRecordWindow
    assert BondRecordWindow.calculate_default_probability(0.36, 2) == pytest.approx(0.2)


def test_two_model_spreads_display_without_working(monkeypatch):
    import desktop.bond_record as module
    app = QApplication.instance() or QApplication([])
    today = pd.Timestamp.now(tz="UTC").normalize()
    maturity = today + pd.Timedelta(days=730)
    window = module.BondRecordWindow(pd.DataFrame({"MATURITY": [maturity]}))
    calls = []
    def model(*args, **kwargs):
        calls.append(args)
        return .02, .012
    monkeypatch.setattr(module, "calculate_merton_spread", model)
    try:
        window.interest_rate = 4.
        window.loss_given_default = .6
        window.option_results = pd.DataFrame({
            "PX_ASK": [.1], "STRIKE_PX": [7.5], "EXPIRE_DT": [today + pd.Timedelta(days=365)],
            "UNDERLYING_CUR_MKT_CAP": [1000.], "UNDERLYING_BS_ST_BORROW": [50.],
            "UNDERLYING_BS_LT_BORROW": [100.], "UNDERLYING_VOLATILITY(CALC_INTERVAL=260D)": [.30],
        })
        window._update_approximate_spread()
        assert "DOOTM credit spread:" in window.approximate_spread_label.text()
        assert "Merton credit spread: 1.2000% (120.00 bps)" in window.merton_spread_label.text()
        assert calls[0] == (1000., 50., 100., 4., maturity, .30, .6)
        assert not hasattr(window, "calculation_label")
    finally:
        window.close()
        app.processEvents()


@pytest.mark.parametrize("values", [(1, 1, 2), (-0.1, 1, 2), (0.2, 0, 2),
                                    (0.2, 1, -1), (float("nan"), 1, 2)])
def test_default_probability_invalid_inputs(values):
    from desktop.bond_record import BondRecordWindow
    with pytest.raises(ValueError):
        BondRecordWindow.calculate_default_probability(*values)
