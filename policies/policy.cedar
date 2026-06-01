// User registry authorization (ADR-0014). Cedar is the source of truth.
// Principal/resource: tenantType, tenantId, roles on users::User; Tier-1 isOperator on JWT.

// Self-service profile
permit (
    principal is users::User,
    action in [Action::"user:read", Action::"user:update"],
    resource is users::User
) when {
    principal.uuid == resource.uuid
};

// Platform tenant + org role admin — full tenant user admin
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

permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.isOperator &&
    principal.tenantType == "platform" &&
    principal.roles.contains("admin")
};

// Platform audit — read-only
permit (
    principal is users::User,
    action in [Action::"user:list", Action::"user:read"],
    resource is users::UserCatalog
) when {
    principal.isOperator &&
    principal.tenantType == "platform" &&
    principal.roles.contains("audit")
};

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

// CRO / sponsor / SMO — operator Tier-1 + matching tenant type + admin or clinical-ops or systems
permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.isOperator &&
    (principal.tenantType == "cro" || principal.tenantType == "sponsor" || principal.tenantType == "smo") &&
    (
        principal.roles.contains("admin") ||
        principal.roles.contains("clinical-ops") ||
        principal.roles.contains("systems")
    )
};

permit (
    principal is users::User,
    action in [Action::"user:read", Action::"user:update"],
    resource is users::User
) when {
    principal.isOperator &&
    (principal.tenantType == "cro" || principal.tenantType == "sponsor" || principal.tenantType == "smo") &&
    (
        principal.roles.contains("admin") ||
        principal.roles.contains("clinical-ops") ||
        principal.roles.contains("systems")
    ) &&
    principal.tenantId == resource.tenantId
};

// Sponsor oversight — read-only within sponsor tenant
permit (
    principal is users::User,
    action in [Action::"user:list", Action::"user:read"],
    resource is users::UserCatalog
) when {
    principal.isOperator &&
    principal.tenantType == "sponsor" &&
    principal.roles.contains("oversight")
};

permit (
    principal is users::User,
    action == Action::"user:read",
    resource is users::User
) when {
    principal.isOperator &&
    principal.tenantType == "sponsor" &&
    principal.roles.contains("oversight") &&
    principal.tenantId == resource.tenantId
};

// Readonly org role (any enterprise tenant type)
permit (
    principal is users::User,
    action in [Action::"user:list", Action::"user:read"],
    resource is users::UserCatalog
) when {
    principal.roles.contains("readonly")
};

permit (
    principal is users::User,
    action == Action::"user:read",
    resource is users::User
) when {
    principal.roles.contains("readonly") &&
    principal.tenantId == resource.tenantId
};

// Clinician Tier-1 — supervised patient roster (CDP demo + care workflows)
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
    action == Action::"user:create",
    resource is users::UserCatalog
) when {
    principal.isClinician
};

permit (
    principal is users::User,
    action == Action::"user:create",
    resource is users::UserCatalog
) when {
    principal.isOperator &&
    principal.tenantType == "platform" &&
    principal.roles.contains("admin")
};

// Site — clinician Tier-1 + site tenant type
permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.tenantType == "site" &&
    (
        principal.roles.contains("admin") ||
        principal.roles.contains("research") ||
        principal.roles.contains("clinical")
    )
};

permit (
    principal is users::User,
    action in [Action::"user:read", Action::"user:update"],
    resource is users::User
) when {
    principal.tenantType == "site" &&
    (
        principal.roles.contains("admin") ||
        principal.roles.contains("research") ||
        principal.roles.contains("clinical")
    ) &&
    principal.tenantId == resource.tenantId
};

// Role catalog — any authenticated principal
permit (
    principal is users::User,
    action == Action::"role_catalog:read",
    resource is users::RoleCatalog
);

// Provisioning — authentication service token only
permit (
    principal is users::Service,
    action == Action::"user:provision",
    resource is users::UserProvisioning
) when {
    principal.tokenType == "service" && principal.serviceSlug == "authentication"
};
