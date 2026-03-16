# Documentation IDP Portal

Documentation du portail développeur interne (IDP Portal).

## Consultation en local

```bash
pip install -r docs-requirements.txt
mkdocs serve
```

Puis ouvrir **http://127.0.0.1:8000**.

## Structure

| Dossier | Contenu |
|---------|---------|
| `architecture/` | Architecture système, guide développeur, workflows, caching, CaC |
| `api/` | Contrats API backend/frontend, documentation Swagger, self-service |
| `backend/` | Django : modèles, services, RBAC, auth, observabilité, intégrations |
| `frontend/` | React : composants, routing, state, design system, tests |
| `integrations/` | Documentation des plateformes externes (AAP, ServiceNow, Terraform, etc.) |
| `operations/` | Déploiement, exploitation production, polling, secrets |
| `security/` | Architecture sécurité, compliance SOC1, WebSocket auth |
| `reference/` | Glossaire, conventions, feature flags, linters, inventaire |
