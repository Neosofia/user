// sponsor.clinical-ops — study actor (CDP default_roles_by_actor.study).

permit (
    principal is users::User,
    action == Action::"user:list",
    resource is users::UserCatalog
) when {
    resource has tenantId &&
    principal.tenantId == resource.tenantId &&
    principal.isStudy &&
    principal.tenantType == "sponsor" &&
    principal.roles.contains("clinical-ops")
};
