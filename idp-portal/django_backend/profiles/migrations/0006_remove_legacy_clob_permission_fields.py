"""
Story 78.15: Remove legacy CLOB permission fields from Django models.

Corresponding Flyway migration: V136__drop_legacy_permission_clobs.sql
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0005_add_iac_sync_tracking'),
    ]

    operations = [
        # ProfileActionPermission — drop CLOB fields
        migrations.RemoveField(
            model_name='profileactionpermission',
            name='action_ids_json',
        ),
        migrations.RemoveField(
            model_name='profileactionpermission',
            name='tag_patterns_json',
        ),
        migrations.RemoveField(
            model_name='profileactionpermission',
            name='environments_json',
        ),
        # ProfileTargetPermission — drop CLOB fields
        migrations.RemoveField(
            model_name='profiletargetpermission',
            name='target_names_json',
        ),
        migrations.RemoveField(
            model_name='profiletargetpermission',
            name='target_patterns_json',
        ),
        migrations.RemoveField(
            model_name='profiletargetpermission',
            name='filter_by_attribute_json',
        ),
        migrations.RemoveField(
            model_name='profiletargetpermission',
            name='exclusion_patterns_json',
        ),
    ]
