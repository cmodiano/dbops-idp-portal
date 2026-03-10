"""
Tests for catalog/services_export_import.py
Story 64.6 - CaC Action export/import.
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

    def test_import_tags_case_normalization(self):
        """_sync_tags normalizes to strip().lower(); export emits normalized names.
        Mixed-case Tag in DB is matched case-insensitively; orphans removed by iexact."""
        action = _make_action(user=self.user)
        mixed_case_tag, _ = Tag.objects.get_or_create(name="Terraform")
        ActionTag.objects.create(action=action, tag=mixed_case_tag)
        # Import with lowercase tag — should match existing "Terraform" (no duplicate)
        content = _make_action_yaml(tags=["terraform"])
        import_action_yaml(content, mode="additive", user=self.user)
        tag_names = list(
            ActionTag.objects.filter(action=action).values_list("tag__name", flat=True)
        )
        self.assertEqual(len(tag_names), 1)
        self.assertEqual(tag_names[0], "Terraform")  # existing tag kept, no "terraform" duplicate

        # Full mode: import ["terraform"] — "Terraform" is same (normalized), no orphan
        content_full = _make_action_yaml(tags=["terraform"])
        import_action_yaml(content_full, mode="full", user=self.user)
        tag_names_full = list(
            ActionTag.objects.filter(action=action).values_list("tag__name", flat=True)
        )
        self.assertEqual(len(tag_names_full), 1)
        self.assertIn(tag_names_full[0], ("Terraform", "terraform"))

        # Full mode with orphan: DB has "Terraform" + "OldTag", import ["terraform"] only
        ActionTag.objects.filter(action=action).delete()
        Tag.objects.filter(name__in=["Terraform", "OldTag"]).delete()
        tag_tf, _ = Tag.objects.get_or_create(name="Terraform")
        tag_old, _ = Tag.objects.get_or_create(name="OldTag")
        ActionTag.objects.create(action=action, tag=tag_tf)
        ActionTag.objects.create(action=action, tag=tag_old)
        import_action_yaml(_make_action_yaml(tags=["terraform"]), mode="full", user=self.user)
        remaining = set(
            ActionTag.objects.filter(action=action).values_list("tag__name", flat=True)
        )
        self.assertIn("Terraform", remaining)
        self.assertNotIn("OldTag", remaining)  # orphan removed via iexact

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

    def test_import_missing_engine_raises(self):
        content = _make_action_yaml(engine="")
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(content, user=self.user)
        self.assertEqual(ctx.exception.code, "MISSING_ENGINE")

    def test_import_missing_platform_raises(self):
        content = _make_action_yaml(platform="")
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(content, user=self.user)
        self.assertEqual(ctx.exception.code, "MISSING_PLATFORM")

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

    def test_import_full_mode_does_not_delete_other_actions(self):
        """En mode full, l'import d'une action ne supprime pas les autres actions existantes (AC #1).
        import_action_yaml est single-entity : la suppression d'orphelins au niveau action
        est du ressort de sync_config, pas du service d'import."""
        _make_action(name="other-action", user=self.user)
        content = _make_action_yaml()
        import_action_yaml(content, mode="full", user=self.user)
        # other-action doit toujours exister
        self.assertTrue(Action.objects.filter(name="other-action").exists())

    def test_import_invalid_yaml_syntax_raises(self):
        """INVALID_YAML_SYNTAX levé quand le contenu YAML est syntaxiquement malformé (AC #3)."""
        bad_yaml = b"apiVersion: idp/v1\nkind: Action\nspec: [\nunclosed"
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(bad_yaml, user=self.user)
        self.assertEqual(ctx.exception.code, "INVALID_YAML_SYNTAX")


# ---------------------------------------------------------------------------
# Story 65.7 — CaC export/import tests for parallel_group
# ---------------------------------------------------------------------------

# Valid parallel_group workflow steps (compatible with validate_workflow_steps).
# Platform steps use referenced_action_id=1; step-apply-patch and step-rollback
# are non-member exit points (on_success_step_id=None).
_VALID_PARALLEL_GROUP_STEPS = [
    {
        "step_id": "pg-backup",
        "step_type": "parallel_group",
        "name": "Backups parallèles",
        "parallel_steps": ["step-backup-db", "step-backup-config"],
        "on_all_success_step_id": "step-apply-patch",
        "on_any_error_step_id": "step-rollback",
    },
    {
        "step_id": "step-backup-db",
        "step_type": "platform",
        "name": "Backup DB",
        "referenced_action_id": 1,
    },
    {
        "step_id": "step-backup-config",
        "step_type": "platform",
        "name": "Backup Config",
        "referenced_action_id": 1,
    },
    {
        "step_id": "step-apply-patch",
        "step_type": "platform",
        "name": "Apply Patch",
        "referenced_action_id": 1,
        "on_success_step_id": None,
    },
    {
        "step_id": "step-rollback",
        "step_type": "platform",
        "name": "Rollback",
        "referenced_action_id": 1,
        "on_success_step_id": None,
    },
]

# Invalid: parallel_group with only 1 parallel_step (must raise INVALID_WORKFLOW_STEPS)
_INVALID_ONE_PARALLEL_STEP = [
    {
        "step_id": "pg-solo",
        "step_type": "parallel_group",
        "name": "Groupe solo",
        "parallel_steps": ["step-only-one"],
        "on_all_success_step_id": None,
        "on_any_error_step_id": None,
    },
    {
        "step_id": "step-only-one",
        "step_type": "platform",
        "name": "Seul step",
        "referenced_action_id": 1,
    },
]

# Invalid: parallel_group referencing a non-existent step_id
_INVALID_BAD_REF_PARALLEL_STEP = [
    {
        "step_id": "pg-bad",
        "step_type": "parallel_group",
        "name": "Groupe bad ref",
        "parallel_steps": ["step-exists", "step-nonexistent"],
        "on_all_success_step_id": None,
        "on_any_error_step_id": None,
    },
    {
        "step_id": "step-exists",
        "step_type": "platform",
        "name": "Existing step",
        "referenced_action_id": 1,
    },
]


def _make_workflow_action_yaml(
    name="workflow-action",
    engine="AAP",
    platform="AAP",
    item_type="workflow",
    execution_steps=None,
):
    """Helper: build workflow Action YAML bytes. Story 65.7."""
    spec = {
        "engine": engine,
        "platform": platform,
        "status": "draft",
        "item_type": item_type,
        "requires_target": False,
    }
    if execution_steps is not None:
        spec["execution_steps"] = execution_steps
    data = {
        "apiVersion": "idp/v1",
        "kind": "Action",
        "metadata": {"name": name},
        "spec": spec,
    }
    return yaml.dump(data, default_flow_style=False, allow_unicode=True).encode("utf-8")


class ExportImportParallelGroupTests(TestCase):
    """Tests CaC export/import pour les workflows avec parallel_group. Story 65.7."""

    def setUp(self):
        self.user = UserFactory()
        self.action = Action.objects.create(
            name="pre-patch-workflow",
            engine="AAP",
            platform="AAP",
            item_type="workflow",
            execution_steps=_VALID_PARALLEL_GROUP_STEPS,
            created_by=self.user,
        )

    def test_export_parallel_group_includes_all_fields(self):
        """Export YAML contient tous les champs du parallel_group. AC #1."""
        parsed = yaml.safe_load(export_action_yaml("pre-patch-workflow"))
        steps = parsed["spec"]["execution_steps"]
        pg_step = next(s for s in steps if s.get("step_type") == "parallel_group")
        self.assertEqual(pg_step["parallel_steps"], ["step-backup-db", "step-backup-config"])
        self.assertEqual(pg_step["on_all_success_step_id"], "step-apply-patch")
        self.assertEqual(pg_step["on_any_error_step_id"], "step-rollback")

    def test_round_trip_preserves_parallel_group_structure(self):
        """Export → réimport → execution_steps préservés sans perte (all pg fields). AC #1."""
        yaml_bytes = export_action_yaml("pre-patch-workflow")
        import_action_yaml(yaml_bytes, mode="full", user=self.user)
        action = Action.objects.get(name="pre-patch-workflow")
        pg_step = next(
            s for s in action.execution_steps
            if s.get("step_type") == "parallel_group"
        )
        self.assertEqual(pg_step["parallel_steps"], ["step-backup-db", "step-backup-config"])
        self.assertEqual(pg_step["on_all_success_step_id"], "step-apply-patch")
        self.assertEqual(pg_step["on_any_error_step_id"], "step-rollback")
        self.assertEqual(pg_step["step_id"], "pg-backup")
        self.assertEqual(pg_step["name"], "Backups parallèles")

    def test_import_valid_parallel_group_creates_action(self):
        """Import d'un nouveau workflow avec parallel_group valide → créé. AC #3."""
        yaml_bytes = _make_workflow_action_yaml(
            name="new-parallel-workflow",
            execution_steps=_VALID_PARALLEL_GROUP_STEPS,
        )
        created, updated, unchanged = import_action_yaml(yaml_bytes, user=self.user)
        self.assertEqual(created, 1)
        action = Action.objects.get(name="new-parallel-workflow")
        self.assertIsNotNone(action.execution_steps)

    def test_import_valid_parallel_group_updates_action(self):
        """Import d'un workflow déjà existant → mis à jour ou inchangé (pas créé). AC #3."""
        yaml_bytes = _make_workflow_action_yaml(
            name="pre-patch-workflow",
            execution_steps=_VALID_PARALLEL_GROUP_STEPS,
        )
        _created, updated, unchanged = import_action_yaml(yaml_bytes, user=self.user)
        # Action already exists from setUp → must not be created again
        self.assertEqual(_created, 0)
        # Either updated (if YAML fields differ from setUp defaults) or unchanged — never created
        self.assertEqual(updated + unchanged, 1)

    def test_import_parallel_group_one_step_now_valid(self):
        """Story 67.1: parallel_group validation supprimée — 1 seul parallel_step n'est plus invalide."""
        yaml_bytes = _make_workflow_action_yaml(
            name="formerly-bad-workflow",
            execution_steps=_INVALID_ONE_PARALLEL_STEP,
        )
        # Avec Story 67.1, la validation parallel_group est supprimée → import réussit
        created, updated, unchanged = import_action_yaml(yaml_bytes, user=self.user)
        self.assertEqual(created, 1)

    def test_import_parallel_steps_bad_ref_now_valid(self):
        """Story 67.1: parallel_group validation supprimée — référence non-existante dans parallel_steps n'est plus vérifiée."""
        yaml_bytes = _make_workflow_action_yaml(
            name="formerly-bad-ref-workflow",
            execution_steps=_INVALID_BAD_REF_PARALLEL_STEP,
        )
        # Avec Story 67.1, la validation parallel_steps est supprimée → import réussit
        created, updated, unchanged = import_action_yaml(yaml_bytes, user=self.user)
        self.assertEqual(created, 1)

    def test_import_parallel_group_non_workflow_item_type_skips_validation(self):
        """item_type='action' : validation execution_steps ignorée même si invalide. AC #2."""
        yaml_bytes = _make_workflow_action_yaml(
            name="action-with-bad-pg",
            item_type="action",
            execution_steps=_INVALID_ONE_PARALLEL_STEP,
        )
        # Must NOT raise (item_type != "workflow" → validation skipped)
        created, updated, unchanged = import_action_yaml(yaml_bytes, user=self.user)
        self.assertEqual(created, 1)


# ---------------------------------------------------------------------------
# Story 67.7 — CaC export/import tests for fan-out multi-connexions
# ---------------------------------------------------------------------------

# Sequential workflow: one step → on_success_step_ids with a single target.
_SEQUENTIAL_FANOUT_STEPS = [
    {
        "step_id": "s1",
        "step_type": "platform",
        "name": "Init",
        "referenced_action_id": 1,
        "on_success_step_ids": ["s2"],
    },
    {
        "step_id": "s2",
        "step_type": "platform",
        "name": "Deploy",
        "referenced_action_id": 1,
        "on_success_step_ids": [],
    },
]

# Fan-out workflow: one step fanning out to 2 parallel branches then joining.
_FANOUT_2_BRANCHES_STEPS = [
    {
        "step_id": "s1",
        "step_type": "platform",
        "name": "Init",
        "referenced_action_id": 1,
        "on_success_step_ids": ["s2", "s3"],
    },
    {
        "step_id": "s2",
        "step_type": "platform",
        "name": "Branch A",
        "referenced_action_id": 1,
        "on_success_step_ids": ["s4"],
    },
    {
        "step_id": "s3",
        "step_type": "platform",
        "name": "Branch B",
        "referenced_action_id": 1,
        "on_success_step_ids": ["s4"],
    },
    {
        "step_id": "s4",
        "step_type": "platform",
        "name": "Join",
        "referenced_action_id": 1,
        "join_policy": "all_success",
        "on_success_step_ids": [],
    },
]

# Invalid: join_policy with unsupported value.
_INVALID_JOIN_POLICY_STEPS = [
    {
        "step_id": "s1",
        "step_type": "platform",
        "name": "Init",
        "referenced_action_id": 1,
        "on_success_step_ids": ["s2", "s3"],
    },
    {
        "step_id": "s2",
        "step_type": "platform",
        "name": "Branch A",
        "referenced_action_id": 1,
        "on_success_step_ids": ["s4"],
    },
    {
        "step_id": "s3",
        "step_type": "platform",
        "name": "Branch B",
        "referenced_action_id": 1,
        "on_success_step_ids": ["s4"],
    },
    {
        "step_id": "s4",
        "step_type": "platform",
        "name": "Join",
        "referenced_action_id": 1,
        "join_policy": "invalid_value",
        "on_success_step_ids": [],
    },
]

# Fan-out workflow with on_error_step_ids for round-trip validation.
_FANOUT_WITH_ERROR_STEPS = [
    {
        "step_id": "s1",
        "step_type": "platform",
        "name": "Init",
        "referenced_action_id": 1,
        "on_success_step_ids": ["s2"],
        "on_error_step_ids": ["s3"],
    },
    {
        "step_id": "s2",
        "step_type": "platform",
        "name": "Deploy",
        "referenced_action_id": 1,
        "on_success_step_ids": [],
    },
    {
        "step_id": "s3",
        "step_type": "platform",
        "name": "Rollback",
        "referenced_action_id": 1,
        "on_success_step_ids": [],
    },
]

# Invalid: on_success_step_ids references a non-existent step_id.
_INVALID_BAD_SUCCESS_REF_STEPS = [
    {
        "step_id": "s1",
        "step_type": "platform",
        "name": "Init",
        "referenced_action_id": 1,
        "on_success_step_ids": ["inexistant"],
    },
]


class TestWorkflowCaCParallelBranches(TestCase):
    """Tests CaC export/import pour les workflows fan-out multi-connexions. Story 67.7."""

    def setUp(self):
        self.user = UserFactory()

    def _make_workflow(self, name, steps):
        """Helper: crée une Action de type workflow avec execution_steps fan-out."""
        return Action.objects.create(
            name=name,
            engine="AAP",
            platform="AAP",
            item_type="workflow",
            execution_steps=steps,
            created_by=self.user,
        )

    # ---- Subtask 2.2 : round-trip séquentiel (1 cible) ----

    def test_round_trip_sequential_on_success_step_ids(self):
        """Export → YAML → re-import : on_success_step_ids avec 1 cible préservé. AC #4, #5."""
        self._make_workflow("workflow-seq", _SEQUENTIAL_FANOUT_STEPS)
        yaml_bytes = export_action_yaml("workflow-seq")
        parsed = yaml.safe_load(yaml_bytes)
        steps = parsed["spec"]["execution_steps"]
        s1 = next(s for s in steps if s["step_id"] == "s1")
        self.assertEqual(s1["on_success_step_ids"], ["s2"])

        import_action_yaml(yaml_bytes, mode="full", user=self.user)
        action = Action.objects.get(name="workflow-seq")
        s1_db = next(s for s in action.execution_steps if s["step_id"] == "s1")
        self.assertEqual(s1_db["on_success_step_ids"], ["s2"])

    # ---- Subtask 2.3 : round-trip fan-out 2 cibles ----

    def test_round_trip_fanout_two_targets(self):
        """Export → YAML contient les 2 cibles → re-import correct. AC #4, #5."""
        self._make_workflow("workflow-fanout", _FANOUT_2_BRANCHES_STEPS)
        yaml_bytes = export_action_yaml("workflow-fanout")
        parsed = yaml.safe_load(yaml_bytes)
        steps = parsed["spec"]["execution_steps"]
        s1 = next(s for s in steps if s["step_id"] == "s1")
        self.assertIn("s2", s1["on_success_step_ids"])
        self.assertIn("s3", s1["on_success_step_ids"])
        self.assertEqual(len(s1["on_success_step_ids"]), 2)

        import_action_yaml(yaml_bytes, mode="full", user=self.user)
        action = Action.objects.get(name="workflow-fanout")
        s1_db = next(s for s in action.execution_steps if s["step_id"] == "s1")
        self.assertEqual(set(s1_db["on_success_step_ids"]), {"s2", "s3"})

    # ---- Subtask 2.4 : round-trip join_policy all_success ----

    def test_round_trip_join_policy_preserved(self):
        """Export → re-import : join_policy='all_success' sur le step de convergence. AC #4, #5."""
        self._make_workflow("workflow-join", _FANOUT_2_BRANCHES_STEPS)
        yaml_bytes = export_action_yaml("workflow-join")
        parsed = yaml.safe_load(yaml_bytes)
        steps = parsed["spec"]["execution_steps"]
        s4 = next(s for s in steps if s["step_id"] == "s4")
        self.assertEqual(s4["join_policy"], "all_success")

        import_action_yaml(yaml_bytes, mode="full", user=self.user)
        action = Action.objects.get(name="workflow-join")
        s4_db = next(s for s in action.execution_steps if s["step_id"] == "s4")
        self.assertEqual(s4_db["join_policy"], "all_success")

    # ---- Subtask 2.5 : import join_policy invalide → InvalidStateError ----

    def test_import_invalid_join_policy_raises(self):
        """Import YAML avec join_policy='invalid_value' → InvalidStateError INVALID_WORKFLOW_STEPS. AC #5."""
        yaml_bytes = _make_workflow_action_yaml(
            name="workflow-bad-join",
            execution_steps=_INVALID_JOIN_POLICY_STEPS,
        )
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(yaml_bytes, user=self.user)
        self.assertEqual(ctx.exception.code, "INVALID_WORKFLOW_STEPS")

    # ---- Subtask 2.6 : import référence invalide → InvalidStateError ----

    def test_import_invalid_success_ref_raises(self):
        """Import YAML avec on_success_step_ids=['inexistant'] → InvalidStateError. AC #5."""
        yaml_bytes = _make_workflow_action_yaml(
            name="workflow-bad-ref",
            execution_steps=_INVALID_BAD_SUCCESS_REF_STEPS,
        )
        with self.assertRaises(InvalidStateError) as ctx:
            import_action_yaml(yaml_bytes, user=self.user)
        self.assertEqual(ctx.exception.code, "INVALID_WORKFLOW_STEPS")

    # ---- Subtask 2.x : round-trip on_error_step_ids ----

    def test_round_trip_on_error_step_ids_preserved(self):
        """Export → re-import : on_error_step_ids préservé dans le round-trip. AC #4."""
        self._make_workflow("workflow-error-path", _FANOUT_WITH_ERROR_STEPS)
        yaml_bytes = export_action_yaml("workflow-error-path")
        parsed = yaml.safe_load(yaml_bytes)
        steps = parsed["spec"]["execution_steps"]
        s1 = next(s for s in steps if s["step_id"] == "s1")
        self.assertEqual(s1["on_error_step_ids"], ["s3"])

        import_action_yaml(yaml_bytes, mode="full", user=self.user)
        action = Action.objects.get(name="workflow-error-path")
        s1_db = next(s for s in action.execution_steps if s["step_id"] == "s1")
        self.assertEqual(s1_db["on_error_step_ids"], ["s3"])
        self.assertEqual(s1_db["on_success_step_ids"], ["s2"])

    # ---- Subtask 2.7 : export bulk inclut les workflows parallèles ----

    def test_export_bulk_includes_parallel_workflow(self):
        """export_actions_yaml() inclut correctement les workflows fan-out. AC #4."""
        from catalog.services_export_import import export_actions_yaml
        self._make_workflow("workflow-bulk-fanout", _FANOUT_2_BRANCHES_STEPS)
        bulk_bytes = export_actions_yaml()
        self.assertIn(b"workflow-bulk-fanout", bulk_bytes)
        self.assertIn(b"on_success_step_ids", bulk_bytes)
        self.assertIn(b"join_policy", bulk_bytes)
