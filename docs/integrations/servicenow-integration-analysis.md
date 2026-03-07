# Analyse intégration ServiceNow — Points d'entrée et descriptions paramétrables

**Date :** 2026-03-02  
**Contexte :** API ServiceNow custom (non standard) — adapter les points d'entrée et permettre des descriptions avec variables issues des inputs.

---

## 1. Points d'entrée actuels

### 1.1 Création du changement (create_change)

| Emplacement | Fichier | Quand | Données disponibles |
|-------------|---------|-------|---------------------|
| **Unique point d'appel** | `executions/container_workflow_runtime.py` | Avant RUNNING, si `change_type_config[env].required == True` | `action`, `execution`, `environment`, `env_config` |

**Important :** Le changement ServiceNow n'est créé que pour les **workflows conteneur** (`item_type='workflow'`). Les **actions** (`item_type='action'`) ne déclenchent pas `create_change` actuellement.

### 1.2 Données passées à create_change (actuel)

```python
# container_workflow_runtime.py, lignes 536-541
change_number = svc.create_change(
    change_model_code=env_config.get('change_model_code') or env_config.get('template_id'),
    change_type=env_config.get('change_type'),
    short_description=f"IDP Portal — {self.action.name}",
    description=f"Exécution automatisée {self.execution.id} (env: {environment})",
)
```

- **short_description** : fixe `"IDP Portal — {action.name}"`
- **description** : fixe `"Exécution automatisée {execution.id} (env: {environment})"`
- **Paramètres d'exécution** : `execution.get_parameters()` existe mais n'est pas utilisé pour la description.

### 1.3 Points d'entrée manquants (non implémentés)

| Méthode | Statut | Usage attendu |
|---------|--------|---------------|
| `close_change(change_id)` | `NotImplementedError` | À la fin de l'exécution (COMPLETED, FAILED, CANCELLED) |
| `update_change(change_id)` | `NotImplementedError` | Mise à jour intermédiaire si besoin |
| `get_change_status(change_id)` | `NotImplementedError` | Vérification statut (optionnel) |

**Où appeler close_change :** Lors des transitions vers états terminaux :
- `container_workflow_runtime._execute_workflow_steps()` (l.639-649)
- `workflow_runtime.run()` (l.487-489)
- `executions/tasks/polling._update_execution_from_poll()` (via `ExecutionService.update_status`)
- `executions/services.ExecutionService.update_status()`

---

## 2. Proposition : descriptions paramétrables avec variables

### 2.1 Besoin

Chaque modèle de changement ServiceNow peut exiger une **description spécifique** dans laquelle des **variables** doivent être remplacées par des **valeurs issues des paramètres d'exécution** (inputs du wizard).

Exemple :
- Template : `"Patching de {{target_name}} — Patch {{patch_id}} appliqué par {{user}}"`
- Variables : `{{target_name}}`, `{{patch_id}}`, `{{user}}`
- Sources : `execution.get_parameters()`, `execution.environment`, `action.name`, etc.

### 2.2 Structure proposée dans change_type_config

Étendre `ChangeTypeConfigEntry` par environnement :

```json
{
  "prod": {
    "required": true,
    "change_model_code": "CHG_TPL_PATCH",
    "change_type": "normal",
    "description_template": "Patching de {{target_name}} — Patch {{patch_id}}. Env: {{environment}}.",
    "short_description_template": "IDP — {{action_name}} — {{target_name}}",
    "variable_mapping": {
      "target_name": "target_names.0",
      "patch_id": "patch_id",
      "action_name": "_meta.action_name",
      "environment": "_meta.environment"
    }
  }
}
```

**Convention :**
- `description_template` / `short_description_template` : chaîne avec placeholders `{{var_name}}`
- `variable_mapping` (optionnel) : mapping `var_name` → chemin dans les paramètres
  - `"target_name": "target_names.0"` → `parameters["target_names"][0]`
  - `"patch_id": "patch_id"` → `parameters["patch_id"]`
  - `"_meta.action_name"` : métadonnées (action.name, execution.id, environment, etc.)

### 2.3 Métadonnées système (_meta)

Variables toujours disponibles sans mapping :

| Variable | Source |
|----------|--------|
| `action_name` | `action.name` |
| `execution_id` | `execution.id` |
| `environment` | `execution.environment` |
| `user` | `execution.user.username` |

### 2.4 Règles de résolution

1. Si `variable_mapping` est absent : utiliser uniquement `_meta.*`
2. Si une variable n'est pas trouvée : remplacer par `""` ou `"<non défini>"` (configurable)
3. Validation : à la sauvegarde de l'action, vérifier que les clés de `variable_mapping` correspondent à des propriétés du `parameters_schema` (ou `_meta`)

### 2.5 Interface utilisateur (ChangeTypeConfig)

Pour chaque environnement avec `required=true` :

1. **Description (template)** : `TextArea` avec placeholder `{{variable}}`
2. **Short description (template)** : `Input` (optionnel, défaut : `"IDP — {{action_name}}"`)
3. **Mapping variables** : liste éditable
   - Variable : `target_name`
   - Source : dropdown ou autocomplete des clés de `parameters_schema` + `_meta.*`
   - Ou mode avancé : saisie du chemin (ex. `target_names.0`, `patch_id`)

**Aide contextuelle :** Afficher les propriétés disponibles depuis `parameters_schema` pour guider l'utilisateur.

---

## 3. Architecture technique proposée

### 3.1 Service de résolution des templates

```python
# executions/servicenow_template_resolver.py (nouveau)
def resolve_description_template(
    template: str,
    parameters: dict | None,
    variable_mapping: dict[str, str] | None,
    meta: dict[str, str],
) -> str:
    """Remplace {{var}} par les valeurs selon variable_mapping et _meta."""
    ...
```

### 3.2 Flux dans _create_servicenow_change_if_required

```python
# 1. Récupérer template et mapping depuis env_config
description_template = env_config.get('description_template') or "Exécution {{execution_id}} (env: {{environment}})"
short_description_template = env_config.get('short_description_template') or "IDP Portal — {{action_name}}"
variable_mapping = env_config.get('variable_mapping') or {}

# 2. Construire meta
meta = {
    'action_name': self.action.name,
    'execution_id': str(self.execution.id),
    'environment': environment,
    'user': getattr(self.execution.user, 'username', ''),
}

# 3. Résoudre les templates
params = self.execution.get_parameters() or {}
description = resolve_description_template(description_template, params, variable_mapping, meta)
short_description = resolve_description_template(short_description_template, params, variable_mapping, meta)

# 4. Appeler create_change avec les descriptions résolues
change_number = svc.create_change(
    ...,
    short_description=short_description,
    description=description,
)
```

### 3.3 Abstraction pour API custom

Le `ServiceNowService` actuel utilise l'API standard (`/api/now/table/change_request`). Pour une **API custom** :

1. **Option A** : Le `base_url` de l'intégration pointe vers l'API custom ; le service envoie un payload générique (change_model_code, description, etc.) et l'API custom fait le mapping.
2. **Option B** : Ajouter dans `Integration.config` un champ `api_style: "standard" | "custom"` et adapter le payload selon le style.
3. **Option C** : Le service reste générique ; le payload est construit à partir de `env_config` étendu (ex. `custom_fields`, `description_field_name`) pour s'adapter aux attentes de l'API custom.

**Recommandation :** Option A ou C — garder le service agnostique, configurer l'URL et le format via l'intégration.

---

## 4. Plan d'implémentation

| Phase | Tâche | Effort |
|-------|-------|--------|
| 1 | Étendre `change_type_config` avec `description_template`, `short_description_template`, `variable_mapping` | 1 j |
| 2 | Créer `resolve_description_template()` et l'intégrer dans `_create_servicenow_change_if_required` | 0.5 j |
| 3 | Mettre à jour `ChangeTypeConfig` (frontend) : champs template + mapping | 1 j |
| 4 | Validation : vérifier que les variables mappées existent dans parameters_schema | 0.5 j |
| 5 | Implémenter `close_change()` (signature + appel API custom) et l'appeler aux points de terminaison | 1–2 j |

---

## 5. Fichiers à modifier

| Fichier | Modification |
|---------|--------------|
| `catalog/validators.py` | Valider `description_template`, `variable_mapping` |
| `executions/container_workflow_runtime.py` | Utiliser templates + resolver dans `_create_servicenow_change_if_required` |
| `services/servicenow_service.py` | Adapter `create_change` pour accepter payload flexible ; implémenter `close_change` |
| `frontend/.../ChangeTypeConfig.tsx` | Ajouter TextArea description, Input short_description, éditeur mapping |
| `frontend/.../catalog.ts` | Étendre `ChangeTypeConfigEntry` |
| `docs/backend/change-type-config.md` | Documenter les nouveaux champs |
