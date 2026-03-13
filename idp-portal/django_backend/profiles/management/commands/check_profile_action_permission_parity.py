"""
Story 78.11, AC4: Parity check between JSON CLOB and normalized profile action permissions.

Compares get_*_from_json() vs get_*_from_normalized() for every profile
and reports divergences. Zero divergences required before enabling the feature flag.

Usage:
    python manage.py check_profile_action_permission_parity
    python manage.py check_profile_action_permission_parity --verbose
"""
from __future__ import annotations

import sys
from typing import Any

from django.core.management.base import BaseCommand

from profiles.action_permission_repository import (
    get_action_ids_from_json,
    get_action_ids_from_normalized,
    get_environments_from_json,
    get_environments_from_normalized,
    get_tag_patterns_from_json,
    get_tag_patterns_from_normalized,
)
from profiles.models import ProfileActionPermission


class Command(BaseCommand):
    help = 'Check parity between JSON CLOB and normalized profile action permissions (Story 78.11, AC4).'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show details for each profile, including OK ones.',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        verbose = options['verbose']

        perms = ProfileActionPermission.objects.all().order_by('profile_id')

        total = 0
        ok_count = 0
        divergent_count = 0

        for perm in perms:
            total += 1
            profile_id = perm.profile_id
            divergences: list[str] = []

            # Compare action IDs (by set — order doesn't matter)
            json_aids = set(get_action_ids_from_json(perm))
            norm_aids = set(get_action_ids_from_normalized(profile_id))
            if json_aids != norm_aids:
                divergences.append(
                    f"action_ids: JSON={sorted(json_aids)}, normalized={sorted(norm_aids)}"
                )

            # Compare tag patterns (by set)
            json_tp = set(get_tag_patterns_from_json(perm))
            norm_tp = set(get_tag_patterns_from_normalized(profile_id))
            if json_tp != norm_tp:
                divergences.append(
                    f"tag_patterns: JSON={sorted(json_tp)}, normalized={sorted(norm_tp)}"
                )

            # Compare environments (by set)
            json_envs = set(get_environments_from_json(perm))
            norm_envs = set(get_environments_from_normalized(profile_id))
            if json_envs != norm_envs:
                divergences.append(
                    f"environments: JSON={sorted(json_envs)}, normalized={sorted(norm_envs)}"
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
