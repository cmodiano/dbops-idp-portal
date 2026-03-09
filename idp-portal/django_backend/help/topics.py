from pathlib import Path

from django.conf import settings

# Répertoire contenant les fichiers d'aide Markdown (in-app pour Docker)
HELP_DIR = Path(settings.BASE_DIR).resolve() / 'help' / 'data'

# Liste blanche topic_id → nom de fichier (sécurité path traversal)
# HELP-LOW-01: Whitelist statique — l'ajout d'un topic nécessite (1) modifier ce dict,
# (2) ajouter le fichier .md dans help/data/, (3) déployer le backend.
# Acceptable à l'échelle actuelle (3 topics). Solution future : auto-découverte *.md dans HELP_DIR.
HELP_TOPICS: dict[str, str] = {
    "action-form-integration": "action-form-integration.md",
    "action-form-changement-servicenow": "action-form-changement-servicenow.md",
    "action-form-gates": "action-form-gates.md",
}
