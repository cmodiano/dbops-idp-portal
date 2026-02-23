"""Story 31.6: Add gate_config field to Action model."""
from django.db import migrations
from core.fields import OracleJSONField


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0009_allow_disabled_without_soft_delete'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='gate_config',
            field=OracleJSONField(blank=True, db_column='GATE_CONFIG', null=True),
        ),
    ]
