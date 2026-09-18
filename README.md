# Convertible Bond Explorer

A Python desktop application for screening convertible and high-yield bonds. Describe a search in plain English or enter filters manually, search live Bloomberg data, and inspect, export, or analyse the results.

The interface uses PySide6, query validation uses Pydantic, and results are handled with pandas. The desktop app calls the modules in `server/` directly; there is no separate web server to start.

## Features

- Convert natural-language requests into editable search filters.
- Select a convertible or high-yield universe, with asset-class selection for high-yield searches.
- Filter by credit rating, price, coupon, issuer, maturity, currency, conversion premium, yield to maturity, country of risk, and amount outstanding.
- View sortable results, including a separate results window.
- Export results through a Save dialog that defaults to Downloads.
- Run AI analysis using the returned dataset and generated BQL, with web search available for additional context.
- Optionally retrieve Bloomberg call-option benchmarks for convertible results.
- Look up currency-specific interest-rate curves and equity puts from bond details, then calculate credit spreads.

## Local setup

Run the following from the repository root in Windows PowerShell. Use Python 3.10 or newer, subject to the requirements of the installed dependencies.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install PySide6 pandas "pydantic>=2" python-dotenv openai pytest
```

Dependencies are currently installed explicitly: `pyproject.toml` contains pytest configuration but does not declare application dependencies or a pinned environment.

For desktop searches and lookups, also install `polars-bloomberg` and configure its Bloomberg API dependencies, including `blpapi`, in this environment. Searches and benchmark lookups require a working Bloomberg connection and the appropriate data access.

```powershell
.\.venv\Scripts\python.exe -m pip install polars-bloomberg
```

Create a `.env` file in the repository root, or add the following entries to your existing file:

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=your-model-name
```

`OPENAI_MODEL` is optional; the code currently defaults to `gpt-5.6`. Choose a model available to your account that supports the API features used by the app. An API key is needed only for AI interpretation and analysis. Manual Bloomberg searches work without an OpenAI key. AI clients are created per request and closed afterwards. Source runs load the project `.env`; packaged runs prefer environment variables, then `.env` beside the executable, then bundled AI settings.

Start the desktop application:

```powershell
.\.venv\Scripts\python.exe -m desktop
```

## Using the application

1. Enter a request and select **Interpret request**, or enter filters directly. For example: “Show me BBB-rated USD convertible bonds priced between 90 and 110, then rank the results by yield.”
2. Review and edit the filters. Amount outstanding is expressed in millions of the bond currency and defaults to a minimum of 50. Date inputs use `MM-DD-YYYY`; percentage filters use percentage values.
3. Select **Submit** to retrieve live Bloomberg results. Results appear directly below the filters; AI analysis is at the bottom of the window.
4. Inspect the results, sort by column, or select **Open in new window**. Select **Export to CSV** to choose a filename and location; the Save dialog defaults to Downloads.
5. Enter or edit the analysis instructions and select **Run analysis** after retrieving results.

AI interpretation sends the search request to OpenAI and can use web search to resolve issuer names. AI analysis sends the returned dataset, BQL, and analysis instructions to OpenAI, and may use web search for additional context.

## CSV utilities

`server/csv_provider.py` provides `load_bond_data()` for filtering a local CSV, defaulting to `data/bond_data.csv`. It accepts normalized column names as well as mapped Bloomberg field names. Additional columns are required by the filters you apply.

The desktop **Submit** action uses `server/bql_search.py` to execute BQL, with the same validated filters and result columns as the CSV utilities. It defaults to High Yield, applies the default minimum amount of 50 million, and applies the maximum-result limit after filtering, ranked by USD amount outstanding. Bond search, optional call benchmarks, interest-rate curves, and put lookups use Bloomberg; failures are reported without falling back to CSV. The existing currency-to-curve mapping is in `desktop/bond_record.py`; rates are linearly interpolated by maturity, using the nearest endpoint outside the curve. Curve availability and suitability require verification in your Bloomberg environment.

The bundled `data/search_demo.csv` and `data/option_demo.csv` are **synthetic**, not market data. Existing CSVs are unchanged. For standalone `search_csv()` calls, override `BOND_CSV_PATH` and `OPTION_CSV_PATH` in `.env` to use your own files. Relative configured paths resolve beside the executable, or against the project root in source runs. Regenerate the complete demos with `python -m data.search_demo_generation`.

Bond CSVs represent active securities. Use the Bloomberg column names in `search_demo.csv` or their normalized aliases in `server/csv_provider.py`. All return fields for the chosen universe must exist, even if some values are null. Sector, payment rank, ISIN, premium, YTM, YTW, country/currency lists and numeric/date ranges are supported. `AMT_OUTSTANDING_USD` is needed for maximum-result ranking when non-USD bonds are present; amount-range filtering uses `AMT_OUTSTANDING`, matching the current BQL expression. Demo USD amounts use synthetic FX factors.

Option CSVs require `TICKER`, `PUT_CALL`, `ID`, `NAME`, `EXPIRE_DT`, `STRIKE_PX`, `PX_LAST`, and `IVOL`. Convertible benchmarks select calls for the underlying ticker with strike within 10% of conversion price, choosing the expiry nearest bond maturity. Missing matches leave empty benchmark values. Neither bond nor benchmark retrieval needs Bloomberg in CSV mode. Sorting, export, double-click record details, and AI analysis remain available.

## Tests

Run the default suite without live OpenAI calls:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest
```

The default pytest configuration discovers tests in `tests/`, excludes tests marked `integration`, and uses pytest's managed temporary directories. The suite covers query validation, interpretation, BQL compilation, CSV filtering, sample-data generation, Bloomberg adapters, benchmarks, analysis, and desktop behaviour.

To run integration tests, use a real API key in `.env` and clear the test-only environment override first:

```powershell
Remove-Item Env:OPENAI_API_KEY
.\.venv\Scripts\python.exe -m pytest -m integration
```

Integration tests call external services and may incur API charges.

## Windows executable

`scripts/build_app.ps1` runs PyInstaller using `.venv` and expects `ConvertibleBondExplorer.spec` in the repository root. The spec is included in version control and packages the legacy bond CSV and both desktop demo CSVs.

With the Bloomberg dependencies installed and a non-empty `OPENAI_API_KEY` in the project `.env`:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\scripts\build_app.ps1
```

The script targets `dist/ConvertibleBondExplorer.exe`. As requested, the build embeds `OPENAI_API_KEY` and optional `OPENAI_MODEL` from the project `.env`. Other `.env` settings are excluded. These credentials are extractable from the executable. Existing executables are not changed by source edits; rebuild to apply changes.

## Project layout

| Path | Purpose |
| --- | --- |
| `desktop/` | Application entry point, Qt interface, results, and analysis windows |
| `desktop/results.py` | Shared result formatting and tables |
| `desktop/analysis_window.py`, `desktop/analysis_browser.py` | AI conversations and citation rendering |
| `shared/config.py`, `server/ai_client.py` | Runtime paths, environment loading, and request-scoped AI clients |
| `desktop/widgets.py`, `desktop/styles.py` | Reusable input widgets and application styling |
| `desktop/background.py` | Background workers for independent AI requests |
| `server/bql_compiler.py` | Compile validated search filters into Bloomberg BQL |
| `server/bloomberg_api.py` | Execute queries through `polars_bloomberg` |
| `server/ai_interpreter.py` | Translate natural-language searches into structured filters |
| `server/ai_analysis.py` | Analyse retrieved data with BQL context |
| `server/prompts.py` | Prompt construction for both AI services |
| `server/benchmarks.py` | Retrieve option benchmark candidates |
| `server/csv_provider.py` | Filter CSV data locally |
| `shared/` | Query models, filter types, and credit ratings |
| `data/` | CSV datasets and synthetic-data generation code |
| `tests/` | Unit and integration tests |
| `scripts/` | Windows build helper |

Generate a reproducible synthetic dataset in a separate file:

```powershell
.\.venv\Scripts\python.exe -m data.data_generation --count 1000 --seed 42 --output data/synthetic.csv
```

Omitting `--output` writes to `data/bond_data.csv`. Importing the generator does not create or overwrite files.

Run the command-line interpretation example:

```powershell
.\.venv\Scripts\python.exe -m examples.run_ai_interpreter "Show me BBB-rated convertible bonds"
```

## Repository review

See [the review findings](docs/repository-review.md) for corrected issues, retained behavior, and verification limits.
