# Release notes

## user v0.2.0

Requires **authentication v0.30.0** and CDP UI **v0.2.0**.

### Update

- Deploy user **v0.2.0** (Postgres + migrations — standard service deploy).
- Authentication `JWT_WEB_AUDIENCE` must include `user`.
- CDP UI build: `VITE_USER_API_URL`.

### Test

1. `GET /health` → 200.
2. As **`operator`**, `GET /api/v1/users` with platform JWT → 200.
3. CDP **Admin → Users** — list/edit/audit (seed a row first if DB is empty).

### Tag

`user/v0.2.0`
