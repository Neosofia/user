// User registry authorization (ADR-0014).
// Write entities carry presentFields, roleNamespaces (slug prefixes), and rolesExact (canonical role sets).

// --- Self-service ---

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

// --- Demo sandbox (platform tenant bootstrap only) ---

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

// --- Platform operator ---

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

// Allow platform audit operators to list users in the platform tenant catalog.
permit (
    principal is users::User,
    action in [Action::"user:list", Action::"user:read"],
    resource is users::UserCatalog
) when {
    principal.isOperator &&
    principal.tenantType == "platform" &&
    principal.roles.contains("audit")
};

// Allow platform audit operators to read users in their tenant.
permit (
    principal is users::User,
    action == Action::"user:read",
    resource is users::User
) when {
    principal.isOperator &&
    principal.tenantType == "platform" &&
    principal.roles.contains("audit") &&
    principal.tenantId == resource.tenantId
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

// --- Study org (CRO / sponsor / SMO) ---

// Allow study org admins and ops roles to list users in their tenant catalog.
permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    resource has tenantId &&
    principal.tenantId == resource.tenantId &&
    principal.isStudy &&
    (principal.tenantType == "cro" || principal.tenantType == "sponsor" || principal.tenantType == "smo") &&
    (
        principal.roles.contains("admin") ||
        principal.roles.contains("clinical-ops") ||
        principal.roles.contains("systems")
    )
};

// --- Readonly org role ---

// Allow readonly roles to list users in their tenant catalog.
permit (
    principal is users::User,
    action in [Action::"user:list", Action::"user:read"],
    resource is users::UserCatalog
) when {
    resource has tenantId &&
    principal.tenantId == resource.tenantId &&
    principal.roles.contains("readonly")
};

// Allow readonly roles to read users in their tenant.
permit (
    principal is users::User,
    action == Action::"user:read",
    resource is users::User
) when {
    principal.roles.contains("readonly") &&
    principal.tenantId == resource.tenantId
};

// --- Site clinician (patient roster) ---

// Allow site clinicians to list users in their tenant catalog.
permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.isClinician &&
    resource has tenantId &&
    principal.tenantId == resource.tenantId
};

// Allow site clinicians to read users in their tenant.
permit (
    principal is users::User,
    action == Action::"user:read",
    resource is users::User
) when {
    principal.isClinician &&
    principal.tenantId == resource.tenantId
};

// Allow site clinicians to enroll new patient.self users without preset identifiers.
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

// Allow site clinicians to update patient profile fields but not roles or identity fields.
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

// --- Catalog and provision ---

// Allow any authenticated user to read the role catalog.
permit (
    principal is users::User,
    action == Action::"role_catalog:read",
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
