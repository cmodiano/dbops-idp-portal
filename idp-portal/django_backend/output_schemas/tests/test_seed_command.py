"""
Tests pour la commande de management seed_output_schemas.
Story 63.5 - Schémas d'Output par Défaut (Seed Data).
"""

import pytest
from django.core.management import call_command
from io import StringIO

from output_schemas.models import OutputSchema
from output_schemas.registry import schema_registry


@pytest.mark.django_db
class TestSeedOutputSchemasCommand:

    def test_seed_initial_creates_all_schemas(self):
        """Seed initial : tous les schémas attendus sont créés."""
        assert OutputSchema.objects.count() == 0

        call_command('seed_output_schemas', verbosity=0)

        expected_names = {
            'aap-standard',
            'servicenow-create-change',
            'servicenow-update-change',
            'servicenow-close-change',
            'servicenow-get-change-status',
            'vault-get-secret',
            'notification-send-email',
            'notification-send-teams',
        }
        actual_names = set(OutputSchema.objects.values_list('name', flat=True))
        assert expected_names == actual_names

    def test_seed_idempotent(self):
        """Second appel sans --force : 0 créés, N inchangés."""
        call_command('seed_output_schemas', verbosity=0)
        count_after_first = OutputSchema.objects.count()
        assert count_after_first > 0

        # Second appel : aucun nouveau schéma créé (early return car des schémas existent)
        call_command('seed_output_schemas', verbosity=0)
        count_after_second = OutputSchema.objects.count()

        assert count_after_second == count_after_first

    def test_seed_force_reloads_existing_schemas(self):
        """Mode --force : les schémas sont rechargés même s'ils existent."""
        call_command('seed_output_schemas', verbosity=0)
        initial_count = OutputSchema.objects.count()
        assert initial_count > 0

        # Modifier un schéma manuellement
        schema = OutputSchema.objects.get(name='aap-standard')
        schema.schema_json = {'output_fields': []}
        schema.save()

        # --force doit restaurer les données d'origine
        out = StringIO()
        call_command('seed_output_schemas', force=True, stdout=out, verbosity=0)

        schema.refresh_from_db()
        fields = schema.schema_json.get('output_fields', [])
        field_names = {f['name'] for f in fields}
        assert 'platform_job_id' in field_names
        assert 'job_status' in field_names

    def test_aap_convention_loaded_before_integrations(self):
        """La convention aap-standard est chargée avant les schémas qui pourraient en hériter."""
        call_command('seed_output_schemas', verbosity=0)

        aap = OutputSchema.objects.filter(name='aap-standard').first()
        assert aap is not None
        assert aap.schema_type == 'platform_convention'

        # Les intégrations sont chargées après (leur création n'a pas planté)
        assert OutputSchema.objects.filter(schema_type='integration').count() > 0

    def test_servicenow_create_change_has_required_fields(self):
        """Le schéma servicenow-create-change contient bien change_number et sys_id."""
        call_command('seed_output_schemas', verbosity=0)

        schema = OutputSchema.objects.get(name='servicenow-create-change')
        assert schema.target_name == 'servicenow'
        assert schema.operation == 'create_change'

        fields = schema.schema_json.get('output_fields', [])
        field_names = {f['name'] for f in fields}
        assert 'change_number' in field_names
        assert 'sys_id' in field_names

    def test_cache_registry_invalidated_after_seed(self):
        """Le cache schema_registry est invalidé après le seed (schémas accessibles via registry)."""
        schema_registry.invalidate()

        call_command('seed_output_schemas', verbosity=0)

        # Après le seed, le registry doit résoudre les schémas chargés
        aap_schema = schema_registry.get_platform_convention('aap')
        assert aap_schema is not None
        field_names = {f['name'] for f in aap_schema.get('output_fields', [])}
        assert 'platform_job_id' in field_names

        sn_schema = schema_registry.get_integration_schema('servicenow', 'create_change')
        assert sn_schema is not None
        sn_fields = {f['name'] for f in sn_schema.get('output_fields', [])}
        assert 'change_number' in sn_fields

    def test_seed_force_mode_full_removes_extra_schemas(self):
        """Mode --force --mode=full : les schémas absents du seed sont supprimés."""
        call_command('seed_output_schemas', verbosity=0)

        # Ajouter un schéma hors-seed
        OutputSchema.objects.create(
            name='extra-schema',
            schema_type='integration',
            target_name='extra',
            operation='do_something',
        )
        assert OutputSchema.objects.filter(name='extra-schema').exists()

        # --force --mode=full doit supprimer le schéma hors-seed
        call_command('seed_output_schemas', force=True, mode='full', verbosity=0)

        assert not OutputSchema.objects.filter(name='extra-schema').exists()
        # Les schémas seed sont toujours présents
        assert OutputSchema.objects.filter(name='aap-standard').exists()

    def test_seed_output_message_on_skip(self):
        """Sans --force, si des schémas existent déjà, le message indique de passer --force."""
        call_command('seed_output_schemas', verbosity=0)

        out = StringIO()
        call_command('seed_output_schemas', stdout=out, verbosity=0)
        output = out.getvalue()

        assert '--force' in output
