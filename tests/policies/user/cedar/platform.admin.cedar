// platform.admin — platform tenant operator administration.

// Allow platform admins to read and update users in their tenant.
permit (
    principal is users::User,
    action in [Action::"user:read", Action::"user:update"],
    resource is users::User
) when {
    principal.isOperator &&
    principal.tenantType == "platform" &&
    principal.roles.contains("admin") &&
    principal.tenantId == resource.tenantId
};

// Allow platform admins to list users in the platform tenant catalog.
permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.isOperator &&
    principal.tenantType == "platform" &&
    principal.roles.contains("admin")
};

// Allow platform admins to create users in the platform tenant.
permit (
    principal is users::User,
    action == Action::"user:create",
    resource is users::User
) when {
    principal.isOperator &&
    principal.tenantType == "platform" &&
    principal.roles.contains("admin")
};

// Block platform admins from assigning non-platform role namespaces.
forbid (
    principal is users::User,
    action in [Action::"user:create", Action::"user:update"],
    resource is users::User
) when {
    principal.isOperator &&
    principal.tenantType == "platform" &&
    principal.roles.contains("admin") &&
    resource.presentFields.contains("roles") &&
    resource has roleNamespaces &&
    !(resource.roleNamespaces == ["platform"])
};
