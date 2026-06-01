# Upgrade notes — User service

## user v0.5.0 (ADR-0014 tenant types and org roles)

Breaking API and schema changes. Deploy with **authentication v0.32.0+** so human tokens include `neosofia:tenant_type` and `neosofia:org_roles`.

### Database

- Run Alembic through revision **002** (`platform_roles` → `org_roles`).
- Deploy **authentication v0.32.0+** and run through **006** (`tenants.type`).

### API

- `platform_roles` is renamed to **`org_roles`** on user rows, audits, and PATCH bodies.
- Registry slugs use **`{tenant_type}.{org_role}`** (e.g. `platform.admin`, `cro.clinical-ops`).
- `GET /api/v1/roles` returns `org_roles`, `tenant_types`, and `assigner_prefixes`.

### Authorization

- Cedar policies use `tenantType`, `orgRoles`, and `isOperator`.
- First Tier-1 operator bootstrap assigns **`platform.admin`**.

### CDP UI

- User admin screens use **`org_roles`** from the user API and role catalog.
