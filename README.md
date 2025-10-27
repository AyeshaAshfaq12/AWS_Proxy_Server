# AWS_Proxy_Server — Single-session reverse proxy for stealthwriter.ai

This repo runs a FastAPI reverse proxy that keeps a single authenticated session to stealthwriter.ai on the server and lets multiple clients share it.

Important:
- Obtain cookies by logging into stealthwriter.ai manually in a browser and copy cookies into SESSION_COOKIE_STRING (or use the admin endpoint to set them at runtime).
- Store API_KEY, ADMIN_API_KEY, and SESSION_COOKIE_STRING in AWS Secrets Manager in production, not in plaintext.

Run locally:
- Fill .env (or export env vars) and run `uvicorn app.main:app --host 0.0.0.0 --port 8080`

Admin API:
- POST /admin/set_cookies with JSON {"cookie_string": "a=1; b=2"} and header x-admin-key to update cookies.

Security:
- Put the app behind TLS and limit access. Do not expose the admin key publicly.
