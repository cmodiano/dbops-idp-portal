# Security Reports

Ce dossier contient les rapports de sécurité générés automatiquement par les outils d'audit.

## pip-audit-report.json

Rapport JSON généré par `pip-audit` qui scanne **toutes** les dépendances Python du virtualenv de développement, y compris les dépendances de test et développement.

**Note importante:** Ce rapport peut contenir des références à des packages comme `fastapi`, `uvicorn`, ou `starlette` dans la liste complète des dépendances scannées. Ces références sont des **artefacts historiques** du scan de l'environnement complet et ne signifient PAS que ces packages sont utilisés dans le code de production.

**Dépendances de production:** Voir `django_backend/requirements.txt` pour la liste officielle des dépendances backend Django.

## Autres rapports

- `bandit-report.json` : Analyse de sécurité statique du code Python (SAST)
- `.secrets.baseline` : Baseline detect-secrets pour éviter les faux positifs
