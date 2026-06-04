# User Service

Authoritative store for **Tier-2 platform roles** on human principals. Authentication attests identity and **Tier-1 actor class** (JWT); this service holds job functions and operator privileges used by Cedar policies in downstream APIs. Domain scope (site, trial, care episode, etc.) belongs in other services—not here.

Design background: authentication service issue #11 (role model for post-discharge care). Implementation scope: `cdp/specs/018-user-service.md`.

**Provisioning:** This service does not expose `POST /api/v1/users`. Authentication continues to own identity cache; on login it best-effort **creates or updates** the Tier-2 profile here through `PUT /api/v1/users/{uuid}`. This service stays the source of truth for `platform_roles`.

## Glossary

Terms below follow the three-layer model from issue #11. Names in **bold** are fields on the `users` table or API.

| Term | Layer | Where it lives | Meaning |
|------|-------|----------------|---------|
| **Actor class** | Tier 1 | JWT (`neosofia:roles`) from Authentication / WorkOS | Broad principal type: `operator`, `clinician`, or `patient`. **Not stored** on the user row. |
| **Platform role** (`platform_roles[]`) | Tier 2 | This service (source of truth) | Dotted job function under a branch, e.g. `clinical.function.surgeon`, `research.function.crc`, `operator.platform-admin`. A person may hold **multiple** roles from different branches. |
| **Scope attributes** (site, trial, region) | Tier 2+ | Domain services (Site, Study, Care Episode, …) | Where a staff member works or which trials they cover—**not** columns on `users`. Cedar in those services matches principal/resource attributes. |
| `tenant_uuid` | — | `users.tenant_uuid` | Platform tenant (org). **Defined in Authentication**; this service stores only the UUID. |
| `uuid` | — | `users.uuid` | **Same value as Authentication `users.uuid`** (JWT `sub`). Assigned by Authentication; required on create here. |
| `idp_id` | — | `users.idp_id` | Stable IDP subject id (`user_01…`); should match Authentication `users.idp_id`. |
| **State** | Tier 3 | Domain services (e.g. Care Episode, Study) | Time-bounded or lifecycle **state** tied to a patient or enrollment — active recovery window, trial participation, episode status. **Not** stored as `platform_roles` here. |

### Tier 1 vs Tier 2 (quick rule)

- **Tier 1** answers: *What kind of principal?* (`patient` vs `clinician` vs `operator`).
- **Tier 2** answers: *What job(s)?* (RN + CRC, operator admin). Site/trial scope is modeled in domain services.
- If it is time-bounded lifecycle state (care episode, study enrollment, etc.) → **Tier 3**, not a `platform_role`.

### Platform role naming (`branch.category.slug`)

From issue #11 — study and site **never** go in the role string; model them in domain services, not on `users`.

```
patient.function.self              ← default patient app access

clinical.function.staff-nurse      ← post-discharge care delivery
clinical.function.surgeon
clinical.risk.reviewer             ← AI alert review, safety
clinical.license.rn                ← regulated credential (Stage 3+ in catalog)

research.function.crc              ← site trial staff (parallel to clinical branch)
research.function.pi

operator.platform-admin            ← mesh / user admin (not a clinical title)
operator.audit-reader
```

The core service ships a generic role catalog in `roles/default.json`. Product deployments can mount a JSON overlay with domain-specific branches such as the clinical and research examples below.

## Examples (from issue #11)

**Jane — RN at site 042 who is also CRC for trial NEO-001**

```json
{
  "platform_roles": [
    "clinical.function.staff-nurse",
    "research.function.crc"
  ]
}
```

Site and trial scope for Jane live in the Site / Study services; Cedar there matches **resource attributes** to those records—not columns on `users`.

**Platform operator (service registry, user admin)**

```json
{
  "platform_roles": ["operator.platform-admin"]
}
```

Tier-1 `operator` in the JWT lets them open operator UI surfaces; `operator.platform-admin` in this service grants user CRUD via Cedar (`isPlatformAdmin`).

**Post-op patient**

Recovery timing and episode lifecycle are **Tier 3 state** (e.g. Care Episode). The user row might only need:

```json
{
  "platform_roles": ["patient.function.self"]
}
```

## What this service does / does not do

| In scope | Elsewhere |
|----------|-----------|
| CRUD on `users` + audit history | Tier-1 token issuance → **Authentication** |
| v1 role catalog (`GET /api/v1/roles`) | Tenant metadata → **Authentication** `GET /api/v1/tenants/{uuid}` |
| Cedar policies for user registry + role catalog | UI menu entitlements → **Capabilities** (bundled UI policy set) |
| Site / trial / episode scope on `users` | Domain services + Tier 3 **state** (Care Episode, Study, Site, …) |

## Operations and security

- Run, test, migrate, and deploy: **[OPERATIONS.md](OPERATIONS.md)**
- Per-release operator steps and verification: **[INSTALLATION_PLAN.md](INSTALLATION_PLAN.md)**
- Threat model, authz boundaries, and logging rules: **[SECURITY.md](SECURITY.md)**
- Stage 2 scope and API contract: **`cdp/specs/018-user-service.md`**

## Endpoints

**Public (no Cedar):** `GET /health`

**Protected (`@with_security` + Cedar):**

- `GET /api/v1/roles` — v1 role catalog (allowed `actor_class` + `platform_roles`)
- `GET /api/v1/users` — list (operator with `operator.platform-admin`; Cedar `user:list` on `UserCatalog`). **No public POST** — user rows are provisioned from authentication on login.
- `GET|PATCH /api/v1/users/{uuid}` — read/update user record (self or `operator.platform-admin`; Cedar `user:read` / `user:update` on `User`)
- `GET /api/v1/users/{uuid}/audits` — audit trail
- `PUT /api/v1/users/{uuid}` — authentication-service provisioning callback; inserts on first login and refreshes identity fields on later logins without changing `platform_roles`

Contract: `openapi.json`.
