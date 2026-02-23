# Story 31.9: Remove RefPlatform model (replaced by IntegrationTypeCatalogue)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('reference', '0004_refengine_icon_url_fix_paths'),
    ]

    operations = [
        migrations.DeleteModel(
            name='RefPlatform',
        ),
    ]
