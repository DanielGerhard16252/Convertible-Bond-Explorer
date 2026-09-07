import os

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget

import desktop.main_window as main_window_module
import server.benchmarks as benchmarks_module
from desktop.main_window import MainWindow, populate_results_table


def test_submit_sends_bql_and_displays_bloomberg_results(monkeypatch):
    app = QApplication.instance() or QApplication([])
    submitted = []
    bloomberg_results = pd.DataFrame([
        {
            "ID": "XS0000000001 Corp",
            "SECURITY_DES": "Example Convertible",
            "PX_LAST": 101.25,
        },
        {
            "ID": "XS0000000002 Corp",
            "SECURITY_DES": "Second Convertible",
            "PX_LAST": 98.75,
        },
    ])

    def fake_execute_bql(query, requested_columns=None):
        submitted.append(query)
        assert requested_columns is not None
        return bloomberg_results

    monkeypatch.setattr(
        main_window_module,
        "execute_bql",
        fake_execute_bql,
    )
    window = MainWindow()
    try:
        window.submit_search()
        app.processEvents()

        assert submitted == [window.bql_query]
        assert window.bql.toPlainText() == window.bql_query
        assert window.bql_query.startswith("GET(")
        assert "FOR(filter(bondsuniv('active'" in window.bql_query
        assert window.results.equals(bloomberg_results)
        assert window.results_table.rowCount() == 2
        assert window.results_table.columnCount() == 3
        assert window.results_count.text() == "2 results"
        assert window.results_table.horizontalHeaderItem(0).text() == "Id"
        assert window.results_table.item(0, 1).text() == "Example Convertible"
    finally:
        window.close()


def test_benchmarks_are_available_only_for_convertible_bonds():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        checkbox = window.get_benchmarks_checkbox
        assert checkbox.isEnabled()
        assert window.get_benchmarks is False

        checkbox.setChecked(True)
        assert window.get_benchmarks is True

        window.universe_dropdown.setCurrentIndex(1)
        app.processEvents()

        assert not checkbox.isChecked()
        assert not checkbox.isEnabled()
        assert window.get_benchmarks is False

        window.universe_dropdown.setCurrentIndex(0)
        app.processEvents()

        assert checkbox.isEnabled()
        assert window.get_benchmarks is False
    finally:
        window.close()


def test_results_table_uses_row_positions_not_dataframe_index_labels():
    app = QApplication.instance() or QApplication([])
    table = QTableWidget()

    populate_results_table(
        table,
        pd.DataFrame({"ID": ["bond-1", "bond-2"]}, index=[7, 3]),
    )

    assert table.item(0, 0).text() == "bond-1"
    assert table.item(1, 0).text() == "bond-2"
    table.deleteLater()
    app.processEvents()


def test_results_table_displays_maturity_in_american_format():
    app = QApplication.instance() or QApplication([])
    table = QTableWidget()

    populate_results_table(
        table,
        pd.DataFrame({"MATURITY": ["2030-01-07"]}),
    )

    assert table.item(0, 0).text() == "01-07-2030"
    table.deleteLater()
    app.processEvents()


def test_results_table_displays_prices_and_yields_to_three_decimals():
    app = QApplication.instance() or QApplication([])
    table = QTableWidget()

    populate_results_table(
        table,
        pd.DataFrame({
            "PX_LAST": [101.2],
            "CV_CNVS_PX": [98.76543],
            "YIELD(YIELD_TYPE=YTM)": [4],
            "BENCHMARK_STRIKE_PX": [100.5555],
        }),
    )

    assert [table.item(0, column).text() for column in range(4)] == [
        "101.200",
        "98.765",
        "4.000",
        "100.555",
    ]
    table.deleteLater()
    app.processEvents()


def test_analysis_window_displays_question_and_string_result(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        main_window_module,
        "run_post_analysis",
        lambda *_args: "## Result\n\n**Bond A** has the highest yield.",
    )
    window = MainWindow()
    try:
        window.results = pd.DataFrame({"bond_name": ["Bond A"]})
        window.bql_query = "GET(SECURITY_DES) FOR(BONDS)"
        window.post_analysis.setPlainText(
            "Which bond has the highest yield?"
        )

        window.run_analysis()
        app.processEvents()

        assert window.analysis_window is not None
        assert window.analysis_window.question_label.text() == (
            "Which bond has the highest yield?"
        )
        rendered_text = window.analysis_window.result_text.toPlainText()
        assert "Result" in rendered_text
        assert "Bond A has the highest yield." in rendered_text
        assert "**" not in rendered_text
    finally:
        if window.analysis_window is not None:
            window.analysis_window.close()
        window.close()


def test_benchmark_results_flow_from_bloomberg_to_table(monkeypatch):
    app = QApplication.instance() or QApplication([])
    bond_results = pd.DataFrame([{
        "CV_COMMON_TICKER_EXCH": "AAA US Equity",
        "CV_CNVS_PX": 100.0,
        "MATURITY": "2030-01-01",
    }])
    monkeypatch.setattr(
        main_window_module,
        "execute_bql",
        lambda _query, requested_columns=None: bond_results,
    )
    monkeypatch.setattr(
        benchmarks_module,
        "execute_bql",
        lambda _query: pd.DataFrame([{"NAME": "AAA call"}]),
    )

    window = MainWindow()
    try:
        window.get_benchmarks_checkbox.setChecked(True)
        window.submit_search()
        app.processEvents()

        assert window.results.loc[0, "BENCHMARK_NAME"] == "AAA call"
        headers = [
            window.results_table.horizontalHeaderItem(column).text()
            for column in range(window.results_table.columnCount())
        ]
        benchmark_column = headers.index("Benchmark Name")
        assert window.results_table.item(0, benchmark_column).text() == (
            "AAA call"
        )
    finally:
        window.close()
