# Repository review — 2026-09-15

## Scope

Reviewed application entry points, desktop windows and workers, AI services and
prompts, CSV and Bloomberg providers, query compilation and models, shared
configuration, data generators, examples, build configuration, and tests.
Existing user changes were preserved. This is a source review and refactor, not
a certification of dependencies or a live market-data integration audit.

## Corrected issues

| Finding | Resolution |
| --- | --- |
| Importing the desktop constructed OpenAI clients and required credentials for local use. | Request-scoped clients; explicit environment loading; clients close on success and failure. |
| Packaged data did not match the desktop's default CSV paths. | The spec includes both desktop demo files and the legacy CSV. |
| Build configuration was ignored and copied the entire `.env`. | The spec is eligible for version control and embeds only the requested AI key and optional model. |
| Runtime configuration could depend on the working directory or implicit dotenv discovery. | Centralized application/resource paths and explicit dotenv locations. |
| Analysis prompts still instructed government-yield collection/interpolation after rate collection was removed. | Removed that workflow and inaccurate claims about access to Python execution. |
| AI text could link to local resources through the answer browser. | No embedded-resource loading; only clicked HTTP/HTTPS citations open externally. |
| CSV filters could silently accept an operator that BQL rejects. | Validate field/operator combinations in the shared model. |
| Repeated populated filters could be ignored by BQL's first-filter selection while CSV applied all of them. | Reject duplicates before execution. |
| NaN, infinity and reversed ranges could reach providers. | Validate ranges at the shared boundary and report errors in the form. |
| Normalized CSV aliases could collide. | Reject ambiguous mapped column names. |
| High-yield CSV searches unnecessarily required a convertible flag. | Require that flag only for the convertible branch. |
| Local rating parsing truncated trailing plus/minus signs. | Corrected token boundaries with regression coverage. |
| Every search printed its BQL to standard output. | Removed unconditional query logging. |
| Analysis conversation code was mixed into table formatting. | Extracted the analysis window and its restricted browser into dedicated modules. |
| Documentation/prompts described amount filtering as USD while code used native amounts. | Corrected units to millions of the bond currency; preserved existing filter semantics. |

## Intentional behavior and remaining limitations

- **Embedded credentials are retained at the user's explicit request.** The
  executable contains extractable AI credentials. Runtime environment variables
  and an external `.env` can override bundled values. The build includes only
  `OPENAI_API_KEY` and `OPENAI_MODEL`; it does not bake local CSV overrides into
  the app. Prior executables require rebuilding to pick up these changes.
- Submit searches local CSV data; generated BQL is a preview. The default CSVs
  are synthetic. The separate Bloomberg adapter still executes live requests
  when called directly.
- AI interpretation sends the request to OpenAI and has web search for issuer
  resolution. Analysis sends all returned source columns, instructions, BQL and
  conversation history, including source columns hidden by the results table.
  There is no local Python execution tool. Long datasets/history are not yet
  capped and can increase request size and cost.
- Missing amount filters imply a minimum of 50 million in native currency.
  Maximum-result ranking uses USD amounts. These are distinct operations;
  converting the filter to USD would change search behavior.
- Bloomberg failures retain diagnostic response excerpts and query text.
  Per-bond option lookup failures remain visible in `BENCHMARK_ERROR` instead of
  aborting the whole batch. Diagnostics can contain source data.
- Closing a window suppresses completion UI but does not cancel an in-flight
  network request. AI clients use a 120-second SDK timeout and one retry; this is
  not a strict wall-clock deadline for the complete operation.
- No dynamic execution of model output, shell-command execution by the app,
  unexpected telemetry endpoint, or import-time data generation was found in
  the reviewed source. Third-party packages and existing binaries were not
  audited for those behaviors.

## Verification

The baseline was 164 passing tests, with four live integration tests excluded.
The final suite passed 185 tests, with four live integration tests excluded.
Python compilation and `git diff --check` also passed. A mocked packaging test
verified that the spec includes the AI credentials and expected CSV files while
excluding unrelated secrets and local CSV overrides.
Regression coverage now includes import-time side effects, credential override
precedence, path resolution, client cleanup, rating suffixes, shared validation,
CSV schema ambiguity, and citation/resource handling. Tests use fake credentials
and mocked services; no live OpenAI or Bloomberg calls are required.

The client lifecycle and timeout options were checked against the installed SDK
and [the official Python SDK reference](https://developers.openai.com/api/reference/python).
No executable was rebuilt or live Bloomberg session exercised during this review.
