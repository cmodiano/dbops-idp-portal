"""
Parametrized tests for edge cases and validation.

Story M.9: Tests unitaires et d'intégration
Uses @pytest.mark.parametrize for comprehensive edge case coverage.
"""

import pytest

from idp_auth.models import User
from catalog.models import Action, ActionStatus, ActionCategory, ActionEngine, ActionPlatform
from catalog.services import CatalogService
from integrations.models import Integration
from executions.models import Execution, ExecutionStatus
from profiles.models import Profile


@pytest.mark.django_db
class TestParametrizedActionFilters:
    """Parametrized tests for action filtering."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test data."""
        self.user = User.objects.create(username='param_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Param AAP',
            base_url='https://aap.example.com'
        )

    @pytest.mark.parametrize('status,expected_count', [
        (ActionStatus.DRAFT, 1),
        (ActionStatus.PUBLISHED, 1),
        (ActionStatus.DISABLED, 1),
    ])
    def test_filter_by_status(self, status, expected_count):
        """Test filtering actions by different statuses."""
        # For disabled status, create as published first then deactivate
        if status == ActionStatus.DISABLED:
            action = Action.objects.create(
                name=f'Action {status}',
                category='Provisioning',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED,
                created_by=self.user,
                integration=self.integration
            )
            service = CatalogService()
            service.deactivate_action(action.id, self.user, deletion_reason="Test")
        else:
            Action.objects.create(
                name=f'Action {status}',
                category='Provisioning',
                engine='Oracle',
                platform='AAP',
                status=status,
                created_by=self.user,
                integration=self.integration
            )

        results = Action.objects.list_by_status(status)
        assert results.count() == expected_count

    @pytest.mark.parametrize('category', [
        ActionCategory.PROVISIONING,
        ActionCategory.PATCHING,
        ActionCategory.ADMINISTRATION,
        ActionCategory.MONITORING,
    ])
    def test_filter_by_category(self, category):
        """Test filtering actions by all category types."""
        Action.objects.create(
            name=f'Action {category}',
            category=category,
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

        results = Action.objects.filter(category=category)
        assert results.count() == 1
        assert results[0].category == category

    @pytest.mark.parametrize('engine', [
        ActionEngine.ORACLE,
        ActionEngine.SQL_SERVER,
        ActionEngine.DB2,
    ])
    def test_filter_by_engine(self, engine):
        """Test filtering actions by all engine types."""
        Action.objects.create(
            name=f'Action {engine}',
            category='Provisioning',
            engine=engine,
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

        results = Action.objects.filter(engine=engine)
        assert results.count() == 1

    @pytest.mark.parametrize('platform', [
        ActionPlatform.AAP,
        ActionPlatform.TERRAFORM,
        ActionPlatform.GITHUB_ACTIONS,
        ActionPlatform.AZURE_DEVOPS,
    ])
    def test_filter_by_platform(self, platform):
        """Test filtering actions by all platform types."""
        Action.objects.create(
            name=f'Action {platform}',
            category='Provisioning',
            engine='Oracle',
            platform=platform,
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

        results = Action.objects.filter(platform=platform)
        assert results.count() == 1


@pytest.mark.django_db
class TestParametrizedPagination:
    """Parametrized tests for pagination edge cases."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test data with 25 actions."""
        self.user = User.objects.create(username='page_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Page AAP',
            base_url='https://aap.example.com'
        )

        # Create 25 actions
        for i in range(25):
            Action.objects.create(
                name=f'Page Action {i:02d}',
                category='Provisioning',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED,
                created_by=self.user,
                integration=self.integration
            )

    @pytest.mark.parametrize('offset,limit,expected_count', [
        (0, 10, 10),   # First page
        (10, 10, 10),  # Second page
        (20, 10, 5),   # Last page (partial)
        (0, 25, 25),   # All items
        (0, 100, 25),  # Beyond total
        (25, 10, 0),   # Offset at total
        (30, 10, 0),   # Offset beyond total
    ])
    def test_pagination_offset_limit(self, offset, limit, expected_count):
        """Test pagination with various offset/limit combinations."""
        results = Action.objects.list_published()[offset:offset + limit]
        assert len(list(results)) == expected_count

    @pytest.mark.parametrize('page_size,total_pages', [
        (10, 3),
        (5, 5),
        (25, 1),
        (7, 4),
    ])
    def test_page_count_calculation(self, page_size, total_pages):
        """Test page count for different page sizes."""
        import math
        total_items = 25
        calculated_pages = math.ceil(total_items / page_size)
        assert calculated_pages == total_pages


@pytest.mark.django_db
class TestParametrizedValidation:
    """Parametrized tests for input validation."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test data."""
        self.user = User.objects.create(username='valid_user', profile='DBA')

    @pytest.mark.parametrize('username,is_valid', [
        ('validuser', True),
        ('user123', True),
        ('user_name', True),
        ('a' * 255, True),  # Max length
        ('', False),  # Empty
    ])
    def test_username_validation(self, username, is_valid):
        """Test username validation rules."""
        if is_valid and username:
            user = User.objects.create(username=username, profile='DBA')
            assert user.username == username
        elif not is_valid:
            # Empty username should fail at DB level (Oracle) or validation level
            # SQLite is more permissive, so we skip this test for empty strings in SQLite
            from django.conf import settings
            if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                pytest.skip("SQLite allows empty usernames, Oracle rejects them")
            with pytest.raises(Exception):
                User.objects.create(username=username, profile='DBA')

    @pytest.mark.parametrize('action_name,should_succeed', [
        ('Valid Action Name', True),
        ('Action with Numbers 123', True),
        ('Action-with-dashes', True),
        ('a' * 255, True),  # Max length
    ])
    def test_action_name_validation(self, action_name, should_succeed):
        """Test action name validation."""
        integration = Integration.objects.create(
            type='aap',
            name=f'Valid Int {action_name[:10]}',
            base_url='https://aap.example.com'
        )

        if should_succeed:
            action = Action.objects.create(
                name=action_name,
                category='Provisioning',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.DRAFT,
                created_by=self.user,
                integration=integration
            )
            assert action.name == action_name


@pytest.mark.django_db
class TestParametrizedExecutionStatus:
    """Parametrized tests for execution status transitions."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test data."""
        self.user = User.objects.create(username='status_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Status AAP',
            base_url='https://aap.example.com'
        )
        self.action = Action.objects.create(
            name='Status Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

    @pytest.mark.parametrize('status', [
        ExecutionStatus.SUBMITTED,
        ExecutionStatus.INTEGRATION_ERROR,
        # DEPRECATED (78.14): PENDING_APPROVAL removed from DB CHECK (V135) — not a valid DB status anymore
        ExecutionStatus.RUNNING,
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.REJECTED,
    ])
    def test_all_execution_statuses(self, status):
        """Test that all execution status values are valid in DB CHECK constraint."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='developpement',
            status=status
        )

        assert execution.status == status
        execution.refresh_from_db()
        assert execution.status == status

    @pytest.mark.parametrize('environment', [
        'developpement',
        'certification',
        'production',
    ])
    def test_all_environments(self, environment):
        """Test execution in all environments (raw inventory values — Story 53.2)."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment=environment,
            status=ExecutionStatus.SUBMITTED
        )

        assert execution.environment == environment


@pytest.mark.django_db
class TestParametrizedRBACCombinations:
    """Parametrized tests for RBAC permission combinations."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test profiles."""
        pass

    @pytest.mark.parametrize('is_admin,is_auditor,expected_access', [
        (0, 0, 'standard'),
        (1, 0, 'admin'),
        (0, 1, 'auditor'),
        (1, 1, 'admin_auditor'),
    ])
    def test_profile_permission_combinations(self, is_admin, is_auditor, expected_access):
        """Test different profile permission flag combinations."""
        profile = Profile.objects.create(
            name=f'Profile_{expected_access}',
            ad_group=f'CN={expected_access},OU=Groups,DC=corp,DC=com',
            is_admin=is_admin,
            is_auditor=is_auditor
        )

        assert profile.is_admin == is_admin
        assert profile.is_auditor == is_auditor

        # Verify admin profiles are in admin filter
        if is_admin:
            admin_profiles = Profile.objects.filter(is_admin=1)
            assert profile.id in [p.id for p in admin_profiles]

        # Verify auditor profiles are in auditor filter
        if is_auditor:
            auditor_profiles = Profile.objects.filter(is_auditor=1)
            assert profile.id in [p.id for p in auditor_profiles]

    @pytest.mark.parametrize('permission_type,allowed_envs,can_execute_prod', [
        ('ALL', ['dev', 'staging', 'prod'], True),
        ('ALL', ['dev', 'staging'], False),
        ('LIST', ['dev'], False),
        ('PATTERN', ['prod'], True),
    ])
    def test_environment_permission_combinations(self, permission_type, allowed_envs, can_execute_prod):
        """Test different environment permission combinations."""
        from profiles.models import ProfileActionPermission
        from profiles.services import ProfileService
        from profiles.action_permission_repository import get_environments

        profile = Profile.objects.create(
            name=f'EnvProfile_{permission_type}_{len(allowed_envs)}',
            ad_group='CN=EnvProfile,OU=Groups,DC=corp,DC=com'
        )

        type_map = {'LIST': 'list', 'PATTERN': 'pattern', 'ALL': 'all'}
        ProfileService().set_action_permissions(
            profile.id,
            {'actions_type': type_map.get(permission_type, 'all'), 'environments': allowed_envs},
        )

        perm = ProfileActionPermission.objects.get(profile=profile)
        environments = get_environments(perm)

        assert ('prod' in environments) == can_execute_prod


@pytest.mark.django_db
class TestParametrizedJSONSerialization:
    """Parametrized tests for JSON field serialization."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test data."""
        self.user = User.objects.create(username='json_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='JSON AAP',
            base_url='https://aap.example.com'
        )

    @pytest.mark.parametrize('parameters', [
        {'key': 'value'},
        {'nested': {'key': 'value'}},
        {'array': [1, 2, 3]},
        {'mixed': {'string': 'text', 'number': 123, 'bool': True, 'null': None}},
        {},  # Empty object
    ])
    def test_action_parameters_schema_serialization(self, parameters):
        """Test parameters_schema JSON serialization."""
        action = Action.objects.create(
            name=f'JSON Action {hash(str(parameters))}',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user,
            integration=self.integration
        )

        action.parameters_schema = parameters
        action.save()

        action.refresh_from_db()
        loaded = action.parameters_schema

        assert loaded == parameters

    @pytest.mark.parametrize('impact_rules', [
        {'dev': {'auto_approve': True}},
        {'dev': {'auto_approve': True}, 'prod': {'auto_approve': False, 'requires_change': True}},
        {},
    ])
    def test_action_impact_rules_serialization(self, impact_rules):
        """Test impact_rules JSON serialization."""
        action = Action.objects.create(
            name=f'Impact Action {hash(str(impact_rules))}',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user,
            integration=self.integration
        )

        action.impact_rules = impact_rules
        action.save()

        action.refresh_from_db()
        loaded = action.impact_rules

        assert loaded == impact_rules
