"""
Story 78.12, AC4: Parity check between JSON CLOB and normalized profile target permissions.

Compares get_*_from_json() vs get_*_from_normalized() for every profile
and reports divergences. Zero divergences required before enabling the feature flag.

Usage:
    python manage.py check_profile_target_permission_parity
    python manage.py check_profile_target_permission_parity --verbose
"""
from __future__ import annotations

import sys
from typing import Any

from django.core.management.base import BaseCommand

from profiles.target_permission_repository import (
    get_target_names_from_json,
    get_target_names_from_normalized,
    get_target_patterns_from_json,
    get_target_patterns_from_normalized,
    get_filter_by_attribute_from_json,
    get_filter_by_attribute_from_normalized,
    get_exclusion_patterns_from_json,
    get_exclusion_patterns_from_normalized,
)
from profiles.models import ProfileTargetPermission


def _normalize_filter(val: dict[str, list[str]] | None) -> dict[str, frozenset[str]]:
    """Normalize filter_by_attribute for comparison: None/empty → empty dict, values → frozensets."""
    if not val:
        return {}
    return {k: frozenset(v) for k, v in val.items()}


class Command(BaseCommand):
    help = 'Check parity between JSON CLOB and normalized profile target permissions (Story 78.12, AC4).'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show details for each profile, including OK ones.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        verbose = options['verbose']

        perms = ProfileTargetPermission.objects.all().order_by('profile_id')

        total = 0
        ok_count = 0
        divergent_count = 0

        for perm in perms:
            total += 1
            profile_id = perm.profile_id
            divergences: list[str] = []

            # Compare target names (by set — order doesn't matter)
            json_names = set(get_target_names_from_json(perm))
            norm_names = set(get_target_names_from_normalized(profile_id))
            if json_names != norm_names:
                divergences.append(
                    f"target_names: JSON={sorted(json_names)}, normalized={sorted(norm_names)}"
                )

            # Compare target patterns (by set)
            json_patterns = set(get_target_patterns_from_json(perm))
            norm_patterns = set(get_target_patterns_from_normalized(profile_id))
            if json_patterns != norm_patterns:
                divergences.append(
                    f"target_patterns: JSON={sorted(json_patterns)}, normalized={sorted(norm_patterns)}"
                )

            # Compare filter_by_attribute (by normalized dict with frozensets)
            json_fa = _normalize_filter(get_filter_by_attribute_from_json(perm))
            norm_fa = _normalize_filter(get_filter_by_attribute_from_normalized(profile_id))
            if json_fa != norm_fa:
                divergences.append(
                    f"filter_by_attribute: JSON={dict(json_fa)}, normalized={dict(norm_fa)}"
                )

            # Compare exclusion patterns (by set)
            json_excl = set(get_exclusion_patterns_from_json(perm))
            norm_excl = set(get_exclusion_patterns_from_normalized(profile_id))
            if json_excl != norm_excl:
                divergences.append(
                    f"exclusion_patterns: JSON={sorted(json_excl)}, normalized={sorted(norm_excl)}"
                )

            if not divergences:
                ok_count += 1
                if verbose:
                    self.stdout.write(self.style.SUCCESS(
                        f"  OK    profile_id={profile_id} type={perm.permission_type}"
                    ))
            else:
                divergent_count += 1
                self.stdout.write(self.style.ERROR(
                    f"  DIFF  profile_id={profile_id} type={perm.permission_type}"
                ))
                for d in divergences:
                    self.stdout.write(f"        - {d}")

        self.stdout.write("")
        self.stdout.write(f"Total profiles: {total}")
        self.stdout.write(f"  OK:        {ok_count}")
        self.stdout.write(f"  Divergent: {divergent_count}")

        if divergent_count > 0:
            self.stdout.write(self.style.ERROR(
                f"\nPARITY CHECK FAILED — {divergent_count} divergence(s) detected."
            ))
            sys.exit(1)
        else:
            self.stdout.write(self.style.SUCCESS(
                "\nPARITY CHECK PASSED — 100% parity between JSON and normalized tables."
            ))
