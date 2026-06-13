# Changelog

What changed for user-service consumers. Deploy: [INSTALLATION_PLAN.md](INSTALLATION_PLAN.md).

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
