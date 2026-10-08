# Validation performed

## Executed

- **45 automated API/analytics tests passed**, no test failures or errors. Tests used FastAPI's actual ASGI application against a temporary copy of the real synthetic database. See `validation/pytest-results.xml`.
- **40 browser/render/workflow checks passed**, including all 15 main workspaces, all six role logins, 8 KPI cards, a date filter, map zoom, SHAP evidence drawer, route forecast filter, what-if calculation, allocation result, profile dialogs and responsive sidebar. No JavaScript page errors were observed.
- Desktop viewport: 1672 × 1020. Mobile viewport: 390 × 844; no horizontal page overflow was detected on the executive screen. Actual rendered screenshots are in `screenshots/`.
- Synthetic seed, ETL, full classification/forecast/SHAP pipeline and optimizer were executed. Numbers in the model report are calculated, not manually authored illustrative accuracy claims.
- Critical relational/data-quality checks passed, including capacity/revenue reconciliation and vehicle/driver schedule overlap checks. Missing-fuel warnings and staging rejects are intentionally retained.
- A fresh-process smoke test deliberately blocked NumPy, Pandas, SciPy, scikit-learn, XGBoost, SHAP, PyArrow and Streamlit imports. The web app, dashboard, resource metadata, model/forecast snapshots, quality and experience APIs still worked; allocation used its explicit greedy fallback. See `validation/core-runtime-results.json`.

## Browser transport caveat

The build environment's managed Chromium blocked direct URL navigation. No browser policy was changed. UI checks loaded the actual HTML/CSS/JavaScript and bundled Plotly through Playwright's offline content interface, then bridged fetch calls to the real local FastAPI server via an HTTP client. This tests rendering, actual API responses and interactions, but **does not prove native-browser cookie transport, CSP enforcement, network navigation or external deployment behaviour**. API tests independently checked cookies, CSRF, origin rejection, authorization and security headers.

`tests/browser_smoke.py` supplies an ordinary native-navigation smoke script for a machine with a permitted local browser. It requires a running SmartMove app and Playwright Chromium; it was not executed in that normal transport mode here.

## Automated test coverage

Authentication failure, anonymous rejection, CSRF enforcement, cross-origin writes, user/session lifecycle, driver/customer ownership, forbidden admin/financial endpoints, atomic booking, overselling prevention, cancellation/ticket/refund consistency, profile privilege-escalation rejection, input validation, SQL-injection-like search, audit redaction, data quality, probability bounds, temporal holdout metadata, SHAP reconstruction and allocation feasibility are covered. These are representative checks, not an exhaustive security or performance audit.

## Environment and untested integrations

Execution environment: Linux x86_64, Python 3.13.5, installed scikit-learn 1.8.0, XGBoost 3.1.3, SHAP 0.50.0, SciPy 1.17.0; Playwright 1.57.0 using installed Chromium for offline rendering. `requirements-dev.txt` pins those tested package families. The local Windows launcher targets Python 3.12.

Windows setup, Docker, the .NET gateway, SQL Server integration and Power BI Desktop assets were **not executed** here. They are supplied as source/configuration with explicit setup and limitations. No claim of production readiness, official regulatory compliance, penetration-test completion or real operational benefit is made.

## Reproduce tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Native browser smoke on your machine, after starting the server:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe tests\browser_smoke.py
```

The main web environment does not require these development dependencies. Keep generated credentials and outbox files private.
