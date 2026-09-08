# Convertible Bond Explorer

A Python desktop application for screening convertible and high-yield bonds. Describe a search in plain English or enter filters manually, submit a Bloomberg Query Language (BQL) query, and inspect, export, or analyse the results.

The interface uses PySide6, query validation uses Pydantic, and results are handled with pandas. The desktop app calls the modules in `server/` directly; there is no separate web server to start.

## Features

- Convert natural-language requests into editable search filters.
- Select a convertible or high-yield universe, with asset-class selection for high-yield searches.
- Filter by credit rating, price, coupon, issuer, maturity, currency, conversion premium, yield to maturity, country of risk, and amount outstanding.
- View the generated BQL and sortable results, including a separate results window.
- Export results to CSV under `data/`.
- Run AI analysis using the returned dataset and generated BQL, with web search available for additional context.
- Optionally retrieve Bloomberg option benchmarks for convertible results.

## Local setup

Run the following from the repository root in Windows PowerShell. Use Python 3.10 or newer, subject to the requirements of the installed dependencies.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install PySide6 pandas "pydantic>=2" python-dotenv openai pytest
```

Dependencies are currently installed explicitly: `pyproject.toml` contains pytest configuration but does not declare application dependencies or a pinned environment.

For live searches, also install `polars-bloomberg` and configure its Bloomberg API dependencies, including `blpapi`, in this environment. Searches require a working Bloomberg connection and the appropriate data access.

```powershell
.\.venv\Scripts\python.exe -m pip install polars-bloomberg
```

Create a `.env` file in the repository root, or add the following entries to your existing file:

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=your-model-name
```

`OPENAI_MODEL` is optional; the code currently defaults to `gpt-5.6`. Choose a model available to your account that supports the API features used by the app. A non-empty API key is required at startup because the AI modules initialise their clients when imported, even if you intend to enter filters manually. The `.env.example` file is currently empty.

Start the desktop application:

```powershell
.\.venv\Scripts\python.exe -m desktop
```

## Using the application

1. Enter a request and select **Interpret request**, or enter filters directly. For example: “Show me BBB-rated USD convertible bonds priced between 90 and 110, then rank the results by yield.”
2. Review and edit the filters. Amount outstanding is expressed in USD millions and defaults to a minimum of 50. Date inputs use `MM-DD-YYYY`; percentage filters use percentage values.
3. Select **Submit** to generate BQL and retrieve Bloomberg results. The generated query appears in the interface.
4. Inspect the results, sort by column, or select **Open in new window**. Enter a CSV filename to export the results.
5. Enter or edit the analysis instructions and select **Run analysis** after retrieving results.

AI interpretation sends the search request to OpenAI. AI analysis sends the returned dataset, BQL, and analysis instructions to OpenAI, and may use web search for additional context.

## CSV utilities

`server/csv_provider.py` provides `load_bond_data()` for filtering a local CSV, defaulting to `data/bond_data.csv`. It accepts normalized column names as well as mapped Bloomberg field names. Additional columns are required by the filters you apply.

The desktop **Submit** action currently uses Bloomberg directly; the CSV provider is a separate utility and is not a selectable desktop data source. `data/data_generation.py` contains synthetic-data generation code.

## Tests

Run the default suite without live OpenAI calls:

```powershell
$env:OPENAI_API_KEY = "test-key"
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m pytest
```

The default pytest configuration excludes tests marked `integration` and stores temporary files in `pytest-temp/`. The suite covers query validation, interpretation, BQL compilation, CSV filtering, Bloomberg adapters, benchmarks, analysis, and desktop behaviour.

To run integration tests, use a real API key in `.env` and clear the test-only environment override first:

```powershell
Remove-Item Env:OPENAI_API_KEY
.\.venv\Scripts\python.exe -m pytest -m integration
```

Integration tests call external services and may incur API charges.

## Windows executable

`scripts/build_app.ps1` runs PyInstaller using `.venv` and expects `ConvertibleBondExplorer.spec` in the repository root. The spec file is ignored by Git, so a fresh clone needs a suitable spec before this build script can run.

With the spec and Bloomberg dependencies present:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\scripts\build_app.ps1
```

The script targets `dist/ConvertibleBondExplorer.exe`. The current local packaging configuration embeds `.env`, including its API key; that key can be extracted from the executable. Do not distribute an executable containing a private key.

## Project layout

| Path | Purpose |
| --- | --- |
| `desktop/` | Application entry point, Qt interface, results, and analysis windows |
| `server/bql_compiler.py` | Compile validated search filters into Bloomberg BQL |
| `server/bloomberg_api.py` | Execute queries through `polars_bloomberg` |
| `server/ai_interpreter.py` | Translate natural-language searches into structured filters |
| `server/ai_analysis.py` | Analyse retrieved data with BQL context |
| `server/benchmarks.py` | Retrieve option benchmark candidates |
| `server/csv_provider.py` | Filter CSV data locally |
| `shared/` | Query models, filter types, and credit ratings |
| `data/` | CSV datasets and synthetic-data generation code |
| `tests/` | Unit and integration tests |
| `scripts/` | Windows build helper |
