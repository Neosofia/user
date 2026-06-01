# Upgrade notes — User service

## user v0.4.0 (ADR-0014 tenant types and roles)

Deploy with **authentication v0.31.2+** so human tokens can include `neosofia:actors`, `neosofia:tenant_type`, and `neosofia:roles` (short Tier-2 names from the auth mirror).

### Database

- Greenfield: Alembic revision **001** creates `users.roles` (Tier-2 slugs `{tenant_type}.{role}`).
- Upgrades from older `platform_roles` columns require a one-off migration in your environment before deploy (no revision `002` in this repo line).

### API

- Registry and PATCH bodies use **`roles`** (array of full slugs, e.g. `platform.admin`, `cro.clinical-ops`).
- `GET /api/v1/roles` returns `roles`, `tenant_types`, `assigner_actors`, and `assigner_actor_prefixes`.

### Authorization

- Cedar policies use `tenantType`, `roles` (short names on the principal), and `isOperator`.
- First Tier-1 `operator` on provision bootstrap assigns **`platform.admin`**.

### CDP UI

- User admin screens use **`roles`** from the user API and role catalog.
