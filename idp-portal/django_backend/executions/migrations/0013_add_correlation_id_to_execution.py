"""
Story 72.1: Ajouter correlation_id sur le modèle Execution.

Permet de propager et tracer le correlation_id sur tout le cycle d'exécution
(soumission, workflow, Celery, polling, gates, audit) via un seul identifiant.

Rétrocompatibilité : colonne nullable, les exécutions existantes ont NULL.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('executions', '0012_add_rejected_fields_to_execution_steps'),
    ]

    operations = [
        migrations.AddField(
            model_name='execution',
            name='correlation_id',
            field=models.CharField(
                blank=True,
                db_column='CORRELATION_ID',
                max_length=64,
                null=True,
            ),
        ),
    ]
