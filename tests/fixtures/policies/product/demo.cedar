// Demo sandbox (platform tenant bootstrap only).

// Allow demo users on the platform tenant to switch between patient and clinician demo roles.
permit (
    principal is users::User,
    action == Action::"user:update",
    resource is users::User
) when {
    principal.uuid == resource.uuid &&
    principal.isDemo &&
    principal.tenantType == "platform" &&
    resource.presentFields.contains("roles") &&
    resource.roles == ["patient.self", "site.clinical"]
};

// Allow demo users to list users in their tenant catalog.
permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.isDemo &&
    resource has tenantId &&
    principal.tenantId == resource.tenantId
};

// Allow demo users to read user records in their tenant.
permit (
    principal is users::User,
    action == Action::"user:read",
    resource is users::User
) when {
    principal.isDemo &&
    principal.tenantId == resource.tenantId
};
