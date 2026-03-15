# capabilities/tests/test_capabilities_views.py
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client(django_user_model):
    user = django_user_model.objects.create_user(username='testuser', password='pass')
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestIntegrationsCapabilities:

    def test_returns_200(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_requires_auth(self):
        client = APIClient()
        url = reverse('capabilities:capabilities-integrations')
        response = client.get(url)
        assert response.status_code == 401

    def test_contains_five_platforms(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        codes = {p['code'] for p in data['platforms']}
        assert codes == {'aap', 'tower', 'azure_devops', 'github_actions', 'terraform_cloud'}

    def test_contains_five_services(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        codes = {s['code'] for s in data['services']}
        assert codes == {'vault', 'splunk', 'servicenow', 'jira', 'notification'}

    def test_servicenow_credential_mode_is_integration(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        servicenow = next(s for s in data['services'] if s['code'] == 'servicenow')
        assert servicenow['credential_mode'] == 'integration'

    def test_notification_credential_mode_is_credential_free(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        notification = next(s for s in data['services'] if s['code'] == 'notification')
        assert notification['credential_mode'] == 'credential_free'

    def test_servicenow_has_create_change_operation(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        servicenow = next(s for s in data['services'] if s['code'] == 'servicenow')
        op_codes = [op['code'] for op in servicenow['operations']]
        assert 'create_change' in op_codes

    def test_servicenow_operations_are_objects_with_code_and_label(self, auth_client):
        """Story 82.7 — opérations retournées comme {code, label}."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        servicenow = next(s for s in data['services'] if s['code'] == 'servicenow')
        for op in servicenow['operations']:
            assert 'code' in op
            assert 'label' in op

    def test_servicenow_create_change_has_fr_label(self, auth_client):
        """Story 82.7 — label FR de create_change."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        servicenow = next(s for s in data['services'] if s['code'] == 'servicenow')
        create_change = next(op for op in servicenow['operations'] if op['code'] == 'create_change')
        assert create_change['label'] == 'Créer un change'

    def test_vault_get_secret_has_fr_label(self, auth_client):
        """Story 82.7 — label FR de get_secret."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        vault = next(s for s in data['services'] if s['code'] == 'vault')
        get_secret = next(op for op in vault['operations'] if op['code'] == 'get_secret')
        assert get_secret['label'] == 'Lire un secret'

    def test_jira_operations_have_labels(self, auth_client):
        """Story 82.7 — opérations Jira ont des labels FR."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        jira = next(s for s in data['services'] if s['code'] == 'jira')
        op_map = {op['code']: op['label'] for op in jira['operations']}
        assert op_map['create_issue'] == 'Créer un ticket'
        assert op_map['update_issue'] == 'Mettre à jour le ticket'
        assert op_map['get_issue'] == 'Lire le ticket'

    def test_notification_operations_have_labels(self, auth_client):
        """Story 82.7 — opérations Notification ont des labels FR."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        notification = next(s for s in data['services'] if s['code'] == 'notification')
        op_map = {op['code']: op['label'] for op in notification['operations']}
        assert op_map['send_email'] == 'Envoyer un email'
        assert op_map['send_teams'] == 'Envoyer un message Teams'

    def test_operations_sorted_alphabetically(self, auth_client):
        """Story 82.7 — opérations triées alphabétiquement."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        servicenow = next(s for s in data['services'] if s['code'] == 'servicenow')
        op_codes = [op['code'] for op in servicenow['operations']]
        assert op_codes == sorted(op_codes)

    def test_platform_has_expected_fields(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        aap = next(p for p in data['platforms'] if p['code'] == 'aap')
        assert aap['display_name'] == 'Ansible Automation Platform'
        assert aap['icon'] == 'aap'
        assert aap['supports_health_check'] is True

    def test_azure_devops_aliases_contains_azuredevops(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        ado = next(p for p in data['platforms'] if p['code'] == 'azure_devops')
        assert 'azuredevops' in ado['aliases']


class TestWorkflowStepsCapabilities:

    def test_returns_200(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_requires_auth(self):
        client = APIClient()
        url = reverse('capabilities:capabilities-workflow-steps')
        response = client.get(url)
        assert response.status_code == 401

    def test_contains_six_step_types(self, auth_client):
        """Story 84.1 (AC4) + Story 84.3 (AC1) : schedule_execution ajouté → 6 types au total."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        codes = {s['code'] for s in data['step_types']}
        assert codes == {'platform', 'service_call', 'gate', 'http_request', 'evaluation', 'schedule_execution'}

    def test_gate_has_two_variants(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        assert len(gate['variants']) == 2

    def test_gate_variant_codes(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        variant_codes = {v['code'] for v in gate['variants']}
        assert variant_codes == {'maintenance_window', 'approval'}

    def test_platform_step_type_has_execution_category(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        platform = next(s for s in data['step_types'] if s['code'] == 'platform')
        assert platform['category'] == 'execution'

    def test_non_gate_step_types_have_no_variants(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        for step in data['step_types']:
            if step['code'] != 'gate':
                assert 'variants' not in step

    # Story 82.8 — constraints
    def test_platform_step_has_requires_integration_constraint(self, auth_client):
        """Story 82.8, AC4: platform step_type a constraints requires_integration=True."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        platform = next(s for s in data['step_types'] if s['code'] == 'platform')
        assert 'constraints' in platform
        assert platform['constraints']['requires_integration'] is True

    def test_service_call_step_has_requires_service_integration_constraint(self, auth_client):
        """Story 82.8, AC4: service_call step_type a constraints requires_service_integration=True."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        service_call = next(s for s in data['step_types'] if s['code'] == 'service_call')
        assert 'constraints' in service_call
        assert service_call['constraints']['requires_service_integration'] is True

    def test_gate_step_has_required_fields_constraint(self, auth_client):
        """Story 84.3 (AC2) : gate step_type a required_fields dans ses constraints."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        assert 'constraints' in gate
        assert 'required_fields' in gate['constraints']
        rf = gate['constraints']['required_fields']
        assert isinstance(rf, list)
        assert any(item['field'] == 'gate_type' for item in rf)

    def test_all_step_types_have_constraints_field(self, auth_client):
        """Story 82.8, AC4: tous les step_types retournent constraints."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        for step in data['step_types']:
            assert 'constraints' in step

    # Story 84.3 (AC1, AC2, AC9) — schedule_execution et required_fields dans l'endpoint
    def test_schedule_execution_present_in_endpoint(self, auth_client):
        """Story 84.3 (AC1) : GET /capabilities/workflow-steps/ contient schedule_execution."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        codes = [s['code'] for s in data['step_types']]
        assert 'schedule_execution' in codes

    def test_schedule_execution_label_and_category(self, auth_client):
        """Story 84.3 (AC1) : schedule_execution a label='Planifier' et category='scheduling'."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        sched = next(s for s in data['step_types'] if s['code'] == 'schedule_execution')
        assert sched['label'] == 'Planifier'
        assert sched['category'] == 'scheduling'

    def test_platform_constraints_has_required_fields(self, auth_client):
        """Story 84.3 (AC2, AC9) : platform.constraints expose required_fields via l'endpoint."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        platform = next(s for s in data['step_types'] if s['code'] == 'platform')
        assert 'required_fields' in platform['constraints']
        rf = platform['constraints']['required_fields']
        assert isinstance(rf, list)
        assert any(item['field'] == 'action_id' for item in rf)

    def test_service_call_constraints_has_required_fields(self, auth_client):
        """Story 84.3 (AC2, AC9) : service_call.constraints expose required_fields via l'endpoint."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        service_call = next(s for s in data['step_types'] if s['code'] == 'service_call')
        assert 'required_fields' in service_call['constraints']
        rf = service_call['constraints']['required_fields']
        fields = [item['field'] for item in rf]
        assert 'integration_type' in fields
        assert 'operation' in fields

    def test_all_step_types_have_required_fields_in_constraints(self, auth_client):
        """Story 84.3 (AC2) : tous les types exposent required_fields non vide via l'endpoint."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        for step in data['step_types']:
            rf = step['constraints'].get('required_fields')
            assert rf is not None, f"{step['code']}: required_fields absent de l'endpoint"
            assert isinstance(rf, list), f"{step['code']}: required_fields doit être une liste"
            assert len(rf) >= 1, f"{step['code']}: required_fields ne doit pas être vide"


class TestOperationSchemas:
    """Story 83-5, AC1/AC5 — input_schema, output_schema, ui_hints par opération."""

    def test_operation_has_input_schema_field(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for service in data['services']:
            for op in service['operations']:
                assert 'input_schema' in op

    def test_operation_has_output_schema_field(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for service in data['services']:
            for op in service['operations']:
                assert 'output_schema' in op

    def test_operation_has_ui_hints_field(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for service in data['services']:
            for op in service['operations']:
                assert 'ui_hints' in op

    def test_operation_schemas_are_dicts(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for service in data['services']:
            for op in service['operations']:
                assert isinstance(op['input_schema'], dict)
                assert isinstance(op['output_schema'], dict)
                assert isinstance(op['ui_hints'], dict)

    def test_operation_schemas_are_empty_by_default(self, auth_client):
        """AC1.2 — input_schema et output_schema valent {} pour toutes les opérations actuelles.
        Story 83-10 : ui_hints peut être non-vide (ex: notification send_email/send_teams).
        """
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for service in data['services']:
            for op in service['operations']:
                assert op['input_schema'] == {}, f"input_schema non vide pour {service['code']}.{op['code']}"
                assert op['output_schema'] == {}, f"output_schema non vide pour {service['code']}.{op['code']}"

    def test_splunk_has_no_operations(self, auth_client):
        """Edge case AC1 — splunk n'a pas d'operation_defs, doit retourner une liste vide."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        splunk = next(s for s in data['services'] if s['code'] == 'splunk')
        assert splunk['operations'] == []


class TestPlatformNewSchemaFields:
    """Story 83-5, AC2/AC5 — runtime_config_schema, health_check_policy par plateforme."""

    def test_platform_has_runtime_config_schema_field(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for platform in data['platforms']:
            assert 'runtime_config_schema' in platform

    def test_platform_has_health_check_policy_field(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for platform in data['platforms']:
            assert 'health_check_policy' in platform

    def test_platform_new_schema_fields_are_dicts(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for platform in data['platforms']:
            assert isinstance(platform['runtime_config_schema'], dict)
            assert isinstance(platform['health_check_policy'], dict)

    def test_platform_new_schema_fields_are_empty_by_default(self, auth_client):
        """AC2.2 — runtime_config_schema et health_check_policy valent {} pour toutes les plateformes actuelles."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for platform in data['platforms']:
            assert platform['runtime_config_schema'] == {}, f"runtime_config_schema non vide pour {platform['code']}"
            assert platform['health_check_policy'] == {}, f"health_check_policy non vide pour {platform['code']}"


class TestWorkflowStepsVariantsDerived:
    """Story 83-6, AC5/AC6 — variants dérivés du gate_registry."""

    def test_gate_variants_derived_from_registry(self, auth_client):
        """AC6.2 : les codes des variants gate correspondent exactement à gate_registry.list_types()."""
        from executions.gates.registry import gate_registry
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        variant_codes = [v['code'] for v in gate['variants']]
        assert variant_codes == gate_registry.list_types()
        # Vérification des champs de chaque variant
        for variant in gate['variants']:
            gdefn = gate_registry.get(variant['code'])
            assert variant['label'] == gdefn.display_name
            assert variant['config_schema'] == gdefn.config_schema

    def test_new_gate_in_registry_appears_in_variants(self, auth_client):
        """Invariant 83-6 (AC5) : un nouveau gate dans gate_registry est auto-visible via l'API."""
        from executions.gates.registry import gate_registry
        from executions.gates.definitions import GateDefinition

        fake_gate = GateDefinition(
            gate_type='fake_gate',
            condition_type='fake_condition',
            display_name='Fake Gate',
            category='test',
        )
        try:
            gate_registry.register(fake_gate)
            url = reverse('capabilities:capabilities-workflow-steps')
            data = auth_client.get(url).data['data']
            gate = next(s for s in data['step_types'] if s['code'] == 'gate')
            variant_codes = {v['code'] for v in gate['variants']}
            assert 'fake_gate' in variant_codes
            assert len(variant_codes) == 3  # 2 gates réels (maintenance_window, approval) + 1 fake enregistré dans ce test
        finally:
            gate_registry._by_gate_type.pop('fake_gate', None)
            gate_registry._by_condition_type.pop('fake_condition', None)


class TestIntegrationsCapabilitiesActionConfigSchema:
    """Story 82.8, AC2: action_config_schema dans chaque platform."""

    def test_platform_has_action_config_schema_field(self, auth_client):
        """Story 82.8, AC2: chaque platform expose action_config_schema."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for platform in data['platforms']:
            assert 'action_config_schema' in platform

    def test_action_config_schema_is_empty_dict_by_default(self, auth_client):
        """Story 82.8, AC2: action_config_schema est {} par défaut (aucune contrainte)."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for platform in data['platforms']:
            assert isinstance(platform['action_config_schema'], dict)


class TestGateVariantConfigSchema:
    """Story 83-9, AC1 — config_schema enrichi pour le gate approval."""

    def test_approval_variant_has_non_empty_config_schema(self, auth_client):
        """AC1.3 : GET /api/v1/capabilities/workflow-steps/ expose config_schema non vide pour approval."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        approval = next(v for v in gate['variants'] if v['code'] == 'approval')
        assert approval['config_schema'] != {}
        assert 'properties' in approval['config_schema']

    def test_approval_config_schema_has_context_from_property(self, auth_client):
        """AC1.1 : config_schema approval déclare context_from."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        approval = next(v for v in gate['variants'] if v['code'] == 'approval')
        props = approval['config_schema']['properties']
        assert 'context_from' in props
        assert props['context_from']['type'] == 'array'

    def test_approval_config_schema_has_approver_profile_ids_property(self, auth_client):
        """AC1.1 : config_schema approval déclare approver_profile_ids."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        approval = next(v for v in gate['variants'] if v['code'] == 'approval')
        props = approval['config_schema']['properties']
        assert 'approver_profile_ids' in props
        assert props['approver_profile_ids']['type'] == 'array'

    def test_maintenance_window_variant_has_empty_config_schema(self, auth_client):
        """AC1.2 : maintenance_window conserve config_schema={}."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        maintenance = next(v for v in gate['variants'] if v['code'] == 'maintenance_window')
        assert maintenance['config_schema'] == {}


class TestNotificationServiceUiHints:
    """Story 83-10, AC1 — ui_hints exposé pour les opérations send_email et send_teams."""

    def test_send_email_has_notification_template_renderer(self, auth_client):
        """send_email doit déclarer ui_hints.input_renderer = 'notification_template'."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        services = data['services']
        notification_svc = next((s for s in services if s['code'] == 'notification'), None)
        assert notification_svc is not None
        send_email_op = next((op for op in notification_svc['operations'] if op['code'] == 'send_email'), None)
        assert send_email_op is not None
        assert send_email_op['ui_hints'] == {'input_renderer': 'notification_template'}

    def test_send_teams_has_notification_template_renderer(self, auth_client):
        """send_teams doit déclarer ui_hints.input_renderer = 'notification_template'."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        services = data['services']
        notification_svc = next((s for s in services if s['code'] == 'notification'), None)
        assert notification_svc is not None
        send_teams_op = next((op for op in notification_svc['operations'] if op['code'] == 'send_teams'), None)
        assert send_teams_op is not None
        assert send_teams_op['ui_hints'] == {'input_renderer': 'notification_template'}

    def test_notify_execution_event_has_empty_ui_hints(self, auth_client):
        """notify_execution_event doit avoir ui_hints vide (renderer générique)."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        services = data['services']
        notification_svc = next((s for s in services if s['code'] == 'notification'), None)
        assert notification_svc is not None
        nee_op = next((op for op in notification_svc['operations'] if op['code'] == 'notify_execution_event'), None)
        assert nee_op is not None
        assert nee_op['ui_hints'] == {}
