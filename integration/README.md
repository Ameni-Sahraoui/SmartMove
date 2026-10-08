# Optional integration tracks

The default, tested runtime is Python/FastAPI + SQLite + a custom HTML/CSS/JavaScript UI. This is an explicit local-edition choice, made to keep Windows setup similar to the previous projects and to reproduce the image without Streamlit's layout restrictions.

## C# / ASP.NET Core gateway

`SmartMove.Gateway` is actual ASP.NET Core source, not a replacement domain implementation. It proxies the local Python application, including cookies, CSRF headers, static assets and API responses. Backend authorization remains enforced by the Python service. It accepts only a loopback upstream.

Start the main app on port 8501 first. With a .NET 10 SDK:

```powershell
cd integration\SmartMove.Gateway
dotnet run
```

Browse `http://localhost:5080`. Optional configuration is supplied through environment variables `SMARTMOVE_UPSTREAM` and `SMARTMOVE_GATEWAY_URL`. There are no passwords or API keys in this project.

Testing status: the .NET SDK was unavailable in the build environment; this gateway was not compiled or runtime-tested here. It is optional and not needed for the tested application.

## SQL Server schema and seed import

`../sql/schema_sqlserver.sql` defines a SQL Server counterpart of the operational schema. The local API does not switch to SQL Server with an environment toggle. A full SQL Server repository implementation, provider-specific migrations and concurrency tests are a separate deployment phase.

`load_sqlserver.py` imports the non-authentication synthetic source tables into an **empty** database after the schema has been applied. Authentication/session/account records are deliberately not migrated. The importer does not delete existing tables or records.

Install `pyodbc`, a Microsoft ODBC driver compatible with your operating system, and set `SMARTMOVE_SQLSERVER_CONNECTION` outside the repository. Then:

```powershell
python integration\load_sqlserver.py
```

Testing status: SQL Server and its ODBC driver were unavailable here. The DDL/importer were generated and source-reviewed, not executed against SQL Server. Keep using the SQLite edition until that integration is tested.

## Production is a separate engineering phase

Do not expose either service directly to the public internet. Add TLS, central identity/SSO and MFA, verified email delivery, managed secrets, durable jobs, bounded logs, monitoring, database backups, least-privilege service accounts, accessibility review, security testing and operational acceptance tests before deployment. No claim of production readiness or compliance certification is made.
