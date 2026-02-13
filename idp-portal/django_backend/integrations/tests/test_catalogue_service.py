"""
Story 24.1: Tests for IntegrationCatalogueService.
"""

import pytest

from integrations.catalogue_service import IntegrationCatalogueService
from tests.factories import IntegrationTypeCatalogueFactory, IntegrationActionFactory


@pytest.mark.django_db
class TestIntegrationCatalogueService:
    """Tests for IntegrationCatalogueService methods."""

    def test_list_all_types_returns_active(self):
        IntegrationTypeCatalogueFactory(code='aap', is_active=True)
        IntegrationTypeCatalogueFactory(code='sn', is_active=True)
        IntegrationTypeCatalogueFactory(code='old', is_active=False)
        result = list(IntegrationCatalogueService.list_all_types())
        codes = [t.code for t in result]
        assert 'aap' in codes
        assert 'sn' in codes
        assert 'old' not in codes

    def test_list_all_types_empty(self):
        result = list(IntegrationCatalogueService.list_all_types())
        assert result == []

    def test_list_all_types_includes_actions(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='start_job')
        IntegrationActionFactory(integration_type=t, action_code='cancel_job')
        result = list(IntegrationCatalogueService.list_all_types())
        assert result[0].actions.count() == 2

    def test_get_type_by_code_found(self):
        IntegrationTypeCatalogueFactory(code='aap', name='AAP')
        result = IntegrationCatalogueService.get_type_by_code('aap')
        assert result is not None
        assert result.code == 'aap'
        assert result.name == 'AAP'

    def test_get_type_by_code_not_found(self):
        result = IntegrationCatalogueService.get_type_by_code('nonexistent')
        assert result is None

    def test_get_type_by_code_inactive_returns_none(self):
        IntegrationTypeCatalogueFactory(code='old', is_active=False)
        result = IntegrationCatalogueService.get_type_by_code('old')
        assert result is None

    def test_get_type_by_code_prefetches_actions(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='a1')
        result = IntegrationCatalogueService.get_type_by_code('aap')
        # Should be prefetched (no extra query)
        assert result.actions.count() == 1

    def test_list_actions_by_type(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='start_job', is_active=True)
        IntegrationActionFactory(integration_type=t, action_code='cancel_job', is_active=True)
        IntegrationActionFactory(integration_type=t, action_code='old', is_active=False)
        result = list(IntegrationCatalogueService.list_actions_by_type('aap'))
        codes = [a.action_code for a in result]
        assert 'start_job' in codes
        assert 'cancel_job' in codes
        assert 'old' not in codes

    def test_list_actions_by_type_empty(self):
        IntegrationTypeCatalogueFactory(code='empty')
        result = list(IntegrationCatalogueService.list_actions_by_type('empty'))
        assert result == []

    def test_list_actions_by_type_nonexistent_type(self):
        result = list(IntegrationCatalogueService.list_actions_by_type('nonexistent'))
        assert result == []

    def test_get_action_found(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='start_job')
        result = IntegrationCatalogueService.get_action('aap', 'start_job')
        assert result is not None
        assert result.action_code == 'start_job'

    def test_get_action_not_found(self):
        IntegrationTypeCatalogueFactory(code='aap')
        result = IntegrationCatalogueService.get_action('aap', 'nonexistent')
        assert result is None

    def test_get_action_inactive_returns_none(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='old', is_active=False)
        result = IntegrationCatalogueService.get_action('aap', 'old')
        assert result is None

    def test_list_all_types_ordered_by_code(self):
        IntegrationTypeCatalogueFactory(code='zz')
        IntegrationTypeCatalogueFactory(code='aa')
        result = list(IntegrationCatalogueService.list_all_types())
        assert result[0].code == 'aa'
        assert result[1].code == 'zz'
