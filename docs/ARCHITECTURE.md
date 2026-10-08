# Architecture and contracts

## Explicit architecture decision

The supplied brief names ASP.NET Core, SQL Server and Python. This delivery provides a tested **Python/FastAPI + SQLite local edition**, a custom web frontend, and separately labelled optional C#/SQL Server integration source. It does not quietly represent the Python edition as the requested .NET production stack. No services use real personal, financial or vehicle-tracking data.

## Layers

| Layer | Implementation | Contract |
|---|---|---|
| Presentation | `web/index.html`, `style.css`, `app.js`, local Plotly | Calls `/api/*`; no embedded production secrets; HTML escaping of data; responsive dark reference-inspired design |
| HTTP application | `smartmove/app.py` | Auth/session/CSRF, middleware, account/admin APIs, jobs, local mail simulator, static app |
| Domain resources | `smartmove/resources.py` | Backend permissions, mandatory ownership filters, validation, transactions, conflict checks, audit |
| Decision support | `smartmove/insights.py` | Calculated KPI SQL, model/forecast snapshots, scenario arithmetic, controlled CSV export |
| Persistence | `smartmove/database.py`, `sql/schema_sqlite.sql` | Foreign keys, parameter binding, `BEGIN IMMEDIATE` writes, rollback and change records |
| Development data | `smartmove/seed.py` | Deterministic relational synthetic seed; refuses duplicate reseeding once complete |
| ETL | `analytics/etl.py` | Critical checks, isolated staging quarantine, full separate warehouse and CSV snapshot |
| Models | `analytics/pipeline.py` | Temporal validation, actual metrics, SHAP, anomaly detection, forecast comparisons |
| Allocation | `analytics/optimize.py` | Constrained MILP when SciPy exists; explicit greedy baseline otherwise |

## Operational relationships

Facilities host employees/vehicles and serve as route endpoints and stops. A route has schedules and trips. A trip has one vehicle, one driver, one route, time boundaries and a seat capacity. A customer has reservations; each reservation has a unique ticket and one simulated payment-state record. Maintenance belongs to vehicles and optionally engineers; part-use lines connect work orders to parts inventory. Telemetry belongs to vehicles. Incidents optionally reference trips and reporters. Customer feedback references customers and trips.

Auth users can link to employee or customer records. Sessions and one-time tokens link to users. The audit trail preserves actor identifiers and sanitized change snapshots even when account deletion is allowed. Data quality validates appointment-independent transport relationships: seats, tickets, time ranges, bookings and vehicle/driver conflicts.

## Transaction invariants

A booking's seat check, reservation insert, ticket creation, sandbox payment and trip counters are in one immediate database transaction. Cancel/refund changes likewise update the reservation, ticket, payment state and trip counters together. Duplicate cancellation is rejected. Actual travel tickets and external money movement do not occur.

Trip creation/modification checks route/vehicle/driver validity and overlaps. Booked capacity cannot be reduced below reservations. Customer inputs never determine another customer's ownership. Driver operations never accept arbitrary administrative trip fields.

## Warehouse

`data/warehouse.db` is separate from `data/smartmove.db`. ETL creates a full analytical snapshot and then atomically replaces its database file. CSVs are written to `exports/`. Model JSON files are individually atomically replaced. This is not a multi-file transactional feature store: different artifacts can temporarily have different refresh timestamps while a job runs. Each artifact's metadata is the source of truth.

The dimensional model is a compact full-snapshot model, not a complete slowly-changing-dimension implementation. Customer names and emails are excluded from `dim_customer`; the operational source remains synthetic.

## API conventions

Authenticated GETs require a valid HttpOnly session cookie. Writes additionally require `X-CSRF-Token` and same-origin checks. List endpoints use pagination, an allowlisted resource and validated query parameters. Protected OpenAPI is available at `/api/openapi.json` to roles with model-workspace access.

Main families:

```text
GET  /api/health
GET  /api/auth/csrf
POST /api/auth/login, /api/auth/logout
POST /api/auth/register, /api/auth/activate, /api/auth/recover, /api/auth/reset
GET  /api/auth/me
PATCH /api/profile
GET/POST/PATCH/DELETE /api/resources/{resource}[/{id}]
GET /api/dashboard, /api/network, /api/experience
GET /api/analytics/forecast, /api/analytics/maintenance, /api/analytics/delay
GET /api/analytics/models, /api/analytics/quality
POST /api/simulate, /api/optimize
GET /api/exports/{dataset}
POST /api/staging/fuel
GET /api/jobs
POST /api/jobs/{etl|models}
GET/POST/PATCH/DELETE /api/admin/users[/{id}]
GET/PUT /api/admin/permissions[/{role}]
GET /api/admin/audit
GET /api/notifications
POST /api/notifications/{id}/read
```

Inspect `resources.py` or the authenticated OpenAPI document for the exact reservation-cancellation, ticket and part-consumption endpoints. Appending a path in the browser does not grant a driver administrator permission.

## Deployment boundaries

The default process binds to loopback. The optional .NET gateway is a reverse gateway, not duplicated business logic or independent authentication. SQL Server DDL/import support does not make the SQLite repository automatically SQL Server-compatible. Those are separate integration tasks, documented honestly in `integration/README.md`.
