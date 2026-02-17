# Generated manually for Story 28.1 (business_rule_policies field on Action)
# Django migration for tests (Oracle schema managed by Flyway)

from django.db import migrations
import core.fields


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_create_action_mutex"),
    ]

    operations = [
        migrations.AddField(
            model_name="action",
            name="business_rule_policies",
            field=core.fields.OracleJSONField(
                blank=True,
                db_column="BUSINESS_RULE_POLICIES",
                help_text="JSON schema defining business rule policies evaluated on step output",
                null=True,
            ),
        ),
    ]
