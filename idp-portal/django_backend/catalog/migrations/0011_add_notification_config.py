"""Story 31.8: Add notification_config field to Action model."""
from django.db import migrations
from core.fields import OracleJSONField


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0010_add_gate_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='notification_config',
            field=OracleJSONField(blank=True, db_column='NOTIFICATION_CONFIG', null=True),
        ),
    ]
