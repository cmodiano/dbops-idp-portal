"""
Tests for catalog/services_export_import.py
Story 64.6 - IaC Action export/import.
"""
import json

import yaml
from django.test import TestCase

from catalog.models import Action, ActionMutex, ActionTag, BusinessRulePolicy, Tag
from catalog.services_export_import import export_action_yaml, import_action_yaml
from core.exceptions import InvalidStateError
from core.models import AuditActionType, AuditLog
from integrations.models import Integration, IntegrationTypeCatalogue
from tests.factories import UserFactory


def _make_integration(name="aap-prod"):
    """Helper: create minimal Integration."""
    itc, _ = IntegrationTypeCatalogue.objects.get_or_create(
        code="AAP",
        defaults={"name": "Ansible Automation Platform"},
    )
    return Integration.objects.create(
        name=name,
        type=itc,
        base_url="https://aap.example.com",
    )


def _make_policy(name="terraform-review", user=None):
    """Helper: create minimal BusinessRulePolicy."""
    u = user or UserFactory()
    return BusinessRulePolicy.objects.create(
        name=name,
        policy_json={"on_step_output": []},
        created_by=u,
    )


def _make_action(
    name="deploy-terraform",
    engine="AAP",
    platform="AAP",
    integration=None,
    policy=None,
    user=None,
):
    """Helper: create minimal Action."""
    return Action.objects.create(
        name=name,
        engine=engine,
        platform=platform,
        integration=integration,
        business_rule_policy=policy,
        created_by=user,
    )


def _make_action_yaml(
    name="deploy-terraform",
    engine="AAP",
    platform="AAP",
    status="draft",
    item_type="action",
    requires_target=True,
    description=None,
    integration_ref=None,
    policy_ref=None,
    tags=None,
    mutex=None,
    parameters_schema=None,
    execution_steps=None,
):
    """Helper: build Action YAML bytes."""
    spec = {
        "engine": engine,
        "platform": platform,
        "status": status,
        "item_type": item_type,
        "requires_target": requires_target,
    }
    if description is not None:
        spec["description"] = description
    if integration_ref is not None:
        spec["integration_ref"] = integration_ref
    if policy_ref is not None:
        spec["business_rule_policy_ref"] = policy_ref
    if tags is not None:
        spec["tags"] = tags
    if mutex is not None:
        spec["mutex"] = mutex
    if parameters_schema is not None:
        spec["parameters_schema"] = parameters_schema
    if execution_steps is not None:
        spec["execution_steps"] = execution_steps
    data = {
        "apiVersion": "idp/v1",
        "kind": "Action",
        "metadata": {"name": name},
        "spec": spec,
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True).encode("utf-8")


# ---- Export tests ----

class ExportActionYamlTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.integration = _make_integration()
        self.policy = _make_policy(user=self.user)
        self.action = _make_action(
            integration=self.integration, policy=self.policy, user=self.user
        )
        tag, _ = Tag.objects.get_or_create(name="terraform")
        ActionTag.objects.create(action=self.action, tag=tag)
        other = _make_action(name="destroy-terraform")
        ActionMutex.objects.create(
            action=self.action,
            incompatible_with=other,
            same_target=True,
            description="Ne pas déployer et détruire simultanément",
        )
        self.action.parameters_schema = {"type": "object"}
        self.action.save()

    def test_export_returns_bytes(self):
        self.assertIsInstance(export_action_yaml("deploy-terraform"), bytes)

    def test_export_envelope_correct(self):
        parsed = yaml.safe_load(export_action_yaml("deploy-terraform"))
        self.assertEqual(parsed["apiVersion"], "idp/v1")
        self.assertEqual(parsed["kind"], "Action")
        self.assertEqual(parsed["metadata"]["name"], "deploy-terraform")

    def test_export_integration_ref_resolved(self):
        parsed = yaml.safe_load(export_action_yaml("deploy-terraform"))
        self.assertEqual(parsed["spec"]["integration_ref"], "aap-prod")

    def test_export_integration_ref_absent(self):
        _make_action(name="no-integration")
        parsed = yaml.safe_load(export_action_yaml("no-integration"))
        self.assertNotIn("integration_ref", parsed["spec"])

    def test_export_policy_ref_resolved(self):
        parsed = yaml.safe_load(export_action_yaml("deploy-terraform"))
        self.assertEqual(parsed["spec"]["business_rule_policy_ref"], "terraform-review")

    def test_export_policy_ref_absent(self):
        _make_action(name="no-policy")
        parsed = yaml.safe_load(export_action_yaml("no-policy"))
        self.assertNotIn("business_rule_policy_ref", parsed["spec"])

    def test_export_tags_sorted(self):
        tag2, _ = Tag.objects.get_or_create(name="provisioning")
        ActionTag.objects.get_or_create(action=self.action, tag=tag2)
        parsed = yaml.safe_load(export_action_yaml("deploy-terraform"))
        self.assertEqual(parsed["spec"]["tags"], sorted(["terraform", "provisioning"]))

    def test_export_tags_absent_if_none(self):
        _make_action(name="no-tags")
        parsed = yaml.safe_load(export_action_yaml("no-tags"))
        self.assertNotIn("tags", parsed["spec"])

    def test_export_mutex_list(self):
        parsed = yaml.safe_load(export_action_yaml("deploy-terraform"))
        mutex = parsed["spec"]["mutex"]
        self.assertEqual(len(mutex), 1)
        self.assertEqual(mutex[0]["incompatible_with"], "destroy-terraform")
        self.assertTrue(mutex[0]["same_target"])
        self.assertEqual(mutex[0]["description"], "Ne pas déployer et détruire simultanément")

    def test_export_mutex_absent_if_none(self):
        _make_action(name="no-mutex")
        parsed = yaml.safe_load(export_action_yaml("no-mutex"))
        self.assertNotIn("mutex", parsed["spec"])

    def test_export_json_fields_as_dict(self):
        self.action.execution_steps = {"steps": [{"name": "run"}]}
        self.action.impact_rules = {"level": "high"}
        self.action.notification_config = {"channels": ["slack"]}
        self.action.remediation_rules = {"auto": True}
        self.action.save()
        parsed = yaml.safe_load(export_action_yaml("deploy-terraform"))
        self.assertIsInstance(parsed["spec"]["parameters_schema"], dict)
        self.assertEqual(parsed["spec"]["parameters_schema"]["type"], "object")
        self.assertIsInstance(parsed["spec"]["execution_steps"], dict)
        self.assertEqual(parsed["spec"]["execution_steps"]["steps"][0]["name"], "run")
        self.assertIsInstance(parsed["spec"]["impact_rules"], dict)
        self.assertIsInstance(parsed["spec"]["notification_config"], dict)
        self.assertIsInstance(parsed["spec"]["remediation_rules"], dict)

    def test_export_optional_fields_absent_if_null(self):
        parsed = yaml.safe_load(export_action_yaml("deploy-terraform"))
        self.assertNotIn("description", parsed["spec"])
        self.assertNotIn("category", parsed["spec"])
        self.assertNotIn("default_impact_level", parsed["spec"])

    def test_export_not_found_raises(self):
        with self.assertRaises(InvalidStateError) as ctx:
            export_action_yaml("nonexistent-action")
        self.assertEqual(ctx.exception.code, "ACTION_NOT_FOUND")


# ---- Import tests ----

class ImportActionYamlTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.integration = _make_integration()
        self.policy = _make_policy(user=self.user)

    def test_import_create(self):
        content = _make_action_yaml()
        created, updated, unchanged = import_action_yaml(content, user=self.user)
        self.assertEqual(created, 1)
        self.assertTrue(Action.objects.filter(name="deploy-terraform").exists())

    def test_import_update(self):
        _make_action(user=self.user)
        content = _make_action_yaml(status="published")
        created, updated, unchanged = import_action_yaml(content, user=self.user)
        self.assertEqual(updated, 1)
        self.assertEqual(Action.objects.get(name="deploy-terraform").status, "published")

    def test_import_unchanged(self):
        _make_action(user=self.user)
        content = _make_action_yaml()  # same as default
        created, updated, unchanged = import_action_yaml(content, user=self.user)
        self.assertEqual(unchanged, 1)

    def test_import_invalid_mode_raises(self):
        content = _make_action_yaml()
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(content, mode="invalid", user=self.user)
        self.assertEqual(ctx.exception.code, "INVALID_IMPORT_MODE")

    def test_import_envelope_invalid_raises(self):
        bad = yaml.dump({"apiVersion": "idp/v1", "kind": "Tags", "metadata": {}, "spec": []}).encode()
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(bad, user=self.user)
        self.assertEqual(ctx.exception.code, "WRONG_KIND")

    def test_import_integration_ref_resolved(self):
        content = _make_action_yaml(integration_ref="aap-prod")
        import_action_yaml(content, user=self.user)
        action = Action.objects.get(name="deploy-terraform")
        self.assertEqual(action.integration_id, self.integration.id)

    def test_import_integration_ref_not_found_raises(self):
        content = _make_action_yaml(integration_ref="nonexistent-integration")
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(content, user=self.user)
        self.assertEqual(ctx.exception.code, "INTEGRATION_NOT_FOUND")

    def test_import_policy_ref_resolved(self):
        content = _make_action_yaml(policy_ref="terraform-review")
        import_action_yaml(content, user=self.user)
        action = Action.objects.get(name="deploy-terraform")
        self.assertEqual(action.business_rule_policy_id, self.policy.id)

    def test_import_policy_ref_not_found_raises(self):
        content = _make_action_yaml(policy_ref="nonexistent-policy")
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(content, user=self.user)
        self.assertEqual(ctx.exception.code, "POLICY_NOT_FOUND")

    def test_import_tags_additive(self):
        action = _make_action(user=self.user)
        existing_tag, _ = Tag.objects.get_or_create(name="existing-tag")
        ActionTag.objects.create(action=action, tag=existing_tag)
        content = _make_action_yaml(tags=["new-tag"])
        import_action_yaml(content, mode="additive", user=self.user)
        tag_names = set(
            ActionTag.objects.filter(action=action).values_list("tag__name", flat=True)
        )
        self.assertIn("new-tag", tag_names)
        self.assertIn("existing-tag", tag_names)  # preserved in additive mode

    def test_import_tags_full_removes_orphans(self):
        action = _make_action(user=self.user)
        existing_tag, _ = Tag.objects.get_or_create(name="old-tag")
        ActionTag.objects.create(action=action, tag=existing_tag)
        content = _make_action_yaml(tags=["new-tag"])
        import_action_yaml(content, mode="full", user=self.user)
        tag_names = set(
            ActionTag.objects.filter(action=action).values_list("tag__name", flat=True)
        )
        self.assertIn("new-tag", tag_names)
        self.assertNotIn("old-tag", tag_names)  # removed in full mode

    def test_import_mutex_additive(self):
        other = _make_action(name="other-action")
        action = _make_action(user=self.user)
        existing_other = _make_action(name="existing-mutex-target")
        ActionMutex.objects.create(action=action, incompatible_with=existing_other, same_target=False)
        content = _make_action_yaml(mutex=[{"incompatible_with": "other-action", "same_target": True}])
        import_action_yaml(content, mode="additive", user=self.user)
        self.assertTrue(ActionMutex.objects.filter(action=action, incompatible_with=other).exists())
        self.assertTrue(ActionMutex.objects.filter(action=action, incompatible_with=existing_other).exists())

    def test_import_mutex_full_removes_orphans(self):
        other = _make_action(name="other-action")
        action = _make_action(user=self.user)
        existing_other = _make_action(name="existing-mutex-target")
        ActionMutex.objects.create(action=action, incompatible_with=existing_other, same_target=False)
        content = _make_action_yaml(mutex=[{"incompatible_with": "other-action", "same_target": True}])
        import_action_yaml(content, mode="full", user=self.user)
        self.assertTrue(ActionMutex.objects.filter(action=action, incompatible_with=other).exists())
        self.assertFalse(ActionMutex.objects.filter(action=action, incompatible_with=existing_other).exists())

    def test_import_mutex_action_not_found_raises(self):
        content = _make_action_yaml(mutex=[{"incompatible_with": "nonexistent-action", "same_target": True}])
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(content, user=self.user)
        self.assertEqual(ctx.exception.code, "ACTION_NOT_FOUND")

    def test_import_mutex_empty_incompatible_with_raises(self):
        content = _make_action_yaml(mutex=[{"incompatible_with": "", "same_target": True}])
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(content, user=self.user)
        self.assertEqual(ctx.exception.code, "MISSING_MUTEX_TARGET")

    def test_import_audit_log_created(self):
        content = _make_action_yaml()
        import_action_yaml(content, user=self.user)
        log = AuditLog.objects.filter(action_type=AuditActionType.CONFIG_SYNC_ACTION_IMPORT).first()
        self.assertIsNotNone(log)
        details = json.loads(log.details)
        self.assertEqual(details["name"], "deploy-terraform")
        self.assertEqual(details["created"], 1)

    def test_import_created_by_not_changed_on_update(self):
        original_user = self.user
        other_user = UserFactory()
        _make_action(user=original_user)
        content = _make_action_yaml(status="published")
        import_action_yaml(content, user=other_user)
        action = Action.objects.get(name="deploy-terraform")
        self.assertEqual(action.created_by_id, original_user.id)

    def test_round_trip(self):
        action = _make_action(
            integration=self.integration,
            policy=self.policy,
            user=self.user,
        )
        action.parameters_schema = {"type": "object", "properties": {"workspace": {"type": "string"}}}
        action.status = "published"
        action.description = "Test action"
        action.save()
        tag, _ = Tag.objects.get_or_create(name="terraform")
        ActionTag.objects.create(action=action, tag=tag)
        exported1 = export_action_yaml("deploy-terraform")
        import_action_yaml(exported1, user=self.user)
        exported2 = export_action_yaml("deploy-terraform")
        self.assertEqual(exported1, exported2)
