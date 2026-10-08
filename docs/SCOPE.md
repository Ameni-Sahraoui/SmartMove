# Scope and delivery status

This document separates implemented behaviours from integration source and future work. It prevents a polished dashboard from being mistaken for a complete transport operator's production estate.

| Requirement family | Delivered | Boundary |
|---|---|---|
| Reference dashboard | Actual responsive UI, local charts/map/assets and computed KPIs | Similar layout/style, not pixel-identical artwork or the image's invented numbers |
| Six workspaces | Six authenticated roles, adaptive navigation and protected backend APIs | Local accounts; no external SSO/MFA |
| Account lifecycle | Registration, activation, reset, status/role controls, self-name update | Activation/reset delivery is a private local outbox, not SMTP |
| Fleet, routes, trips | Validated CRUD, route stops, scheduling conflicts, driver assignment/status | No GPS/telematics provider, dispatch radio or road-routing service |
| Reservations/tickets/payments | Owned reservations, atomic capacity, digital demo ticket, cancellation and refund state | No real money, cards or travel validity; payment state is not an immutable accounting journal |
| Maintenance | Work orders, parts stock/consumption endpoint, technical telemetry, review queue | No automatic roadworthiness determination or actual fault diagnosis |
| Documents/notifications | Text documents and in-app role/user notifications | No arbitrary binary upload or email/SMS notification provider |
| BI | Separate snapshot warehouse, fact/dimension CSVs, calculated KPIs | No slowly changing dimensions or native Power BI PBIX |
| ML | Three-model classification comparisons, temporal tests/CV, calibration, actual SHAP, forecast baselines, anomaly flags | Synthetic validation only; no continuous online training or live feature-store inference |
| Optimization | Constrained allocation MILP + explicit optional greedy baseline | Simplified one-window problem; no full routing/driver roster/labour-law implementation |
| Security | Hashing, session revocation, backend RBAC/ownership, CSRF, validation, audit, tested negative paths | No certification, penetration test, external tamper-evident logging or full production controls |
| C# | Optional ASP.NET Core reverse gateway source | Not compiled/run here; not a C# rewrite of the domain |
| SQL Server | DDL counterpart and synthetic non-auth import script | Not run here; not the active API persistence provider |
| Deployment | Windows scripts, Linux script, Docker files, configuration and backup documentation | Windows, Docker, .NET and SQL Server not executed in the validation environment |

No placeholders are presented as successful training, compiled integration or measured production performance. Model scores are the result of the included synthetic experiment and must not be generalized to real transport operations.
