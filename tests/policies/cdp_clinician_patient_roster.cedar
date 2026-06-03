// CDP product policy — clinician supervised patient roster (enroll + profile edit).
// Canonical copy: cdp/policies/service-overrides/user/cdp_clinician_patient_roster.cedar
// Packed into unit-test policy dir by tests/conftest.py (CI has no sibling cdp repo).

permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.isClinician
};

permit (
    principal is users::User,
    action == Action::"user:read",
    resource is users::User
) when {
    principal.isClinician &&
    principal.tenantId == resource.tenantId
};

permit (
    principal is users::User,
    action == Action::"user:update",
    resource is users::User
) when {
    principal.isClinician &&
    principal.tenantId == resource.tenantId &&
    resource.roles.contains("self")
};

permit (
    principal is users::User,
    action == Action::"user:create",
    resource is users::UserCatalog
) when {
    principal.isClinician
};
