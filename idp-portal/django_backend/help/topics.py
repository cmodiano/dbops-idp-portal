from pathlib import Path

from django.conf import settings

# Répertoire contenant les fichiers d'aide Markdown
HELP_DIR = Path(settings.BASE_DIR) / 'docs' / 'help'

# Liste blanche topic_id → nom de fichier (sécurité path traversal)
HELP_TOPICS: dict[str, str] = {
    "action-form-integration": "action-form-integration.md",
    "action-form-changement-servicenow": "action-form-changement-servicenow.md",
    "action-form-gates": "action-form-gates.md",
}
