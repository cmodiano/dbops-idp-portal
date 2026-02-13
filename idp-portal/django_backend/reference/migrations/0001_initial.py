# Generated manually for Story 13.7
# Table REF_ENGINES created by Flyway migration V049

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='RefEngine',
            fields=[
                ('id', models.BigAutoField(db_column='ID', primary_key=True, serialize=False)),
                ('code', models.CharField(db_column='CODE', max_length=50, unique=True)),
                ('label', models.CharField(db_column='LABEL', max_length=100)),
                ('display_order', models.IntegerField(db_column='DISPLAY_ORDER', default=0)),
                ('is_active', models.IntegerField(db_column='IS_ACTIVE', default=1)),
            ],
            options={
                'db_table': 'REF_ENGINES',
                'ordering': ['display_order', 'code'],
                'verbose_name': 'Engine Reference',
                'verbose_name_plural': 'Engine References',
            },
        ),
        migrations.CreateModel(
            name='RefPlatform',
            fields=[
                ('id', models.BigAutoField(db_column='ID', primary_key=True, serialize=False)),
                ('code', models.CharField(db_column='CODE', max_length=50, unique=True)),
                ('label', models.CharField(db_column='LABEL', max_length=100)),
                ('display_order', models.IntegerField(db_column='DISPLAY_ORDER', default=0)),
                ('is_active', models.IntegerField(db_column='IS_ACTIVE', default=1)),
            ],
            options={
                'db_table': 'REF_PLATFORMS',
                'ordering': ['display_order', 'code'],
                'verbose_name': 'Platform Reference',
                'verbose_name_plural': 'Platform References',
            },
        ),
    ]
