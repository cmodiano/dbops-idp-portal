# Migration vide documentant l'ajout de oauth2_client_credentials et api_key
# à Integration.AuthFlow (Story 31.12). La contrainte Oracle est mise à jour via Flyway V088.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("integrations", "0006_integration_secret_service")]
    operations = []
