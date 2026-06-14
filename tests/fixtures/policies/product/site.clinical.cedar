// site.clinical — site clinician patient roster management.

permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.isClinician &&
    resource has tenantId &&
    principal.tenantId == resource.tenantId
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
    action == Action::"user:create",
    resource is users::User
) when {
    principal.isClinician &&
    principal.tenantId == resource.tenantId &&
    resource.rolesExact == ["patient.self"] &&
    !resource.presentFields.contains("uuid") &&
    !resource.presentFields.contains("idp_id")
};

permit (
    principal is users::User,
    action == Action::"user:update",
    resource is users::User
) when {
    principal.isClinician &&
    principal.tenantId == resource.tenantId &&
    resource.roles == ["patient.self"] &&
    !resource.presentFields.contains("roles") &&
    !resource.presentFields.contains("tenant_uuid") &&
    !resource.presentFields.contains("uuid") &&
    !resource.presentFields.contains("idp_id") &&
    !resource.presentFields.contains("tos_accepted") &&
    !resource.presentFields.contains("actor_class")
};
