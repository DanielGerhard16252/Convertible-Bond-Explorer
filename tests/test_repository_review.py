"""Regression coverage for configuration, validation and rendering boundaries."""

import os
from pathlib import Path
import subprocess
import sys
import runpy
from types import ModuleType, SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from server.csv_provider import load_bond_data
from server.interpreter import interpret_request
from shared.models import BondSearchQuery


@pytest.mark.parametrize("rating", ["AA+", "AA-", "A+", "BBB-", "BB+", "CCC-"])
def test_local_interpreter_preserves_rating_suffix(rating):
    assert interpret_request(f"Bonds rated {rating}").filters[0].value == [rating]


@pytest.mark.parametrize("field,value", [
    ("price", {"minimum": float("nan")}),
    ("yield_to_maturity", {"maximum": float("inf")}),
    ("amount_outstanding", "Infinity"),
    ("price", {"minimum": 110, "maximum": 90}),
    ("maturity", {"minimum": "2031-01-01", "maximum": "2030-01-01"}),
])
def test_invalid_ranges_rejected_before_search(field, value):
    with pytest.raises(ValueError):
        BondSearchQuery.model_validate({"filters": [
            {"field": field, "operator": "between", "value": value},
        ]})


def test_invalid_csv_operator_is_rejected():
    with pytest.raises(ValueError, match="requires BETWEEN"):
        BondSearchQuery.model_validate({"filters": [
            {"field": "price", "operator": "equals", "value": {"minimum": 100}},
        ]})


def test_duplicate_rating_filters_cannot_diverge_between_providers():
    with pytest.raises(ValueError, match="Duplicate filter"):
        BondSearchQuery.model_validate({"filters": [
            {"field": "credit_rating", "operator": "in", "value": [rating]}
            for rating in ("B", "BB")
        ]})


def test_ambiguous_csv_aliases_rejected(tmp_path):
    path = tmp_path / "duplicate.csv"
    pd.DataFrame({"SECURITY_DES": ["Bond"], "BB_COMPOSITE": ["B"],
                  "PX_LAST": [90], "price": [110]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="duplicate fields"):
        load_bond_data(BondSearchQuery(filters=[]), path)


def test_high_yield_csv_does_not_require_convertible_flag(tmp_path):
    path = tmp_path / "hy.csv"
    pd.DataFrame({"SECURITY_DES": ["Bond"], "BB_COMPOSITE": ["B"],
                  "PX_LAST": [90], "SRCH_ASSET_CLASS": ["Corporates"]}).to_csv(path, index=False)
    query = BondSearchQuery.model_validate({"filters": [
        {"field": "bond_universe", "operator": "equals", "value": "high_yield"},
    ]})
    assert len(load_bond_data(query, path)) == 1


def test_importing_desktop_never_creates_client_or_loads_environment():
    script = """
import dotenv
import openai
def unexpected(*args, **kwargs):
    raise AssertionError('Import must not load credentials or create clients')
dotenv.load_dotenv = unexpected
openai.OpenAI = unexpected
import desktop.__main__
import desktop.main_window
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_bundled_key_fallback_and_runtime_override(tmp_path, monkeypatch):
    from shared import config
    runtime, bundle = tmp_path / "runtime", tmp_path / "bundle"
    runtime.mkdir()
    bundle.mkdir()
    (bundle / ".env").write_text("OPENAI_API_KEY=bundled-test-key\n")
    monkeypatch.setattr(config, "application_directory", lambda: runtime)
    monkeypatch.setattr(config, "resource_directory", lambda: bundle)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config.load_app_environment()
    assert os.environ["OPENAI_API_KEY"] == "bundled-test-key"
    monkeypatch.setenv("OPENAI_API_KEY", "runtime-test-key")
    config.load_app_environment()
    assert os.environ["OPENAI_API_KEY"] == "runtime-test-key"


def test_relative_csv_configuration_uses_application_directory(tmp_path, monkeypatch):
    from shared import config
    monkeypatch.setattr(config, "application_directory", lambda: tmp_path)
    monkeypatch.setenv("BOND_CSV_PATH", "custom/bonds.csv")
    assert config.configured_data_path("BOND_CSV_PATH", "search_demo.csv") == tmp_path / "custom/bonds.csv"


def test_analysis_links_cannot_open_local_files(monkeypatch):
    import desktop.analysis_browser as module
    app = QApplication.instance() or QApplication([])
    opened = []
    monkeypatch.setattr(module.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    browser = module.AnalysisBrowser()
    try:
        for link in ("file:///C:/private.txt", "javascript:alert(1)", "mailto:test@example.com", "https://example.com/source"):
            browser.open_citation(QUrl(link))
        assert opened == ["https://example.com/source"]
        assert browser.loadResource(2, QUrl("file:///C:/private.png")) is None
    finally:
        browser.close()
        app.processEvents()


def test_ai_client_is_closed_after_service_error(monkeypatch):
    import server.ai_interpreter as module
    closed = []
    class Client:
        def __enter__(self):
            self.responses = self
            return self
        def __exit__(self, *args):
            closed.append(True)
        def parse(self, **kwargs):
            raise RuntimeError("Service unavailable")
    monkeypatch.setattr(module, "create_client", Client)
    with pytest.raises(RuntimeError, match="Service unavailable"):
        module.interpret_request_with_ai("Bonds")
    assert closed == [True]


def test_build_bundles_ai_credentials_and_desktop_csvs_only(tmp_path, monkeypatch):
    from dotenv import dotenv_values
    spec = Path(__file__).resolve().parents[1] / "ConvertibleBondExplorer.spec"
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=build-test-key\nOPENAI_MODEL=test-model\n"
        "UNRELATED_SECRET=must-not-be-bundled\nBOND_CSV_PATH=private.csv\n"
    )
    fake_blpapi = ModuleType("blpapi")
    fake_blpapi.__file__ = str(tmp_path / "__init__.py")
    (tmp_path / "ffiutils.test.pyd").touch()
    monkeypatch.setitem(sys.modules, "blpapi", fake_blpapi)
    hooks = ModuleType("PyInstaller.utils.hooks")
    hooks.collect_all = lambda name: ([], [], [])
    monkeypatch.setitem(sys.modules, "PyInstaller.utils.hooks", hooks)
    captured = {}
    def analyse(*args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=kwargs["datas"])
    runpy.run_path(str(spec), init_globals={
        "Analysis": analyse, "PYZ": lambda *args: None,
        "EXE": lambda *args, **kwargs: None,
    })
    environment_path = next(path for path, destination in captured["datas"] if destination == ".")
    assert dict(dotenv_values(environment_path)) == {
        "OPENAI_API_KEY": "build-test-key", "OPENAI_MODEL": "test-model",
    }
    assert {Path(path).name for path, destination in captured["datas"] if destination == "data"} == {
        "bond_data.csv", "search_demo.csv", "option_demo.csv",
    }
