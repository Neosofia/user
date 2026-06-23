# Product Installation Plan

Per-version instructions for system administrators: prerequisites, deploy and configuration steps, post-deploy verification, and evidence to capture. For what changed in each release, see [CHANGELOG.md](CHANGELOG.md) when present, or the GitHub release for that tag.

## Greenfield Step 0 — assign platform registry roles

Run once per new environment before platform admin flows work. Authentication `PUT /api/v1/users/{uuid}` provision creates the registry row with **`roles: []`** and never assigns tier-2 roles on login. Tier-1 **`operator`** in WorkOS does not grant **`platform.admin`**.

**Prerequisites:** stack deployed; admin has logged in once (registry row exists); note `user_uuid`.

**Assign roles** (example — first platform admin):

```sql
UPDATE users
SET roles = ARRAY['platform.admin']::text[]
WHERE uuid = '<admin-user-uuid>';
```

Use the user service migration/superuser URL. Then the admin **logs out and back in** (refreshes the authentication JWT roles mirror). Verify `GET /api/v1/users/{uuid}` and `neosofia:roles` in the platform JWT.

CDP stacks: see [CDP INSTALLATION_PLAN — Step 0](https://github.com/Neosofia/cdp/blob/main/INSTALLATION_PLAN.md#greenfield-step-0--assign-platform-registry-roles) for the full checklist and evidence list.

---

## user v0.8.5

**Build identifiers:** **user v0.8.5**; **cdp-policies v0.3.1**; SDK **`authorization-in-the-middle/v0.7.6`**.

**Deploy:**

1. Confirm **`cdp-policies/v0.3.1`** is published (`ghcr.io/neosofia/cdp-policies:v0.3.1`).
2. Pull `ghcr.io/neosofia/user:v0.8.5` (tag `user/v0.8.5`).

**Post-deploy verification:**

1. `GET /health` reports **0.8.5**.
2. Care-episode service token can `GET /api/v1/tenants/{tenant_uuid}/users` and `GET /api/v1/users/{user_uuid}` (**200**, not **403**).

**Evidence:** Health JSON version field; care-episode roster/profile enrichment loads registry display names.

---

## user v0.8.4

**Build identifiers:** **user v0.8.4**; SDK **`authorization-in-the-middle/v0.7.6`**.

**Deploy:**

1. Pull `ghcr.io/neosofia/user:v0.8.4` (tag `user/v0.8.4`).

**Post-deploy verification:**

1. `GET /health` reports **0.8.4**.
2. `PATCH /api/v1/users/{uuid}` with a display code already used in the tenant returns **409**.

**Evidence:** Health JSON version field; conflict response on duplicate display code.

---

## user v0.8.3

**Build identifiers:** **user v0.8.3**; SDK **`authorization-in-the-middle/v0.7.6`**.

**Deploy:**

1. Pull `ghcr.io/neosofia/user:v0.8.3` (tag `user/v0.8.3`).

**Post-deploy verification:**

1. `GET /health` reports **0.8.3**.
2. `PATCH /api/v1/users/{uuid}` with a display code already used in the tenant returns **409**.

**Evidence:** Health JSON version field; conflict response on duplicate display code.

---

## user v0.8.2

**Build:** **user v0.8.2** (default tenant user list page size **15**).

**Deploy:**

1. Pull `ghcr.io/neosofia/user:v0.8.2` (tag `user/v0.8.2`).

**Post-deploy verification:**

1. `GET /health` reports **0.8.2**.
2. `GET /api/v1/tenants/{tenant}/users` without `page_size` returns at most 15 items.

**Evidence:** Health JSON version field.

---

## user v0.8.1

**Build identifiers:** Tag `user/v0.8.1`; SDK **`authorization-in-the-middle/v0.7.1`**; **cdp-policies v0.2.0**.

**Deploy:**

1. Publish **cdp-policies v0.2.0** (adds `policies/user/cedar/`).
2. Rebuild user with `USER_PRODUCT_POLICIES_IMAGE=ghcr.io/neosofia/cdp-policies:v0.2.0` (Dockerfile default).
3. Deploy **user v0.8.1** (no new runtime env vars).

**Post-deploy verification:**

1. `GET /health` reports **0.8.1**.
2. Platform admin list/patch, site clinician roster, and sponsor clinical-ops list still authorize as before.
3. `GET /api/v1/roles` unchanged.

**Evidence:**

- Health version **0.8.1**; authorized list/patch responses for platform, site, and sponsor principals.

---

## user v0.8.0

**Build identifiers:** Tag `user/v0.8.0`; SDK **`authorization-in-the-middle/v0.7.1`**; **cdp-policies v0.1.0**.

**Deploy:**

1. Publish **cdp-policies v0.1.0** and rebuild user with `CDP_POLICIES_IMAGE=ghcr.io/neosofia/cdp-policies:v0.1.0`.
2. Deploy **user v0.8.0** (no new env vars).

**Post-deploy verification:**

1. `GET /health` reports **0.8.0**.
2. `GET /api/v1/roles` returns `tenant_types` with full role slugs per org kind.
3. `GET /api/v1/users` and authorized `PATCH /api/v1/users/{uuid}` succeed for platform and enterprise admins.

**Evidence:**

- Health version **0.8.0**; sample `GET /api/v1/roles` JSON; authorized list/patch responses.

---

## user v0.7.0

**Build identifiers:** Tag `user/v0.7.0`; SDK **`authorization-in-the-middle/v0.4.23`**; **cdp-user-policies v0.2.1** unchanged.

**Deploy:**

1. Rebuild and deploy **user v0.7.0** (no config changes).

**Post-deploy verification:**

1. `GET /health` reports **0.7.0**.
2. `GET /api/v1/users` and `GET /api/v1/users/{uuid}` succeed for authorized operator JWTs.
3. `PUT /api/v1/users/{uuid}` provisioning from authentication still returns **200** or **201**.

**Evidence:**

- Health version **0.7.0**; sample authorized list/read/provision responses.

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

- Publish **cdp-user-policies v0.2.1** (bundles `cdp-overlay.json` for role catalog validation and UI labels).
- Authentication **service registry** entry for `user` uses an **HTTPS** `base_url` (not plain HTTP internal mesh URLs).

**Pre-deploy:**

- Pin `CDP_USER_POLICIES_IMAGE=ghcr.io/neosofia/cdp-user-policies:v0.2.1` at user image build (default in Dockerfile for this tag).
- CDP deployments: set `ROLE_CATALOG_OVERLAY=/app/policies/cdp-overlay.json` on the user service (file is copied from the policy bundle at build time).

**Deploy:**

1. Rebuild and deploy **user v0.6.8**.
2. Confirm Authentication `services.base_url` for slug `user` is HTTPS.

**Post-deploy verification:**

1. `GET /health` reports **0.6.8**.
2. Log in as a multi-actor demo user; provision creates the registry row with **`roles: []`**; demo seeds or admin UI assign tier-2 roles before the session picker lists them.

**Evidence:**

- Auth log line `user_provisioning_succeeded` (not `status_code=302`) on login.
- `GET /api/v1/users/{self}` returns the provisioned row (`roles` may be `[]` until seeds or admin assign them).

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
2. `GET /api/v1/roles` returns `roles`, `tenant_types`, `role_definitions`, and `actor_classes`.
3. Registry and PATCH bodies accept **`roles`** (full slugs, e.g. `platform.admin`, `cro.clinical-ops`).
4. `PUT` provision on first login returns **`roles: []`**; complete [Greenfield Step 0](#greenfield-step-0--assign-platform-registry-roles) (or use an existing admin via **Admin → Users**) before operator list flows.
5. CDP **Admin → Users** lists users and saves role edits (with authentication and UI versions from prerequisites).

**Evidence:**

- Migrate job or `alembic upgrade` success log.
- API response capture for `GET /api/v1/roles` (structure check, no PHI in shared artifacts).
- Operator test: PATCH user roles → GET confirms update; CDP save succeeds.
