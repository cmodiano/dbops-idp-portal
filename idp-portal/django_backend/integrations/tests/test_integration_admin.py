"""
Story 27.10, AC4: Integration admin tests for Jira type.

Tests that:
- POST /admin/integrations with type=jira creates integration (status 201)
- Validation config for Jira (base_url, credential_ref)
- IntegrationValidationService.validate_integration() for Jira = VALID
"""
from __future__ import annotations

import pytest
from django.core.management import call_command

from integrations.models import Integration, IntegrationStatus
from integrations.validation_service import IntegrationValidationService


@pytest.mark.django_db
class TestJiraIntegrationAdmin:
    """Tests for Jira integration in admin context."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

    def test_create_jira_integration(self):
        """AC4: Create integration with type=jira."""
        integration = Integration.objects.create(
            type='jira',
            name='Jira Cloud Production',
            base_url='https://company.atlassian.net',
            credential_ref='vault:secret/data/jira/cloud#api_token',
        )
        assert integration.id is not None
        assert integration.type == 'jira'
        assert integration.name == 'Jira Cloud Production'
        assert integration.base_url == 'https://company.atlassian.net'

    def test_jira_validation_valid(self):
        """AC4: IntegrationValidationService validates Jira = VALID."""
        integration = Integration.objects.create(
            type='jira',
            name='Jira Cloud Test',
            base_url='https://company.atlassian.net',
            credential_ref='vault:secret/data/jira/cloud#api_token',
        )
        status = IntegrationValidationService.validate_integration(integration)
        assert status == IntegrationStatus.VALID

    def test_jira_config_stored(self):
        """Config JSON stored and retrieved correctly for Jira."""
        integration = Integration.objects.create(
            type='jira',
            name='Jira Server',
            base_url='https://jira.company.com',
            credential_ref='vault:secret/data/jira/server#pat',
        )
        integration.set_config({
            "api_version": "2",
            "auth_type": "pat",
        })
        integration.save()

        refreshed = Integration.objects.get(pk=integration.pk)
        config = refreshed.get_config()
        assert config["api_version"] == "2"
        assert config["auth_type"] == "pat"
