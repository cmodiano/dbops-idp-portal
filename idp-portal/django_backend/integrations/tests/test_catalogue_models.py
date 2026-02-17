"""
Story 24.1: Tests for IntegrationTypeCatalogue and IntegrationAction models.
"""

import json
import pytest
from django.db import IntegrityError

from integrations.models import IntegrationAction
from tests.factories import IntegrationTypeCatalogueFactory, IntegrationActionFactory


@pytest.mark.django_db
class TestIntegrationTypeCatalogueModel:
    """Tests for IntegrationTypeCatalogue model."""

    def test_create_type(self):
        t = IntegrationTypeCatalogueFactory(code='aap', name='AAP')
        assert t.code == 'aap'
        assert t.name == 'AAP'
        assert t.is_active is True
        assert t.version == '1.0'

    def test_str_representation(self):
        t = IntegrationTypeCatalogueFactory(code='aap', name='AAP')
        assert str(t) == 'aap (AAP)'

    def test_default_is_active(self):
        t = IntegrationTypeCatalogueFactory()
        assert t.is_active is True

    def test_timestamps_auto_set(self):
        t = IntegrationTypeCatalogueFactory()
        assert t.created_at is not None
        assert t.updated_at is not None

    def test_duplicate_code_raises_error(self):
        IntegrationTypeCatalogueFactory(code='dup')
        with pytest.raises(IntegrityError):
            IntegrationTypeCatalogueFactory(code='dup')

    def test_inactive_type(self):
        t = IntegrationTypeCatalogueFactory(is_active=False)
        assert t.is_active is False


@pytest.mark.django_db
class TestIntegrationActionModel:
    """Tests for IntegrationAction model."""

    def test_create_action(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        a = IntegrationActionFactory(
            integration_type=t,
            action_code='start_job',
            action_label='Démarrer un job',
        )
        assert a.integration_type == t
        assert a.action_code == 'start_job'
        assert a.action_label == 'Démarrer un job'
        assert a.is_active is True

    def test_str_representation(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        a = IntegrationActionFactory(integration_type=t, action_code='start_job')
        assert str(a) == 'aap:start_job'

    def test_foreign_key_relation(self):
        t = IntegrationTypeCatalogueFactory(code='sn')
        IntegrationActionFactory(integration_type=t, action_code='a1')
        IntegrationActionFactory(integration_type=t, action_code='a2')
        assert t.actions.count() == 2

    def test_cascade_delete(self):
        t = IntegrationTypeCatalogueFactory(code='del_test')
        IntegrationActionFactory(integration_type=t, action_code='a1')
        IntegrationActionFactory(integration_type=t, action_code='a2')
        t.delete()
        assert IntegrationAction.objects.filter(integration_type__code='del_test').count() == 0

    def test_unique_together_type_action_code(self):
        t = IntegrationTypeCatalogueFactory(code='uniq')
        IntegrationActionFactory(integration_type=t, action_code='same')
        with pytest.raises(IntegrityError):
            IntegrationActionFactory(integration_type=t, action_code='same')

    def test_get_required_params(self):
        schema = {"type": "object", "properties": {"id": {"type": "integer"}}}
        a = IntegrationActionFactory(required_params=json.dumps(schema))
        assert a.get_required_params() == schema

    def test_set_required_params(self):
        a = IntegrationActionFactory()
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        a.set_required_params(schema)
        assert json.loads(a.required_params) == schema

    def test_get_optional_params(self):
        schema = {"type": "object", "properties": {"opt": {"type": "string"}}}
        a = IntegrationActionFactory(optional_params=json.dumps(schema))
        assert a.get_optional_params() == schema

    def test_set_optional_params(self):
        a = IntegrationActionFactory()
        schema = {"type": "object"}
        a.set_optional_params(schema)
        assert json.loads(a.optional_params) == schema

    def test_get_response_format(self):
        fmt = {"job_id": "integer", "status": "string"}
        a = IntegrationActionFactory(response_format=json.dumps(fmt))
        assert a.get_response_format() == fmt

    def test_set_response_format(self):
        a = IntegrationActionFactory()
        fmt = {"result": "boolean"}
        a.set_response_format(fmt)
        assert json.loads(a.response_format) == fmt

    def test_get_required_params_invalid_json(self):
        a = IntegrationActionFactory()
        a.required_params = 'not-json'
        assert a.get_required_params() == {}

    def test_get_optional_params_empty(self):
        a = IntegrationActionFactory(optional_params='')
        assert a.get_optional_params() == {}

    def test_get_response_format_empty_string(self):
        a = IntegrationActionFactory(response_format='')
        assert a.get_response_format() == {}

    def test_set_required_params_none(self):
        a = IntegrationActionFactory()
        a.set_required_params(None)
        assert a.required_params == '{}'

    def test_timestamps_auto_set(self):
        a = IntegrationActionFactory()
        assert a.created_at is not None
        assert a.updated_at is not None
