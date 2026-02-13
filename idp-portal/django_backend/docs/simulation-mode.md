# Mode Simulation - Développement (Story 19.0)

Le mode simulation permet de tester l'UX de la vue d'exécution temps réel sans dépendre des plateformes distantes (AAP, ServiceNow, Vault).

## Configuration Backend

Variables d'environnement (fichier `.env`) :

| Variable | Type | Défaut | Description |
|---|---|---|---|
| `SIMULATE_EXECUTION_DEV` | bool | `DEBUG` | Active le mode simulation |
| `SIMULATE_EXECUTION_FAILURE_RATE` | float | `0.1` | Taux d'échecs aléatoires (0.0 à 1.0) |
| `SIMULATE_EXECUTION_STEP_DURATION` | int | `2` | Durée de chaque étape en secondes |

```bash
# .env
SIMULATE_EXECUTION_DEV=true
SIMULATE_EXECUTION_FAILURE_RATE=0.1
SIMULATE_EXECUTION_STEP_DURATION=2
```

## Configuration Frontend

Variable dans `frontend/.env.development` :

| Variable | Type | Défaut | Description |
|---|---|---|---|
| `VITE_SIMULATE_EXECUTION` | string | - | Force le mode polling (pas de WebSocket) |

```bash
# frontend/.env.development
VITE_SIMULATE_EXECUTION=true
```

## Comportement

### Backend

Quand `SIMULATE_EXECUTION_DEV=true` :

1. **POST /api/v1/executions/** crée automatiquement 5 ExecutionSteps simulés :
   - Préparation (prerequisite)
   - Récupération secrets Vault (vault)
   - Déclenchement plateforme (platform)
   - Exécution distante (platform)
   - Vérification résultat (verification)

2. Un thread daemon fait progresser chaque étape :
   - PENDING → RUNNING (avec `started_at`)
   - Logs fictifs accumulés dans `output`
   - RUNNING → COMPLETED (avec `completed_at`)

3. L'exécution progresse : SUBMITTED → RUNNING → COMPLETED (ou FAILED selon `FAILURE_RATE`)

4. Aucun appel aux plateformes réelles (AAP, ServiceNow, Vault) n'est effectué.

### Frontend

Quand `VITE_SIMULATE_EXECUTION=true` ou WebSocket indisponible :

1. Le composant `ExecutionTimeline` utilise le hook `useExecutionPolling` au lieu de `useWebSocket`
2. Polling toutes les 2.5s : GET /executions/{id} + GET /executions/{id}/steps
3. Un indicateur visuel "Mode polling activé (dev)" est affiché
4. Le polling s'arrête automatiquement quand l'exécution atteint un statut terminal (COMPLETED, FAILED, CANCELLED, REJECTED)

## Désactivation

Pour revenir au mode normal (appels plateforme réels + WebSocket) :

```bash
# Backend
SIMULATE_EXECUTION_DEV=false

# Frontend
# Supprimer ou commenter VITE_SIMULATE_EXECUTION dans .env.development
```

## Tests

```bash
# Tests backend simulation
.venv/bin/python -m pytest executions/tests/test_simulation_service.py -v
.venv/bin/python -m pytest executions/tests/test_execution_api_simulation.py -v

# Tests frontend polling
npx vitest run src/hooks/useExecutionPolling.test.ts
npx vitest run src/components/execution/ExecutionTimeline.test.tsx
```
