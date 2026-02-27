"""
Tests for profiles services (ProfileService).
Story 20.5: Fixed method names, audit assertions, added edge cases.
"""

import pytest
from django.test import TestCase
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from profiles.services import ProfileService
from core.models import AuditLog, AuditActionType, AuditEntityType
from tests.factories import UserFactory


@pytest.mark.django_db
class TestProfileService(TestCase):
    """Tests for ProfileService."""

    def setUp(self):
        """Set up test data."""
        self.service = ProfileService()
        self.user = UserFactory(profile='dbops')

    def test_create_profile(self):
        """Test create_profile() creates profile with audit."""
        profile_data = {
            'name': 'Test Profile',
            'description': 'Test Description',
            'ad_group': 'CN=Test,OU=Groups,DC=example,DC=com',
            'is_admin': 0,
            'is_auditor': 0
        }

        profile = self.service.create_profile(profile_data, user=self.user)

        self.assertIsNotNone(profile.id)
        self.assertEqual(profile.name, 'Test Profile')

        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.PROFILE,
            entity_id=profile.id,
            action_type=AuditActionType.PROFILE_CREATED
        ).first()
        self.assertIsNotNone(audit)

    def test_create_profile_without_user_no_audit(self):
        """Test create_profile() without user does not create audit entry."""
        profile_data = {
            'name': 'No Audit Profile',
            'ad_group': 'CN=NoAudit,OU=Groups,DC=example,DC=com',
        }

        profile = self.service.create_profile(profile_data)
        self.assertIsNotNone(profile.id)

        # No audit entry should exist
        audit_count = AuditLog.objects.filter(
            entity_type=AuditEntityType.PROFILE,
            entity_id=profile.id,
        ).count()
        self.assertEqual(audit_count, 0)

    def test_create_profile_duplicate_name_raises(self):
        """Test create_profile() with duplicate name raises ValueError."""
        Profile.objects.create(name='Duplicate', ad_group='GRP-A')

        with self.assertRaises(ValueError):
            self.service.create_profile({
                'name': 'Duplicate',
                'ad_group': 'GRP-B',
            })

    def test_create_profile_is_admin_bool_conversion(self):
        """Test create_profile() converts boolean is_admin to 0/1."""
        profile = self.service.create_profile({
            'name': 'Admin Profile',
            'ad_group': 'GRP-ADMIN',
            'is_admin': True,
            'is_auditor': False,
        })

        self.assertEqual(profile.is_admin, 1)
        self.assertEqual(profile.is_auditor, 0)

    def test_list_all(self):
        """Test list_all() returns profiles with permission count."""
        Profile.objects.create(
            name='Profile 1',
            ad_group='CN=Profile1,OU=Groups,DC=example,DC=com'
        )

        profiles = self.service.list_all()
        self.assertGreaterEqual(profiles.count(), 1)

    def test_get_by_id(self):
        """Test get_by_id() retrieves profile with permissions."""
        profile = Profile.objects.create(
            name='Test Profile',
            ad_group='CN=Test,OU=Groups,DC=example,DC=com'
        )

        retrieved = self.service.get_by_id(profile.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, profile.id)

    def test_get_by_id_not_found(self):
        """Test get_by_id() returns None for non-existent profile."""
        result = self.service.get_by_id(99999)
        self.assertIsNone(result)

    def test_get_by_name(self):
        """Test get_by_name() retrieves profile by name."""
        Profile.objects.create(name='Named Profile', ad_group='GRP-NAMED')

        result = self.service.get_by_name('Named Profile')
        self.assertIsNotNone(result)
        self.assertEqual(result.name, 'Named Profile')

    def test_get_by_name_strips_whitespace(self):
        """Test get_by_name() strips whitespace."""
        Profile.objects.create(name='Trimmed', ad_group='GRP-TRIM')

        result = self.service.get_by_name('  Trimmed  ')
        self.assertIsNotNone(result)

    def test_get_by_name_not_found(self):
        """Test get_by_name() returns None for non-existent name."""
        result = self.service.get_by_name('Nonexistent')
        self.assertIsNone(result)

    def test_update_profile(self):
        """Test update_profile() updates profile and creates audit."""
        profile = Profile.objects.create(
            name='Original Name',
            ad_group='CN=Original,OU=Groups,DC=example,DC=com'
        )

        update_data = {
            'name': 'Updated Name',
            'description': 'Updated Description'
        }

        updated = self.service.update_profile(profile.id, update_data, user=self.user)

        self.assertEqual(updated.name, 'Updated Name')
        self.assertEqual(updated.description, 'Updated Description')

        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.PROFILE,
            entity_id=profile.id,
            action_type=AuditActionType.PROFILE_UPDATED
        ).first()
        self.assertIsNotNone(audit)

    def test_update_profile_not_found(self):
        """Test update_profile() returns None for non-existent profile."""
        result = self.service.update_profile(99999, {'name': 'X'})
        self.assertIsNone(result)

    def test_update_profile_partial_fields(self):
        """Test update_profile() only updates provided fields."""
        profile = Profile.objects.create(
            name='Original', description='Keep me', ad_group='GRP-PARTIAL'
        )

        updated = self.service.update_profile(profile.id, {'name': 'Changed'})
        self.assertEqual(updated.name, 'Changed')
        self.assertEqual(updated.description, 'Keep me')

    def test_delete_profile(self):
        """Test delete_profile() deletes profile and creates audit."""
        profile = Profile.objects.create(
            name='Profile to Delete',
            ad_group='CN=Delete,OU=Groups,DC=example,DC=com'
        )
        profile_id = profile.id

        result = self.service.delete_profile(profile_id, user=self.user)

        self.assertTrue(result)
        self.assertFalse(Profile.objects.filter(id=profile_id).exists())

        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.PROFILE,
            entity_id=profile_id,
            action_type=AuditActionType.PROFILE_DELETED
        ).first()
        self.assertIsNotNone(audit)

    def test_delete_profile_not_found(self):
        """Test delete_profile() returns False for non-existent profile."""
        result = self.service.delete_profile(99999)
        self.assertFalse(result)

    def test_delete_profile_cascades_permissions(self):
        """Test delete_profile() cascades to action/target permissions."""
        profile = Profile.objects.create(name='Cascade', ad_group='GRP-CASCADE')
        ProfileActionPermission.objects.create(
            profile=profile, permission_type='ALL'
        )
        ProfileTargetPermission.objects.create(
            profile=profile, permission_type='ALL'
        )
        profile_id = profile.id

        self.service.delete_profile(profile_id)

        self.assertFalse(ProfileActionPermission.objects.filter(profile_id=profile_id).exists())
        self.assertFalse(ProfileTargetPermission.objects.filter(profile_id=profile_id).exists())


@pytest.mark.django_db
class TestProfileServiceActionPermissions(TestCase):
    """Tests for ProfileService action permission methods."""

    def setUp(self):
        self.service = ProfileService()
        self.profile = Profile.objects.create(name='Perm Profile', ad_group='GRP-PERM')

    def test_set_action_permissions_list(self):
        """Test set_action_permissions() with list type."""
        perm = self.service.set_action_permissions(self.profile.id, {
            'actions_type': 'list',
            'action_ids': [1, 2, 3],
            'environments': ['PROD'],
        })
        self.assertIsNotNone(perm)
        self.assertEqual(perm.permission_type, 'LIST')
        self.assertEqual(perm.get_action_ids(), [1, 2, 3])

    def test_set_action_permissions_pattern(self):
        """Test set_action_permissions() with pattern type."""
        perm = self.service.set_action_permissions(self.profile.id, {
            'actions_type': 'pattern',
            'tag_patterns': ['oracle*'],
        })
        self.assertEqual(perm.permission_type, 'PATTERN')
        self.assertEqual(perm.get_tag_patterns(), ['oracle*'])

    def test_set_action_permissions_all(self):
        """Test set_action_permissions() with all type."""
        perm = self.service.set_action_permissions(self.profile.id, {
            'actions_type': 'all',
        })
        self.assertEqual(perm.permission_type, 'ALL')

    def test_set_action_permissions_upsert(self):
        """Test set_action_permissions() updates existing permission."""
        self.service.set_action_permissions(self.profile.id, {
            'actions_type': 'list', 'action_ids': [1],
        })
        perm = self.service.set_action_permissions(self.profile.id, {
            'actions_type': 'all',
        })
        self.assertEqual(perm.permission_type, 'ALL')
        self.assertEqual(ProfileActionPermission.objects.filter(profile=self.profile).count(), 1)

    def test_set_action_permissions_profile_not_found(self):
        """Test set_action_permissions() returns None if profile not found."""
        result = self.service.set_action_permissions(99999, {'actions_type': 'all'})
        self.assertIsNone(result)

    def test_get_action_permissions(self):
        """Test get_action_permissions() retrieves existing permission."""
        ProfileActionPermission.objects.create(
            profile=self.profile, permission_type='ALL'
        )
        perm = self.service.get_action_permissions(self.profile.id)
        self.assertIsNotNone(perm)
        self.assertEqual(perm.permission_type, 'ALL')

    def test_get_action_permissions_none(self):
        """Test get_action_permissions() returns None when no permission exists."""
        perm = self.service.get_action_permissions(self.profile.id)
        self.assertIsNone(perm)

    def test_delete_action_permissions(self):
        """Test delete_action_permissions() removes permission."""
        ProfileActionPermission.objects.create(
            profile=self.profile, permission_type='ALL'
        )
        result = self.service.delete_action_permissions(self.profile.id)
        self.assertTrue(result)
        self.assertFalse(ProfileActionPermission.objects.filter(profile=self.profile).exists())

    def test_delete_action_permissions_not_found(self):
        """Test delete_action_permissions() returns False when no permission."""
        result = self.service.delete_action_permissions(self.profile.id)
        self.assertFalse(result)


@pytest.mark.django_db
class TestProfileServiceTargetPermissions(TestCase):
    """Tests for ProfileService target permission methods."""

    def setUp(self):
        self.service = ProfileService()
        self.profile = Profile.objects.create(name='Target Profile', ad_group='GRP-TGT')

    def test_set_target_permissions_list(self):
        """Test set_target_permissions() with list type."""
        perm = self.service.set_target_permissions(self.profile.id, {
            'targets_type': 'list',
            'target_names': ['srv-01', 'srv-02'],
        })
        self.assertIsNotNone(perm)
        self.assertEqual(perm.permission_type, 'LIST')
        self.assertEqual(perm.get_target_names(), ['srv-01', 'srv-02'])

    def test_set_target_permissions_pattern(self):
        """Test set_target_permissions() with pattern type."""
        perm = self.service.set_target_permissions(self.profile.id, {
            'targets_type': 'pattern',
            'target_patterns': ['db-*'],
        })
        self.assertEqual(perm.permission_type, 'PATTERN')
        self.assertEqual(perm.get_target_patterns(), ['db-*'])

    def test_set_target_permissions_all(self):
        """Test set_target_permissions() with all type."""
        perm = self.service.set_target_permissions(self.profile.id, {
            'targets_type': 'all',
        })
        self.assertEqual(perm.permission_type, 'ALL')

    def test_set_target_permissions_profile_not_found(self):
        """Test set_target_permissions() returns None if profile not found."""
        result = self.service.set_target_permissions(99999, {'targets_type': 'all'})
        self.assertIsNone(result)

    def test_get_target_permissions(self):
        """Test get_target_permissions() retrieves existing permission."""
        ProfileTargetPermission.objects.create(
            profile=self.profile, permission_type='LIST'
        )
        perm = self.service.get_target_permissions(self.profile.id)
        self.assertIsNotNone(perm)

    def test_get_target_permissions_none(self):
        """Test get_target_permissions() returns None when no permission."""
        perm = self.service.get_target_permissions(self.profile.id)
        self.assertIsNone(perm)

    def test_delete_target_permissions(self):
        """Test delete_target_permissions() removes permission."""
        ProfileTargetPermission.objects.create(
            profile=self.profile, permission_type='ALL'
        )
        result = self.service.delete_target_permissions(self.profile.id)
        self.assertTrue(result)

    def test_delete_target_permissions_not_found(self):
        """Test delete_target_permissions() returns False when none."""
        result = self.service.delete_target_permissions(self.profile.id)
        self.assertFalse(result)


@pytest.mark.django_db
class TestProfileServiceCumulativePermissions(TestCase):
    """Tests for ProfileService.get_cumulative_permissions()."""

    def setUp(self):
        self.service = ProfileService()

    def test_cumulative_single_profile_all(self):
        """Test cumulative permissions with a single 'all' profile."""
        profile = Profile.objects.create(
            name='DBA', ad_group='GRP-DBA', is_admin=1
        )
        ProfileActionPermission.objects.create(
            profile=profile, permission_type='ALL'
        )

        result = self.service.get_cumulative_permissions(user_id=1, ad_groups=['GRP-DBA'])
        self.assertEqual(len(result['action_permissions']), 1)
        self.assertEqual(result['action_permissions'][0]['actions_type'], 'all')

    def test_cumulative_multiple_profiles(self):
        """Test cumulative permissions aggregates across multiple profiles."""
        p1 = Profile.objects.create(name='P1', ad_group='GRP-A')
        p2 = Profile.objects.create(name='P2', ad_group='GRP-B')
        ProfileActionPermission.objects.create(
            profile=p1, permission_type='LIST'
        )
        ProfileActionPermission.objects.create(
            profile=p2, permission_type='ALL'
        )

        result = self.service.get_cumulative_permissions(
            user_id=1, ad_groups=['GRP-A', 'GRP-B']
        )
        self.assertEqual(len(result['action_permissions']), 2)

    def test_cumulative_no_matching_profiles(self):
        """Test cumulative permissions with no matching AD groups."""
        result = self.service.get_cumulative_permissions(
            user_id=1, ad_groups=['NONEXISTENT']
        )
        self.assertEqual(result['action_permissions'], [])
        self.assertEqual(result['target_permissions'], [])

    def test_cumulative_admin_fallback(self):
        """Test admin profile gets 'all' when no explicit permissions set."""
        Profile.objects.create(name='Admin', ad_group='GRP-ADMIN', is_admin=1)

        result = self.service.get_cumulative_permissions(
            user_id=1, ad_groups=['GRP-ADMIN']
        )
        self.assertEqual(len(result['action_permissions']), 1)
        self.assertEqual(result['action_permissions'][0]['actions_type'], 'all')
        self.assertEqual(len(result['target_permissions']), 1)
        self.assertEqual(result['target_permissions'][0]['targets_type'], 'all')

    def test_cumulative_empty_ad_groups(self):
        """Test cumulative permissions with empty AD groups list."""
        result = self.service.get_cumulative_permissions(user_id=1, ad_groups=[])
        self.assertEqual(result['action_permissions'], [])

    def test_cumulative_invalid_user_id(self):
        """Test cumulative permissions raises ValueError for None user_id."""
        with self.assertRaises(ValueError):
            self.service.get_cumulative_permissions(user_id=None, ad_groups=['GRP-A'])

    def test_cumulative_dba_multi_technologies(self):
        """AC2 — DBA appartenant à GRP-DBA-SQL et GRP-DBA-ORACLE obtient l'union des permissions.

        Vérifie que la règle produit spec-rbac-cumul-permissions-multi-groupes.md est respectée :
        un DBA multi-technologies voit les actions taguées sql-server ET oracle.
        """
        # Profil SQL : actions taguées sql-server
        profile_sql = Profile.objects.create(name='DBA-SQL', ad_group='GRP-DBA-SQL')
        perm_sql = ProfileActionPermission.objects.create(
            profile=profile_sql, permission_type='PATTERN'
        )
        perm_sql.set_tag_patterns(['sql-server'])
        perm_sql.set_environments(['dev', 'staging'])
        perm_sql.save()

        # Profil Oracle : actions taguées oracle
        profile_oracle = Profile.objects.create(name='DBA-ORACLE', ad_group='GRP-DBA-ORACLE')
        perm_oracle = ProfileActionPermission.objects.create(
            profile=profile_oracle, permission_type='PATTERN'
        )
        perm_oracle.set_tag_patterns(['oracle'])
        perm_oracle.set_environments(['prod'])
        perm_oracle.save()

        result = self.service.get_cumulative_permissions(
            user_id=42,
            ad_groups=['GRP-DBA-SQL', 'GRP-DBA-ORACLE']
        )

        # Les deux profils sont présents dans action_permissions
        self.assertEqual(len(result['action_permissions']), 2)

        # Vérification que tag_patterns des deux profils sont disponibles
        all_tags = set()
        for perm in result['action_permissions']:
            all_tags.update(perm.get('tag_patterns', []))
        self.assertIn('sql-server', all_tags)
        self.assertIn('oracle', all_tags)

        # Vérification des environnements des deux profils
        all_envs = set()
        for perm in result['action_permissions']:
            all_envs.update(perm.get('environments', []))
        self.assertIn('dev', all_envs)
        self.assertIn('staging', all_envs)
        self.assertIn('prod', all_envs)

    def test_cumulative_conflict_resolved_by_union(self):
        """AC3 — Si Profil 1 autorise l'action X et Profil 2 ne l'autorise pas, X est autorisé.

        La règle d'union (most permissive wins) : si au moins un profil autorise → oui.
        """
        # Profil 1 : autorise action_id=10
        profile1 = Profile.objects.create(name='Profil-Allow', ad_group='GRP-ALLOW')
        perm1 = ProfileActionPermission.objects.create(
            profile=profile1, permission_type='LIST'
        )
        perm1.set_action_ids([10])
        perm1.set_environments(['dev'])
        perm1.save()

        # Profil 2 : autorise uniquement action_id=20 (n'autorise pas 10)
        profile2 = Profile.objects.create(name='Profil-Deny', ad_group='GRP-DENY')
        perm2 = ProfileActionPermission.objects.create(
            profile=profile2, permission_type='LIST'
        )
        perm2.set_action_ids([20])
        perm2.set_environments(['staging'])
        perm2.save()

        result = self.service.get_cumulative_permissions(
            user_id=99,
            ad_groups=['GRP-ALLOW', 'GRP-DENY']
        )

        # Les deux profils sont présents (union brute de ProfileService)
        self.assertEqual(len(result['action_permissions']), 2)

        # Les action_ids des deux profils sont présents (union)
        all_action_ids = set()
        for perm in result['action_permissions']:
            all_action_ids.update(perm.get('action_ids', []))
        # Action 10 (autorisée par profil 1) est présente dans l'union
        self.assertIn(10, all_action_ids)
        # Action 20 (autorisée par profil 2) est aussi présente
        self.assertIn(20, all_action_ids)
