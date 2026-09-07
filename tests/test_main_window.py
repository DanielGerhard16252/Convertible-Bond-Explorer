import os

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget

import desktop.main_window as main_window_module
from desktop.main_window import MainWindow, populate_results_table


def test_submit_compiles_bql_and_displays_csv_results(monkeypatch):
    app = QApplication.instance() or QApplication([])
    submitted = []
    csv_results = pd.DataFrame([
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

    def fake_load_bond_data(query):
        submitted.append(query)
        return csv_results

    monkeypatch.setattr(
        main_window_module,
        "load_bond_data",
        fake_load_bond_data,
    )
    window = MainWindow()
    try:
        window.submit_search()
        app.processEvents()

        assert len(submitted) == 1
        assert window.bql.toPlainText() == window.bql_query
        assert window.bql_query.startswith("GET(")
        assert "FOR(filter(bondsuniv('active'" in window.bql_query
        assert window.results.equals(csv_results)
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


def test_analysis_window_displays_question_and_string_result(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        main_window_module,
        "run_post_analysis",
        lambda *_args: "The highest-yielding bond is Bond A.",
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
        assert window.analysis_window.result_text.toPlainText() == (
            "The highest-yielding bond is Bond A."
        )
    finally:
        if window.analysis_window is not None:
            window.analysis_window.close()
        window.close()
