"""
Story 31.3 — Add icon_url column to REF_ENGINES table.
Oracle: VARCHAR2(500 CHAR) NULL — compatible.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reference', '0002_refcategory'),
    ]

    operations = [
        migrations.AddField(
            model_name='refengine',
            name='icon_url',
            field=models.CharField(
                blank=True,
                db_column='ICON_URL',
                max_length=500,
                null=True,
            ),
        ),
    ]
