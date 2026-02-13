"""
InventoryRBACFilter: Multi-layer RBAC filtering for inventory targets.

Responsibility: Apply WHAT to filter on inventory results (permissions, attributes, exclusions).
Story 26.1 - AC1, AC4: Separation of concerns from InventoryService.
"""

from __future__ import annotations

import fnmatch

import structlog

from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

# Maximum targets to load for in-memory RBAC filtering
MAX_TARGETS_FOR_RBAC_FILTER = 5000


class InventoryRBACFilter:
    """
    Multi-layer RBAC filtering for inventory targets.

    Applies filters in order:
    1. Target restrictions (LIST/PATTERN/ALL)
    2. Attribute filters (filter_by_attribute)
    3. Exclusion patterns (deny explicit)

    Story 26.1 - AC1: Extracted from InventoryService.
    """

    @staticmethod
    def _apply_attribute_filter(
        servers: list[dict],
        filter_by_attr: dict,
        correlation_id: str = '',
    ) -> list[dict]:
        """
        Apply attribute-based filtering to servers list.

        Filters are cumulative (AND): server must match ALL criteria.
        If an attribute is absent from server data, that criterion is ignored (WARNING logged).

        Args:
            servers: List of server dicts
            filter_by_attr: Dict mapping attribute keys to allowed values.
            correlation_id: Correlation ID for logging.

        Returns:
            Filtered list of servers matching all criteria.

        Story 23.4 - AC2.
        """
        nb_before = len(servers)
        if not filter_by_attr:
            return servers

        filtered = list(servers)

        for attr_key, allowed_values in filter_by_attr.items():
            if not allowed_values:
                continue

            # Check if attribute exists in any server
            has_attribute = any(attr_key in srv for srv in servers)
            if not has_attribute:
                logger.warning(
                    "rbac_filter_attribute_not_found",
                    attribute=attr_key,
                    allowed_values=allowed_values,
                    correlation_id=correlation_id,
                )
                continue

            # Case-insensitive matching for attribute values
            allowed_lower = [str(v).lower() for v in allowed_values]
            filtered = [
                srv for srv in filtered
                if str(srv.get(attr_key, '')).lower() in allowed_lower
            ]

        nb_after = len(filtered)

        logger.info(
            "rbac_filter_by_attribute_applied",
            filter=filter_by_attr,
            nb_servers_before=nb_before,
            nb_servers_after=nb_after,
            correlation_id=correlation_id,
        )

        return filtered

    def apply_rbac_chain(
        self,
        targets: list[dict],
        permissions: dict,
    ) -> list[dict]:
        """
        Apply RBAC filtering chain to targets.

        Applies filters in order:
        1. Target restrictions (LIST/PATTERN/ALL)
        2. Attribute filters (filter_by_attribute)
        3. Exclusion patterns (deny explicit)

        Args:
            targets: Unfiltered targets from inventory source
            permissions: Dict with keys:
                - has_all_access: bool
                - target_restrictions: list[tuple[str, list[str] | None]]
                - attribute_filters: list[dict | None]
                - all_access_attribute_filters: list[dict | None]
                - exclusion_patterns: list[str]

        Returns:
            Filtered list of targets after RBAC chain

        Story 26.1 - AC4: RBAC chain orchestration.
        """
        correlation_id = get_correlation_id()

        has_all_access = permissions.get('has_all_access', False)
        target_restrictions = permissions.get('target_restrictions', [])
        attribute_filters = permissions.get('attribute_filters', [])
        all_access_attribute_filters = permissions.get('all_access_attribute_filters', [])
        exclusion_patterns = permissions.get('exclusion_patterns', [])

        nb_before = len(targets)

        # Step 1: Apply target restrictions
        if not has_all_access and target_restrictions:
            targets = self.apply_target_restrictions(targets, target_restrictions)

        nb_after_restrictions = len(targets)

        # Step 2: Apply attribute filters
        targets = self.apply_attribute_filters_across_profiles(
            targets,
            has_all_access,
            all_access_attribute_filters,
            target_restrictions,
            attribute_filters,
            correlation_id,
        )

        nb_after_attributes = len(targets)

        # Step 3: Apply exclusion patterns
        if exclusion_patterns:
            unique_exclusion_patterns = list(set(exclusion_patterns))
            targets = self.apply_exclusion_patterns(
                targets, unique_exclusion_patterns, correlation_id
            )

        nb_after_exclusions = len(targets)

        logger.info(
            "rbac_chain_applied",
            nb_before=nb_before,
            nb_after_restrictions=nb_after_restrictions,
            nb_after_attributes=nb_after_attributes,
            nb_after_exclusions=nb_after_exclusions,
            correlation_id=correlation_id,
        )

        return targets

    def apply_target_restrictions(
        self,
        targets: list[dict],
        restrictions: list[tuple[str, list[str] | None]],
    ) -> list[dict]:
        """
        Apply target restrictions (union of patterns and lists).

        Args:
            targets: List of target dicts
            restrictions: List of (type, values) tuples

        Returns:
            Filtered list of targets matching any restriction
        """
        result = []
        for target in targets:
            target_name = target['name']
            matches = False

            for perm_type, values in restrictions:
                if values is None:
                    continue

                if perm_type == 'LIST':
                    values_lower = [v.lower() for v in values if isinstance(v, str)]
                    if target_name.lower() in values_lower:
                        matches = True
                        break
                elif perm_type == 'PATTERN':
                    for pattern in values:
                        if fnmatch.fnmatch(target_name.lower(), pattern.lower()):
                            matches = True
                            break
                    if matches:
                        break

            if matches:
                result.append(target)

        return result

    def apply_attribute_filters_across_profiles(
        self,
        targets: list[dict],
        has_all_access: bool,
        all_access_attribute_filters: list[dict | None],
        target_restrictions: list[tuple[str, list[str] | None]],
        attribute_filters: list[dict | None],
        correlation_id: str,
    ) -> list[dict]:
        """
        Apply attribute-based filters across profiles (OR between profiles).

        Story 23.4 - AC2:
        - Within a profile: attribute filters are cumulative (AND)
        - Between profiles: results are additive (OR)
        - If ANY profile has no attribute filter, its targets pass through unfiltered

        Args:
            targets: Pre-filtered targets (after env + target restrictions)
            has_all_access: Whether any profile has ALL target access
            all_access_attribute_filters: Attribute filters for ALL-access profiles
            target_restrictions: List of (type, values) for non-ALL profiles
            attribute_filters: Parallel list of attribute filters for non-ALL profiles
            correlation_id: Correlation ID for logging

        Returns:
            Targets filtered by attribute filters (OR across profiles)
        """
        active_filters = []
        has_unfiltered_profile = False

        if has_all_access:
            for af in all_access_attribute_filters:
                if af:
                    active_filters.append(af)
                else:
                    has_unfiltered_profile = True

        for af in attribute_filters:
            if af:
                active_filters.append(af)
            else:
                has_unfiltered_profile = True

        if not active_filters or has_unfiltered_profile:
            return targets

        result_set: set[tuple[str, str]] = set()
        result_targets: dict[tuple[str, str], dict] = {}

        for attr_filter in active_filters:
            filtered = self._apply_attribute_filter(targets, attr_filter, correlation_id)
            for t in filtered:
                name = t.get('name', '')
                env = t.get('environment', '')
                key = (name, env)
                if key not in result_set:
                    result_set.add(key)
                    result_targets[key] = t

        nb_before = len(targets)
        nb_after = len(result_targets)

        logger.info(
            "rbac_filter_by_attribute_applied_across_profiles",
            nb_filters=len(active_filters),
            nb_servers_before=nb_before,
            nb_servers_after=nb_after,
            correlation_id=correlation_id,
        )

        return [t for t in targets if (t.get('name', ''), t.get('environment', '')) in result_set]

    def apply_exclusion_patterns(
        self,
        targets: list[dict],
        exclusion_patterns: list[str],
        correlation_id: str,
    ) -> list[dict]:
        """
        Apply exclusion patterns to filter out targets matching any pattern.

        Story 25.6 - Deny explicit RBAC:
        - Exclusion patterns are applied AFTER inclusion rules
        - If a target matches ANY exclusion pattern, it's removed
        - Matching is case-insensitive using fnmatch (glob-style: *, ?, [abc])

        Args:
            targets: Pre-filtered targets (after inclusion + attributes)
            exclusion_patterns: List of glob patterns to exclude
            correlation_id: Correlation ID for logging

        Returns:
            Targets with exclusions applied (subset of input)
        """
        if not exclusion_patterns:
            return targets

        nb_before = len(targets)
        result = []
        excluded_count = 0

        pattern_match_count = {pattern: 0 for pattern in exclusion_patterns}

        for target in targets:
            target_name = target.get('name', '').lower()
            is_excluded = False

            for pattern in exclusion_patterns:
                pattern_lower = pattern.lower()
                if fnmatch.fnmatch(target_name, pattern_lower):
                    is_excluded = True
                    excluded_count += 1
                    pattern_match_count[pattern] += 1
                    logger.debug(
                        "rbac_target_excluded",
                        target_name=target.get('name'),
                        exclusion_pattern=pattern,
                        correlation_id=correlation_id
                    )
                    break

            if not is_excluded:
                result.append(target)

        nb_after = len(result)

        unused_patterns = [p for p, count in pattern_match_count.items() if count == 0]
        if unused_patterns:
            logger.warning(
                "rbac_exclusion_patterns_never_matched",
                unused_patterns=unused_patterns,
                nb_targets_checked=nb_before,
                message="These exclusion patterns did not match any target (check for typos or misconfiguration)",
                correlation_id=correlation_id,
            )

        logger.info(
            "rbac_exclusion_patterns_applied",
            nb_patterns=len(exclusion_patterns),
            patterns=exclusion_patterns,
            nb_targets_before=nb_before,
            nb_targets_excluded=excluded_count,
            nb_targets_after=nb_after,
            correlation_id=correlation_id,
        )

        return result
