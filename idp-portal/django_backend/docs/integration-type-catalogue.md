# Catalogue des Types d'Intégration

> Story 24.1 — Modèle `IntegrationTypeCatalogue` + `IntegrationAction` et API de lecture.

## Architecture

### Schéma ER

```
IntegrationTypeCatalogue (1) ──── (N) IntegrationAction
         PK: code                      PK: id
                                       FK: integration_type_code
```

### Tables Oracle

| Table | Description |
|-------|-------------|
| `INTEGRATION_TYPE_CATALOGUE` | Types d'intégration supportés (AAP, ServiceNow, etc.) |
| `INTEGRATION_ACTIONS` | Actions disponibles par type (start_job, create_change, etc.) |

### Modèle IntegrationTypeCatalogue

| Champ | Type | Description |
|-------|------|-------------|
| `code` | CharField(50), PK | Code unique du type (ex: `aap`, `servicenow`) |
| `name` | CharField(255) | Nom affichage (ex: `Ansible Automation Platform`) |
| `description` | TextField | Description du type d'intégration |
| `version` | CharField(20) | Version du catalogue (ex: `1.0`) |
| `is_active` | BooleanField | Actif/déprécié |
| `created_at` | DateTimeField | Date de création |
| `updated_at` | DateTimeField | Date de mise à jour |

### Modèle IntegrationAction

| Champ | Type | Description |
|-------|------|-------------|
| `id` | BigAutoField, PK | Identifiant auto-incrémenté |
| `integration_type` | FK → IntegrationTypeCatalogue | Type parent |
| `action_code` | CharField(100) | Code technique (ex: `start_job`) |
| `action_label` | CharField(255) | Label UI (ex: `Démarrer un job`) |
| `description` | TextField | Description de l'action |
| `required_params` | TextField (JSON) | Schéma JSON des paramètres obligatoires |
| `optional_params` | TextField (JSON) | Schéma JSON des paramètres optionnels |
| `response_format` | TextField (JSON) | Description du format de réponse |
| `is_active` | BooleanField | Actif/déprécié |
| `created_at` | DateTimeField | Date de création |
| `updated_at` | DateTimeField | Date de mise à jour |

**Contrainte unique :** `(integration_type, action_code)`

## Types Supportés

### AAP (Ansible Automation Platform)

| Action | Label | Paramètres obligatoires |
|--------|-------|------------------------|
| `start_job` | Démarrer un job | `job_template_id` (integer) |
| `start_workflow` | Démarrer un workflow | `workflow_job_template_id` (integer) |
| `get_job_status` | Récupérer le statut d'un job | `job_id` (integer) |
| `cancel_job` | Annuler un job | `job_id` (integer) |

### ServiceNow ITSM

| Action | Label | Paramètres obligatoires |
|--------|-------|------------------------|
| `create_change` | Créer un changement | `short_description`, `category` |
| `update_change` | Mettre à jour un changement | `change_id` |
| `get_change_status` | Récupérer le statut d'un changement | `change_id` |

## Format JSON Schema des Paramètres

Les champs `required_params` et `optional_params` utilisent un format JSON Schema simplifié :

```json
{
  "type": "object",
  "properties": {
    "job_template_id": {
      "type": "integer",
      "description": "ID du job template AAP"
    }
  },
  "required": ["job_template_id"]
}
```

## API Endpoints

### GET /api/v1/integrations/types/

Liste tous les types d'intégration actifs avec leurs actions.

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/types/
```

**Réponse 200 :**
```json
{
  "data": [
    {
      "code": "aap",
      "name": "Ansible Automation Platform",
      "description": "Exécution de jobs et workflows Ansible via AAP Controller",
      "version": "1.0",
      "is_active": true,
      "created_at": "2026-02-10T10:00:00Z",
      "updated_at": "2026-02-10T10:00:00Z",
      "actions": [
        {
          "id": 1,
          "action_code": "start_job",
          "action_label": "Démarrer un job",
          "description": "Lance un job template AAP avec paramètres extra_vars",
          "required_params": {"type": "object", "properties": {"job_template_id": {"type": "integer"}}},
          "optional_params": {"type": "object", "properties": {"extra_vars": {"type": "object"}}},
          "response_format": {"job_id": "integer", "status": "string"},
          "is_active": true,
          "created_at": "2026-02-10T10:00:00Z",
          "updated_at": "2026-02-10T10:00:00Z"
        }
      ]
    }
  ]
}
```

### GET /api/v1/integrations/types/{code}/

Récupère un type spécifique avec ses actions.

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/types/aap/
```

**Réponse 404 si le code n'existe pas.**

### GET /api/v1/integrations/types/{code}/actions/

Liste les actions d'un type spécifique.

```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/integrations/types/aap/actions/
```

## Guide : Ajouter un nouveau type d'intégration

1. **Créer le type** dans la fixture `integrations/fixtures/integration_type_catalogue.json` ou via l'admin Django :
   ```json
   {
     "model": "integrations.integrationtypecatalogue",
     "pk": "terraform",
     "fields": {
       "name": "Terraform Cloud",
       "description": "Gestion d'infrastructure via Terraform",
       "version": "1.0",
       "is_active": true,
       "created_at": "2026-02-10T10:00:00Z",
       "updated_at": "2026-02-10T10:00:00Z"
     }
   }
   ```

2. **Ajouter les actions** supportées par ce type :
   ```json
   {
     "model": "integrations.integrationaction",
     "fields": {
       "integration_type": "terraform",
       "action_code": "plan",
       "action_label": "Terraform Plan",
       "description": "Génère un plan d'exécution Terraform",
       "required_params": "{...}",
       "optional_params": "{...}",
       "response_format": "{...}",
       "is_active": true,
       "created_at": "2026-02-10T10:00:00Z",
       "updated_at": "2026-02-10T10:00:00Z"
     }
   }
   ```

3. **Charger les fixtures** :
   ```bash
   python manage.py loaddata integration_type_catalogue
   ```

4. **Vérifier** via l'API :
   ```bash
   curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/v1/integrations/types/terraform/
   ```

## Gestion des Versions et Dépréciation

### Stratégie de Versionnement

Le champ `version` suit un modèle de versionnement sémantique simplifié (`MAJOR.MINOR`) :

| Type de changement | Incrémentation | Exemple | Impact |
|-------------------|---------------|---------|--------|
| **Ajout d'actions** (non-breaking) | Minor | `1.0` → `1.1` | Les intégrations existantes continuent de fonctionner |
| **Modification de paramètres existants** (breaking) | Major | `1.0` → `2.0` | Nécessite migration des intégrations |
| **Suppression d'actions** (breaking) | Major | `1.0` → `2.0` | Nécessite migration des intégrations |
| **Modification du format de réponse** (breaking) | Major | `1.0` → `2.0` | Nécessite adaptation du code client |

### Dépréciation d'un Type ou d'une Action

**Étape 1: Marquer comme inactif**
```python
# Via Django shell ou Admin
type_obj = IntegrationTypeCatalogue.objects.get(code='old_type')
type_obj.is_active = False
type_obj.save()
```

**Étape 2: Communication**
- Les types/actions avec `is_active=False` ne sont **plus retournés par l'API** (`GET /api/v1/integrations/types`)
- Les intégrations existantes utilisant un type déprécié continuent de fonctionner **mais un warning est loggé** (Story 24.4)

**Étape 3: Migration**
- Identifier les intégrations affectées : `Integration.objects.filter(type='old_type')`
- Mettre à jour manuellement ou via script de migration vers le nouveau type
- Les exécutions utilisant un type déprécié **sont rejetées avec erreur explicite** (Story 24.4)

**Étape 4: Suppression (optionnelle)**
- **JAMAIS supprimer les données** de la table (violation SOC1/NFR8 audit trail)
- Garder `is_active=False` indéfiniment pour traçabilité historique

### Migration Breaking Changes

Exemple : Changement du paramètre `job_template_id` (integer) vers `job_template_name` (string) dans AAP `start_job`

**1. Créer nouvelle version du type :**
```json
{
  "model": "integrations.integrationtypecatalogue",
  "pk": "aap",
  "fields": {
    "version": "2.0",  // Incrément major
    ...
  }
}
```

**2. Modifier l'action avec nouveaux paramètres :**
```json
{
  "model": "integrations.integrationaction",
  "fields": {
    "integration_type": "aap",
    "action_code": "start_job",
    "required_params": "{\"type\": \"object\", \"properties\": {\"job_template_name\": {\"type\": \"string\"}}, \"required\": [\"job_template_name\"]}", // CHANGÉ
    ...
  }
}
```

**3. Script de migration des intégrations existantes :**
```python
# Adapter les configurations JSON des intégrations existantes
for integration in Integration.objects.filter(type='aap'):
    config = integration.get_config()
    if 'job_template_id' in config:
        config['job_template_name'] = resolve_template_name(config['job_template_id'])
        del config['job_template_id']
        integration.set_config(config)
        integration.save()
```

**4. Validation lors des exécutions** (Story 24.4) :
- Valider que `required_params` du catalogue correspondent aux params fournis
- Rejeter les exécutions avec paramètres obsolètes

## Audit Trail

Toute création ou modification de type ou d'action est automatiquement auditée via les signaux Django `post_save` :

- `INTEGRATION_TYPE_CREATED` / `INTEGRATION_TYPE_UPDATED`
- `INTEGRATION_ACTION_CREATED` / `INTEGRATION_ACTION_UPDATED`

Les entrées d'audit sont immutables (SOC1/NFR8).
