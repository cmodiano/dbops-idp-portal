# Documentation IDP Portal

Documentation consolidée du portail développeur interne (IDP Portal).

## Consultation en local

```bash
# À la racine du projet
pip install -r docs-requirements.txt
mkdocs serve
```

Puis ouvrir **http://127.0.0.1:8000** dans un navigateur.

## Build pour déploiement

```bash
mkdocs build
```

Le site statique est généré dans le dossier `site/`.

## Structure

| Dossier | Contenu |
|---------|---------|
| `overview/` | Vue d'ensemble, structure, stack technique |
| `architecture/` | Architecture frontend, backend, intégration |
| `api/` | Contrats API, documentation, self-service |
| `backend/` | Django, ADR, runbooks, standards |
| `frontend/` | React, composants, design system |
| `operations/` | Déploiement, exploitation |
| `security/` | Sécurité, audit, compliance |
| `integrations/` | Analyses d'intégrations externes |
| `reference/` | Guides, conventions, glossaire |
