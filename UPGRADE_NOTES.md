# Upgrade notes

## user v0.3.0

### Manual actions

- If your deployment path does not already automate Alembic, run `python -m alembic upgrade head` or the migrate container for user **v0.3.0**.
- In user service env, set `JWT_CLAIM_NAMESPACE` to the same namespace Authentication issues (`neosofia` by default).
- In user service env, set `ROLE_CATALOG_OVERLAY` if this deployment uses product-specific role overlays.
- After the first operator logs in once and is provisioned, grant `operator.platform-admin` directly in the user database before using Admin → Users.

## user v0.2.1

### Manual actions

- Update `PORT`, compose wiring, and `VITE_USER_API_URL` if you previously pinned **8015**.

## user v0.2.0

### Manual actions

- Set CDP UI `VITE_USER_API_URL`.