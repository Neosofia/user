# Changelog

What changed for user-service consumers. Deploy: [INSTALLATION_PLAN.md](INSTALLATION_PLAN.md).

## [0.7.0] - 2026-06-10

### Changed

- `@with_security` on user and role routes uses REST inference; removed `src/bootstrap/capabilities.py`.
- Provisioning helpers moved to `src/authorization/entities.py`.
- Pinned **`authorization-in-the-middle/v0.4.23`**.
