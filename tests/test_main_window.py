import os
import time
from threading import Event

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget
from PySide6.QtCore import QThread, QTimer
from PySide6.QtTest import QTest

import desktop.main_window as main_window_module
import server.benchmarks as benchmarks_module
from desktop.main_window import MainWindow, populate_results_table


def test_export_save_dialog_defaults_to_downloads_and_handles_cancel(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    saved_path = tmp_path / "export.csv"
    monkeypatch.setattr(main_window_module.QStandardPaths, "writableLocation", lambda location: str(tmp_path))
    monkeypatch.setattr(main_window_module.QMessageBox, "information", lambda *args: None)
    accepted = False

    def choose(dialog):
        assert dialog.directory().absolutePath() == tmp_path.as_posix()
        assert dialog.acceptMode() == main_window_module.QFileDialog.AcceptMode.AcceptSave
        assert dialog.defaultSuffix() == "csv"
        dialog.selectFile(str(saved_path))
        return (main_window_module.QFileDialog.DialogCode.Accepted if accepted
                else main_window_module.QFileDialog.DialogCode.Rejected)

    monkeypatch.setattr(main_window_module.QFileDialog, "exec", choose)
    try:
        window.results = pd.DataFrame({"ID": ["bond-1"], "PX_LAST": [100.]})
        window.export_to_csv()
        assert not saved_path.exists()
        accepted = True
        window.export_to_csv()
        assert pd.read_csv(saved_path).to_dict("records") == window.results.to_dict("records")
    finally:
        window.close()
        app.processEvents()


def test_max_number_input_compiles_validates_and_resets(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    errors = []
    monkeypatch.setattr(main_window_module.QMessageBox, "warning",
                        lambda *args: errors.append(args[-1]))
    try:
        original = main_window_module.compile_query(window.query_from_controls())
        assert window.universe_dropdown.currentData() == "high_yield"
        assert main_window_module.BondSearchQuery(filters=[]).universe == "high_yield"
        window.max_number_input.setText(" 25 ")
        query = window.query_from_controls()
        assert query.max_number == 25
        assert "FOR(TOP(filter(" in main_window_module.compile_query(query)
        window.display_query_in_controls(query)
        assert window.max_number_input.text() == "25"
        for invalid in ["0", "-1", "2.5", "abc"]:
            window.max_number_input.setText(invalid)
            assert window.query_from_controls() is None
        assert len(errors) == 4
        window.reset_filters()
        assert window.universe_dropdown.currentData() == "high_yield"
        assert window.max_number_input.text() == "100"
        assert main_window_module.compile_query(window.query_from_controls()) == original
    finally:
        window.close()
        app.processEvents()


def test_isin_input_populates_and_compiles():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        query = main_window_module.BondSearchQuery.model_validate({"filters": [
            {"field": "isin", "operator": "equals", "value": " us0378331005 "},
        ]})
        window.display_query_in_controls(query)
        assert window.isin_input.text() == "US0378331005"
        rebuilt = window.query_from_controls()
        assert "ID_ISIN == 'US0378331005'" in main_window_module.compile_query(rebuilt)
        window.display_query_in_controls(main_window_module.BondSearchQuery(filters=[]))
        assert window.isin_input.text() == ""
    finally:
        window.close()
        app.processEvents()


def test_ai_currency_lists_populate_controls_and_round_trip_to_bql(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        for request, currencies in [("bonds in euros", ["EUR"]),
                                    ("bonds in euros and pounds", ["EUR", "GBP"])]:
            query = main_window_module.BondSearchQuery.model_validate({"filters": [
                {"field": "currency", "operator": "in", "value": currencies},
            ]})
            monkeypatch.setattr(main_window_module, "interpret_request_with_ai", lambda text: query)
            window.request_input.setPlainText(request)
            window.interpret_request()
            wait_for(app, lambda: window._interpret_job is None)
            assert window.currency_input.text() == ", ".join(currencies)
            rebuilt = window.query_from_controls()
            assert rebuilt is not None
            expected = ", ".join(f"'{code}'" for code in currencies)
            assert f"CRNCY IN [{expected}]" in main_window_module.compile_query(rebuilt)
        window.display_query_in_controls(main_window_module.BondSearchQuery(filters=[]))
        assert window.currency_input.text() == ""
    finally:
        window.close()


def test_display_filters_both_universes_using_friendly_names():
    from desktop.results import RESULT_COLUMN_LABELS, HIGH_YIELD_COLUMN_LABELS
    app = QApplication.instance() or QApplication([])
    for universe, labels in [("convertible", RESULT_COLUMN_LABELS),
                             ("high_yield", HIGH_YIELD_COLUMN_LABELS)]:
        data = pd.DataFrame({label: ["sample"] for label in reversed(list(labels.values()))})
        data["DATE"] = "2026-09-08"
        data["REQUEST_ID"] = "metadata"
        data["BENCHMARK_NAME"] = "extra"
        data.attrs["bond_universe"] = universe
        table = QTableWidget()
        populate_results_table(table, data)
        assert [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())] == list(labels.values())
        assert table.rowCount() == 1
        table.deleteLater()
    app.processEvents()


def test_benchmark_columns_only_display_when_requested():
    from desktop.results import select_display_columns, BENCHMARK_COLUMN_LABELS
    for names in [list(BENCHMARK_COLUMN_LABELS.values()),
                  ["BENCHMARK_ID", "BENCHMARK_NAME", "BENCHMARK_EXPIRE_DT()", "BENCHMARK_STRIKE_PX()"]]:
        data = pd.DataFrame({"ID": ["bond"], **{name: ["value"] for name in names},
                             "BENCHMARK_DATE": ["extra"]})
        data.attrs["bond_universe"] = "convertible"
        assert select_display_columns(data).columns.tolist() == ["ID"]
        data.attrs["include_benchmarks"] = True
        expected = [
            "ID", "BENCHMARK_NAME", "BENCHMARK_EXPIRE_DT", "BENCHMARK_STRIKE_PX",
        ]
        if names == list(BENCHMARK_COLUMN_LABELS.values()):
            expected = ["ID", *[name.upper() for name in BENCHMARK_COLUMN_LABELS]]
        assert select_display_columns(data).columns.tolist() == expected


def test_analysis_chats_are_independent_and_close_clears_context(monkeypatch):
    import desktop.analysis_window as results_module
    from PySide6.QtCore import Qt
    app = QApplication.instance() or QApplication([])
    calls = []
    def reply(question, dataset, bql, history):
        calls.append((question, history))
        return "Follow-up answer"
    monkeypatch.setattr(results_module, "run_post_analysis", reply)
    first = results_module.AnalysisWindow("First", "Answer one", pd.DataFrame({"x": [1]}), "BQL")
    second = results_module.AnalysisWindow("Second", "Answer two", pd.DataFrame({"x": [2]}), "BQL2")
    try:
        first.follow_up.setPlainText("Why?")
        QTest.keyClick(first.follow_up, Qt.Key.Key_Return)
        wait_for(app, lambda: first._job is None)
        assert calls[0] == ("Why?", [{"role": "user", "content": "First"},
                                    {"role": "assistant", "content": "Answer one"}])
        assert len(first.history) == 4
        assert len(second.history) == 2
        text = first.result_text.toPlainText()
        assert text.index("First") < text.index("Answer one") < text.index("Why?") < text.index("Follow-up answer")
        first.close()
        assert first.history == []
        assert first.dataset.empty
        assert first.bql_query == ""
        assert len(second.history) == 2
    finally:
        first.close()
        second.close()


def test_maturity_form_round_trip_preserves_iso_query_dates():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        query = main_window_module.BondSearchQuery.model_validate({"filters": [
            {"field": "maturity", "operator": "between",
             "value": {"minimum": "2030-01-07", "maximum": "2032-12-31"}},
        ]})
        window.display_query_in_controls(query)
        assert window.minimum_maturity.text() == "01-07-2030"
        assert window.maximum_maturity.text() == "12-31-2032"
        rebuilt = window.query_from_controls()
        assert rebuilt is not None
        bql = main_window_module.compile_query(rebuilt)
        assert "MATURITY >= 2030-01-07" in bql
        assert "MATURITY <= 2032-12-31" in bql
    finally:
        window.close()
        app.processEvents()


def wait_for(app, condition):
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(5)
    assert condition()


def test_search_runs_in_background_and_restores_submit(monkeypatch):
    app = QApplication.instance() or QApplication([])
    release = Event()
    started = Event()
    def search(*args, **kwargs):
        assert QThread.currentThread() != app.thread()
        started.set()
        assert release.wait(5)
        return pd.DataFrame({"ID": ["bond-1"], "PX_LAST": [100.]})
    monkeypatch.setattr(main_window_module, "search_bql", search)
    window = MainWindow()
    try:
        window.submit_search()
        wait_for(app, started.is_set)
        assert window.submit_button.text() == "Submitting..."
        assert not window.submit_button.isEnabled()
        job = window._search_job
        window.submit_search()
        assert window._search_job is job
        ticks = []
        QTimer.singleShot(0, lambda: ticks.append(True))
        wait_for(app, lambda: bool(ticks))
        release.set()
        wait_for(app, lambda: window._search_job is None)
        assert window.submit_button.isEnabled()
        assert window.submit_button.text() == "Submit"
        assert window.results.iloc[0]["PX_LAST"] == 100.
    finally:
        release.set()
        wait_for(app, lambda: window._search_job is None)
        window.close()


def test_ai_jobs_are_independent_and_keep_ui_responsive(monkeypatch):
    app = QApplication.instance() or QApplication([])
    release = Event()
    interpreter_started = Event()
    analysis_started = Event()
    captured = []

    def interpret(request):
        assert QThread.currentThread() != app.thread()
        interpreter_started.set()
        assert release.wait(5)
        return main_window_module.BondSearchQuery(filters=[])

    def analyse(question, dataset, bql):
        assert QThread.currentThread() != app.thread()
        analysis_started.set()
        assert release.wait(5)
        captured.append((question, dataset.iloc[0, 0], bql))
        return "Completed"

    monkeypatch.setattr(main_window_module, "interpret_request_with_ai", interpret)
    monkeypatch.setattr(main_window_module, "run_post_analysis", analyse)
    window = MainWindow()
    try:
        window.request_input.setPlainText("Find bonds")
        window.results = pd.DataFrame({"price": [100]})
        window.bql_query = "original BQL"
        window.post_analysis.setPlainText("Original question")
        window.interpret_request()
        window.run_analysis()
        wait_for(app, lambda: interpreter_started.is_set() and analysis_started.is_set())
        ticks = []
        QTimer.singleShot(0, lambda: ticks.append(True))
        wait_for(app, lambda: bool(ticks))
        original_job = window._interpret_job
        window.interpret_request()
        assert window._interpret_job is original_job
        window.post_analysis.setPlainText("Edited question")
        window.results.iloc[0, 0] = 200
        window.bql_query = "edited BQL"
        assert not window.run_analysis_button.isEnabled()
        release.set()
        wait_for(app, lambda: window._interpret_job is None and window._analysis_job is None)
        assert captured == [("Original question", 100, "original BQL")]
        assert window.analysis_window.question_label.text() == "Original question"
        assert window.interpret_button.isEnabled()
    finally:
        release.set()
        wait_for(app, lambda: window._interpret_job is None and window._analysis_job is None)
        if window.analysis_window:
            window.analysis_window.close()
        window.close()


def test_ai_errors_restore_controls_on_ui_thread(monkeypatch):
    app = QApplication.instance() or QApplication([])
    errors = []

    def fail(*args):
        raise RuntimeError("Service unavailable")

    def report(parent, title, message):
        assert QThread.currentThread() == app.thread()
        errors.append(message)

    monkeypatch.setattr(main_window_module, "interpret_request_with_ai", fail)
    monkeypatch.setattr(main_window_module, "run_post_analysis", fail)
    monkeypatch.setattr(main_window_module.QMessageBox, "critical", report)
    window = MainWindow()
    try:
        window.request_input.setPlainText("Find bonds")
        window.results = pd.DataFrame({"price": [100]})
        window.post_analysis.setPlainText("Analyse")
        window.interpret_request()
        window.run_analysis()
        wait_for(app, lambda: window._interpret_job is None and window._analysis_job is None)
        assert errors == ["Service unavailable", "Service unavailable"]
        assert window.interpret_button.isEnabled()
        assert window.run_analysis_button.isEnabled()
    finally:
        window.close()


def test_submit_sends_bql_and_displays_results(monkeypatch):
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

    def fake_search_bql(query, **kwargs):
        submitted.append(main_window_module.compile_query(query))
        return bloomberg_results

    monkeypatch.setattr(
        main_window_module,
        "search_bql",
        fake_search_bql,
    )
    window = MainWindow()
    try:
        window.submit_search()
        wait_for(app, lambda: window._search_job is None)

        assert len(submitted) == 1
        assert submitted[0] == window.bql_query
        assert window.bql_query.startswith("GET(")
        assert "FOR(TOP(filter(debtuniv('active'" in window.bql_query
        assert ", 100, AMT_OUTSTANDING" in window.bql_query
        assert window.results.equals(bloomberg_results)
        assert window.results_table.rowCount() == 2
        assert window.results_table.columnCount() == 3
        assert window.results_count.text() == "2 results"
        assert window.results_table.horizontalHeaderItem(0).text() == "ID"
        assert window.results_table.item(0, 2).text() == "Example Convertible"
    finally:
        window.close()


def test_benchmarks_are_available_only_for_convertible_bonds():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.universe_dropdown.setCurrentIndex(window.universe_dropdown.findData("convertible"))
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


def test_distant_dates_sort_and_benchmark_dates_use_us_format():
    from datetime import date
    from desktop.results import SortableTableItem, format_table_value
    app = QApplication.instance() or QApplication([])
    dates = [pd.Timestamp("9999-12-31"), pd.Timestamp("2030-01-07"),
             date(2500, 6, 15), pd.NaT]
    ordered = sorted(dates, key=SortableTableItem.normalized_sort_value)
    assert ordered[:3] == [dates[1], dates[2], dates[0]]
    assert pd.isna(ordered[3])
    assert format_table_value("MATURITY", dates[0]) == "12-31-9999"
    for column in ["BENCHMARK_EXPIRE_DT", "BENCHMARK_EXPIRE_DT()", "Benchmark Expire Dt()"]:
        assert format_table_value(column, "2030-01-07T00:00:00") == "01-07-2030"
    table = QTableWidget()
    data = pd.DataFrame({"MATURITY": dates[:3], "BENCHMARK_EXPIRE_DT()": dates[:3]})
    data.attrs.update(bond_universe="convertible", include_benchmarks=True)
    populate_results_table(table, data)
    assert table.item(0, 0).text() == "12-31-9999"
    assert table.item(0, 1).text() == "12-31-9999"
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
            "CV_CNVS_RATIO": [2.34567],
            "YIELD(YIELD_TYPE=YTM)": [4],
            "BENCHMARK_STRIKE_PX": [100.5555],
            "PARITY": [95.1254],
            "CV_PCT_PREMIUM": [6.4382],
            "AMT_OUTSTANDING": [250000000],
        }),
    )

    assert [table.item(0, column).text() for column in range(8)] == [
        "101.200",
        "98.765",
        "2.346",
        "4.000",
        "100.555",
        "95.125",
        "6.438",
        "250,000,000",
    ]
    assert table.horizontalHeaderItem(6).text() == "Premium (%)"
    assert table.horizontalHeaderItem(7).text() == "Outstanding"
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
        wait_for(app, lambda: window._analysis_job is None)

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


def test_benchmark_results_flow_from_bql_to_table(monkeypatch):
    app = QApplication.instance() or QApplication([])
    bond_results = pd.DataFrame([{
        "CV_COMMON_TICKER_EXCH": "AAA US Equity",
        "CV_CNVS_PX": 100.0,
        "MATURITY": "2030-01-01",
    }])
    monkeypatch.setattr(
        main_window_module,
        "search_bql",
        lambda _query, **kwargs: bond_results.assign(
            BENCHMARK_NAME="AAA call", BENCHMARK_PX_LAST=12.34567,
            BENCHMARK_EXPIRE_DT="2030-01-07"),
    )
    window = MainWindow()
    try:
        window.universe_dropdown.setCurrentIndex(window.universe_dropdown.findData("convertible"))
        window.get_benchmarks_checkbox.setChecked(True)
        window.submit_search()
        wait_for(app, lambda: window._search_job is None)

        assert window.results.loc[0, "BENCHMARK_NAME"] == "AAA call"
        headers = [
            window.results_table.horizontalHeaderItem(column).text()
            for column in range(window.results_table.columnCount())
        ]
        assert "Option name" in headers
        expected = {
            "Option price": "12.346",
            "Option expiry": "01-07-2030",
        }
        for label, value in expected.items():
            assert window.results_table.item(0, headers.index(label)).text() == value
    finally:
        window.close()
