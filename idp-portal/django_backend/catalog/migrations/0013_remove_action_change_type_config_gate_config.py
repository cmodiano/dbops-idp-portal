"""Story 57.18 Task 2: Remove deprecated change_type_config and gate_config fields from Action model."""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0012_migrate_change_type_config_to_execution_steps'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='action',
            name='change_type_config',
        ),
        migrations.RemoveField(
            model_name='action',
            name='gate_config',
        ),
    ]
