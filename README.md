# SmartMove
## Intelligent Transportation Management & Business Intelligence System
**From Transportation Data to Better Operational Decisions.**

A runnable, local-first transportation operations and BI application with a custom dark dashboard inspired by the supplied visual reference: teal and emerald accents, amber/coral status indicators, a Canadian network map, eight KPI cards, demand and delay charts, fleet utilization, route performance, maintenance alerts, incidents and evidence-linked recommendations.

This is actual HTML/CSS/JavaScript connected to authenticated APIs and a relational database. It is not a screenshot displayed inside a page. Only the mountain scenery crops come from the visual reference. Numbers are calculated from synthetic records and therefore differ from the illustrative image.

**Local operational prototype. All people, facilities, trips, payments, incidents and model outcomes are fictional/synthetic. City coordinates are real geographic references. No live GPS, real ticket, payment processing, mechanical diagnosis or official Canadian statistics are supplied.**

## Start on Windows

1. Extract the ZIP completely. Open the `SmartMove_Enterprise_Platform` folder containing `run.py` and `START_SMARTMOVE.bat`.
2. Install **Python 3.12, 64-bit**, selecting **Add Python to PATH**. Close and reopen PowerShell after installation.
3. Double-click **`START_SMARTMOVE.bat`**. It creates `.venv`, installs the small web runtime, initializes local accounts and starts the server.
4. On the first launch, Notepad opens **`data\LOCAL_CREDENTIALS.txt`**. Use the **Admin** row's email and its generated password.
5. Open **http://localhost:8501**. Keep the terminal open. Press **Ctrl+C** in that terminal to stop the app.

Passwords are generated independently on your computer. There is no shared, hard-coded demo password. Protect `LOCAL_CREDENTIALS.txt` and `data/outbox`; never commit or share them.

**This edition does not use Streamlit. Do not run `streamlit run app.py`.** The startup command is `python run.py`. NumPy, PyArrow, SQL Server and .NET are not needed to open the dashboard.

See [START_HERE_WINDOWS.md](START_HERE_WINDOWS.md) for one-command-at-a-time instructions and troubleshooting.

## What is included

| Workspace | Working functionality |
|---|---|
| Executive Overview | Database-derived KPIs; 7/30/90-day comparison; clickable Canada network; demand, delay, utilization and route charts; maintenance, incidents and recommendations |
| Operations / Fleet / Routes / Trips | Search, pagination, filtering, validated create/edit forms, vehicles, facilities, employees, routes/stops, conflict-checked schedules and trips, driver status updates |
| Reservations / customer portal | Customer login, scheduled-trip search, atomic seat booking, synthetic tickets, simulated payments, cancellation/refund state, owned history and complaints |
| Maintenance / engineer workspace | Technical fleet data, work orders, parts stock, maintenance history, risk review and computed SHAP explanations; part consumption also available through the API |
| Demand / Delay / Predictive Maintenance | Real saved model outputs, daily/weekly/monthly forecasts, route filters, chronological holdout evaluation, calibration plots, current risk queues |
| What-If Simulator | Explicit capacity/staffing/scheduling assumptions; non-causal scenario comparison; constrained vehicle allocation using optional MILP or a labelled greedy baseline |
| Customer Experience | Satisfaction, delay/experience association, loyalty mix, complaint categories and service feedback |
| Data Quality | Referential integrity, seat/revenue reconciliation, schedule conflicts, missing data, staging quarantine, isolated CSV import and warehouse refresh |
| Security & Audit | Six roles, user activation/deactivation, role grants, backend permission/ownership enforcement, revocable sessions, password recovery and audit records |
| Model Lab | Actual model comparison, temporal splits, feature definitions, caveats, refresh jobs and run metadata |

All 15 main sidebar workspaces are implemented. The navigation adapts to the authenticated role; backend authorization is enforced independently of visible buttons. Account details allow users to update their own display name. The API additionally permits a linked passenger to change province; email and role changes are not self-service.

## Six local workspaces

Use the corresponding row from `data/LOCAL_CREDENTIALS.txt`:

| Role | Representative scope |
|---|---|
| Admin | All workspaces, account controls, grants and audit |
| Manager | Operations, fleet, routes, trips, incidents, reservations, maintenance and management analytics |
| Driver | Assigned trips, permitted status changes, own incident reporting and documents |
| Engineer | Fleet technical data, maintenance, parts and predictive maintenance |
| Analyst | Authorized analytics, model results, data quality, ETL and exports; no unrestricted account administration |
| Customer | Available schedules, own bookings/tickets/payments, complaints and account details |

Permission grants are editable by an administrator. Ownership restrictions still apply to customer and driver resources. User deletion may be refused when operational history references the account; deactivate it instead.

## Data already included

The included seed uses **548 historical days**, an **as-of date of 2026-08-31**, and eight further days of demonstration service. It contains **32,804 trips, 328,985 reservations, 12,000 fictional customers, 96 vehicles, 180 employees, 22 directional routes, 12 facilities and 7,584 telemetry rows** across British Columbia, Alberta, Saskatchewan, Manitoba, Ontario and Quebec.

Operational records, the separate warehouse, CSV exports and evaluated model snapshots are bundled. First launch does **not** need to train models. Simulation dates are intentionally tied to the synthetic dataset, not today's date.

## Architecture: explicit local-edition choice

```text
Custom HTML / CSS / JavaScript + local Plotly
                     |
            FastAPI REST application
          authentication / CSRF / RBAC
                     |
         SQLite operational database
                     |
   validation -> isolated staging -> ETL
                     |
      separate warehouse.db + CSVs
                     |
 Python model evaluation / SHAP / forecasting
                     |
      JSON snapshots + Power BI-ready data
```

Python and SQLite make this local package straightforward to run on Windows. The custom frontend reproduces the reference layout more closely than a standard Streamlit layout. This is a deliberate adaptation of the supplied C#/SQL Server brief, **not a claim that the runtime is already an ASP.NET Core / SQL Server deployment**.

`integration/` includes an optional C#/.NET 10 reverse gateway and a SQL Server schema/import path. Those integration files are source-reviewed but **were not compiled or executed against .NET/SQL Server in this environment**. They are not required for the main application. See [integration/README.md](integration/README.md).

## Commands

### Manual local startup — no virtual-environment activation required

Run these from the extracted project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m smartmove.bootstrap
.\.venv\Scripts\python.exe run.py
```

On subsequent launches:

```powershell
.\.venv\Scripts\python.exe run.py
```

Linux/macOS with Python 3.12 or newer: `bash start.sh`. Core runtime does not import the optional numerical stack.

### Optional analytics rebuild

Double-click `REBUILD_ANALYTICS.bat`, or:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-analytics.txt
.\.venv\Scripts\python.exe -m analytics.pipeline
```

This validates records, rebuilds the warehouse/CSV exports, trains and evaluates classifiers, calculates SHAP, and produces forecasts. It is a local CPU workload, not an external AI service. Models are not retrained on each page load. After editing operational data, dashboard SQL aggregates update immediately; model scores/forecasts remain explicitly dated snapshots until rebuilt.

ETL only:

```powershell
.\.venv\Scripts\python.exe -m analytics.etl
```

### Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The API tests create a temporary database copy; they do not intentionally modify your working operational records. Optional browser automation requires a Playwright-supported browser installation. See [docs/TESTING.md](docs/TESTING.md) for actual build validation and its boundaries.

### Docker — supplied, not executed here

```text
docker compose up --build
```

The supplied compose file publishes port 8501 only on loopback and uses named data volumes. Review [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) before using containers or exposing a service. This package is not approved for public internet deployment.

## BI and research

`powerbi/` contains a theme, M import template, DAX measures and relationship instructions. **No native `.pbix` file is included or claimed.** The full dimension/fact CSVs can be imported in Power BI Desktop.

Research framing: how can transportation information systems turn heterogeneous operational records into transparent, useful planning decisions? The package supports studying data quality, analytical capability, predictive performance, explanations and constrained allocation. Synthetic model performance is not evidence of real-world transport effectiveness.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data dictionary and KPI definitions](docs/DATA_DICTIONARY.md)
- [Research and model methodology](docs/METHODOLOGY.md)
- [Security, roles and limitations](docs/SECURITY.md)
- [Scope and implementation status](docs/SCOPE.md)
- [Testing report](docs/TESTING.md)
- [Deployment and backup](docs/DEPLOYMENT.md)
- [Power BI setup](powerbi/README.md)
- [Original user brief](docs/ORIGINAL_BRIEF.md)

## Important limitations

This is an operational analytics prototype, not production-certified transport software. Payments are sandbox states, route positions are visual replay, mail is a private local outbox, and optimized allocations are proposals only. No live dispatch, external payment gateway, SMTP service, identity provider, legal-hours validation or real-time inference endpoint is configured. There are no guaranteed forecasts or maintenance diagnoses. Model artifacts and dashboard records must be reviewed by people before decisions.

Project code is supplied under MIT. Bundled Plotly and Natural Earth attribution is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
