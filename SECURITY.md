# User Service — Security Posture

This service follows the [Neosofia Service Security Baseline](https://github.com/Neosofia/templates/blob/main/python/service/SECURITY.md), which defines the controls required of every platform web service. This document covers only deviations and concerns specific to the User Service.

The User Service is the **Tier-2 source of truth** for **`roles[]`** on human principals (registry slugs `{tenant_type}.{role}`, e.g. `platform.admin`). **Tenant type** is owned by Authentication (`tenants.type`, JWT `neosofia:tenant_type`). Site, trial, and other domain scope live in downstream services—not in this registry. It validates platform JWTs but does **not** issue tokens or run the identity provider login flow.

To report any security-related issue please email security@neosofia.tech — do not create a public issue.

---

## Role in the Platform

| Concern | This service | Owner elsewhere |
|---------|--------------|-----------------|
| Login, MFA, WorkOS, JWT issuance | — | **Authentication** |
| Tier-1 actor class on the JWT (`operator`, `clinician`, `patient`) | — | **Authentication** (`neosofia:actors`) |
| Tier-2 roles (`roles[]`, full slugs) | **Source of truth** | — |
| Tenant type (`platform`, `cro`, …) | — | **Authentication** |
| Tenant display name / WorkOS org | — | **Authentication** `GET /api/v1/tenants/{uuid}` |
| UI menu entitlements | — | **Capabilities** + CDP policy bundle |
| Tier-3 patient/study **state** | — | Care Episode, Study, etc. |

---

## Trust Boundaries

| Boundary | Control |
|----------|---------|
| Caller identity | Platform JWT from **Authentication**; human `sub` equals `users.uuid`, service `sub` equals caller slug |
| Tier-1 gate (list/admin update) | JWT must include Tier-1 actor `operator` (`authentication-in-the-middle`) |
| Tier-2 gate (read/update/audits) | Cedar in `policies/policy.cedar` (`users` namespace), evaluated in-process via `authorization-in-the-middle` |
| Cedar principal | Row loaded by JWT `sub` through `resolve_principal()`; no row → authorization path fails closed |
| Internal provisioning | Service token with `sub=authentication`, `aud=user`, and `neosofia:token_type=service` |
| Public surface | Only `GET /health` is unauthenticated |

---

## Authorization (Cedar)

Policy bundle: `policies/*.cedar` only (no Cedar schema file). Entity payloads are built in `src/authorization/entities.py`. Policy layout and CDP overlays: [policies/README.md](policies/README.md).

| Rule | Who | Action | Resource |
|------|-----|--------|----------|
| Self-service | Principal | `user:read`, `user:update` | Own `users::User` |
| Platform admin | Tier-1 `operator` + JWT `tenant_type=platform` + role `admin` | `user:read`, `user:update`, `user:list` | Same-tenant users / catalog |
| Enterprise admin | Tier-1 `operator` + matching `tenant_type` + `admin` / `clinical-ops` / `systems` (see `policy.cedar`) | `user:read`, `user:update`, `user:list` | Same-tenant users / catalog |
| Site admin | `tenant_type=site` + `admin` / `research` / `clinical` | `user:read`, `user:update`, `user:list` | Same-tenant users / catalog |
| Role picklists | Any authenticated principal | `role_catalog:read` | `users::RoleCatalog` |
| Login provisioning | `authentication` service token | `user:provision` | `users::UserProvisioning` |

**Defense in depth:** Registry administration requires matching **tenant type**, **roles** (from JWT `neosofia:roles` and/or this registry), and same **tenant** as the target row. **Role assignment** on create/update is enforced in Cedar (`policies/policy.cedar`; proposed slugs → `roleNamespaces` on the write entity). Catalog JSON lists valid slug vocabulary; `validate_roles` rejects unknown slugs at persistence. Self-service PATCH field allowlist remains in application code. See [ADR-0014](https://github.com/Neosofia/cdp/blob/main/architecture/adrs/0014-tenant-types-and-org-roles.md).

---

## Sensitive Data

This service **stores** name and email in PostgreSQL (needed for admin UI and profile enrichment). Baseline logging rules still apply: **do not** log names, email, or role strings.

| Data | In API / DB | In logs |
|------|-------------|---------|
| Name, email | Yes | **No** — use `user_uuid`, `actor_uuid`, `error_type` only |
| `roles`, scope UUIDs | Yes | **No** |
| `tenant_uuid`, `idp_id` | Yes | **No** |

Row-level audit history is in `users_audit` (platform audit SQL); treat audit tables with the same log discipline.

---

## Deployment Deviations

| Setting | Requirement |
|---------|-------------|
| `JWT_AUDIENCE` | Must include `user` |
| Authentication `JWT_WEB_AUDIENCE` | Must list `user` so CDP and operators can call this API |
| `JWT_JWKS_URI` / `JWT_PUBLIC_KEY` | Authentication service JWKS or PEM — same trust chain as other platform APIs |
| `AUTHORIZATION_POLICIES_DIR` | Default `policies`; ship `policy.cedar` in the image |
| `ROLE_CATALOG_OVERLAY` | Optional product-owned JSON file merged with `roles/default.json` at startup/request cache load |
| SDK wheels | Pin `authentication-in-the-middle` and `authorization-in-the-middle` to published release URLs in `pyproject.toml` (not local paths in production) |

---

## Known Limitations

| Item | Status | Notes |
|------|--------|-------|
| Public create API | By design | User rows are created only by the internal Authentication provisioning route; this service does not mint user ids |
| List/admin update gate | By design | Cedar uses `tenantType`, `roles`, and `tenantId` match (ADR-0014) |
| Principal must exist locally | By design | JWT valid but no user row → self/admin authorization is limited until login provisioning creates the row |
| Rate limit storage in-memory | Accepted (baseline) | Set `RATELIMIT_STORAGE_URI` to Redis when running multiple replicas |
| OpenAPI contract | In progress | Runtime validation is in route handlers; published `openapi.json` may lag full route surface |
