"""
Environment helper utilities — Story 26.7.

Centralized case-insensitive environment comparison and matching.
Epic 21 removed normalization via aliases (certif→staging).
Inventory is now the single source of truth with raw values.
This helper provides case-insensitive comparison only.
"""
from __future__ import annotations

from typing import Any, cast


class EnvironmentHelper:
    """
    Helper for case-insensitive environment comparison and matching.

    Story 26.7 — Centralized environment logic post-Epic 21.
    Epic 21 removed normalization via aliases.
    Inventory is the single source of truth with raw values
    (dev, lab, qa, uat, certif, staging, prod).
    This helper provides case-insensitive comparison only.

    Examples:
        >>> EnvironmentHelper.normalize('DEV')
        'dev'
        >>> EnvironmentHelper.matches('DEV', 'dev')
        True
        >>> EnvironmentHelper.is_in('Staging', ['dev', 'STAGING', 'prod'])
        True
        >>> config = {'DEV': {'required': False}, 'PROD': {'required': True}}
        >>> EnvironmentHelper.find_in_dict(config, 'dev')
        {'required': False}
    """

    @staticmethod
    def normalize(env: str | None) -> str:
        """
        Normalize environment string to lowercase for comparison.

        Args:
            env: Environment string (e.g., 'DEV', 'Staging', 'PROD')

        Returns:
            Lowercase, trimmed string. Empty string if None.

        Examples:
            >>> EnvironmentHelper.normalize('DEV')
            'dev'
            >>> EnvironmentHelper.normalize('  Staging  ')
            'staging'
            >>> EnvironmentHelper.normalize(None)
            ''
        """
        if not env:
            return ''
        return str(env).strip().lower()

    @staticmethod
    def matches(a: str | None, b: str | None) -> bool:
        """
        Check if two environment strings match (case-insensitive).

        Args:
            a: First environment string
            b: Second environment string

        Returns:
            True if normalized strings are equal, False otherwise.

        Examples:
            >>> EnvironmentHelper.matches('DEV', 'dev')
            True
            >>> EnvironmentHelper.matches('Staging', 'STAGING')
            True
            >>> EnvironmentHelper.matches('prod', 'staging')
            False
            >>> EnvironmentHelper.matches(None, '')
            True
        """
        return EnvironmentHelper.normalize(a) == EnvironmentHelper.normalize(b)

    @staticmethod
    def is_in(env: str | None, env_list: list[str]) -> bool:
        """
        Check if environment is in list (case-insensitive).

        Args:
            env: Environment string to check
            env_list: List of environment strings

        Returns:
            True if env (normalized) is in list (normalized), False otherwise.

        Examples:
            >>> EnvironmentHelper.is_in('DEV', ['dev', 'staging', 'prod'])
            True
            >>> EnvironmentHelper.is_in('Staging', ['DEV', 'PROD'])
            False
            >>> EnvironmentHelper.is_in(None, ['dev'])
            False
        """
        if not env:
            return False
        normalized_env = EnvironmentHelper.normalize(env)
        normalized_list = {EnvironmentHelper.normalize(e) for e in env_list}
        return normalized_env in normalized_list

    @staticmethod
    def find_in_dict(config: dict, env: str | None) -> dict | None:
        """
        Find environment key in dict (case-insensitive).

        Used for resolving environment-specific config.

        Args:
            config: Dictionary with environment keys
            env: Environment string to find

        Returns:
            Value for matching key, or None if not found.

        Examples:
            >>> config = {'DEV': {'required': False}, 'PROD': {'required': True}}
            >>> EnvironmentHelper.find_in_dict(config, 'dev')
            {'required': False}
            >>> EnvironmentHelper.find_in_dict(config, 'staging')
        """
        if not config or not env:
            return None
        normalized_env = EnvironmentHelper.normalize(env)
        for key, value in config.items():
            if EnvironmentHelper.normalize(key) == normalized_env:
                return cast("dict[Any, Any] | None", value)
        return None
