# Product Installation Plan

Per-version instructions for system administrators: prerequisites, deploy and configuration steps, post-deploy verification, and evidence to capture. For what changed in each release, see [CHANGELOG.md](CHANGELOG.md) when present, or the GitHub release for that tag.

## user v0.6.9

**Build identifiers:** Tag `user/v0.6.9`; **cdp-user-policies v0.2.1** unchanged.

**Deploy:**

1. Rebuild and deploy **user v0.6.9** (no config changes from v0.6.8).

**Post-deploy verification:**

1. `GET /health` reports **0.6.9**.
2. As a multi-role operator (registry row includes `platform.admin` plus site/patient roles), select **Platform Admin** and confirm **Admin → Registered users** / `GET /api/v1/users` returns **200** (not 403).

**Evidence:**

- Operator dashboard **Registered users** count loads; **Admin → Users** list opens.

## user v0.6.8

**Build identifiers:** Tag `user/v0.6.8`; **cdp-user-policies v0.2.1** (CDP stacks).

**Prerequisites:**

- Publish **cdp-user-policies v0.2.1** (bundles `cdp-overlay.json` for role catalog defaults).
- Authentication **service registry** entry for `user` uses an **HTTPS** `base_url` (not plain HTTP internal mesh URLs).

**Pre-deploy:**

- Pin `CDP_USER_POLICIES_IMAGE=ghcr.io/neosofia/cdp-user-policies:v0.2.1` at user image build (default in Dockerfile for this tag).
- CDP deployments: set `ROLE_CATALOG_OVERLAY=/app/policies/cdp-overlay.json` on the user service (file is copied from the policy bundle at build time).

**Deploy:**

1. Rebuild and deploy **user v0.6.8**.
2. Confirm Authentication `services.base_url` for slug `user` is HTTPS.

**Post-deploy verification:**

1. `GET /health` reports **0.6.8**.
2. Log in as a multi-actor demo user; provision assigns default tier-2 roles (`site.clinical`, `patient.self`, etc.) and the session picker lists them.

**Evidence:**

- Auth log line `user_provisioning_succeeded` (not `status_code=302`) on login.
- `GET /api/v1/users/{self}` returns non-empty `roles` after first login.

## user v0.4.0 (ADR-0014 tenant types and roles)

**Build identifiers:** Tag `user/v0.4.0` (or current line on this branch); **authentication v0.31.2+** for human token claims used by Cedar and the CDP UI.

**Prerequisites:**

- Authentication v0.31.2+ deployed so human tokens can include `neosofia:actors`, `neosofia:tenant_type`, and `neosofia:roles` (short Tier-2 names from the auth mirror).
- CDP UI build that consumes **`roles`** from the user API and role catalog (see [CDP INSTALLATION_PLAN](https://github.com/Neosofia/cdp/blob/main/INSTALLATION_PLAN.md)).

**Pre-deploy:**

- **Greenfield:** Alembic revision **001** creates `users.roles` (Tier-2 slugs `{tenant_type}.{role}`).
- **Upgrade from `platform_roles`:** run a one-off data migration in your environment before deploy (no revision `002` in this repo line).
- Pin **cdp-user-policies** (or equivalent) at image build for Cedar using `tenantType`, `roles` (short names on the principal), and `isOperator`.

**Deploy:**

1. Apply database migration (greenfield `001` or your one-off upgrade path).
2. Deploy user service image for v0.4.0.
3. Deploy or rebuild CDP UI if operator admin flows are in scope.

**Post-deploy verification:**

1. `GET /health` succeeds.
2. `GET /api/v1/roles` returns `roles`, `tenant_types`, `assigner_actors`, and `assigner_actor_prefixes`.
3. Registry and PATCH bodies accept **`roles`** (full slugs, e.g. `platform.admin`, `cro.clinical-ops`).
4. First Tier-1 `operator` provisioned on login receives **`platform.admin`**.
5. CDP **Admin → Users** lists users and saves role edits (with authentication and UI versions from prerequisites).

**Evidence:**

- Migrate job or `alembic upgrade` success log.
- API response capture for `GET /api/v1/roles` (structure check, no PHI in shared artifacts).
- Operator test: PATCH user roles → GET confirms update; CDP save succeeds.
