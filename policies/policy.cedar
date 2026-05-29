// Read/update your own user record (GET/PATCH /api/v1/users/{uuid}).
permit (
    principal is users::User,
    action in [Action::"user:read", Action::"user:update"],
    resource is users::User
) when {
    principal.uuid == resource.uuid
};

// Interim: Tier-1 operators may do anything with user records and the user catalog.
// Refine (e.g. platform-admin scopes) after admin UI testing. See entities.py for isOperator.
permit (
    principal is users::User,
    action in [Action::"user:read", Action::"user:update"],
    resource is users::User
) when {
    principal.isOperator
};

permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.isOperator
};

// Any authenticated principal may read the role catalog (CDP user admin UI).
permit (
    principal is users::User,
    action == Action::"role_catalog:read",
    resource is users::RoleCatalog
);
