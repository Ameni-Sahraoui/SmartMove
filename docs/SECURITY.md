# Security model and responsible use

## Implemented controls

Passwords use Argon2id; authentication tokens are random opaque values stored as SHA-256 hashes. Session cookies are HttpOnly and SameSite=Strict, with an eight-hour absolute expiration. In production-mode configuration the cookies additionally require HTTPS. User status and an authorization version are checked on each request. Account changes/reset revoke sessions.

Write requests use a session-bound CSRF token plus a same-origin check when the browser sends Origin. The UI retrieves the token through `/api/auth/csrf` and sends `X-CSRF-Token`. Login, account-token and registration endpoints are rate-limited; repeated account failures trigger a temporary lock. Public login failures do not reveal whether a password was correct for an inactive account.

Backend module/action checks protect reads and writes. Driver and customer resource queries include ownership constraints. Export permission does not bypass those constraints. SQL parameters carry values; only allowlisted internal schema/resource identifiers form query identifiers. Validation rejects unknown fields and impossible states. Dynamic text is escaped in the frontend. Security response headers restrict scripts to local assets, forbid object embedding and external framing, and mark API responses no-store.

Booking, cancellation, part consumption and operational writes are transactional. Audit records preserve actor/action/entity/time and sanitized before/after values where appropriate. Account secrets, session cookies, password hashes and recovery tokens are not logged in change snapshots. API deletion of audit records is not exposed.

## Local credential lifecycle

No passwords or live auth sessions are distributed with the ZIP. `bootstrap()` creates fresh random local passwords when an empty account table is found and writes a private local credentials file. Authentication tables remain separate from analytical exports. Treat an in-use `smartmove.db` as sensitive even though its transport data is synthetic.

Recovery/activation uses hashed, expiring, single-use tokens. The **local outbox is deliberately a development mail simulator**. Anyone who can read that directory can use a recovery token; this is not a production transport. Production-mode token delivery refuses to operate until an actual delivery implementation is added. Do not expose the local edition and assume email verification has been deployed.

## Permissions

Roles: Admin, Manager, Driver, Engineer, Analyst, Customer. Actions: view, create, modify, delete, approve, export, administer. Not every action has a separate operational endpoint; grants represent the authorization vocabulary. Administer is required for account/grant changes. Drivers can view/change only assigned trips within allowed transitions and report incidents within their work. Customers book and cancel only their own reservations and view only their owned ticket/payment history. Engineers cannot read the reservation/payment administrative workspace by default.

## What these controls do not establish

This is not a security certification or assurance of production readiness. There has been no external penetration test, source-code security audit, privacy-law assessment or regulatory certification. Important missing production capabilities include SSO/MFA, distributed rate limits, durable workers, log retention controls, encryption-at-rest management, tamper-evident external audit storage, centralized secret management, SMTP verification, disaster recovery exercises, per-depot permissions and access-review processes.

The application uses one local process for background rebuild coordination. Job records survive, but job execution is not a durable task queue; startup marks interrupted jobs. Do not deploy multiple independent workers against this simplistic coordination mechanism and assume distributed consistency.

The example size guard uses the declared HTTP Content-Length; a production ingress must enforce real request/stream limits, connection timeouts and upload controls. CSP permits inline styles for chart/layout compatibility. Protecting public deployments requires a maintained reverse proxy, TLS, secure host validation, rate-limit infrastructure and browser-based security validation beyond the offline rendering test performed here.

## Responsible analytics

All operational data is synthetic. Risk scores and forecasts are uncertain decision support. Never use the model to determine roadworthiness, deny essential services, automatically discipline drivers or identify a medical/mechanical cause. SHAP is predictive attribution, not causation. Review accessible transportation, contractual commitments and underserved areas before acting on low-utilization suggestions. No dashboard score authorizes a vehicle for real use.

## References

- Microsoft ASP.NET Core antiforgery guidance for the optional integration track: https://learn.microsoft.com/en-us/aspnet/core/security/anti-request-forgery?view=aspnetcore-10.0
- Microsoft cookie authentication guidance: https://learn.microsoft.com/en-us/aspnet/core/security/authentication/cookie?view=aspnetcore-10.0

These references are engineering context. The tested local authentication implementation is Python, not ASP.NET Identity.
