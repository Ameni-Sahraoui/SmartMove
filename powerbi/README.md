# Power BI-ready SmartMove model

Power BI Desktop is an optional analytical surface. **No `.pbix` file is supplied.** The tested UI already renders its own charts and tables without Power BI installed.

## Load the data

In Power BI Desktop, use Get Data → Text/CSV for `exports/dim_*.csv` and `exports/fact_*.csv`. Alternatively, create a text parameter `SmartMoveFolder` pointing to the extracted project folder and adapt `ImportFactTrip.pq` in a Blank Query. CSVs use UTF-8 with a BOM.

Set identifiers/counts/cents to whole numbers, ratios/measurements to decimals, dimension date to Date and UTC timestamps to Date/Time/Timezone as appropriate. Fields named `*_cents` are integer Canadian cents; divide by 100 for CAD, not again if the field already ends `_cad`.

## Relationships

Use one-to-many, single-direction dimension-to-fact relationships:

| Dimension | Fact key |
|---|---|
| `dim_date[date_key]` | `fact_trip[date_key]`, `fact_route_daily[date_key]` |
| `dim_time[time_key]` | `fact_trip[time_key]` |
| `dim_route[id]` | `fact_trip[route_id]`, `fact_route_daily[route_id]`, route IDs in forecasts/risk exports |
| `dim_vehicle[id]` | `fact_trip[vehicle_id]`, `fact_maintenance[vehicle_id]`, `fact_incident[vehicle_id]`, `fact_vehicle_risk[vehicle_id]` |
| `dim_driver[id]` | `fact_trip[driver_id]` |
| `dim_customer[id]` | `fact_reservation[customer_id]`, `fact_satisfaction[customer_id]` |
| `fact_trip[id]` (unique) | `fact_reservation[trip_id]`, `fact_satisfaction[trip_id]`, `fact_incident[trip_id]` |
| `fact_reservation[id]` (unique) | `fact_payment[reservation_id]` |

Avoid ambiguous filter paths. For reservation/payment-specific reporting, prefer an explicit trip bridge or independent role-playing date dimensions rather than switching everything to bidirectional relationships. Do not join every fact table to every other fact.

`dim_station` can be role-played as Origin and Destination by duplicating the query. `dim_location` is a small geography lookup without a surrogate location key; use it for geography reference or add a tested surrogate key during a fuller dimensional-model implementation.

## Measures and report

Create measures from `Measures.dax` on `fact_trip`. Suggested report pages: Executive, Fleet & Reliability, Demand, Financial Contribution, Passenger Experience, Maintenance, Data Quality. Use `SmartMove_Dark_Theme.json` under View → Themes → Browse for themes.

Always display: **Synthetic network — as of 2026-08-31 — not official Canadian statistics**. On-time means completed delay ≤15 minutes. Route profitability is direct contribution, not audited net income. Forecast envelopes and maintenance scores retain the methodological caveats from the application.

## Refresh

Run `python -m analytics.etl`, then refresh Power BI. `python -m analytics.pipeline` additionally refreshes the ML/forecast CSVs. Never point Power BI at local credential/outbox files. The warehouse omits passenger names/emails from its customer dimension. CSV snapshots do not support transactional write-back.
