# Tâches de polling — Limites de retry

## Vue d'ensemble

Les tâches Celery de polling surveillent l'état des jobs sur les plateformes distantes
(AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud). Elles se re-planifient
automatiquement tant que le job n'est pas terminé.

## Limite de retry (Story 30.7)

Chaque tâche de polling possède un paramètre `retry_count` incrémenté à chaque erreur
d'adapter (connexion refusée, timeout, erreur HTTP, etc.).

- **MAX_POLLING_RETRIES** : 20 tentatives
- **Intervalle par défaut** : 5 secondes (AAP, Tower, Azure DevOps) ou 60 secondes (GitHub, Terraform)
- **Durée maximale avant abandon** : ~100s (5s × 20) à ~20min (60s × 20)

### Comportement

1. **Poll réussi (non-terminal)** : `retry_count` remis à 0, re-planification normale
2. **Poll réussi (terminal)** : tâche terminée, statut final enregistré
3. **Erreur adapter (retry_count < MAX)** : re-planification avec `retry_count + 1`
4. **Erreur adapter (retry_count >= MAX)** : exécution marquée `FAILED`, audit `EXECUTION_POLLING_EXHAUSTED`

### Audit

Quand le maximum de retries est atteint :
- Type d'audit : `EXECUTION_POLLING_EXHAUSTED`
- Détails : `platform_job_id`, `retry_count`, `max_retries`, `last_error`
- Le step de polling est marqué `FAILED` avec un `error_message` explicite

## Tâches de polling

| Tâche | Plateforme | Intervalle | Fichier |
|-------|-----------|------------|---------|
| `poll_aap_job_status` | AAP/AWX | 5s | `executions/tasks.py` |
| `poll_tower_job_status` | Tower/AWX | 5s | `executions/tasks.py` |
| `poll_azure_devops_run_status` | Azure DevOps | 5s | `executions/tasks.py` |
| `poll_github_actions_run_status` | GitHub Actions | 60s | `executions/tasks.py` |
| `poll_terraform_cloud_run_status` | Terraform Cloud | 60s | `executions/tasks.py` |

## Configuration

La constante `MAX_POLLING_RETRIES` est définie dans `executions/tasks.py`.
Pour modifier la limite, ajuster cette constante et redéployer.
