"""Story 57.18 Task 1: Migrate actions with change_type_config to execution_steps.

Converts legacy change_type_config (flat format) to execution_steps workflow
(3 steps: create-change -> execute-action -> close-change).
Reproduces _build_change_wrapper_steps() logic from Story 57.11.
"""

from django.db import migrations


def migrate_change_type_config_to_execution_steps(apps, schema_editor):
    Action = apps.get_model('catalog', 'Action')
    actions = Action.objects.filter(
        change_type_config__isnull=False,
    ).exclude(
        change_type_config={},
    )

    migrated = 0
    for action in actions:
        # Skip actions that already have execution_steps
        if action.execution_steps and len(action.execution_steps) > 0:
            continue

        config = action.change_type_config or {}
        action.execution_steps = [
            {
                "order": 1,
                "step_id": "create-change",
                "step_type": "service_call",
                "name": "Créer change ServiceNow",
                "integration_type": "servicenow",
                "operation": "create_change",
                "input_mapping": {
                    "short_description": f"IDP Portal — {action.name}"[:160],
                    "change_type": config.get("model", "standard"),
                    "category": config.get("category", ""),
                    "assignment_group": config.get("assignment_group", ""),
                },
                "output_mapping": {
                    "change_number": "$.number",
                    "sys_id": "$.sys_id",
                },
                "on_success_step_id": "execute-action",
            },
            {
                "order": 2,
                "step_id": "execute-action",
                "step_type": "platform",
                "name": action.name,
                "referenced_action_id": action.id,
                "on_success_step_id": "close-change",
            },
            {
                "order": 3,
                "step_id": "close-change",
                "step_type": "service_call",
                "name": "Fermer change ServiceNow",
                "integration_type": "servicenow",
                "operation": "close_change",
                "input_mapping": {
                    "change_id": "{{ steps['create-change']['change_number'] }}",
                    "close_code": "successful",
                },
                "output_mapping": {
                    "closed": "$.closed",
                },
            },
        ]
        action.item_type = 'workflow'
        action.save(update_fields=['execution_steps', 'item_type'])
        migrated += 1

    if migrated:
        print(f"\n  Migrated {migrated} actions from change_type_config to execution_steps")


def reverse_migration(apps, schema_editor):
    pass  # Data migration — no reverse needed


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0011_add_notification_config'),
    ]

    operations = [
        migrations.RunPython(
            migrate_change_type_config_to_execution_steps,
            reverse_migration,
        ),
    ]
