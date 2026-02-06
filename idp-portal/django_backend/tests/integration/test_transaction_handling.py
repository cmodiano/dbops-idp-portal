"""
Transaction and rollback tests.

Story M.9: Tests unitaires et d'intégration
Tests atomic transactions in services and rollback behavior.
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.db import transaction, IntegrityError

from idp_auth.models import User
from catalog.models import Action, ActionStatus, Tag, ActionTag
from integrations.models import Integration
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from executions.models import Execution, ExecutionStatus, ExecutionStep
from core.models import AuditLog


@pytest.mark.django_db(transaction=True)
@pytest.mark.transaction
class TestActionTransactions(TransactionTestCase):
    """Tests for action creation with transaction handling."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='txn_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Txn AAP',
            base_url='https://aap.example.com'
        )

    def test_action_creation_atomic_success(self):
        """Test that action creation in atomic block commits all changes."""
        with transaction.atomic():
            action = Action.objects.create(
                name='Atomic Action',
                category='Provisioning',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.DRAFT,
                created_by=self.user,
                integration=self.integration
            )

            tag = Tag.objects.create(name='atomic-tag')
            ActionTag.objects.create(action=action, tag=tag)

            AuditLog.objects.create_entry(
                user_id=str(self.user.id),
                action_type='ACTION_CREATED',
                entity_type='action',
                entity_id=action.id
            )

        # Verify all objects created
        self.assertEqual(Action.objects.filter(name='Atomic Action').count(), 1)
        self.assertEqual(Tag.objects.filter(name='atomic-tag').count(), 1)
        self.assertEqual(ActionTag.objects.filter(action=action).count(), 1)
        self.assertGreaterEqual(
            AuditLog.objects.filter(entity_type='action', entity_id=action.id).count(),
            1
        )

    def test_action_creation_rollback_on_error(self):
        """Test that action creation rolls back on error."""
        initial_action_count = Action.objects.count()
        initial_tag_count = Tag.objects.count()

        try:
            with transaction.atomic():
                action = Action.objects.create(
                    name='Rollback Action',
                    category='Provisioning',
                    engine='Oracle',
                    platform='AAP',
                    status=ActionStatus.DRAFT,
                    created_by=self.user,
                    integration=self.integration
                )

                tag = Tag.objects.create(name='rollback-tag')
                ActionTag.objects.create(action=action, tag=tag)

                # Force an error
                raise ValueError("Simulated error for rollback test")

        except ValueError:
            pass

        # Verify rollback - objects should not exist
        self.assertEqual(Action.objects.count(), initial_action_count)
        self.assertEqual(Tag.objects.count(), initial_tag_count)

    def test_action_with_duplicate_name_rolls_back(self):
        """Test that duplicate action name causes rollback."""
        # Create first action
        Action.objects.create(
            name='Unique Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            created_by=self.user,
            integration=self.integration
        )

        initial_count = Action.objects.count()

        try:
            with transaction.atomic():
                # Try to create duplicate
                Action.objects.create(
                    name='Unique Action',  # Duplicate name
                    category='Patching',
                    engine='Oracle',
                    platform='AAP',
                    status=ActionStatus.DRAFT,
                    created_by=self.user,
                    integration=self.integration
                )
        except IntegrityError:
            pass

        # Count should not have increased
        self.assertEqual(Action.objects.count(), initial_count)


@pytest.mark.django_db(transaction=True)
@pytest.mark.transaction
class TestProfileTransactions(TransactionTestCase):
    """Tests for profile creation with transaction handling."""

    def test_profile_with_permissions_atomic(self):
        """Test that profile + permissions creation is atomic."""
        with transaction.atomic():
            profile = Profile.objects.create(
                name='Atomic Profile',
                ad_group='CN=AtomicProfile,OU=Groups,DC=corp,DC=com',
                is_admin=0
            )

            ProfileActionPermission.objects.create(
                profile=profile,
                permission_type='ALL'
            )

            ProfileTargetPermission.objects.create(
                profile=profile,
                permission_type='ALL'
            )

        # Verify all created
        self.assertEqual(Profile.objects.filter(name='Atomic Profile').count(), 1)
        self.assertEqual(ProfileActionPermission.objects.filter(profile=profile).count(), 1)
        self.assertEqual(ProfileTargetPermission.objects.filter(profile=profile).count(), 1)

    def test_profile_permissions_rollback_on_error(self):
        """Test that profile creation rolls back if permission fails."""
        initial_profile_count = Profile.objects.count()

        try:
            with transaction.atomic():
                profile = Profile.objects.create(
                    name='Rollback Profile',
                    ad_group='CN=RollbackProfile,OU=Groups,DC=corp,DC=com',
                    is_admin=0
                )

                # Create valid permission
                ProfileActionPermission.objects.create(
                    profile=profile,
                    permission_type='ALL'
                )

                # Force error
                raise ValueError("Simulated error")

        except ValueError:
            pass

        # Profile should not exist
        self.assertEqual(Profile.objects.count(), initial_profile_count)


@pytest.mark.django_db(transaction=True)
@pytest.mark.transaction
class TestExecutionTransactions(TransactionTestCase):
    """Tests for execution creation with transaction handling."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='exec_txn_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Exec Txn AAP',
            base_url='https://aap.example.com'
        )
        self.action = Action.objects.create(
            name='Exec Txn Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            integration=self.integration
        )

    def test_execution_with_steps_atomic(self):
        """Test that execution + steps creation is atomic."""
        with transaction.atomic():
            execution = Execution.objects.create(
                action=self.action,
                user=self.user,
                environment='dev',
                status=ExecutionStatus.SUBMITTED
            )

            ExecutionStep.objects.create(
                execution=execution,
                step_order=1,
                step_name='Step 1',
                step_type='vault',
                status='PENDING'
            )

            ExecutionStep.objects.create(
                execution=execution,
                step_order=2,
                step_name='Step 2',
                step_type='platform',
                status='PENDING'
            )

            AuditLog.objects.create_entry(
                user_id=str(self.user.id),
                action_type='EXECUTION_SUBMITTED',
                entity_type='execution',
                entity_id=execution.id
            )

        # Verify all created
        self.assertEqual(Execution.objects.filter(action=self.action).count(), 1)
        self.assertEqual(ExecutionStep.objects.filter(execution=execution).count(), 2)

    def test_execution_steps_rollback_on_error(self):
        """Test that execution creation rolls back if step fails."""
        initial_exec_count = Execution.objects.count()

        try:
            with transaction.atomic():
                execution = Execution.objects.create(
                    action=self.action,
                    user=self.user,
                    environment='dev',
                    status=ExecutionStatus.SUBMITTED
                )

                ExecutionStep.objects.create(
                    execution=execution,
                    step_order=1,
                    step_name='Step 1',
                    step_type='vault',
                    status='PENDING'
                )

                # Force error
                raise ValueError("Simulated step creation error")

        except ValueError:
            pass

        # Execution should not exist
        self.assertEqual(Execution.objects.count(), initial_exec_count)


@pytest.mark.django_db(transaction=True)
@pytest.mark.transaction
class TestNestedTransactions(TransactionTestCase):
    """Tests for nested transactions (savepoints)."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='nested_user', profile='DBA')
        self.integration = Integration.objects.create(
            type='aap',
            name='Nested AAP',
            base_url='https://aap.example.com'
        )

    def test_nested_atomic_partial_rollback(self):
        """Test that nested atomic blocks can have partial rollback."""
        # Create outer action
        with transaction.atomic():
            outer_action = Action.objects.create(
                name='Outer Action',
                category='Provisioning',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.DRAFT,
                created_by=self.user,
                integration=self.integration
            )

            try:
                with transaction.atomic():
                    # Create inner action
                    inner_action = Action.objects.create(
                        name='Inner Action',
                        category='Patching',
                        engine='Oracle',
                        platform='AAP',
                        status=ActionStatus.DRAFT,
                        created_by=self.user,
                        integration=self.integration
                    )

                    # Force error in inner block
                    raise ValueError("Inner block error")

            except ValueError:
                # Inner block rolled back, outer continues
                pass

            # Create another action in outer block
            another_action = Action.objects.create(
                name='Another Action',
                category='Administration',
                engine='Oracle',
                platform='AAP',
                status=ActionStatus.DRAFT,
                created_by=self.user,
                integration=self.integration
            )

        # Outer and another should exist, inner should not
        self.assertEqual(Action.objects.filter(name='Outer Action').count(), 1)
        self.assertEqual(Action.objects.filter(name='Inner Action').count(), 0)
        self.assertEqual(Action.objects.filter(name='Another Action').count(), 1)


@pytest.mark.django_db(transaction=True)
@pytest.mark.transaction
class TestTransactionIsolation(TransactionTestCase):
    """Tests for transaction isolation behavior."""

    def test_concurrent_unique_constraint(self):
        """Test that unique constraint is enforced across transactions."""
        from django.db import connection

        # Create initial user
        User.objects.create(username='isolation_test', profile='DBA')

        # Try to create duplicate - should fail
        try:
            User.objects.create(username='isolation_test', profile='DBOPS')
            self.fail("Should have raised IntegrityError")
        except IntegrityError:
            pass

        # Only one user should exist
        self.assertEqual(User.objects.filter(username='isolation_test').count(), 1)

    def test_select_for_update(self):
        """Test SELECT FOR UPDATE locks the row."""
        user = User.objects.create(username='lock_test', profile='DBA')

        with transaction.atomic():
            # Lock the row
            locked_user = User.objects.select_for_update().get(id=user.id)
            locked_user.profile = 'DBOPS'
            locked_user.save()

        # Verify update
        user.refresh_from_db()
        self.assertEqual(user.profile, 'DBOPS')
