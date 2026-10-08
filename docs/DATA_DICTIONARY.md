# Data dictionary and KPI definitions

Dataset: synthetic-ca-v1-seed42. As-of: 2026-08-31. UTC timestamp strings use ISO 8601. Prices/costs ending `_cents` are integer Canadian cents; `*_cad` is dollars. Distances are km, durations/delays minutes, fuel liters, engine temperature °C, brake wear %, battery voltage V, and vibration an illustrative scalar. `fault_7d` is a synthetic future outcome, not an input feature.

## KPI contracts

| KPI | Definition |
|---|---|
| Total trips | Trips whose scheduled departure falls in the selected synthetic date window, including cancellations |
| On-time performance | Completed trips with delay ≤15 minutes divided by all completed trips in that window |
| Average delay | Mean delay among completed trips only |
| Occupancy | Passenger count divided by seat capacity of non-cancelled trips; weighted by seats, not an average of route percentages |
| Route profitability | Revenue less recorded direct operating cost; contribution before overhead, not net accounting income |
| Active vehicles | Current fleet records with status Active; not changed by a historical date filter |
| Maintenance risk alerts | Latest model snapshot records with rounded risk score ≥60/100; not a confirmed-fault count |
| Satisfaction | Average available survey score, 1–5, filtered by survey date; response bias not corrected |
| Fleet utilization | Distinct completed/in-progress vehicle-days divided by vehicle count × days; a vehicle-day activity proxy, not occupied seat rate or duty-hour utilization |
| KPI change | Current vs prior equally sized period; percentage-point differences for rates; point differences for satisfaction; relative percent change for counts/currency/delay |

The delay mini-chart always shows the latest 14 synthetic days. Demand forecasts retain their own origin/horizon. Active-vehicle and model-risk cards are current snapshots, labelled rather than given invented prior-period changes.

## Operational schema

### `account_tokens`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `token_hash` | TEXT | PK | — |
| `user_id` | INTEGER | Required | users.id |
| `kind` | TEXT | Required | — |
| `expires_at` | TEXT | Required | — |
| `used` | INTEGER | Required | — |

### `audit_log`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `user_id` | INTEGER | Nullable | — |
| `actor` | TEXT | Required | — |
| `action` | TEXT | Required | — |
| `entity` | TEXT | Required | — |
| `entity_id` | TEXT | Nullable | — |
| `before_json` | TEXT | Nullable | — |
| `after_json` | TEXT | Nullable | — |
| `created_at` | TEXT | Required | — |
| `ip` | TEXT | Nullable | — |
| `user_agent` | TEXT | Nullable | — |

### `complaints`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `customer_id` | INTEGER | Required | customers.id |
| `trip_id` | INTEGER | Nullable | trips.id |
| `category` | TEXT | Required | — |
| `summary` | TEXT | Required | — |
| `status` | TEXT | Required | — |
| `created_at` | TEXT | Required | — |

### `customers`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `name` | TEXT | Required | — |
| `email` | TEXT | Required | — |
| `province` | TEXT | Required | — |
| `loyalty_tier` | TEXT | Required | — |
| `created_at` | TEXT | Required | — |

### `documents`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `title` | TEXT | Required | — |
| `category` | TEXT | Required | — |
| `body` | TEXT | Required | — |
| `updated_at` | TEXT | Required | — |

### `employees`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `code` | TEXT | Required | — |
| `name` | TEXT | Required | — |
| `job` | TEXT | Required | — |
| `facility_id` | INTEGER | Required | facilities.id |
| `active` | INTEGER | Required | — |

### `facilities`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `name` | TEXT | Required | — |
| `city` | TEXT | Required | — |
| `province` | TEXT | Required | — |
| `latitude` | REAL | Required | — |
| `longitude` | REAL | Required | — |
| `kind` | TEXT | Required | — |
| `active` | INTEGER | Required | — |

### `incidents`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `trip_id` | INTEGER | Nullable | trips.id |
| `vehicle_id` | INTEGER | Required | vehicles.id |
| `reported_by` | INTEGER | Nullable | users.id |
| `incident_time` | TEXT | Required | — |
| `location` | TEXT | Required | — |
| `type` | TEXT | Required | — |
| `severity` | TEXT | Required | — |
| `status` | TEXT | Required | — |
| `description` | TEXT | Required | — |

### `jobs`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `kind` | TEXT | Required | — |
| `status` | TEXT | Required | — |
| `message` | TEXT | Nullable | — |
| `started_at` | TEXT | Required | — |
| `finished_at` | TEXT | Nullable | — |

### `maintenance`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `vehicle_id` | INTEGER | Required | vehicles.id |
| `engineer_id` | INTEGER | Nullable | employees.id |
| `opened_at` | TEXT | Required | — |
| `completed_at` | TEXT | Nullable | — |
| `category` | TEXT | Required | — |
| `status` | TEXT | Required | — |
| `cost_cents` | INTEGER | Required | — |
| `summary` | TEXT | Required | — |

### `meta`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `key` | TEXT | PK | — |
| `value` | TEXT | Required | — |

### `notification_reads`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `notification_id` | INTEGER | PK | notifications.id |
| `user_id` | INTEGER | PK | users.id |

### `notifications`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `user_id` | INTEGER | Nullable | users.id |
| `role` | TEXT | Nullable | — |
| `title` | TEXT | Required | — |
| `body` | TEXT | Required | — |
| `created_at` | TEXT | Required | — |

### `parts`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `name` | TEXT | Required | — |
| `quantity` | INTEGER | Required | — |
| `unit_cost_cents` | INTEGER | Required | — |

### `payments`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `reservation_id` | INTEGER | Required | reservations.id |
| `amount_cents` | INTEGER | Required | — |
| `status` | TEXT | Required | — |
| `created_at` | TEXT | Required | — |

### `permissions`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `role` | TEXT | PK | — |
| `module` | TEXT | PK | — |
| `action` | TEXT | PK | — |

### `reservations`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `customer_id` | INTEGER | Required | customers.id |
| `trip_id` | INTEGER | Required | trips.id |
| `seats` | INTEGER | Required | — |
| `price_cents` | INTEGER | Required | — |
| `status` | TEXT | Required | — |
| `created_at` | TEXT | Required | — |

### `route_stops`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `route_id` | INTEGER | PK | routes.id |
| `facility_id` | INTEGER | Required | facilities.id |
| `stop_order` | INTEGER | PK | — |

### `routes`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `name` | TEXT | Required | — |
| `origin_id` | INTEGER | Required | facilities.id |
| `destination_id` | INTEGER | Required | facilities.id |
| `distance_km` | REAL | Required | — |
| `duration_min` | INTEGER | Required | — |
| `fare_cents` | INTEGER | Required | — |
| `status` | TEXT | Required | — |

### `satisfaction`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `customer_id` | INTEGER | Required | customers.id |
| `trip_id` | INTEGER | Required | trips.id |
| `score` | INTEGER | Required | — |
| `survey_date` | TEXT | Required | — |

### `schedules`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `route_id` | INTEGER | Required | routes.id |
| `departure_hour` | INTEGER | Required | — |
| `days` | TEXT | Required | — |

### `sessions`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `token_hash` | TEXT | PK | — |
| `user_id` | INTEGER | Required | users.id |
| `csrf_hash` | TEXT | Required | — |
| `auth_version` | INTEGER | Required | — |
| `created_at` | TEXT | Required | — |
| `expires_at` | TEXT | Required | — |
| `ip` | TEXT | Nullable | — |
| `user_agent` | TEXT | Nullable | — |

### `telemetry`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `vehicle_id` | INTEGER | Required | vehicles.id |
| `captured_at` | TEXT | Required | — |
| `engine_temp` | REAL | Nullable | — |
| `brake_wear` | REAL | Nullable | — |
| `battery_voltage` | REAL | Nullable | — |
| `km_since_service` | REAL | Nullable | — |
| `vibration` | REAL | Nullable | — |
| `fault_7d` | INTEGER | Nullable | — |

### `tickets`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `reservation_id` | INTEGER | Required | reservations.id |
| `reference` | TEXT | Required | — |
| `status` | TEXT | Required | — |

### `trips`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `code` | TEXT | Required | — |
| `route_id` | INTEGER | Required | routes.id |
| `vehicle_id` | INTEGER | Required | vehicles.id |
| `driver_id` | INTEGER | Required | employees.id |
| `departure_utc` | TEXT | Required | — |
| `expected_arrival_utc` | TEXT | Required | — |
| `actual_arrival_utc` | TEXT | Nullable | — |
| `status` | TEXT | Required | — |
| `passenger_count` | INTEGER | Required | — |
| `capacity` | INTEGER | Required | — |
| `delay_min` | REAL | Required | — |
| `revenue_cents` | INTEGER | Required | — |
| `operating_cost_cents` | INTEGER | Required | — |
| `fuel_liters` | REAL | Nullable | — |
| `weather_index` | REAL | Required | — |
| `congestion_index` | REAL | Required | — |
| `peak_hour` | INTEGER | Required | — |

### `users`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `email` | TEXT | Required | — |
| `name` | TEXT | Required | — |
| `role` | TEXT | Required | — |
| `password_hash` | TEXT | Required | — |
| `status` | TEXT | Required | — |
| `employee_id` | INTEGER | Nullable | employees.id |
| `customer_id` | INTEGER | Nullable | customers.id |
| `auth_version` | INTEGER | Required | — |
| `failed_attempts` | INTEGER | Required | — |
| `locked_until` | TEXT | Nullable | — |
| `created_at` | TEXT | Required | — |

### `vehicles`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `id` | INTEGER | PK | — |
| `code` | TEXT | Required | — |
| `type` | TEXT | Required | — |
| `capacity` | INTEGER | Required | — |
| `facility_id` | INTEGER | Required | facilities.id |
| `status` | TEXT | Required | — |
| `odometer_km` | REAL | Required | — |
| `energy` | TEXT | Required | — |
| `last_service` | TEXT | Required | — |

### `work_order_parts`

| Column | SQL type | Key / nullability | Reference |
|---|---|---|---|
| `maintenance_id` | INTEGER | PK | maintenance.id |
| `part_id` | INTEGER | PK | parts.id |
| `quantity` | INTEGER | Required | — |

## Warehouse grain

`fact_trip`: one operational trip. `fact_reservation`: one reservation (possibly multiple seats). `fact_payment`: one sandbox payment-state record per reservation. `fact_maintenance`: one work order. `fact_incident`: one recorded incident. `fact_satisfaction`: one survey. `fact_route_daily`: one route/departure-date aggregate. `fact_vehicle_risk`: one scored vehicle snapshot. `fact_delay_risk`: one scored future/in-progress trip snapshot. `fact_demand_forecast`: one route/future-date prediction.

The exported route-day seat-capacity sum includes all trip records; for dashboard-equivalent occupancy use `fact_trip` with its non-cancelled denominator. All tables are full snapshots. Authentication, session, token and audit tables are not warehouse dimensions.
