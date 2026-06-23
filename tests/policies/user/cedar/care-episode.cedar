// Care Episode resolves tenant patient registries for roster search and profile enrichment.
permit (
    principal is users::Service,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    principal.tokenType == "service" &&
    principal.serviceSlug == "care-episode" &&
    resource has tenantId
};

permit (
    principal is users::Service,
    action == Action::"user:read",
    resource is users::User
) when {
    principal.tokenType == "service" &&
    principal.serviceSlug == "care-episode" &&
    resource has tenantId
};
