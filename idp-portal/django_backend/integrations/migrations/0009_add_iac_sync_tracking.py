"""Story 64.11: Add IaC sync tracking columns to Integration and IntegrationTypeCatalogue."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0008_integration_health_check_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="integration",
            name="last_synced_at",
            field=models.DateTimeField(null=True, blank=True, db_column="LAST_SYNCED_AT"),
        ),
        migrations.AddField(
            model_name="integration",
            name="last_synced_hash",
            field=models.CharField(max_length=64, null=True, blank=True, db_column="LAST_SYNCED_HASH"),
        ),
        migrations.AddField(
            model_name="integrationtypecatalogue",
            name="last_synced_at",
            field=models.DateTimeField(null=True, blank=True, db_column="LAST_SYNCED_AT"),
        ),
        migrations.AddField(
            model_name="integrationtypecatalogue",
            name="last_synced_hash",
            field=models.CharField(max_length=64, null=True, blank=True, db_column="LAST_SYNCED_HASH"),
        ),
    ]
