# Story 57.14: Add is_approver to Profile
# SQL Oracle equivalent (pour DBA Flyway):
#   ALTER TABLE PROFILES ADD IS_APPROVER NUMBER(1) DEFAULT 0 NOT NULL;
#   ALTER TABLE PROFILES ADD CONSTRAINT CK_PROFILES_IS_APPROVER CHECK (IS_APPROVER IN (0, 1));
#   COMMENT ON COLUMN PROFILES.IS_APPROVER IS '1 = profil éligible comme approbateur dans un step gate approval (Epic 57)';
#   UPDATE PROFILES SET IS_APPROVER = 1 WHERE NAME IN ('DBA', 'DBOPS');
#
# Pattern INCON-4: IntegerField intentionnel pour compatibilité Oracle NUMBER(1).
# Backfill: DBA et DBOPS sont les profils approbateurs par défaut.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0003_add_exclusion_patterns'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='is_approver',
            field=models.IntegerField(default=0, db_column='IS_APPROVER'),
        ),
        migrations.RunSQL(
            sql="UPDATE PROFILES SET IS_APPROVER = 1 WHERE NAME IN ('DBA', 'DBOPS')",
            reverse_sql="UPDATE PROFILES SET IS_APPROVER = 0",
        ),
    ]
