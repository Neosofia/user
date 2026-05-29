# User Service — Security Posture

This service follows the [Neosofia Service Security Baseline](https://github.com/Neosofia/templates/blob/main/python/service/SECURITY.md), which defines the controls required of every platform web service. This document covers only deviations and concerns specific to the User Service.

The User Service is the **Tier-2 source of truth** for `platform_roles` on human principals. Site, trial, and other domain scope live in downstream services—not in this registry. It validates platform JWTs but does **not** issue tokens or run the identity provider login flow.

To report any security-related issue please email security@neosofia.tech — do not create a public issue.

---

## Role in the Platform

| Concern | This service | Owner elsewhere |
|---------|--------------|-----------------|
| Login, MFA, WorkOS, JWT issuance | — | **Authentication** |
| Tier-1 actor class on the JWT (`operator`, `clinician`, `patient`) | Copy on user row for Cedar | **Authentication** (JWT) |
| Tier-2 roles and org scope | **Source of truth** | — |
| Tenant display name / WorkOS org | — | **Authentication** `GET /api/v1/tenants/{uuid}` |
| UI menu entitlements | — | **Capabilities** + CDP policy bundle |
| Tier-3 patient/study **state** | — | Care Episode, Study, etc. |

---

## Trust Boundaries

| Boundary | Control |
|----------|---------|
| Caller identity | Platform JWT from **Authentication**; `sub` must equal `users.uuid` in this database |
| Tier-1 gate (list/create) | JWT must include Tier-1 role `operator` (`authentication-in-the-middle`) |
| Tier-2 gate (read/update/audits) | Cedar in `policies/policy.cedar` (`users` namespace), evaluated in-process via `authorization-in-the-middle` |
| Cedar principal | Row loaded by JWT `sub` through `resolve_principal()`; no row → authorization path fails closed |
| Public surface | Only `GET /health` is unauthenticated |

---

## Authorization (Cedar)

Policy bundle: `policies/*.cedar` only (no Cedar schema file). Entity payloads are built in `src/authorization/entities.py`.

| Rule | Who | Action | Resource |
|------|-----|--------|----------|
| Self-service | Principal | `user:read`, `user:update` | Own `users::User` |
| Interim operator | Tier-1 JWT `operator` → Cedar `isOperator` | `user:read`, `user:update` | Any `users::User` |
| Interim operator registry | `isOperator` | `user:list` | `users::UserCatalog` |
| Role picklists | Any authenticated principal | `role_catalog:read` | `users::RoleCatalog` |

**Interim operator rules:** broad user/catalog access for Stage 2 testing; replace with finer platform-admin scopes later. Self-service PATCH field allowlist stays in application code.

**Defense in depth:** Tier-1 `operator` on the JWT (`authentication-in-the-middle`). Cedar `isOperator` is derived from JWT Tier-1 roles only (actor class is not stored in the user registry). Operators can bootstrap the registry before their own row exists. Platform role assignment is scoped to the union of Tier-1 namespaces on the JWT session (`neosofia:session_roles`, or `neosofia:roles` when only one role is present), not the UI active-role selection (`neosofia:roles` after `X-Active-Role` narrowing). Self-service PATCH field allowlist remains in application code for when narrower policies return.

---

## Sensitive Data

This service **stores** name and email in PostgreSQL (needed for admin UI and profile enrichment). Baseline logging rules still apply: **do not** log names, email, or role strings.

| Data | In API / DB | In logs |
|------|-------------|---------|
| Name, email | Yes | **No** — use `user_uuid`, `actor_uuid`, `error_type` only |
| `platform_roles`, scope UUIDs | Yes | **No** |
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
| SDK wheels | Pin `authentication-in-the-middle` and `authorization-in-the-middle` to published release URLs in `pyproject.toml` (not local paths in production) |

---

## Known Limitations

| Item | Status | Notes |
|------|--------|-------|
| Identity provisioning | By design | `POST /api/v1/users` requires a `uuid` already assigned by **Authentication**; this service does not mint user ids |
| List/create operator gate | By design | Tier-1 JWT role `operator` required; not replaceable by Tier-2 `operator.platform-admin` alone |
| Principal must exist locally | By design | JWT valid but no user row → Cedar principal load fails; register the user before expecting registry APIs to work |
| Rate limit storage in-memory | Accepted (baseline) | Set `RATELIMIT_STORAGE_URI` to Redis when running multiple replicas |
| OpenAPI contract | In progress | Runtime validation is in route handlers; published `openapi.json` may lag full route surface |

---

## References

- Feature spec: `cdp/specs/018-user-service.md`
- Role model: [authentication#11](https://github.com/Neosofia/authentication/issues/11)
- [Constitution](https://github.com/Neosofia/cdp/blob/main/architecture/constitution.md)
- [ADR-0008: Published JSON Schema contracts](https://github.com/Neosofia/cdp/blob/main/architecture/structurizr/decisions/0008-published-json-schema-contracts-for-api-testing.md)
