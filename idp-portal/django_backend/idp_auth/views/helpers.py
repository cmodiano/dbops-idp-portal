"""
Shared helpers for authentication views.
Extracted from saml.py to satisfy AC-8 (<250 LOC per module) — Story 54.7.
"""


def _extract_ad_groups(attributes: dict, raw_profile: str | None) -> list[str]:
    """Extract AD groups from SAML attributes.

    Looks for groups in: groups, memberOf, ad_groups.
    Falls back to raw_profile for backward compatibility.
    """
    raw_groups = (
        attributes.get("groups")
        or attributes.get("memberOf")
        or attributes.get("ad_groups")
        or []
    )
    if isinstance(raw_groups, str):
        ad_groups = [raw_groups.strip()] if raw_groups.strip() else []
    else:
        ad_groups = [g.strip() for g in raw_groups if g and str(g).strip()]

    # Fallback to raw_profile for backward compat
    if not ad_groups and raw_profile:
        ad_groups = [raw_profile]

    return ad_groups
