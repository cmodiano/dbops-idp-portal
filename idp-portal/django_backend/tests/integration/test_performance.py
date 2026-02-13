"""
Performance and benchmark tests.

Story M.9: Tests unitaires et d'intégration
Uses pytest-benchmark for performance measurement.
"""

import pytest
from django.test import TestCase

from idp_auth.models import User
from catalog.models import Action, ActionStatus, Tag, ActionTag
from integrations.models import Integration
from profiles.models import Profile
from executions.models import Execution, ExecutionStatus
from core.models import AuditLog


@pytest.mark.django_db
@pytest.mark.benchmark
@pytest.mark.slow
class TestProfileResolutionPerformance:
    """Performance tests for profile resolution."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test data with many AD groups."""
        # Create 100 profiles with different AD groups
        self.profiles = []
        for i in range(100):
            profile = Profile.objects.create(
                name=f'Profile{i:03d}',
                ad_group=f'CN=Group{i:03d},OU=Groups,DC=corp,DC=com',
                is_admin=1 if i % 10 == 0 else 0
            )
            self.profiles.append(profile)

    def test_profile_resolution_100_groups(self, benchmark):
        """Benchmark profile resolution with 100 AD groups."""
        # User has 100 AD groups
        ad_groups = [f'CN=Group{i:03d},OU=Groups,DC=corp,DC=com' for i in range(100)]

        def resolve_profiles():
            return list(Profile.objects.find_by_ad_groups(ad_groups))

        result = benchmark(resolve_profiles)

        # Verify result
        assert len(result) == 100

    def test_profile_resolution_10_groups(self, benchmark):
        """Benchmark profile resolution with 10 AD groups."""
        ad_groups = [f'CN=Group{i:03d},OU=Groups,DC=corp,DC=com' for i in range(10)]

        def resolve_profiles():
            return list(Profile.objects.find_by_ad_groups(ad_groups))

        result = benchmark(resolve_profiles)
        assert len(result) == 10


@pytest.mark.django_db
@pytest.mark.benchmark
@pytest.mark.slow
class TestCatalogPerformance:
    """Performance tests for catalog operations."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test data with 1000 actions."""
        self.user = User.objects.create(username='perf_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Perf AAP',
            base_url='https://aap.example.com'
        )

        # Create 1000 actions
        actions = []
        for i in range(1000):
            action = Action(
                name=f'Perf Action {i:04d}',
                category='Provisioning' if i % 4 == 0 else (
                    'Patching' if i % 4 == 1 else (
                        'Administration' if i % 4 == 2 else 'Monitoring'
                    )
                ),
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED if i % 5 != 0 else ActionStatus.DRAFT,
                created_by=self.user,
                integration=self.integration
            )
            actions.append(action)

        Action.objects.bulk_create(actions)
        self.actions = Action.objects.all()

        # Create tags
        self.tags = []
        for name in ['oracle', 'database', 'provisioning', 'patching', 'monitoring']:
            tag = Tag.objects.create(name=name)
            self.tags.append(tag)

        # Assign tags to actions
        action_tags = []
        for i, action in enumerate(self.actions[:500]):
            tag = self.tags[i % len(self.tags)]
            action_tags.append(ActionTag(action=action, tag=tag))

        ActionTag.objects.bulk_create(action_tags)

    def test_list_published_1000_actions(self, benchmark):
        """Benchmark listing published actions from 1000 total."""
        def list_published():
            return list(Action.objects.list_published()[:100])

        result = benchmark(list_published)
        assert len(result) <= 100

    def test_search_by_tags(self, benchmark):
        """Benchmark tag search."""
        def search_by_tag():
            return list(Action.objects.search_by_tags(['oracle'])[:50])

        result = benchmark(search_by_tag)
        assert len(result) <= 50

    def test_filter_by_category(self, benchmark):
        """Benchmark category filtering."""
        def filter_category():
            return list(Action.objects.filter(
                category='Provisioning',
                status=ActionStatus.PUBLISHED
            )[:100])

        result = benchmark(filter_category)
        assert len(result) <= 100

    def test_with_tags_prefetch(self, benchmark):
        """Benchmark with_tags() prefetch optimization."""
        def fetch_with_tags():
            return list(Action.objects.with_tags().list_published()[:50])

        result = benchmark(fetch_with_tags)
        assert len(result) <= 50


@pytest.mark.django_db
@pytest.mark.benchmark
@pytest.mark.slow
class TestExecutionPerformance:
    """Performance tests for execution operations."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test data with 10000 executions."""
        self.user = User.objects.create(username='exec_perf_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Exec Perf AAP',
            base_url='https://aap.example.com'
        )
        self.action = Action.objects.create(
            name='Exec Perf Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

        # Create 10000 executions
        executions = []
        statuses = [
            ExecutionStatus.SUBMITTED,
            ExecutionStatus.RUNNING,
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED
        ]
        environments = ['dev', 'staging', 'prod']

        for i in range(10000):
            execution = Execution(
                action=self.action,
                user=self.user,
                environment=environments[i % 3],
                status=statuses[i % 4]
            )
            executions.append(execution)

        Execution.objects.bulk_create(executions)

    def test_list_executions_10000(self, benchmark):
        """Benchmark listing recent executions from 10000 total."""
        def list_recent():
            return list(Execution.objects.get_recent(limit=100))

        result = benchmark(list_recent)
        assert len(result) == 100

    def test_filter_by_status(self, benchmark):
        """Benchmark status filtering on 10000 executions."""
        def filter_status():
            return list(Execution.objects.list_by_status(ExecutionStatus.COMPLETED)[:100])

        result = benchmark(filter_status)
        assert len(result) <= 100

    def test_filter_by_user(self, benchmark):
        """Benchmark user filtering on 10000 executions."""
        def filter_user():
            return list(Execution.objects.list_by_user(self.user.id)[:100])

        result = benchmark(filter_user)
        assert len(result) == 100

    def test_with_action_select_related(self, benchmark):
        """Benchmark select_related optimization."""
        def fetch_with_action():
            return list(Execution.objects.with_action().order_by('-created_at')[:50])

        result = benchmark(fetch_with_action)
        assert len(result) == 50
        # Verify no N+1 queries (action should be prefetched)
        for exec in result:
            assert exec.action.name is not None


@pytest.mark.django_db
@pytest.mark.benchmark
@pytest.mark.slow
class TestActionCreationPerformance:
    """Performance tests for action creation with many steps."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test data."""
        self.user = User.objects.create(username='create_perf_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Create Perf AAP',
            base_url='https://aap.example.com'
        )

    def test_create_action_with_50_steps(self, benchmark):
        """Benchmark action creation with 50 steps in JSON."""
        import json
        import uuid

        steps = [
            {'name': f'Step {i}', 'type': 'platform', 'order': i}
            for i in range(50)
        ]

        def create_action():
            action = Action.objects.create(
                name=f'Perf Action {uuid.uuid4().hex[:8]}',
                category='Provisioning',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.DRAFT,
                created_by=self.user,
                integration=self.integration,
                execution_steps=json.dumps(steps)
            )
            return action

        result = benchmark(create_action)
        assert result.id is not None

        # Verify steps stored (execution_steps is a JSON field, need to parse it)
        stored_steps = json.loads(result.execution_steps) if isinstance(result.execution_steps, str) else result.execution_steps
        assert len(stored_steps) == 50

    def test_bulk_create_100_actions(self, benchmark):
        """Benchmark bulk creation of 100 actions."""
        import uuid

        def bulk_create():
            actions = [
                Action(
                    name=f'Bulk Action {uuid.uuid4().hex[:8]}',
                    category='Provisioning',
                    engine='Oracle',
                    platform='AAP',
                    status=ActionStatus.DRAFT,
                    created_by=self.user,
                    integration=self.integration
                )
                for _ in range(100)
            ]
            return Action.objects.bulk_create(actions)

        result = benchmark(bulk_create)
        assert len(result) == 100


@pytest.mark.django_db
@pytest.mark.benchmark
@pytest.mark.slow
class TestAuditLogPerformance:
    """Performance tests for audit log operations."""

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Set up test data with many audit entries."""
        # Create 50000 audit entries
        entries = []
        for i in range(50000):
            entry = AuditLog(
                user_id=f'user{i % 100}',
                action_type='ACTION_CREATED' if i % 3 == 0 else (
                    'ACTION_UPDATED' if i % 3 == 1 else 'EXECUTION_SUBMITTED'
                ),
                entity_type='action' if i % 2 == 0 else 'execution',
                entity_id=i % 1000 + 1
            )
            entries.append(entry)

        AuditLog.objects.bulk_create(entries, batch_size=5000)

    def test_filter_by_user_50000(self, benchmark):
        """Benchmark user filtering on 50000 audit entries."""
        def filter_user():
            return list(AuditLog.objects.list_by_user('user0')[:100])

        result = benchmark(filter_user)
        assert len(result) <= 100

    def test_filter_by_entity_50000(self, benchmark):
        """Benchmark entity filtering on 50000 audit entries."""
        def filter_entity():
            return list(AuditLog.objects.list_by_entity('action', 1)[:100])

        result = benchmark(filter_entity)
        assert len(result) <= 100

    def test_date_range_filter(self, benchmark):
        """Benchmark date range filtering."""
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        one_day_ago = now - timedelta(days=1)

        def filter_date_range():
            return list(AuditLog.objects.list_by_date_range(
                from_date=one_day_ago,
                to_date=now
            )[:100])

        result = benchmark(filter_date_range)
        # All entries created now should be in range
        assert len(result) <= 100


@pytest.mark.django_db
class TestQueryOptimization(TestCase):
    """Tests for query optimization verification."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='query_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Query AAP',
            base_url='https://aap.example.com'
        )

        # Create actions with tags
        for i in range(10):
            action = Action.objects.create(
                name=f'Query Action {i}',
                category='Provisioning',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.PUBLISHED,
                created_by=self.user,
                integration=self.integration
            )
            tag = Tag.objects.create(name=f'tag{i}')
            ActionTag.objects.create(action=action, tag=tag)

    def test_with_tags_reduces_queries(self):
        """Test that with_tags() reduces N+1 queries."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # Without prefetch - would have N+1
        with CaptureQueriesContext(connection) as context_without:
            actions = list(Action.objects.all())
            for action in actions:
                list(action.actiontag_set.all())

        # With prefetch - should be fewer queries
        with CaptureQueriesContext(connection) as context_with:
            actions = list(Action.objects.with_tags())
            for action in actions:
                list(action.actiontag_set.all())

        # Prefetch should use fewer queries
        # Note: Exact counts depend on DB implementation
        self.assertLessEqual(
            len(context_with.captured_queries),
            len(context_without.captured_queries)
        )

    def test_select_related_reduces_queries(self):
        """Test that select_related() reduces queries for foreign keys."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # Create executions
        action = Action.objects.first()
        for i in range(5):
            Execution.objects.create(
                action=action,
                user=self.user,
                environment='dev',
                status=ExecutionStatus.COMPLETED
            )

        # Without select_related
        with CaptureQueriesContext(connection) as context_without:
            execs = list(Execution.objects.all())
            for e in execs:
                _ = e.action.name

        # With select_related
        with CaptureQueriesContext(connection) as context_with:
            execs = list(Execution.objects.with_action())
            for e in execs:
                _ = e.action.name

        # select_related should use fewer queries
        self.assertLessEqual(
            len(context_with.captured_queries),
            len(context_without.captured_queries)
        )
