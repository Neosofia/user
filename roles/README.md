# Role catalog vocabulary (v1)

Authoritative machine-readable catalog: [`default.json`](default.json). Products merge deploy-time overlays (for example CDP [`user-catalog.overlay.json`](https://github.com/Neosofia/cdp/blob/main/roles/user-catalog.overlay.json)).

Architecture: [ADR-0014](https://github.com/Neosofia/cdp/blob/main/architecture/adrs/0014-tenant-types-and-org-roles.md). Registry behavior: [spec 018](https://github.com/Neosofia/cdp/blob/main/specs/018-user-service.md).

Assignment slugs use `{tenant_type}.{role}` (for example `cro.clinical-ops`). Job functions in overlay JSON are labels for pickers only; they are not authorization roles.

---

## Tenant types

| Type | Typical organisation |
|------|----------------------|
| `platform` | Platform operator (Neosofia) |
| `cro` | Contract research organisation |
| `sponsor` | Pharma or biotech sponsor |
| `site` | Hospital or investigator site |
| `smo` | Site management organisation |
| `patient` | Patient-facing organisation (when distinct) |

`tenants.type` on Authentication has no default; operators set type explicitly per org. Overlays may omit unused types.

---

## Roles per tenant type

Role names omit `-lead` / `-manager`; seniority is handled by role overrides when that ships.

| Tenant type | Roles |
|-------------|-------|
| `platform` | `admin`, `audit` |
| `cro` | `admin`, `clinical-ops`, `systems`, `monitor`, `readonly` |
| `sponsor` | `admin`, `clinical-ops`, `systems`, `oversight`, `readonly` |
| `site` | `admin`, `research`, `clinical`, `readonly` |
| `smo` | `admin`, `activation`, `readonly` |
| `patient` | `self`, `advocate` |

---

## Who may assign which tenant types

Tier-1 actor class (from login) limits which `{tenant_type}.*` slugs an assigner may grant. Prefixes are defined under `assigner_actors` in `default.json`.

| Actor class | May assign roles under |
|-------------|-------------------------|
| `operator` | `platform.*`, `cro.*`, `sponsor.*`, `smo.*` |
| `clinician` | `site.*` |
| `patient` | `patient.*` |

---

When this document and `default.json` disagree, **`default.json` wins**. Update both together when vocabulary changes.
