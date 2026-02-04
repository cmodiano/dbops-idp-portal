"""
RBAC utility functions for Django backend.
Matches FastAPI rbac_service functionality for navigation permissions and business profile detection.
"""

# Navigation tabs by profile — DBOPS sees Admin, others do not
_NAVIGATION_MAP: dict[str, list[str]] = {
    "dbops": ["catalog", "executions", "dashboard", "admin"],
}

_DEFAULT_TABS: list[str] = ["catalog", "executions", "dashboard"]

# Story 7.1: Business profiles for simplified UI
# Includes variations for backward compatibility with seed data
_BUSINESS_PROFILES: set[str] = {"client_business", "business"}


def get_user_navigation_permissions(profile: str) -> list[str]:
    """
    Return navigation tab keys based on user profile.
    
    Args:
        profile: User profile name (e.g., "dbops", "dba_applicatif")
    
    Returns:
        List of navigation tab keys the user can access
    """
    return _NAVIGATION_MAP.get(profile.lower(), _DEFAULT_TABS)


def is_business_profile(profile: str) -> bool:
    """
    Story 7.1: Check if profile is a business profile (simplified UI).
    
    Args:
        profile: User profile name
    
    Returns:
        True if profile is a business profile, False otherwise
    """
    return profile.lower() in _BUSINESS_PROFILES
