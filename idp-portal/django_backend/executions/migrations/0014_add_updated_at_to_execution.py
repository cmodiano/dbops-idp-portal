"""
Story 76.3: Ajouter updated_at sur le modèle Execution pour la détection de staleness par heartbeat.

Rétrocompatibilité : colonne nullable, les exécutions existantes auront NULL (utilisation de created_at).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('executions', '0013_add_correlation_id_to_execution'),
    ]

    operations = [
        migrations.AddField(
            model_name='execution',
            name='updated_at',
            field=models.DateTimeField(
                blank=True,
                db_column='UPDATED_AT',
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name='execution',
            index=models.Index(fields=['updated_at'], name='idx_exec_updated_at'),
        ),
    ]
