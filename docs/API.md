# API reference

Interactive OpenAPI documentation is available at `/docs`; the machine-readable schema is at `/openapi.json`.

Authentication uses the `sld_session` HTTP-only, SameSite=Strict cookie. Bearer JWTs are also accepted for API clients.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/auth/signup` | Create an account; password must be 12–128 characters |
| POST | `/api/auth/login` | Start a cookie session; rate limited |
| POST | `/api/auth/logout` | Clear the session cookie |
| GET | `/api/auth/google/login` | Begin Google OpenID Connect authorization-code flow |
| GET | `/api/auth/google/callback` | Validate Google identity and create the app session |
| POST | `/api/upload` | Upload a UTF-8 CSV up to the configured byte limit |
| GET | `/api/uploads?limit=50&offset=0` | Paginated upload history |
| GET | `/api/uploads/{id}/status` | Poll analysis status and import diagnostics |
| GET | `/api/subscriptions?upload_id=&limit=50&offset=0` | Paginated detections |
| GET | `/api/subscriptions/savings` | Projected savings for subscriptions marked for cancellation |
| PATCH | `/api/subscriptions/{id}/decision` | Record a planning decision: `keep`, `cancel`, or `undecided`; this does not contact the merchant |

CSV columns are matched case-insensitively. Required fields are a date, description, and either a generic amount or separate debit/credit columns. Credit rows are counted but excluded from subscription analysis; malformed rows are returned in upload diagnostics.
