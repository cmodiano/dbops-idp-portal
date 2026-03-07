# change_type_config — Configuration par environnement

## Contexte

Le champ `Action.change_type_config` (OracleJSONField) stocke la configuration du type de changement ServiceNow **par environnement**. Il est étendu dans la Story 25.4 pour inclure des overrides de gouvernance (opération autorisée, plage de maintenance, approbation).

Référence : `_bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md` (dépôt) section 2.

## Structure JSON

```json
{
  "prod": {
    "change_type": "normal",
    "template_id": "CHG_TPL_001",
    "required": true,
    "change_model_code": "1516B",
    "requires_maintenance_window": true,
    "requires_approval": true,
    "allowed": true
  },
  "staging": {
    "change_type": "standard",
    "requires_maintenance_window": false,
    "requires_approval": false,
    "allowed": true
  },
  "dev": {
    "allowed": true,
    "requires_maintenance_window": false,
    "requires_approval": false
  }
}
```

## Champs par environnement

| Champ | Type | Requis | Description |
|------|------|--------|-------------|
| `required` | boolean | Non | Changement ServiceNow requis pour cet environnement |
| `change_model_code` | string | Si required=true | Code modèle alphanumérique (max 50) |
| `change_type` | string | Non | Type de changement ServiceNow |
| `template_id` | string | Non | ID du template ServiceNow |
| `allowed` | boolean | Non | Si `false` → exécution refusée pour cet env. Défaut : `true` |
| `requires_maintenance_window` | boolean | Non | Nécessite une plage de maintenance. Défaut : `false` |
| `requires_approval` | boolean | Non | Nécessite une approbation avant exécution. Défaut : `false` |

## Rétrocompatibilité

- Absence de `allowed` → traité comme `true` (comportement existant conservé)
- Les clés existantes (`required`, `change_model_code`) restent inchangées
- Pas de migration SQL : le JSON existant reste valide

## Utilisation côté backend

- **À la soumission** (`executions/views.py`) : lecture via `_get_env_config_case_insensitive(change_type_config, env)`
- Si `allowed === false` → `BadRequestError` (code `EXECUTION_NOT_ALLOWED_FOR_ENVIRONMENT`)
- `requires_maintenance_window` et `requires_approval` sont stockés dans `parameters['_env_config']` pour usage downstream (gate `maintenance_window`, flux ServiceNow)

## Validation

- **catalog/validators.py** : `validate_change_type_config()` — `allowed`, `requires_maintenance_window`, `requires_approval` doivent être booléens si présents ; `required=true` → `change_model_code` obligatoire et alphanumérique

## Voir aussi

- [condition-gates.md](./condition-gates.md) — gates `maintenance_window`, `approval_granted`
- `_bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md` (dépôt)
