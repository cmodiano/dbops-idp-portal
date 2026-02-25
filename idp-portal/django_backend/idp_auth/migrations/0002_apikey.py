# Generated for Story 44.1 — APIKey model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('idp_auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='APIKey',
            fields=[
                ('id', models.BigAutoField(db_column='ID', primary_key=True, serialize=False)),
                ('user', models.ForeignKey(
                    db_column='USER_ID',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='api_keys',
                    to='idp_auth.user',
                )),
                ('key_hash', models.CharField(db_column='KEY_HASH', max_length=64, unique=True)),
                ('name', models.CharField(blank=True, db_column='NAME', default='', max_length=255)),
                ('scope', models.CharField(
                    blank=True,
                    choices=[('executions', 'Executions'), ('catalog', 'Catalog'), ('full', 'Full')],
                    db_column='SCOPE',
                    max_length=50,
                    null=True,
                )),
                ('expires_at', models.DateTimeField(blank=True, db_column='EXPIRES_AT', null=True)),
                ('is_active', models.BooleanField(db_column='IS_ACTIVE', default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='UPDATED_AT')),
            ],
            options={
                'db_table': 'API_KEYS',
                'ordering': ['-created_at'],
            },
        ),
    ]
