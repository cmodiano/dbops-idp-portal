# Condition Gates — Préconditions sur les étapes d'exécution

## Scope de Story 25.2

✅ **Implémenté dans cette story :**
- Statut WAITING ajouté à ExecutionStepStatus (modèle + migrations Django + SQL)
- Schéma JSON gate_conditions documenté et validé côté backend
- WorkflowRuntime crée ExecutionStep en WAITING si gate_conditions présent
- Contexte d'attente stocké dans ExecutionStep.output avec waiting_since, gate_conditions, gate_status
- Validation gate_conditions intégrée dans CatalogService.update_execution_steps()
- Tests unitaires (29) et d'intégration (7) pour tous les ACs

❌ **Hors scope (Story 25.3 — à venir) :**
- Évaluation périodique des gates (tâche Celery Beat `evaluate_waiting_gates`)
- Transition WAITING → RUNNING quand conditions satisfaites
- Implémentation des evaluators spécifiques (maintenance_window, time_window, approval_granted, target_state)
- Gestion des timeouts et passage en FAILED/SKIPPED selon on_timeout
- Déblocage et reprise d'exécution après satisfaction des gates

---

## Concept

Les **condition gates** (portes conditionnelles) permettent de définir des préconditions sur une étape d'exécution d'un workflow. Une étape avec des gate_conditions ne démarre pas immédiatement : elle est créée avec le statut **WAITING** et attend que toutes ses conditions soient satisfaites avant de passer en exécution.

### Cas d'usage

- **Plage de maintenance** : ne déployer que pendant la fenêtre de maintenance des serveurs cibles
- **Créneau horaire** : exécuter uniquement entre 22h et 6h (hors heures ouvrables)
- **Approbation** : attendre qu'un DBA approuve manuellement l'étape
- **État cible** : attendre que le serveur soit en mode maintenance

## Structure JSON des gate_conditions

Les `gate_conditions` sont un attribut optionnel d'une étape dans le champ `execution_steps` (JSON CLOB) d'une Action.

### Schéma d'une condition

```json
{
  "type": "maintenance_window | time_window | approval_granted | target_state",
  "description": "Description lisible (optionnel)",
  "timeout_hours": 48,
  "on_timeout": "FAIL | SKIP"
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `type` | string | **Oui** | Type de condition : `maintenance_window`, `time_window`, `approval_granted`, `target_state` |
| `description` | string | Non | Description lisible pour l'utilisateur |
| `timeout_hours` | number | Non | Délai maximum d'attente en heures (doit être > 0) |
| `on_timeout` | string | Non | Comportement si timeout : `FAIL` (échouer) ou `SKIP` (ignorer l'étape) |

## Types de conditions supportés

### 1. maintenance_window

Attend la plage de maintenance des serveurs cibles (via l'inventaire).

```json
{
  "type": "maintenance_window",
  "description": "Attendre la plage de maintenance des serveurs cibles",
  "timeout_hours": 72,
  "on_timeout": "FAIL"
}
```

**Évaluation** : interroge l'inventaire via `InventoryService.get_next_maintenance_window(target_id)` pour chaque `ExecutionTarget`. Si au moins un serveur n'est pas dans sa plage, condition = NON SATISFAITE. Le contexte retourné inclut `next_possible_at`.

### 2. time_window

Attend un créneau horaire spécifique.

```json
{
  "type": "time_window",
  "after": "22:00",
  "before": "06:00",
  "timezone": "America/Toronto",
  "description": "Exécuter uniquement entre 22h et 6h (heure de Toronto)",
  "timeout_hours": 24,
  "on_timeout": "SKIP"
}
```

**Évaluation** : vérifie que l'heure actuelle (dans le timezone spécifié) est entre `after` et `before`.

### 3. approval_granted

Attend une approbation manuelle.

```json
{
  "type": "approval_granted",
  "description": "Attendre l'approbation manuelle d'un DBA",
  "timeout_hours": 48,
  "on_timeout": "FAIL"
}
```

**Évaluation** : vérifie qu'une approbation a été accordée pour cette étape d'exécution.

### 4. target_state

Attend qu'une cible soit dans un état donné.

```json
{
  "type": "target_state",
  "required_state": "MAINTENANCE",
  "description": "Attendre que le serveur cible soit en mode maintenance",
  "timeout_hours": 12,
  "on_timeout": "SKIP"
}
```

**Évaluation** : interroge l'inventaire pour vérifier l'état de la cible.

## Cycle de vie d'une étape WAITING

```
PENDING → WAITING → RUNNING → COMPLETED/FAILED
                  ↘ (timeout) → FAILED/SKIPPED
```

1. **Création** : le WorkflowRuntime détecte `gate_conditions` dans la définition de l'étape
2. **WAITING** : l'ExecutionStep est créé avec `status='WAITING'` et un contexte d'attente dans `output`
3. **Évaluation périodique** : la tâche Celery Beat `evaluate_waiting_gates` vérifie les conditions
4. **Déblocage** : quand toutes les conditions sont satisfaites, l'étape passe en RUNNING
5. **Timeout** : si `timeout_hours` expire, l'étape passe en FAILED ou SKIPPED selon `on_timeout`

### Contexte d'attente (ExecutionStep.output)

Quand une étape est en WAITING, son champ `output` contient :

```json
{
  "waiting_since": "2026-02-10T15:30:00Z",
  "gate_conditions": [
    {
      "type": "maintenance_window",
      "timeout_hours": 72,
      "on_timeout": "FAIL"
    }
  ],
  "gate_status": [
    {
      "type": "maintenance_window",
      "satisfied": false,
      "reason": "En attente d'évaluation",
      "next_evaluation_at": null
    }
  ]
}
```

## Exemple complet

```json
{
  "execution_steps": [
    {
      "order": 1,
      "step_id": "prepare",
      "name": "Préparer le déploiement",
      "type": "platform",
      "referenced_action_id": 12
    },
    {
      "order": 2,
      "step_id": "deploy",
      "name": "Déployer le patch Oracle",
      "type": "platform",
      "referenced_action_id": 15,
      "gate_conditions": [
        {
          "type": "maintenance_window",
          "description": "Attendre la plage de maintenance",
          "timeout_hours": 72,
          "on_timeout": "FAIL"
        }
      ],
      "on_success_step_id": "verify"
    },
    {
      "order": 3,
      "step_id": "verify",
      "name": "Vérification post-déploiement",
      "type": "verification",
      "referenced_action_id": 18
    }
  ]
}
```

Dans cet exemple, l'étape 2 (deploy) attend la plage de maintenance avant de s'exécuter. L'étape 1 s'exécute normalement, puis le workflow s'arrête à l'étape 2 en WAITING.

## Validation

La validation des `gate_conditions` est effectuée côté backend lors de la création ou modification d'une action :

- `gate_conditions` doit être un tableau JSON (peut être vide)
- Chaque condition doit avoir un champ `type` valide
- Si `timeout_hours` est présent, il doit être un nombre > 0
- Si `on_timeout` est présent, il doit être `FAIL` ou `SKIP`

Les champs spécifiques par type (ex: `after`, `before` pour `time_window`) sont validés par les evaluators correspondants.

## Limitations

- **Pas d'évaluation synchrone** : les gates sont évaluées périodiquement par une tâche Celery Beat, pas en temps réel
- **Types limités** : seuls 4 types de conditions sont supportés dans cette version
- **Pas de conditions composées** : toutes les conditions doivent être satisfaites (ET logique), pas de OU
- **Champs spécifiques non validés** : les champs propres à chaque type (ex: `after`, `timezone`) sont validés uniquement lors de l'évaluation

## Références

- Story 25.1 : ExecutionTarget (fondation cibles explicites)
- Story 25.2 : Condition Gates (cette fonctionnalité)
- Story 25.3 : Tâche Celery Beat evaluate_waiting_gates (évaluation et déblocage)
