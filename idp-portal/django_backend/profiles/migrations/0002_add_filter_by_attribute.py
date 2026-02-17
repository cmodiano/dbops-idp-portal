# Story 23.4: Add filter_by_attribute_json to ProfileTargetPermission
# SQL equivalent:
#   ALTER TABLE PROFILE_TARGET_PERMISSIONS ADD FILTER_BY_ATTRIBUTE_JSON CLOB;
#
# Oracle JSON validation constraint (commented - requires Oracle 12c+):
#   -- ALTER TABLE PROFILE_TARGET_PERMISSIONS
#   -- ADD CONSTRAINT CHK_FILTER_BY_ATTRIBUTE_JSON_VALID
#   -- CHECK (FILTER_BY_ATTRIBUTE_JSON IS NULL OR FILTER_BY_ATTRIBUTE_JSON IS JSON);
#
# Code review fix: AC1 validation strategy documented below:
#   Django migration does NOT add Oracle CHECK constraint because:
#   1. Requires Oracle 12c+ (not all environments may be 12c+)
#   2. Validation is enforced at API layer (ProfileTargetPermissionsSerializer.validate_filter_by_attribute)
#   3. Model layer has graceful degradation (ProfileTargetPermission.get_filter_by_attribute logs ERROR on malformed JSON)
#   This is an acceptable trade-off: performance (no DB constraint) vs safety (app-level validation).
#
# Format: JSON dict mapping inventory concept keys to value lists.
# Example: {"engine_type": ["oracle", "sqlserver"], "zone": ["prod"]}
# Keys are business concepts from InventoryMapper config (stable, not Oracle column names).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='profiletargetpermission',
            name='filter_by_attribute_json',
            field=models.TextField(
                blank=True,
                db_column='FILTER_BY_ATTRIBUTE_JSON',
                help_text='JSON dict filtering targets by inventory attributes. Format: {"engine_type": ["oracle"], ...}',
                null=True,
            ),
        ),
    ]
