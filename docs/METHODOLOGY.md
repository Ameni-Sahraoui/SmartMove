# Research methodology and analytics

## Research question

How can heterogeneous transportation operational data be transformed into transparent predictive and descriptive intelligence that supports capacity, reliability, service-quality and maintenance planning?

The platform joins transactional information systems, data engineering, BI, explainable machine learning and constrained operations research. Its synthetic experiments support software and methodology demonstration; they cannot establish effects on real safety, passenger outcomes or organizational productivity.

## Data-generating process

The seed fixes random seed 42 and as-of date 2026-08-31. It creates 548 historical days plus eight days of scheduled service. Passenger counts depend on route, weekday, season and random variation. Delays depend on synthetic weather, congestion, route characteristics and random effects. Fault labels are probabilistic functions of synthetic telemetry. This creates learnable but noisy relationships by construction; predictive accuracy is not independent evidence of real-world validity.

Geographical coordinates describe real cities; facilities, service links, passenger aliases, bookings, employees, telemetry and financial records are fictional. There is no real traffic, weather, geolocation or clinical data feed. The network map draws schematic links, not road-navigation itineraries.

## Classifiers

Maintenance target: `fault_7d`, a synthetic technical fault within seven days. Data is only eligible when its target window has matured relative to the as-of date. Features: engine temperature, brake wear, battery voltage, kilometres since service and vibration.

Delay target: a completed trip's delay exceeds **15 minutes**. Features available in the demonstration before departure include synthetic weather/congestion assumptions, route/distance/duration and calendar/peak indicators. Actual arrival or observed delay is not included in the prediction features.

Both experiments compare Logistic Regression, Random Forest and XGBoost. Median imputation is fit only on training data; Logistic Regression also scales training features. Data is ordered chronologically. The pipeline uses a 60% training / 20% validation / 20% test design; maintenance uses a seven-day purge between label windows. Selection uses validation PR-AUC, and the operating threshold uses validation F1. The held-out test is not used to choose the classifier or threshold. Three expanding-time training/validation folds are additionally evaluated for the selected model.

Reported metrics include ROC-AUC, PR-AUC, precision, recall, F1, a confusion matrix, Brier score and calibration bins. Results are actual pipeline output, not manually inserted numbers. Class imbalance and test sample size remain visible. The final selected model is refit to available matured records for current snapshot scoring; the test metrics remain labelled as pre-refit holdout evaluation, not performance on that final fitted snapshot.

## SHAP and anomaly detection

The maintenance explanation pipeline computes actual SHAP contributions for the selected model. Logistic Regression uses a linear explanation; tree models use tree explanations. The artifact identifies the output units. Log-odds contributions must not be mistaken for probability percentages. A reconstruction check compares base value plus feature contributions with the model output and records the largest residual.

Global mean absolute SHAP values show the model's overall attribution pattern for the scored fleet. Individual signed contributions support the review drawer. These are model explanations, not causal mechanisms, mechanical diagnoses, proof of a defect or identification of a responsible employee.

Isolation Forest adds separate anomaly flags. An unusual observation is not a confirmed fault. Recommendations point to technical records and human engineering review rather than issuing repair/safety instructions automatically.

## Demand forecasting

Each directional route compares a calendar-feature Ridge model with a trailing eight-week weekday baseline. A 28-day validation block selects the model and supplies empirical absolute residuals for an illustrative 80% band. A separate final 28-day holdout reports MAE, RMSE and realized band coverage. Daily forecasts extend 180 days; the UI aggregates them weekly or monthly and filters routes.

A residual band calibrated for short holdout behaviour is not a guarantee of long-horizon coverage. Aggregating lower/upper daily values is a visual planning envelope, **not a statistically calibrated joint interval**. The UI states this limitation. There is no universal claim that a chosen confidence level holds across routes and horizons.

The future forecasts predict observed passenger volume learned from the generated history. They do not estimate latent unconstrained demand, suppressed bookings, competitor services or demand caused by new timetables. Capacity changes may change demand in reality; that response is not identified here.

## Route performance

A Random Forest regression experiment estimates synthetic contribution/revenue behaviour using time-ordered data and reports held-out MAE alongside a simple baseline. Route contribution is passenger revenue less recorded direct trip operating cost; it excludes overhead, tax, financing, depreciation and other costs. It is not audited net profit.

## What-if simulation

The simulator deliberately uses explicit arithmetic rather than claiming causal ML:

```text
scenario_capacity = baseline_seat_capacity * (1 + capacity_change / 100)
scenario_occupancy = baseline_passengers / scenario_capacity * 100
scenario_delay = baseline_delay
               * (1 - min(capacity_change, staffing_change) / 300)
               * (1 - scheduling_change / 500)
```

The fixed-demand assumption can produce occupancy above 100%, signalling unmet capacity rather than a feasible operating plan. The staffing and scheduling coefficients are illustrative choices, not fitted causal effects. A zero-change input reproduces the baseline, which is tested. No records are changed by simulation.

## Allocation optimization

A binary vehicle/route assignment minimizes illustrative operating cost plus a 1000-unit penalty for each unserved passenger. Constraints: a vehicle is used at most once, total assignments do not exceed available drivers, a selected route duration is at most 480 minutes, and unmet demand is explicit. The solver is SciPy MILP/HiGHS when the optional numerical environment is installed; otherwise an explicitly labelled greedy feasible baseline is used.

This is a one-window fleet-capacity illustration, not a full vehicle-routing or crew-rostering solver. Depot compatibility, repositioning, accessibility requirements, driver certifications, labour agreements, rest rules, multi-trip sequencing and safety constraints must be added before real use. The UI must not equate a 480-minute bound with legal compliance. A time-limited feasible MILP result is not automatically certified optimal.

## Reproducibility

Run `python -m analytics.pipeline` in an environment with `requirements-analytics.txt`. Artifacts include dataset/model versions, actual run time, temporal cutoffs and selected models. Synthetic data can be regenerated by running `python -m smartmove.seed` against a **new empty data directory**. Preserve the supplied original dataset rather than deleting a working database.

Potential research extensions: hold out entire vehicles/routes to test transfer, add explicit drift monitoring, evaluate fairness across service areas without inferring protected traits, compare business-cost thresholds, run sensitivity studies, and conduct administrator usability studies. These are proposed extensions, not completed validation results.

## Method references

These references explain the tools/methods; they do not validate the synthetic network:
- scikit-learn time-series cross-validation: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- scikit-learn cross-validation guidance: https://scikit-learn.org/stable/modules/cross_validation.html
- SHAP project documentation: https://shap.readthedocs.io/
- SciPy `milp`: https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html
