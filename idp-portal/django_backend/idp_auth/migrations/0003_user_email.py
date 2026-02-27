# Generated for Story 50.1 — Email utilisateur depuis AD

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('idp_auth', '0002_apikey'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email',
            field=models.EmailField(blank=True, db_column='EMAIL', max_length=254, null=True),
        ),
    ]
