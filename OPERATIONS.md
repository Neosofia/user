# Operations

## Local development

1. Sync dependencies:

   ```bash
   uv sync
   ```

2. Configure environment (copy `.env.example` to `.env`). Required:

   | Variable | Purpose |
   |----------|---------|
   | `MIGRATION_DATABASE_URL` | Superuser URL for Alembic |
   | `APP_DATABASE_URL` | Restricted `app` role at runtime |
   | `JWT_AUDIENCE` | Expected JWT audience (include authentication service) |
   | `JWT_JWKS_URI` or `JWT_PUBLIC_KEY` | Verify platform JWTs |
   | `JWT_CLAIM_NAMESPACE` | Custom claim prefix (default `neosofia`; must match Authentication) |
   | `ROLE_CATALOG_OVERLAY` | Optional JSON file merged into the default role catalog |

   Local example (Postgres on host port `5015` when using compose):

   ```dotenv
   MIGRATION_DATABASE_URL=postgresql+psycopg://user_template:change-me@localhost:5015/cdp_user
   APP_DATABASE_URL=postgresql+psycopg://app:change-me@localhost:5015/cdp_user
   JWT_JWKS_URI=http://localhost:8014/.well-known/jwks.json
   JWT_AUDIENCE=authentication,user
   JWT_CLAIM_NAMESPACE=neosofia
   ```

3. Apply migrations (audit SQL from `templates/sql/audit` in the monorepo, or baked into the migrate image):

   ```bash
   uv run alembic upgrade head
   ```

4. Run tests:

   ```bash
   uv run --dev -m pytest -q
   RUN_DOCKER_TESTS=1 uv run --dev -m pytest tests/integration -q
   ```

5. Start the service:

   ```bash
   uv run --dev -m gunicorn -c src/gunicorn.py src.app:app
   ```

6. Check health:

   ```bash
   curl http://localhost:8018/health
   ```

Protected routes need a platform JWT from the authentication service (`operator` Tier-1 role plus `operator.platform-admin` for list/admin updates; Cedar governs per-user read/update). There is no public user create API. See `openapi.json` for paths.

Authentication provisions registry rows with `PUT /api/v1/users/{uuid}` using a service token with `aud=user`. The route is idempotent: first login creates the row with empty `platform_roles`; later logins refresh identity fields and leave `platform_roles` unchanged.

### Bootstrapping the first operator

Because provisioning always creates rows with empty `platform_roles`, the very first operator cannot grant themselves `operator.platform-admin` through the API (Cedar denies list/admin-update without it). After that operator has logged in once (creating their row), an administrator with database access must seed the role directly, e.g.:

```sql
UPDATE users SET platform_roles = ARRAY['operator.platform-admin'] WHERE email = '<first-operator-email>';
```

Subsequent operators can then be granted roles through **Admin → Users** in the UI.

## Full stack (compose)

Run with authentication and the rest of the platform from the compose project that includes this service:

- Copy `.user.env.sample` → `.user.env` and `.user-postgres.env.sample` → `.user-postgres.env` (alongside other service env files).
- Ensure authentication `JWT_WEB_AUDIENCE` includes `user`.
- Mount product role overlays and set `ROLE_CATALOG_OVERLAY` when domain-specific roles are needed.
- Build and start: `docker compose -f docker-compose.local.yml up -d --build` (paths vary by workspace layout).

Service listens on **8018** (CDP spec 018 → port 8000 + 18). UI admin **Users** screen calls this API; tenant names come from authentication `GET /api/v1/tenants/{uuid}`.

## Docker build and run

From this repository:

```bash
docker build --target runtime -t user:local .
docker run -d --rm -p 8018:8018 -e ENV=development --env-file .env --name user-dev user:local
```

Run migrations via a one-off migrate container or `uv run alembic upgrade head` against the same database URLs.

## Public cloud deployment

Shared JWT, JWKS, CORS, healthcheck, and PaaS networking guidance live in the infrastructure **public-cloud** operations guide in your deployment repo.

**Service-specific notes:**

- **Audience:** `JWT_AUDIENCE` must include `user`; authentication must list `user` in `JWT_WEB_AUDIENCE`.
- **JWKS:** Point `JWT_JWKS_URI` at the authentication service (private mesh URL in cloud, not localhost).
- **CORS:** Set `FRONTEND_URL` to the UI origin.
- **Health:** Exempt `/health` from forced HTTPS redirect behind TLS-terminating proxies (`ENV=development` locally disables strict HTTPS for Talisman).
