"""
Story 25.4: change_type_config validation tests.

Tests for validate_change_type_config:
- allowed bool required when present
- requires_maintenance_window, requires_approval bool when present
- required=true → change_model_code required and alphanumeric
- backward compat: no allowed = valid
"""
import pytest
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from catalog.models import Action, ActionStatus, ActionItemType
from catalog.services import CatalogService
from catalog.validators import validate_change_type_config
from reference.models import RefEngine, RefPlatform
from tests.factories import UserFactory


class TestStory254ValidateChangeTypeConfig(TestCase):
    """Task 6.4: change_type_config validation — allowed bool invalide → erreur."""

    def test_allowed_string_rejects(self):
        """allowed as string (e.g. "true") → ValidationError."""
        config = {'dev': {'allowed': 'true'}}
        with self.assertRaises(ValidationError) as ctx:
            validate_change_type_config(config)
        self.assertIn('allowed', str(ctx.exception).lower())
        self.assertIn('booléen', str(ctx.exception).lower())

    def test_allowed_false_accepted(self):
        """allowed=false is valid."""
        validate_change_type_config({'dev': {'allowed': False}})

    def test_allowed_true_accepted(self):
        """allowed=true is valid."""
        validate_change_type_config({'dev': {'allowed': True}})

    def test_requires_maintenance_window_string_rejects(self):
        """requires_maintenance_window as string → ValidationError."""
        config = {'dev': {'requires_maintenance_window': 'yes'}}
        with self.assertRaises(ValidationError) as ctx:
            validate_change_type_config(config)
        self.assertIn('requires_maintenance_window', str(ctx.exception).lower())

    def test_requires_approval_string_rejects(self):
        """requires_approval as string → ValidationError."""
        config = {'dev': {'requires_approval': '1'}}
        with self.assertRaises(ValidationError) as ctx:
            validate_change_type_config(config)
        self.assertIn('requires_approval', str(ctx.exception).lower())

    def test_required_true_empty_change_model_code_rejects(self):
        """required=true with empty change_model_code → ValidationError."""
        config = {'prod': {'required': True, 'change_model_code': ''}}
        with self.assertRaises(ValidationError) as ctx:
            validate_change_type_config(config)
        self.assertIn('change_model_code', str(ctx.exception).lower())

    def test_required_true_change_model_code_non_alphanumeric_rejects(self):
        """required=true with change_model_code containing special chars → ValidationError."""
        config = {'prod': {'required': True, 'change_model_code': '1516-B'}}
        with self.assertRaises(ValidationError) as ctx:
            validate_change_type_config(config)
        self.assertIn('alphanumérique', str(ctx.exception).lower())

    def test_required_true_change_model_code_alphanumeric_accepted(self):
        """required=true with alphanumeric change_model_code → accepted."""
        validate_change_type_config({'prod': {'required': True, 'change_model_code': '1516B'}})

    def test_backward_compat_no_allowed_accepted(self):
        """Config without allowed → accepted (Task 6.5)."""
        validate_change_type_config({'dev': {'required': False}})
        validate_change_type_config({'prod': {'required': True, 'change_model_code': 'PRD001'}})

    def test_required_string_rejects(self):
        """required as string → ValidationError."""
        config = {'dev': {'required': 'yes'}}
        with self.assertRaises(ValidationError) as ctx:
            validate_change_type_config(config)
        self.assertIn('required', str(ctx.exception).lower())

    def test_change_type_non_string_rejects(self):
        """change_type must be a string when present."""
        config = {'dev': {'change_type': 123}}
        with self.assertRaises(ValidationError) as ctx:
            validate_change_type_config(config)
        self.assertIn('change_type', str(ctx.exception).lower())

    def test_template_id_non_string_rejects(self):
        """template_id must be a string when present."""
        config = {'dev': {'template_id': 123}}
        with self.assertRaises(ValidationError) as ctx:
            validate_change_type_config(config)
        self.assertIn('template_id', str(ctx.exception).lower())

    def test_non_dict_top_level_rejects(self):
        """Top-level non-dict should be rejected to avoid persisting corrupted data."""
        with self.assertRaises(ValidationError):
            validate_change_type_config(['bad'])  # type: ignore[arg-type]

    def test_none_config_accepted(self):
        """None config → no error."""
        validate_change_type_config(None)

    def test_empty_config_accepted(self):
        """Empty dict → no error."""
        validate_change_type_config({})


@pytest.mark.django_db
class TestStory254CatalogServiceIntegration(TestCase):
    """Task 6.4: CatalogService.update_execution_steps rejects invalid change_type_config."""

    def setUp(self):
        RefEngine.objects.get_or_create(code='Oracle', defaults={'label': 'Oracle', 'display_order': 1})
        RefPlatform.objects.get_or_create(code='AAP', defaults={'label': 'AAP', 'display_order': 1})
        self.user = UserFactory(username='story254_admin', profile='dbops')
        self.action = Action.objects.create(
            name='Story 25.4 Test',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.DRAFT,
            item_type=ActionItemType.ACTION,
        )

    def test_update_execution_steps_invalid_allowed_raises(self):
        """PUT execution-steps with allowed as string → ValidationError."""
        invalid_config = {'dev': {'allowed': 'true'}}
        steps = [{'order': 1, 'name': 'Step', 'type': 'execution', 'connector_type': 'none', 'conditional_environments': None}]
        with self.assertRaises(ValidationError):
            CatalogService().update_execution_steps(
                action_id=self.action.id,
                steps=steps,
                change_type_config=invalid_config,
                user=self.user,
            )
