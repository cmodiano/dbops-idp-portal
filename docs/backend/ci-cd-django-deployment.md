# CI/CD Django Deployment Guide

## Vue d'ensemble

Le pipeline CI/CD utilise GitHub Actions pour automatiser le lint, les tests, le build et le
déploiement de l'application IDP Portal (backend Django + frontend React).

**Fichier workflow :** `.github/workflows/deploy.yml`

## Déclencheurs

| Événement | Branche | Environnement cible | Mode |
|-----------|---------|---------------------|------|
| `push` | `develop` | staging | Automatique |
| `push` | `main` | staging | Automatique |
| `workflow_dispatch` | N/A | staging ou production | Manuel |

### Auto-deploy staging

Chaque push vers `develop` déclenche automatiquement :
1. Lint backend (ruff) + frontend (ESLint)
2. Type check backend (mypy) + frontend (tsc)
3. Tests backend (pytest) + frontend (vitest)
4. Build frontend (vite)
5. Déploiement staging si toutes les étapes passent

### Deploy production (manuel)

Production nécessite un déclenchement manuel via `workflow_dispatch` :

**Via interface web GitHub:**
1. Aller dans Actions > Deploy > Run workflow
2. Sélectionner `environment: production`
3. L'environnement GitHub `production` peut exiger des approbateurs

**Via CLI GitHub (`gh`):**
```bash
gh workflow run deploy.yml -f environment=production
```

**Note:** Nécessite `gh` CLI authentifié et permissions sur le repo.

## Jobs du pipeline

```
lint-backend ──┐
lint-frontend ─┤
typecheck-backend ─┤
typecheck-frontend ─┼──► build-frontend ──► deploy
test-backend ──┤
test-frontend ─┘
```

## Étapes de déploiement

1. **Backup** : Copie du release actuel (`django_backend.bak`, `frontend/dist.bak`)
2. **rsync frontend** : Synchronisation `frontend/dist/` vers le serveur
3. **rsync backend** : Synchronisation `django_backend/` (sans `__pycache__`, tests, `.env*`)
4. **Install deps** : `uv pip install -r requirements.lock`
5. **collectstatic** : Assets statiques Django
6. **migrate --check** : Vérification migrations (pas d'application automatique)
7. **systemctl restart** : Redémarrage du service `idp-django`
8. **Health check** : `curl /api/v1/health` (délai 5s)
9. **Smoke tests** : `post-switchover-validation.sh` (non-bloquant)

## Rollback automatique

Si le health check échoue après déploiement :
1. Le backup précédent est restauré automatiquement
2. Le service Django est redémarré avec l'ancienne version
3. Le job est marqué en échec dans GitHub Actions

## Secrets requis

| Secret | Description |
|--------|-------------|
| `DEPLOY_KEY` | Clé SSH privée pour le serveur |
| `DEPLOY_HOST` | Hostname du serveur cible |
| `DEPLOY_USER` | Utilisateur SSH |
| `DEPLOY_PATH` | Chemin d'installation sur le serveur |

## Environnements GitHub

Configurer dans Settings > Environments :

- **staging** : Pas de protection, déploiement automatique
- **production** : Reviewers requis, protection branche `main`

## Notifications

### Notifications actuelles

Les notifications de succès/échec sont gérées nativement par GitHub Actions :
- Email aux committers et watchers
- Notifications dans l'interface GitHub
- Status checks sur les PRs

### Configuration Slack/Teams (recommandé)

Pour des notifications temps réel en production, ajouter un step au workflow :

```yaml
- name: Notify deployment status
  if: always()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    payload: |
      {
        "text": "Deployment ${{ job.status }} for ${{ github.repository }}",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Deployment:* ${{ job.status }}\n*Environment:* ${{ github.event.inputs.environment || 'staging' }}\n*Commit:* ${{ github.sha }}"
            }
          }
        ]
      }
```

Ou pour Microsoft Teams :
```yaml
- name: Notify Teams
  if: always()
  uses: toko-bifrost/ms-teams-deploy-card@master
  with:
    webhook-uri: ${{ secrets.TEAMS_WEBHOOK_URL }}
```
