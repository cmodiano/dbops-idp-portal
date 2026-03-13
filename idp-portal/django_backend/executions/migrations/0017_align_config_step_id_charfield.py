# 0017_align_config_step_id_charfield.py
# Note: schéma Oracle déjà VARCHAR2(255) depuis Flyway V116. Cette migration
# aligne uniquement le modèle Django. En production : python manage.py
# migrate --fake executions 0017

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("executions", "0016_harden_runnable_steps_with_leases"),
    ]

    operations = [
        migrations.AlterField(
            model_name="executionstep",
            name="config_step_id",
            field=models.CharField(
                max_length=255,
                blank=True,
                db_column="CONFIG_STEP_ID",
                null=True,
            ),
        ),
    ]
