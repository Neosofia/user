# User service role catalog

Machine source: [`default.json`](default.json). Optional deploy overlay: `ROLE_CATALOG_OVERLAY` (see [OPERATIONS.md](../OPERATIONS.md)).

## Schema

| Key | Purpose |
|-----|---------|
| `roles` | Authoritative tier-2 vocabulary — full slugs (`platform.admin`, `patient.self`) and optional `{ "id", "label" }` objects. |
| `tenant_types` | Assignment index: org kind → `{ "roles": [ full slugs assignable in that kind ] }`. |

**Slug family** (prefix before `.`) groups roles for Cedar; it is **not** Authentication tenant type. Example: `patient.self` is assignable on **site** tenants because it appears under `tenant_types.site.roles`.

Partial overlay files may list `tenant_types` slugs that exist only in the base catalog; referential integrity is checked on the **merged** catalog (`merge_catalogs` / `role_catalog()`), not on overlay files in isolation.

## API

`GET /api/v1/roles` returns `roles`, `role_definitions`, `tenant_types` (full slugs per kind), and `actor_classes`. See [openapi.json](../openapi.json).

## Related

- [ADR-0014](https://github.com/Neosofia/cdp/blob/main/architecture/adrs/0014-tenant-types-and-org-roles.md)
- CDP labels overlay: [cdp/roles/user-catalog.overlay.json](https://github.com/Neosofia/cdp/blob/main/roles/user-catalog.overlay.json)
