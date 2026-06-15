# Changelog

What changed for user-service consumers. Deploy: [INSTALLATION_PLAN.md](INSTALLATION_PLAN.md).

## [0.8.2] - 2026-06-16

### Changed

- Default tenant user list page size is **15** (was 20), matching the CDP Admin Users table.

## [0.8.1] - 2026-06-14

### Changed

- CDP product Cedar (including demo sandbox) and the full role catalog ship from **`cdp-policies`** at image build. Generic Cedar remains in this repo (`policies/default.cedar` only). No base role catalog in the user repo.
- Removed `policies/roles/default.json`; role vocabulary comes entirely from `ROLE_CATALOG_OVERLAY`.
- Build arg **`USER_PRODUCT_POLICIES_IMAGE`** (default `ghcr.io/neosofia/cdp-policies:v0.2.0`) selects the product policy bundle; **`CDP_POLICIES_IMAGE`** remains a deprecated alias. Non-CDP deployments pass their own bundle image with the same `/policies/user/` layout.

## [0.8.0] - 2026-06-14

### Changed

- Role catalog decouples **role slugs** from **tenant type**: `roles[]` is the vocabulary; `tenant_types.{kind}.roles` lists full assignable slugs per org kind (e.g. `patient.self` under `site`). Loader validates shape and referential integrity only — no domain constants in code. `GET /api/v1/roles` `tenant_types` values are full slugs, not short names.
- Pinned **`authorization-in-the-middle/v0.7.1`** — SDK REST inference on user and role routes; Cedar policies split by role family (`policies/*.cedar`).
- Rebuild with **`cdp-user-policies/v0.3.0`** (decoupled role-catalog overlay).

## [0.7.1] - 2026-06-13

### Changed

- Pinned **`authorization-in-the-middle/v0.5.0`** (REST entity inference, Cedar merge on PATCH).
- Role catalog loader lives under `src/services/role_catalog.py`; Cedar-only PATCH fields rejected with **400**.
- Rebuild with **`cdp-user-policies/v0.2.2`** (demo actor overlay, roster policy removed from bundle).

## [0.7.0] - 2026-06-10

### Changed

- `@with_security` on user and role routes uses REST inference; removed `src/bootstrap/capabilities.py`.
- Provisioning helpers moved to `src/authorization/entities.py`.
- Pinned **`authorization-in-the-middle/v0.4.23`**.
