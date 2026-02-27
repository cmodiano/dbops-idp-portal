# Story 51.1: Migration ajoutant les colonnes health check à la table INTEGRATIONS.
# Colonnes Oracle : HEALTH_STATUS (VARCHAR2 NOT NULL default 'unknown'),
#                   HEALTH_CHECKED_AT (TIMESTAMP NULL), HEALTH_ERROR_MESSAGE (CLOB NULL).
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0007_integration_authflow_oauth2_apikey")]

    operations = [
        migrations.AddField(
            model_name='integration',
            name='health_status',
            field=models.CharField(
                max_length=10,
                choices=[('ok', 'OK'), ('error', 'Erreur'), ('unknown', 'Inconnu')],
                default='unknown',
                db_column='HEALTH_STATUS',
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name='integration',
            name='health_checked_at',
            field=models.DateTimeField(null=True, blank=True, db_column='HEALTH_CHECKED_AT'),
        ),
        migrations.AddField(
            model_name='integration',
            name='health_error_message',
            field=models.TextField(null=True, blank=True, db_column='HEALTH_ERROR_MESSAGE'),
        ),
    ]
