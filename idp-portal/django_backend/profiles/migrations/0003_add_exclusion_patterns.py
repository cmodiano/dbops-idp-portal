# Story 25.6: Add exclusion_patterns_json to ProfileTargetPermission
# SQL equivalent:
#   ALTER TABLE PROFILE_TARGET_PERMISSIONS ADD EXCLUSION_PATTERNS_JSON CLOB;
#
# Semantics: "allow first, then exclude"
# - Exclusion patterns are applied AFTER inclusion rules (LIST/PATTERN/ALL)
# - If a target matches an exclusion pattern, it's removed from allowed targets
# - Multiple profiles: union of exclusions (most restrictive wins)
#
# Validation strategy (following pattern from 0002_add_filter_by_attribute):
#   1. No Oracle CHECK constraint (compatibility, performance)
#   2. Validation enforced at API layer (ProfileTargetPermissionSerializer)
#   3. Model layer has graceful degradation (get_exclusion_patterns filters invalid patterns)
#
# Format: JSON array of glob-style patterns.
# Example: ["PROD-CRITICAL-*", "DR-*", "SERVER-123"]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0002_add_filter_by_attribute'),
    ]

    operations = [
        migrations.AddField(
            model_name='profiletargetpermission',
            name='exclusion_patterns_json',
            field=models.TextField(
                blank=True,
                db_column='EXCLUSION_PATTERNS_JSON',
                help_text='JSON array filtering out targets matching any pattern. Applied after inclusion rules. Format: ["PROD-CRITICAL-*", "DR-*"]. Story 25.6',
                null=True,
            ),
        ),
    ]
