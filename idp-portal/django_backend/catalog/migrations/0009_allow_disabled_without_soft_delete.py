# Allow status=disabled without soft-delete (V080 / integration-deletion flow)
# deleted_at and deletion_reason stay NULL when actions are disabled due to integration deletion.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0008_alter_action_business_rule_policies_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="action",
            name="ck_actions_soft_delete_consistency",
        ),
        migrations.AddConstraint(
            model_name="action",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(status="disabled")
                    | models.Q(
                        status__in=["draft", "published"],
                        deleted_at__isnull=True,
                    )
                ),
                name="ck_actions_soft_delete_consistency",
            ),
        ),
    ]
