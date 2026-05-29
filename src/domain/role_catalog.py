"""v1 platform role catalog (authentication#11 MVP subset)."""

from __future__ import annotations

TIER1_ACTOR_CLASSES: frozenset[str] = frozenset({"operator", "clinician", "patient"})

# Platform role id prefixes allowed per Tier-1 assigner (JWT neosofia:roles).
TIER1_PLATFORM_PREFIXES: dict[str, tuple[str, ...]] = {
    "operator": ("operator.",),
    "clinician": ("clinical.", "research."),
    "patient": ("patient.",),
}

V1_PLATFORM_ROLES: frozenset[str] = frozenset({
    "patient.function.self",
    "clinical.function.surgeon",
    "clinical.function.staff-nurse",
    "clinical.function.care-coordinator",
    "clinical.function.readonly",
    "clinical.risk.reviewer",
    "clinical.risk.quality-analyst",
    "research.function.crc",
    "research.function.pi",
    "operator.platform-admin",
    "operator.audit-reader",
})


def platform_roles_for_tier1(tier1: str) -> frozenset[str]:
    prefixes = TIER1_PLATFORM_PREFIXES.get(tier1, ())
    return frozenset(
        role for role in V1_PLATFORM_ROLES if any(role.startswith(prefix) for prefix in prefixes)
    )


def assigner_tier1_roles_from_jwt(roles: list[str]) -> list[str]:
    """Distinct Tier-1 roles from JWT, preserving claim order."""
    tier1: list[str] = []
    seen: set[str] = set()
    for role in roles:
        if role in TIER1_ACTOR_CLASSES and role not in seen:
            seen.add(role)
            tier1.append(role)
    if not tier1:
        raise ValueError(
            "JWT must include at least one Tier-1 role (operator, clinician, patient)"
        )
    return tier1


def platform_roles_for_tier1_roles(tier1_roles: list[str]) -> frozenset[str]:
    allowed: set[str] = set()
    for tier1 in assigner_tier1_roles_from_jwt(tier1_roles):
        allowed.update(platform_roles_for_tier1(tier1))
    return frozenset(allowed)


def validate_tier1_actor(tier1: str) -> None:
    if tier1 not in TIER1_ACTOR_CLASSES:
        raise ValueError(f"tier1 role must be one of {sorted(TIER1_ACTOR_CLASSES)}")


def validate_platform_roles(platform_roles: list[str]) -> None:
    unknown = sorted(set(platform_roles) - V1_PLATFORM_ROLES)
    if unknown:
        raise ValueError(f"unknown platform_roles: {unknown}")


def validate_platform_roles_for_assigner(platform_roles: list[str], assigner_tier1: str) -> None:
    validate_platform_roles_for_assigner_tiers(platform_roles, [assigner_tier1])


def validate_platform_roles_for_assigner_tiers(
    platform_roles: list[str],
    assigner_tier1_roles: list[str],
) -> None:
    tier1_roles = assigner_tier1_roles_from_jwt(assigner_tier1_roles)
    validate_platform_roles(platform_roles)
    allowed = platform_roles_for_tier1_roles(tier1_roles)
    disallowed = sorted(set(platform_roles) - allowed)
    if disallowed:
        namespaces = ", ".join(tier1_roles)
        raise ValueError(
            "platform_roles must use a namespace allowed by your Tier-1 JWT roles "
            f"({namespaces}); disallowed: {disallowed}"
        )
