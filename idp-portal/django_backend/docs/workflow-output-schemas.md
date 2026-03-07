# Workflow Output Schemas — Guide Développeur

Documentation du système de schémas d'output pour les workflows IDP.
Stories 63.1–63.6.

---

## Table des matières

1. [Créer un schéma d'output](#créer-un-schéma-doutput)
2. [API Reference](#api-reference)
3. [Templates Jinja2](#templates-jinja2)
4. [Architecture](#architecture)

---

## Créer un schéma d'output

### Format YAML complet

Les schémas d'output sont définis en YAML selon la structure suivante :

```yaml
items:
  - apiVersion: idp/v1
    kind: OutputSchema
    metadata:
      name: servicenow-create-change      # Identifiant unique global
                                          # Convention : {target}-{operation}
      schema_type: integration            # action | integration | platform_convention
      target_name: servicenow             # Voir "Types" ci-dessous
      operation: create_change            # null pour action et platform_convention
    spec:
      inherits_from: aap-standard         # null ou nom du schéma parent
      output_fields:
        - name: change_number
          path: "$.number"               # JSONPath simple
          type: string                   # string | text | integer | array | boolean
          description: "Numéro de changement CHG"
          required: true
        - name: sys_id
          path: "$.sys_id"
          type: string
          description: "Identifiant système ServiceNow"
          required: false
```

### Types disponibles

| `schema_type`          | Utilisation                               | `target_name`                      | `operation`       |
|------------------------|-------------------------------------------|------------------------------------|-------------------|
| `action`               | Step de type plateforme (step_type=platform) | Nom de l'action catalogue (`Action.name`) | `null`       |
| `integration`          | Step de type service_call                 | Type d'intégration (`integration_type`) | Nom de l'opération |
| `platform_convention`  | Schéma parent partagé (héritage)          | Nom de la convention               | `null`            |

### Héritage

Un schéma peut hériter d'un parent via `inherits_from`. Les champs du schéma enfant écrasent ceux du parent par `name`.

**Règles :**
- Le parent doit exister en base **avant** l'enfant.
- Dans un fichier YAML importé, le parent doit apparaître **avant** l'enfant dans la liste `items`.
- L'héritage est limité à 1 niveau (pas d'héritage en chaîne).

**Exemple avec héritage :**

```yaml
items:
  # Parent : convention commune AAP
  - apiVersion: idp/v1
    kind: OutputSchema
    metadata:
      name: aap-standard
      schema_type: platform_convention
      target_name: aap-standard
      operation: null
    spec:
      inherits_from: null
      output_fields:
        - name: job_id
          path: "$.id"
          type: integer
          description: "ID du job AAP"
          required: true
        - name: job_status
          path: "$.status"
          type: string
          description: "Statut du job"
          required: true

  # Enfant : action spécifique héritant d'aap-standard
  - apiVersion: idp/v1
    kind: OutputSchema
    metadata:
      name: flyway-migrate
      schema_type: action
      target_name: flyway-migrate
      operation: null
    spec:
      inherits_from: aap-standard         # Hérite de job_id et job_status
      output_fields:
        - name: migrations_applied
          path: "$.extra_vars.migrations_applied"
          type: integer
          description: "Nombre de migrations appliquées"
          required: false
```

### Importer des schémas via le management command

```bash
# Charger les schémas seed par défaut
python manage.py seed_output_schemas

# Forcer la mise à jour même si inchangés
python manage.py seed_output_schemas --force
```

### Importer via l'API admin

```bash
# Mode additif (ne supprime pas les schémas absents)
curl -X POST /api/v1/admin/output-schemas/sync/?mode=additive \
  -H "Content-Type: application/x-yaml" \
  --data-binary @my-schemas.yaml

# Mode complet (supprime les schémas absents du YAML)
curl -X POST /api/v1/admin/output-schemas/sync/?mode=full \
  -H "Content-Type: application/x-yaml" \
  --data-binary @my-schemas.yaml
```

---

## API Reference

### Vue d'ensemble des endpoints

| # | Méthode | URL | Permission | Description |
|---|---------|-----|------------|-------------|
| 1 | GET | `/api/v1/output-schemas/` | IsAuthenticated | Liste paginée des schémas |
| 2 | GET | `/api/v1/output-schemas/{id}/` | IsAuthenticated | Détail d'un schéma |
| 3 | GET | `/api/v1/output-schemas/workflows/{id}/steps/{step_id}/output-schema/` | IsAuthenticated | Schéma résolu d'un step |
| 4 | GET | `/api/v1/output-schemas/workflows/{id}/available-variables/` | IsAuthenticated | Variables disponibles par step |
| 5 | GET | `/api/v1/admin/output-schemas/export/yaml/` | IsAdminUser | Export YAML de tous les schémas |
| 6 | POST | `/api/v1/admin/output-schemas/sync/` | IsAdminUser | Import/sync YAML |

---

### 1. Liste des schémas

```
GET /api/v1/output-schemas/
```

**Paramètres de filtre (query string) :**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `schema_type` | string | Filtre par type : `action`, `integration`, `platform_convention` |
| `target_name` | string | Filtre par nom de cible |

**Réponse 200 :**

```json
{
  "count": 8,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "aap-standard",
      "schema_type": "platform_convention",
      "target_name": "aap-standard",
      "operation": null,
      "inherits_from": null,
      "schema_json": {
        "output_fields": [
          {"name": "job_id", "path": "$.id", "type": "integer", "required": true}
        ]
      }
    }
  ]
}
```

---

### 2. Détail d'un schéma

```
GET /api/v1/output-schemas/{id}/
```

**Réponse 200 :** même structure qu'un item de la liste ci-dessus.

---

### 3. Schéma résolu d'un step

```
GET /api/v1/output-schemas/workflows/{workflow_id}/steps/{step_id}/output-schema/
```

Retourne le schéma d'output **résolu** (héritage appliqué) pour un step spécifique d'un workflow.

**Paramètres de chemin :**

| Paramètre | Type | Description |
|-----------|------|-------------|
| `workflow_id` | integer | ID de l'action de type `workflow` |
| `step_id` | string | `step_id` du step dans `execution_steps` |

**Réponse 200 :**

```json
{
  "step_id": "aap_deploy",
  "step_name": "Deploy via AAP",
  "step_type": "platform",
  "schema": {
    "output_fields": [
      {"name": "job_id", "path": "$.id", "type": "integer", "required": true},
      {"name": "job_status", "path": "$.status", "type": "string", "required": true}
    ],
    "template_variables": []
  }
}
```

**Réponse 404 :** si le workflow ou le step est introuvable.

---

### 4. Variables disponibles par step

```
GET /api/v1/output-schemas/workflows/{workflow_id}/available-variables/
```

Retourne les variables disponibles pour tous les steps d'un workflow, triés par `step_order`.
Utilisé par le **VariablePicker** dans l'interface admin.

**Réponse 200 :**

```json
[
  {
    "step_id": "create_change",
    "step_name": "Créer un changement ServiceNow",
    "step_type": "service_call",
    "variables": [
      {"name": "change_number", "path": "$.number", "type": "string", "required": true},
      {"name": "sys_id", "path": "$.sys_id", "type": "string", "required": false}
    ]
  },
  {
    "step_id": "aap_deploy",
    "step_name": "Deploy via AAP",
    "step_type": "platform",
    "variables": [
      {"name": "job_id", "path": "$.id", "type": "integer", "required": true}
    ]
  }
]
```

Seuls les steps ayant un schéma avec des `output_fields` apparaissent dans la réponse.

---

### 5. Export YAML (admin)

```
GET /api/v1/admin/output-schemas/export/yaml/
```

**Permission :** `IsAdminUser`

Exporte tous les schémas en YAML, ordonnés par `id` (parents avant enfants).

**Réponse 200 :**
- Content-Type : `application/x-yaml`
- Corps : fichier YAML multi-documents (format `items:`)

---

### 6. Import/Sync YAML (admin)

```
POST /api/v1/admin/output-schemas/sync/?mode=additive|full
```

**Permission :** `IsAdminUser`

**Paramètre query :**

| Paramètre | Valeurs | Défaut | Description |
|-----------|---------|--------|-------------|
| `mode` | `additive`, `full` | `additive` | `additive` : ne supprime pas ; `full` : supprime les absents |

**Corps de la requête :**
- `Content-Type: application/x-yaml` avec le YAML en body, **ou**
- `multipart/form-data` avec le fichier dans le champ `file`

**Réponse 200 :**

```json
{
  "data": {
    "created": 2,
    "updated": 1,
    "unchanged": 5,
    "deleted": 0
  }
}
```

**Codes d'erreur :**
- `400` : YAML invalide, `mode` invalide, ou aucun contenu fourni.
- `500` : erreur interne à l'import.

---

## Templates Jinja2

Les templates de notification utilisent des variables issues des schémas d'output pour référencer les résultats des steps du workflow.

### Syntaxe

```
{{ steps.<step_id>.<field_name> }}
```

### Variables disponibles

| Variable | Description |
|----------|-------------|
| `steps.<step_id>.<field_name>` | Valeur du champ `field_name` retournée par le step `step_id` |
| `execution.id` | ID de l'exécution |
| `execution.status` | Statut final de l'exécution |
| `execution.started_at` | Timestamp de démarrage |
| `execution.finished_at` | Timestamp de fin |
| `action.name` | Nom de l'action exécutée |
| `user.username` | Nom d'utilisateur ayant déclenché l'exécution |

### Exemples concrets

**Template de notification de déploiement :**

```jinja2
Déploiement terminé avec succès.

Changement ServiceNow : {{ steps.create_change.change_number }}
Job AAP : #{{ steps.aap_deploy.job_id }} ({{ steps.aap_deploy.job_status }})
Migrations appliquées : {{ steps.flyway_migrate.migrations_applied }}

Exécution #{{ execution.id }} lancée par {{ user.username }}.
```

**Filtre `truncate` :**

```jinja2
Description : {{ steps.create_change.description | truncate(100) }}
```

### Comment les variables sont-elles résolues ?

Au moment du rendu, le moteur de template :

1. Charge l'`execution_context` de l'exécution (résultat JSON de chaque step).
2. Pour chaque `step_id` référencé, applique le JSONPath défini dans le schéma d'output.
3. Expose le résultat sous `steps.<step_id>.<field_name>`.

Si un step n'a pas de schéma, ses champs ne sont pas accessibles dans le template.

### Accéder aux variables disponibles

Via l'API :

```bash
GET /api/v1/output-schemas/workflows/{workflow_id}/available-variables/
```

Via l'interface admin, le **VariablePicker** liste automatiquement les variables disponibles lors de la configuration d'un step.

---

## Architecture

```
Requête API / Template
        │
        ▼
┌───────────────────┐
│  OutputSchemaRegistry (singleton global)  │
│  Cache thread-safe en mémoire             │
│  Résolution d'héritage (1 niveau)         │
└───────────────────┘
        │  cache miss → SELECT DB
        ▼
┌───────────────────┐
│  Base de données Oracle                   │
│  Table OUTPUT_SCHEMAS                     │
│  FK : inherits_from → OUTPUT_SCHEMAS(id)  │
└───────────────────┘
        ▲
        │  import / seed
┌───────────────────┐
│  YAML (fichiers seed ou API sync)         │
│  output_schemas/fixtures/seed_schemas/    │
│  management/commands/seed_output_schemas  │
└───────────────────┘
```

### Composants clés

| Composant | Fichier | Rôle |
|-----------|---------|------|
| `OutputSchema` | `output_schemas/models.py` | Modèle Django, table `OUTPUT_SCHEMAS` |
| `OutputSchemaRegistry` | `output_schemas/registry.py` | Cache + résolution héritage |
| `schema_registry` | `output_schemas/registry.py` | Instance globale du registre |
| `export_output_schemas_yaml()` | `output_schemas/services_export_import.py` | Sérialisation YAML |
| `import_output_schemas_yaml()` | `output_schemas/services_export_import.py` | Import/sync YAML |
| `OutputSchemaViewSet` | `output_schemas/views.py` | Endpoints CRUD publics |
| `seed_output_schemas` | `output_schemas/management/commands/` | Chargement des données seed |

### Flux d'invalidation du cache

Le cache du registre est invalidé automatiquement après chaque import :

```python
from output_schemas.registry import schema_registry
from output_schemas.services_export_import import import_output_schemas_yaml

stats = import_output_schemas_yaml(yaml_content, mode='additive')
# schema_registry._cache est vidé automatiquement après l'import
```

### Données seed incluses

8 schémas seed sont fournis dans `output_schemas/fixtures/seed_schemas/` :

| Schéma | Type | Description |
|--------|------|-------------|
| `aap-standard` | `platform_convention` | Convention commune AAP (job_id, job_status, etc.) |
| `servicenow-create-change` | `integration` | Création de changement ServiceNow |
| `servicenow-close-change` | `integration` | Clôture de changement ServiceNow |
| `servicenow-create-incident` | `integration` | Création d'incident ServiceNow |
| `servicenow-close-incident` | `integration` | Clôture d'incident ServiceNow |
| `vault-read-secret` | `integration` | Lecture de secret Vault |
| `notification-standard` | `platform_convention` | Convention notification standard |
| `notification-with-details` | `platform_convention` | Convention notification avec détails |
