# Generated migration — Story 53.2
# Retire les choices ExecutionEnvironment des champs environment de Execution
# et ScheduledExecution. L'inventaire est désormais la seule source de vérité
# pour les valeurs d'environnement valides (Epic 53).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('executions', '0006_add_waiting_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='execution',
            name='environment',
            field=models.CharField(db_column='ENVIRONMENT', max_length=50),
        ),
        migrations.AlterField(
            model_name='scheduledexecution',
            name='environment',
            field=models.CharField(db_column='ENVIRONMENT', max_length=50),
        ),
    ]
