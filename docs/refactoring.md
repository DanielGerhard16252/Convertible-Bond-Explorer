# Application structure

The desktop calls Python services directly; no separate application server is required.

| Responsibility | Module |
| --- | --- |
| Search form and background-job lifecycle | `desktop/main_window.py` |
| Display validated filters in controls | `desktop/filter_controls.py` |
| Bond details and calculation presentation | `desktop/bond_record.py` |
| Credit metrics, annual default probability and spread | `server/credit_analytics.py` |
| Interest-rate interpolation, curve mapping and put retrieval | `server/bond_lookups.py` |
| Result column selection, labels and formatting | `desktop/result_formatting.py` |
| Qt result tables, sorting and secondary windows | `desktop/results.py` |
| Static AI interpretation instructions | `server/prompt_templates.py` |
| Dynamic prompt context and analysis instructions | `server/prompts.py` |
| Shared Bloomberg column normalization | `shared/columns.py` |

Credit calculations return an immutable `CreditMetrics` object. Both the displayed
intermediate values and the final spread come from this result. Rates enter as
percentages; probabilities, LGD and spread are decimals. Default probability uses
a one-year horizon and spread is LGD multiplied by that probability.

Bloomberg services accept an optional executor for offline testing. Existing
window helper methods and result-formatting imports remain available for callers.
The put search includes expiries at least 10 days from today, including day 10.

The CSV providers, query validation, BICS configuration and packaging entry points
retain their existing contracts. New modules are ordinary Python imports and
require no new packaged data files or dependencies.
