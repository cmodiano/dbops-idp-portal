"""
Story 78.12 — Tests for the parity check management command.

Tests: parity OK for all permission types, divergence detection, NULL/empty normalization.
Tables managed by conftest.py session-scoped fixture.
"""
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from profiles.target_permission_repository import sync_from_json
from profiles.models import Profile, ProfileTargetPermission
from profiles.models_target_permission_normalized import (
    ProfileTargetAllowlist,
    ProfileTargetAttributeFilter,
)


@pytest.mark.django_db
class ParityCheckTest(TestCase):
    def _call_command(self, *args):
        out = StringIO()
        err = StringIO()
        try:
            call_command(
                'check_profile_target_permission_parity',
                *args,
                stdout=out,
                stderr=err,
            )
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code
        return out.getvalue(), exit_code

    def test_parity_ok_list_type(self):
        """Profile with LIST + target_names: parity OK after sync."""
        profile = Profile.objects.create(name='t-parity-list', ad_group='GRP-IDP-TPL')
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='LIST',
            target_names_json=json.dumps(['server-1', 'server-2']),
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)
        self.assertIn('PARITY CHECK PASSED', output)

    def test_parity_ok_pattern_type(self):
        """Profile with PATTERN + target_patterns: parity OK after sync."""
        profile = Profile.objects.create(name='t-parity-pattern', ad_group='GRP-IDP-TPP')
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='PATTERN',
            target_patterns_json=json.dumps(['prod-*', 'staging-*']),
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)

    def test_parity_ok_filter_by_attribute(self):
        """Profile with filter_by_attribute: parity OK after sync."""
        profile = Profile.objects.create(name='t-parity-fa', ad_group='GRP-IDP-TPFA')
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            filter_by_attribute_json=json.dumps({'engine_type': ['oracle', 'mysql'], 'zone': ['prod']}),
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)

    def test_parity_ok_exclusion_patterns(self):
        """Profile with exclusion_patterns: parity OK after sync."""
        profile = Profile.objects.create(name='t-parity-excl', ad_group='GRP-IDP-TPE')
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            exclusion_patterns_json=json.dumps(['DR-*', 'BACKUP-*']),
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)

    def test_parity_ok_complete_profile(self):
        """Profile with all fields populated: parity OK after sync."""
        profile = Profile.objects.create(name='t-parity-full', ad_group='GRP-IDP-TPF')
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='LIST',
            target_names_json=json.dumps(['server-1', 'server-2']),
            target_patterns_json=json.dumps(['staging-*']),
            filter_by_attribute_json=json.dumps({'engine_type': ['oracle']}),
            exclusion_patterns_json=json.dumps(['DR-*']),
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)

    def test_divergence_detected_target_names(self):
        """Manually introduce divergence in target_names — parity check must detect it."""
        profile = Profile.objects.create(name='t-parity-div-tn', ad_group='GRP-IDP-TPDT')
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='LIST',
            target_names_json=json.dumps(['server-1']),
        )
        sync_from_json(profile.id)

        # Introduce divergence: add an extra entry to normalized table
        ProfileTargetAllowlist.objects.create(profile_id=profile.id, target_name='extra-server')

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 1)
        self.assertIn('PARITY CHECK FAILED', output)
        self.assertIn('DIFF', output)

    def test_divergence_detected_filter_by_attribute(self):
        """Manually introduce divergence in filter_by_attribute — parity check must detect it."""
        profile = Profile.objects.create(name='t-parity-div-fa', ad_group='GRP-IDP-TPDF')
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            filter_by_attribute_json=json.dumps({'zone': ['prod']}),
        )
        sync_from_json(profile.id)

        # Introduce divergence: add an extra attribute filter
        ProfileTargetAttributeFilter.objects.create(
            profile_id=profile.id, attribute_key='zone', attribute_value='staging'
        )

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 1)
        self.assertIn('PARITY CHECK FAILED', output)

    def test_parity_ok_null_json_fields(self):
        """Profile with NULL JSON → no normalized entries → parity OK."""
        profile = Profile.objects.create(name='t-parity-null', ad_group='GRP-IDP-TPN')
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            target_names_json=None,
            target_patterns_json=None,
            filter_by_attribute_json=None,
            exclusion_patterns_json=None,
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)

    def test_parity_ok_empty_json(self):
        """Profile with empty arrays/dict → no normalized entries → parity OK."""
        profile = Profile.objects.create(name='t-parity-empty', ad_group='GRP-IDP-TPEM')
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='ALL',
            target_names_json=json.dumps([]),
            target_patterns_json=json.dumps([]),
            filter_by_attribute_json=json.dumps({}),
            exclusion_patterns_json=json.dumps([]),
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command()
        self.assertEqual(exit_code, 0)

    def test_verbose_flag(self):
        """--verbose shows OK entries."""
        profile = Profile.objects.create(name='t-parity-verbose', ad_group='GRP-IDP-TPV')
        ProfileTargetPermission.objects.create(
            profile=profile,
            permission_type='ALL',
        )
        sync_from_json(profile.id)

        output, exit_code = self._call_command('--verbose')
        self.assertEqual(exit_code, 0)
        self.assertIn('OK', output)
