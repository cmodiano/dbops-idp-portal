"""Story 64.11: Add IaC sync tracking columns to RefEngine and RefCategory."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reference", "0005_delete_refplatform"),
    ]

    operations = [
        migrations.AddField(
            model_name="refengine",
            name="last_synced_at",
            field=models.DateTimeField(null=True, blank=True, db_column="LAST_SYNCED_AT"),
        ),
        migrations.AddField(
            model_name="refengine",
            name="last_synced_hash",
            field=models.CharField(max_length=64, null=True, blank=True, db_column="LAST_SYNCED_HASH"),
        ),
        migrations.AddField(
            model_name="refcategory",
            name="last_synced_at",
            field=models.DateTimeField(null=True, blank=True, db_column="LAST_SYNCED_AT"),
        ),
        migrations.AddField(
            model_name="refcategory",
            name="last_synced_hash",
            field=models.CharField(max_length=64, null=True, blank=True, db_column="LAST_SYNCED_HASH"),
        ),
    ]
