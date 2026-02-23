"""
Story 31.3 — Fix icon_url paths for built-in engines.
Icons are served from the frontend's public/icons/engines/ directory.
Corrects paths like /icons/oracle.svg → /icons/engines/oracle.svg.
"""

from django.db import migrations


ICON_URL_CORRECTIONS = {
    # Wrong path → correct path
    '/icons/oracle.svg': '/icons/engines/oracle.svg',
    '/icons/sqlserver.svg': '/icons/engines/sqlserver.svg',
    '/icons/sql_server.svg': '/icons/engines/sqlserver.svg',
    '/icons/db2.svg': '/icons/engines/db2.svg',
}

# Canonical icon_url for known engine codes (applied if icon_url is null or incorrect)
ENGINE_CODE_TO_ICON = {
    'Oracle': '/icons/engines/oracle.svg',
    'SQL Server': '/icons/engines/sqlserver.svg',
    'DB2': '/icons/engines/db2.svg',
}


def fix_engine_icon_urls(apps, schema_editor):
    RefEngine = apps.get_model('reference', 'RefEngine')

    for engine in RefEngine.objects.all():
        new_url = None

        # Fix known wrong paths
        if engine.icon_url and engine.icon_url in ICON_URL_CORRECTIONS:
            new_url = ICON_URL_CORRECTIONS[engine.icon_url]

        # Set canonical path for known engines with missing icon_url
        if engine.icon_url is None and engine.code in ENGINE_CODE_TO_ICON:
            new_url = ENGINE_CODE_TO_ICON[engine.code]

        if new_url is not None:
            engine.icon_url = new_url
            engine.save(update_fields=['icon_url'])


def reverse_fix(apps, schema_editor):
    # Not reversible — leave as-is
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('reference', '0003_refengine_icon_url'),
    ]

    operations = [
        migrations.RunPython(fix_engine_icon_urls, reverse_fix),
    ]
