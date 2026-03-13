"""
Story 78.11 — Tests for the parity check management command.

Tests: parity OK for all permission types, divergence detection.
Tables managed by conftest.py session-scoped fixture.
"""
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from profiles.action_permission_repository import sync_from_json
from profiles.models import Profile, ProfileActionPermission
from profiles.models_action_permission_normalized import (
    ProfileActionAllowlist,
)


@pytest.mark.django_db
class ParityCheckTest(TestCase):
    def _call_command(self, *args):
        out = StringIO()
        err = StringIO()
        try:
            call_command(
                'check_profile_action_permission_parity',
                *args,
                stdout=out,
                stderr=err,
            )
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code
        return out.getvalue(), exit_code

    def test_parity_ok_list_type(self):
        """Profile with LIST + action_ids: parity OK after sync."""
        profile = Profile.objects.create(name='parity-list', ad_group='GRP-IDP-PL')
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='LIST',
            action_ids_json=json.dumps([1, 3, 5]),
            environments_json=json.dumps(['dev']),
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)
        self.assertIn('PARITY CHECK PASSED', output)

    def test_parity_ok_pattern_type(self):
        """Profile with PATTERN + tag_patterns: parity OK after sync."""
        profile = Profile.objects.create(name='parity-pattern', ad_group='GRP-IDP-PP')
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='PATTERN',
            tag_patterns_json=json.dumps(['oracle', 'provisioning']),
            environments_json=json.dumps(['staging', 'prod']),
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)

    def test_parity_ok_all_type(self):
        """Profile with ALL + environments: parity OK after sync."""
        profile = Profile.objects.create(name='parity-all', ad_group='GRP-IDP-PA')
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            environments_json=json.dumps(['dev', 'staging', 'prod']),
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)

    def test_divergence_detected(self):
        """Manually introduce divergence — parity check must detect it."""
        profile = Profile.objects.create(name='parity-div', ad_group='GRP-IDP-PD')
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='LIST',
            action_ids_json=json.dumps([1, 2, 3]),
        )
        sync_from_json(profile.id)

        # Introduce divergence: add an extra entry to normalized table
        ProfileActionAllowlist.objects.create(profile_id=profile.id, action_id=999)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 1)
        self.assertIn('PARITY CHECK FAILED', output)
        self.assertIn('DIFF', output)

    def test_parity_ok_null_json_fields(self):
        """Profile with NULL JSON → no normalized entries → parity OK."""
        profile = Profile.objects.create(name='parity-null', ad_group='GRP-IDP-PN')
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            action_ids_json=None,
            tag_patterns_json=None,
            environments_json=None,
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)

    def test_verbose_flag(self):
        """--verbose shows OK entries."""
        profile = Profile.objects.create(name='parity-verbose', ad_group='GRP-IDP-PV')
        ProfileActionPermission.objects.create(
            profile=profile,
            permission_type='ALL',
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command('--verbose')
        self.assertEqual(exit_code, 0)
        self.assertIn('OK', output)
