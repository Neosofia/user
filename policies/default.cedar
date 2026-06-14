// User registry authorization (ADR-0014).
// Shared policies for every authenticated principal and service callers.
// Product role rules (platform, site, sponsor, demo) ship in the CDP policy bundle (user/cedar/).
// Write entities carry presentFields, roleNamespaces (slug prefixes), and rolesExact (canonical role sets).

// Allow users to read and update their own user record.
permit (
    principal is users::User,
    action in [Action::"user:read", Action::"user:update"],
    resource is users::User
) when {
    principal.uuid == resource.uuid
};

// Block non-operator, non-demo users from changing protected fields on their own record.
forbid (
    principal is users::User,
    action == Action::"user:update",
    resource is users::User
) when {
    principal.uuid == resource.uuid &&
    !principal.isOperator &&
    !principal.isDemo &&
    (
        resource.presentFields.contains("roles") ||
        resource.presentFields.contains("tenant_uuid") ||
        resource.presentFields.contains("uuid") ||
        resource.presentFields.contains("idp_id") ||
        resource.presentFields.contains("actor_class")
    )
};

// Allow any authenticated user to list the role catalog.
permit (
    principal is users::User,
    action == Action::"role:list",
    resource is users::RoleCatalog
);

// Allow the authentication service to provision users during sign-in.
permit (
    principal is users::Service,
    action == Action::"user:provision",
    resource is users::UserProvisioning
) when {
    principal.tokenType == "service" && principal.serviceSlug == "authentication"
};
