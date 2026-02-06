"""
Factory classes for generating test data using factory-boy.

Story M.9: Tests unitaires et d'intégration
This module provides DjangoModelFactory subclasses for all Django models.
"""

import json
import factory
from factory.django import DjangoModelFactory
from faker import Faker
from django.utils import timezone

fake = Faker()


# ============================================================================
# User Factory
# ============================================================================

class UserFactory(DjangoModelFactory):
    """Factory for idp_auth.User model."""

    class Meta:
        model = 'idp_auth.User'

    username = factory.Sequence(lambda n: f'user{n}')
    display_name = factory.LazyAttribute(lambda o: fake.name())
    profile = 'DBA'
    saml_subject = factory.LazyAttribute(lambda o: f'{o.username}@example.com')


# ============================================================================
# Integration Factory
# ============================================================================

class IntegrationFactory(DjangoModelFactory):
    """Factory for integrations.Integration model."""

    class Meta:
        model = 'integrations.Integration'

    type = 'aap'
    name = factory.Sequence(lambda n: f'Integration {n}')
    base_url = factory.LazyAttribute(lambda o: f'https://{o.type}.example.com')
    credential_ref = factory.LazyAttribute(lambda o: f'vault/path/{o.type}/credentials')
    icon = None
    auth_flow = 'token'
    token_url = factory.LazyAttribute(lambda o: f'https://{o.type}.example.com/oauth/token')
    config = factory.LazyFunction(lambda: json.dumps({'timeout': 30, 'verify_ssl': True}))


# ============================================================================
# Action Factory
# ============================================================================

class ActionFactory(DjangoModelFactory):
    """Factory for catalog.Action model."""

    class Meta:
        model = 'catalog.Action'

    name = factory.Sequence(lambda n: f'Action {n}')
    description = factory.LazyAttribute(lambda o: fake.text(200))
    category = 'Provisioning'
    engine = 'Oracle'
    platform = 'AAP'
    status = 'draft'
    item_type = 'action'
    default_impact_level = 'medium'

    # JSON fields as serialized strings
    parameters_schema = factory.LazyFunction(lambda: json.dumps({
        "type": "object",
        "properties": {
            "target_host": {"type": "string", "description": "Target database host"},
            "database_name": {"type": "string", "description": "Database SID/name"}
        },
        "required": ["target_host", "database_name"]
    }))

    impact_rules = factory.LazyFunction(lambda: json.dumps({
        "dev": {"requires_change": False, "auto_approve": True},
        "staging": {"requires_change": True, "auto_approve": False},
        "prod": {"requires_change": True, "auto_approve": False}
    }))

    execution_steps = factory.LazyFunction(lambda: json.dumps([
        {"name": "Fetch credentials", "type": "vault"},
        {"name": "Create change ticket", "type": "servicenow"},
        {"name": "Execute on platform", "type": "platform"}
    ]))

    change_type_config = factory.LazyFunction(lambda: json.dumps({
        "model": "standard",
        "category": "database",
        "assignment_group": "DBA-Team"
    }))

    documentation_md = factory.LazyAttribute(lambda o: f"# {o.name}\n\nThis action performs database operations.")

    remediation_rules = factory.LazyFunction(lambda: json.dumps({
        "on_failure": [
            {"condition": "ORA-01017", "action": "notify_dba", "severity": "high"},
            {"condition": "ORA-00942", "action": "retry", "max_retries": 3}
        ]
    }))

    created_by = factory.SubFactory(UserFactory)
    integration = factory.SubFactory(IntegrationFactory)


# ============================================================================
# Tag Factory
# ============================================================================

class TagFactory(DjangoModelFactory):
    """Factory for catalog.Tag model."""

    class Meta:
        model = 'catalog.Tag'

    name = factory.Sequence(lambda n: f'tag{n}')


class ActionTagFactory(DjangoModelFactory):
    """Factory for catalog.ActionTag model."""

    class Meta:
        model = 'catalog.ActionTag'

    action = factory.SubFactory(ActionFactory)
    tag = factory.SubFactory(TagFactory)


# ============================================================================
# User Favorite Factory
# ============================================================================

class UserFavoriteFactory(DjangoModelFactory):
    """Factory for catalog.UserFavorite model."""

    class Meta:
        model = 'catalog.UserFavorite'

    user = factory.SubFactory(UserFactory)
    action = factory.SubFactory(ActionFactory)


# ============================================================================
# Profile Factories
# ============================================================================

class ProfileFactory(DjangoModelFactory):
    """Factory for profiles.Profile model."""

    class Meta:
        model = 'profiles.Profile'

    name = factory.Sequence(lambda n: f'Profile{n}')
    description = factory.LazyAttribute(lambda o: f'Description for {o.name}')
    ad_group = factory.LazyAttribute(lambda o: f'CN={o.name},OU=Groups,DC=example,DC=com')
    is_admin = 0
    is_auditor = 0


class ProfileActionPermissionFactory(DjangoModelFactory):
    """Factory for profiles.ProfileActionPermission model."""

    class Meta:
        model = 'profiles.ProfileActionPermission'

    profile = factory.SubFactory(ProfileFactory)
    permission_type = 'ALL'
    action_ids_json = None
    tag_patterns_json = None
    environments_json = factory.LazyFunction(lambda: json.dumps(['dev', 'staging', 'prod']))


class ProfileTargetPermissionFactory(DjangoModelFactory):
    """Factory for profiles.ProfileTargetPermission model."""

    class Meta:
        model = 'profiles.ProfileTargetPermission'

    profile = factory.SubFactory(ProfileFactory)
    permission_type = 'ALL'
    target_names_json = None
    target_patterns_json = None


# ============================================================================
# Execution Factories
# ============================================================================

class ExecutionFactory(DjangoModelFactory):
    """Factory for executions.Execution model."""

    class Meta:
        model = 'executions.Execution'

    action = factory.SubFactory(ActionFactory)
    user = factory.SubFactory(UserFactory)
    environment = 'dev'
    parameters = factory.LazyFunction(lambda: json.dumps({
        "target_host": "db-dev-01.example.com",
        "database_name": "DEVDB"
    }))
    status = 'SUBMITTED'
    servicenow_change_id = None
    approved_by = None
    approved_at = None
    approval_comment = None
    parent_execution = None
    started_at = None
    completed_at = None


class ExecutionStepFactory(DjangoModelFactory):
    """Factory for executions.ExecutionStep model."""

    class Meta:
        model = 'executions.ExecutionStep'

    execution = factory.SubFactory(ExecutionFactory)
    step_order = factory.Sequence(lambda n: n + 1)
    step_name = factory.LazyAttribute(lambda o: f'Step {o.step_order}')
    step_type = 'platform'
    status = 'PENDING'
    started_at = None
    completed_at = None
    output = None
    platform_job_id = None
    error_message = None


class ScheduledExecutionFactory(DjangoModelFactory):
    """Factory for executions.ScheduledExecution model."""

    class Meta:
        model = 'executions.ScheduledExecution'

    action = factory.SubFactory(ActionFactory)
    user = factory.SubFactory(UserFactory)
    environment = 'dev'
    parameters = factory.LazyFunction(lambda: json.dumps({
        "target_host": "db-dev-01.example.com",
        "database_name": "DEVDB"
    }))
    scheduled_at = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(hours=1))
    status = 'pending'


class RecurringPatternFactory(DjangoModelFactory):
    """Factory for executions.RecurringPattern model."""

    class Meta:
        model = 'executions.RecurringPattern'

    scheduled_execution = factory.SubFactory(ScheduledExecutionFactory)
    pattern_type = 'daily'
    pattern_config = factory.LazyFunction(lambda: json.dumps({
        "time": "02:00",
        "timezone": "UTC"
    }))
    next_execution_date = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(days=1))
    is_active = 1


# ============================================================================
# Audit Log Factory
# ============================================================================

class AuditLogFactory(DjangoModelFactory):
    """Factory for core.AuditLog model."""

    class Meta:
        model = 'core.AuditLog'

    user_id = factory.Sequence(lambda n: f'user{n}')
    action_type = 'ACTION_CREATED'
    entity_type = 'action'
    entity_id = factory.Sequence(lambda n: n + 1)
    details = factory.LazyFunction(lambda: json.dumps({
        "action": "created",
        "source": "test"
    }))
    ip_address = factory.LazyAttribute(lambda o: fake.ipv4())
    correlation_id = factory.LazyAttribute(lambda o: fake.uuid4())


# ============================================================================
# Batch Factories for Performance Tests
# ============================================================================

class ActionBatchFactory:
    """Helper for creating multiple actions efficiently."""

    @staticmethod
    def create_batch(count, user, integration, **kwargs):
        """Create multiple actions with the same user and integration."""
        return ActionFactory.create_batch(
            count,
            created_by=user,
            integration=integration,
            **kwargs
        )


class ExecutionBatchFactory:
    """Helper for creating multiple executions efficiently."""

    @staticmethod
    def create_batch(count, action, user, **kwargs):
        """Create multiple executions for the same action."""
        return ExecutionFactory.create_batch(
            count,
            action=action,
            user=user,
            **kwargs
        )


class AuditLogBatchFactory:
    """Helper for creating multiple audit log entries efficiently."""

    @staticmethod
    def create_batch(count, user_id='test_user', **kwargs):
        """Create multiple audit log entries."""
        return AuditLogFactory.create_batch(
            count,
            user_id=user_id,
            **kwargs
        )
