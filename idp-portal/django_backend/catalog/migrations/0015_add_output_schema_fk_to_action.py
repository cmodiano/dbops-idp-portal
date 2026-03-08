"""
Migration Django: ajout du FK output_schema sur le modèle Action.
Story 63.9 - Déclarer les outputs par action.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0014_add_iac_sync_tracking'),
        ('output_schemas', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='output_schema',
            field=models.ForeignKey(
                to='output_schemas.outputschema',
                blank=True,
                db_column='OUTPUT_SCHEMA_ID',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='actions',
            ),
        ),
    ]
