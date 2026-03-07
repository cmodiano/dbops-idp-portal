"""
Initial migration for output_schemas app.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

from django.db import migrations, models
import django.db.models.deletion
import core.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='OutputSchema',
            fields=[
                ('id', models.BigAutoField(db_column='ID', primary_key=True, serialize=False)),
                ('name', models.CharField(db_column='NAME', max_length=255, unique=True)),
                ('schema_type', models.CharField(
                    choices=[
                        ('action', 'Action'),
                        ('integration', 'Integration'),
                        ('platform_convention', 'Platform Convention'),
                    ],
                    db_column='SCHEMA_TYPE',
                    max_length=30,
                )),
                ('target_name', models.CharField(
                    db_column='TARGET_NAME',
                    help_text='action_name, integration_type, or convention_name',
                    max_length=255,
                )),
                ('operation', models.CharField(
                    blank=True,
                    db_column='OPERATION',
                    help_text='operation name for integration schemas (e.g. create_change)',
                    max_length=255,
                    null=True,
                )),
                ('inherits_from', models.ForeignKey(
                    blank=True,
                    db_column='INHERITS_FROM_ID',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='children',
                    to='output_schemas.outputschema',
                )),
                ('schema_json', core.fields.OracleJSONField(blank=True, db_column='SCHEMA_JSON', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='UPDATED_AT')),
            ],
            options={
                'db_table': 'OUTPUT_SCHEMAS',
            },
        ),
        migrations.AddConstraint(
            model_name='outputschema',
            constraint=models.UniqueConstraint(
                condition=models.Q(operation__isnull=False),
                fields=['schema_type', 'target_name', 'operation'],
                name='uq_output_schema_type_target_op',
            ),
        ),
    ]
