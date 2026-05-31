# Upgrade notes

## user v0.4.0

### Manual actions

- Nuke and re-run migrations on greenfield deployments only (no production clones yet). Audit templates v2 archive soft-deleted rows into `_audit` and remove them from the main table; RLS is no longer used.
- Deploy authentication **v0.31.1** (or later) alongside user **v0.4.0** so login provisioning sends `tier1_roles` and the first Tier-1 operator receives `operator.platform-admin` automatically.
- Requires **sql-template v0.6.0** (or later) with audit v2 templates baked into the image, or mount `templates/sql/audit` locally during migrate.

## user v0.3.1

### Manual actions

- Superseded by v0.4.0 for fresh installs. Do not apply migration `002` on new databases.

## user v0.3.0

### Manual actions

- If your deployment path does not already automate Alembic, run `python -m alembic upgrade head` or the migrate container for user **v0.3.0**.
- In user service env, set `JWT_CLAIM_NAMESPACE` to the same namespace Authentication issues (`neosofia` by default).
- In user service env, set `ROLE_CATALOG_OVERLAY` if this deployment uses product-specific role overlays.

## user v0.2.1

### Manual actions

- Update `PORT`, compose wiring, and `VITE_USER_API_URL` if you previously pinned **8015**.

## user v0.2.0

### Manual actions

- Set CDP UI `VITE_USER_API_URL`.