# Deployment, configuration and backup

## Local execution

Use `START_SMARTMOVE.bat` on Windows, or `python run.py` from the prepared environment. The service binds to `127.0.0.1:8501` by default. Different port: `python run.py --port 8502`. On Linux/macOS `bash start.sh` creates the runtime environment. The supplied scripts are source-reviewed; tests executed in Linux/Python 3.13, not a Windows installer laboratory.

Environment overrides are read from the process environment:

| Variable | Meaning |
|---|---|
| `SMARTMOVE_DATA_DIR` | Operational and warehouse files, generated local credentials, staging and outbox |
| `SMARTMOVE_ARTIFACTS_DIR` | Model, forecast and quality JSON snapshots |
| `SMARTMOVE_EXPORTS_DIR` | Analytical CSVs and quarantine |
| `SMARTMOVE_ENV` | `local` (default) or `production` to require secure cookies/bootstrap configuration |
| `SMARTMOVE_ADMIN_EMAIL`, `SMARTMOVE_ADMIN_PASSWORD` | Required external values for first production-mode account bootstrap |

`.env.example` is a list of available names, **not automatically loaded by the Python app**. Leave unneeded variables unset rather than assigning an empty directory string. For PowerShell, use `$env:SMARTMOVE_DATA_DIR = 'C:\SmartMoveData'` before starting the process. A new data directory triggers synthetic data generation; copy the bundled data instead when preserving the existing snapshot.

## Data regeneration

`python -m smartmove.seed` generates records only when the seed-complete marker is absent. It does not reset working data. To create a separate dataset, point `SMARTMOVE_DATA_DIR` to an empty directory and use `python -m smartmove.bootstrap`; preserve the original directory as backup. The default generator has a fixed as-of date and seed defined in `smartmove/config.py` and `smartmove/seed.py`.

## Backup

Stop the app before making a simple file copy of the data directory, or use SQLite's online backup interface from a separate controlled process. A live WAL database may have recent changes in `-wal` files; copying only the main `.db` while it is running can omit changes. Back up `data`, `artifacts` and `exports` together with version metadata. A used operational database includes authentication records: store it securely. Keep generated credentials/outbox tokens private and exclude them from public backups or repositories.

## Docker

The provided Dockerfile runs a non-root process and copies the local application into a Python 3.12 slim image. The compose configuration exposes the service only through `127.0.0.1:8501` and persists data/artifacts/exports in named volumes. Container startup can create local demo accounts inside its data volume. Inspect its credentials locally, not in a public log or image. This container configuration was not built/run during this delivery.

Optional analytics needs the larger numerical stack; it is intentionally absent from the minimal web image. Use a controlled analytics environment to rebuild snapshots and deploy those artifacts. A production design would separate worker/API services, credentials, storage and resource limits.

## C# and SQL Server

See `integration/README.md`. The reverse gateway is optional .NET 10 source; the operational SQL Server schema/importer is an unexecuted integration path. No environment toggle converts the current SQLite repository into SQL Server. Apply provider-specific migrations and tests before changing the runtime database.

## Public deployment is out of scope

Do not simply bind `--host 0.0.0.0` and expose the local edition. Before real use: implement TLS and trusted-host ingress, production identity and MFA, SMTP delivery, durable jobs, database migrations, access reviews, monitoring, tested backups, privacy assessment and operational safety sign-off. Setting `SMARTMOVE_ENV=production` enables selected safeguards; it is not a production readiness certificate.
