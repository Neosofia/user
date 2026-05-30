// Read/update your own user record (GET/PATCH /api/v1/users/{uuid}).
permit (
    principal is users::User,
    action in [Action::"user:read", Action::"user:update"],
    resource is users::User
) when {
    principal.uuid == resource.uuid
};

// Operators need the Tier-2 platform-admin role before managing other records.
permit (
    principal is users::User,
    action in [Action::"user:read", Action::"user:update"],
    resource is users::User
) when {
    principal.isOperator && principal.isPlatformAdmin
};

permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.isOperator && principal.isPlatformAdmin
};

permit (
    principal is users::Service,
    action == Action::"user:provision",
    resource is users::UserProvisioning
) when {
    principal.tokenType == "service" && principal.serviceSlug == "authentication"
};

// Any authenticated principal may read the role catalog (CDP user admin UI).
permit (
    principal is users::User,
    action == Action::"role_catalog:read",
    resource is users::RoleCatalog
);
