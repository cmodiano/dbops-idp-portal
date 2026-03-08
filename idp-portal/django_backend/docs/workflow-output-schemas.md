# Workflow Output Schemas — Guide Développeur

Documentation du système de schémas d'output pour les workflows IDP.
Stories 63.1–63.11.

---

## Table des matières

1. [Créer un schéma d'output](#créer-un-schéma-doutput)
2. [API Reference](#api-reference)
3. [Structure `execution_steps`](#structure-execution_steps)
4. [`output_mapping` : extraction des données d'un step](#output_mapping--extraction-des-données-dun-step)
5. [Templates Jinja2 / `input_mapping`](#templates-jinja2--input_mapping)
6. [Flux complet `output_mapping` → `input_mapping`](#flux-complet-output_mapping--input_mapping)
7. [Relation `output_mapping` vs `OutputSchema`](#relation-output_mapping-vs-outputschema)
8. [Cas limites et comportements](#cas-limites-et-comportements)
9. [Architecture](#architecture)

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

## Structure `execution_steps`

Le champ `execution_steps` est un tableau JSON stocké sur le modèle `Action` (`catalog/models.py`). Il décrit la séquence des steps à exécuter dans un workflow.

### Tableau des champs

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `order` | integer | Oui | Ordre d'exécution (1 = premier). Les steps sont exécutés par ordre croissant. |
| `step_id` | string | Non* | Identifiant unique du step dans le workflow. Requis pour le chaînage (`{{ steps.<step_id>. }}`). |
| `name` | string | Non | Libellé affiché dans l'interface et les logs. |
| `step_type` | string | Oui | Type d'exécution : `platform` (action catalogue), `service_call` (intégration tierce), `http_request` (requête HTTP), `evaluation` (évaluation de condition), `gate` (validation manuelle/gate d'approbation). |
| `integration_type` | string | Conditionnel | Requis si `step_type=service_call`. Ex : `servicenow`, `vault`, `github`. |
| `operation` | string | Conditionnel | Requis si `step_type=service_call`. Nom de l'opération à exécuter. |
| `referenced_action_id` | integer | Conditionnel | Requis si `step_type=platform`. ID de l'action catalogue enfant à exécuter. |
| `input_mapping` | object | Non | Paramètres d'entrée du step, avec templates Jinja2. Défaut : `{}`. |
| `output_mapping` | object | Non | Extraction des données de sortie du step via JSONPath. Défaut : `{}`. |
| `condition` | string \| object | Non | Condition d'exécution. Deux formats supportés : expression Jinja2 string (`"{{ steps.X.field != '' }}"`) ou objet de condition (`{"environment_in": ["production", "pre-production"]}`). Si évaluée à `false`, le step est SKIPPED. |

> **\*** `step_id` doit être **unique dans un workflow**. Un step sans `step_id` n'est pas chaînable (ses sorties ne sont pas accessibles aux steps suivants).

### Exemple complet

```json
[
  {
    "order": 1,
    "step_id": "create_change",
    "name": "Créer un changement ServiceNow",
    "step_type": "service_call",
    "integration_type": "servicenow",
    "operation": "create_change",
    "input_mapping": {
      "short_description": "Déploiement {{ action_name }}",
      "environment": "{{ environment }}"
    },
    "output_mapping": {
      "change_number": "$.number",
      "sys_id": "$.sys_id"
    }
  },
  {
    "order": 2,
    "step_id": "aap_deploy",
    "name": "Déploiement via AAP",
    "step_type": "platform",
    "referenced_action_id": 42,
    "input_mapping": {
      "change": "{{ steps.create_change.change_number }}",
      "target_env": "{{ environment }}"
    },
    "output_mapping": {
      "job_id": "$.platform_job_id",
      "job_status": "$.job_status"
    },
    "condition": "{{ steps.create_change.change_number != '' }}"
  }
]
```

---

## `output_mapping` : extraction des données d'un step

Le champ `output_mapping` définit comment extraire des données de la réponse brute d'un step (`raw_output`) pour les rendre disponibles aux steps suivants.

### Définition

```json
"output_mapping": {
  "<alias>": "<expression_jsonpath>"
}
```

- **`<alias>`** : nom de la variable accessible via `{{ steps.<step_id>.<alias> }}`.
- **`<expression_jsonpath>`** : chemin JSONPath simple pointant vers le champ dans `raw_output`.

### Syntaxe JSONPath supportée

Seule la **notation point simple** est supportée (`output_extractor.py`) :

| Expression | Accès dans `raw_output` |
|------------|------------------------|
| `$.key` | `raw_output["key"]` |
| `$.key.subkey` | `raw_output["key"]["subkey"]` |
| `$.key.subkey.deep` | `raw_output["key"]["subkey"]["deep"]` |

> **⚠️ Non supporté :** `$[0]`, `$.key[*]`, filtres JSONPath complexes, accès par index.
> Pour accéder à un élément de liste, utiliser les filtres Jinja2 dans `input_mapping` (voir section suivante).

### Exemples concrets

**Réponse brute d'un step ServiceNow (`raw_output`) :**
```json
{"number": "CHG0012345", "sys_id": "abc123def456", "state": "new"}
```

**`output_mapping` configuré :**
```json
{"change_number": "$.number", "sys_id": "$.sys_id"}
```

**Résultat stocké dans `_step_outputs["create_change"]` :**
```json
{"change_number": "CHG0012345", "sys_id": "abc123def456"}
```

**Réponse brute d'un step avec structure imbriquée :**
```json
{"result": {"job": {"id": 1234, "status": "successful"}}}
```

**`output_mapping` pour accéder aux données imbriquées :**
```json
{"job_id": "$.result.job.id", "job_status": "$.result.job.status"}
```

### Comportement si `output_mapping` est absent

Si un step ne définit pas `output_mapping` (ou si la valeur est `{}`), ses données de sortie ne sont pas extraites. Le step n'est **pas chaînable** : `_step_outputs[step_id]` vaudra `{}` et toute référence `{{ steps.<step_id>.<field> }}` retournera `''`.

---

## Templates Jinja2 / `input_mapping`

Le champ `input_mapping` définit les paramètres d'entrée d'un step. Les valeurs peuvent contenir des templates **Jinja2** pour référencer les sorties des steps précédents ou des variables d'exécution.

### Syntaxe

```
{{ steps.<step_id>.<field_name> }}
```

Où `<step_id>` est le `step_id` d'un step **précédent** dans le workflow (ordre inférieur) et `<field_name>` est un alias défini dans son `output_mapping`.

### Variables d'exécution disponibles

| Variable | Description |
|----------|-------------|
| `{{ execution_id }}` | ID de l'exécution IDP |
| `{{ environment }}` | Environnement cible de l'exécution |
| `{{ action_name }}` | Nom de l'action exécutée |
| `{{ steps.<step_id>.<field> }}` | Output extrait du step `step_id`, champ `field` |

> **Note :** ces variables sont des clés plates dans le contexte Jinja2 (pas d'objet `execution` imbriqué). Utiliser `{{ environment }}` et non `{{ execution.environment }}`.

### Exemples concrets

**Référence à un step précédent :**

```json
"input_mapping": {
  "change": "{{ steps.create_change.change_number }}",
  "target_env": "{{ environment }}"
}
```

**Composition de chaînes :**

```json
"input_mapping": {
  "description": "Déploiement {{ action_name }} sur {{ environment }}",
  "ref_change": "CHG: {{ steps.create_change.change_number }}"
}
```

### Filtres Jinja2 autorisés

Le moteur Jinja2 utilise un `SandboxedEnvironment` (`template_resolver.py`). Seuls les filtres suivants sont autorisés :

| Filtre | Exemple | Résultat |
|--------|---------|---------|
| `join` | `{{ steps.step1.dbs \| join(',') }}` | `"DB1,DB2,DB3"` |
| `length` | `{{ steps.step1.dbs \| length }}` | `3` |
| `first` | `{{ steps.step1.dbs \| first }}` | `"DB1"` |
| `default` | `{{ steps.step1.val \| default('N/A') }}` | `"N/A"` si absent |
| `truncate` | `{{ steps.step1.msg \| truncate(100) }}` | 100 premiers caractères |

> **Filtres bloqués :** tous les autres filtres Jinja2 standard (`upper`, `lower`, `replace`, `tojson`, etc.) sont bloqués pour des raisons de sécurité. Une erreur de filtre non autorisé retourne la valeur brute (mode failsafe).

**Exemple avec filtre `first` (accès à un élément de liste) :**

```json
// raw_output du step "discovery"
{ "databases": ["DB_PROD", "DB_STAGING", "DB_DEV"] }

// output_mapping du step "discovery"
"output_mapping": { "databases": "$.databases" }

// input_mapping du step suivant
"input_mapping": {
  "primary_db": "{{ steps.discovery.databases | first }}"
}
// Résultat : "DB_PROD"
```

**Exemple avec filtre `join` :**

```json
"input_mapping": {
  "db_list": "{{ steps.discovery.databases | join(', ') }}"
}
// Résultat : "DB_PROD, DB_STAGING, DB_DEV"
```

### Accéder aux variables disponibles

Via l'API :

```bash
GET /api/v1/output-schemas/workflows/{workflow_id}/available-variables/
```

Via l'interface admin, le **VariablePicker** liste automatiquement les variables disponibles lors de la configuration d'un step.

---

## Flux complet `output_mapping` → `input_mapping`

### Diagramme

```
Définition workflow (execution_steps JSON)
              │
              ▼
┌─────────────────────────────────────┐
│  Step N exécuté                     │
│  1. Résolution input_mapping        │
│     StepTemplateResolver.resolve()  │
│     → templates Jinja2 remplacés   │
│     → paramètres finaux du step     │
└─────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  Exécution du step                  │
│  (appel intégration / child exec)   │
│  → raw_output (dict JSON)           │
└─────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  Extraction output_mapping          │
│  OutputExtractor.extract()          │
│  $.key → raw_output["key"]          │
│  → extracted = {alias: valeur}      │
└─────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  Stockage dans _step_outputs        │
│  _step_outputs[step_id] = extracted │
│  (disponible pour les steps suivants)│
└─────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  Step N+1 : résolution input_mapping│
│  {{ steps.step_id.alias }}          │
│  → remplacé par valeur extraite     │
└─────────────────────────────────────┘
```

### Exemple bout-en-bout : ServiceNow → AAP

**Configuration des deux steps :**

```json
[
  {
    "order": 1,
    "step_id": "create_change",
    "name": "Créer un changement ServiceNow",
    "step_type": "service_call",
    "integration_type": "servicenow",
    "operation": "create_change",
    "input_mapping": {
      "short_description": "Déploiement {{ action_name }} — {{ environment }}"
    },
    "output_mapping": {
      "change_number": "$.number",
      "sys_id": "$.sys_id"
    }
  },
  {
    "order": 2,
    "step_id": "aap_deploy",
    "name": "Déploiement via AAP",
    "step_type": "platform",
    "referenced_action_id": 42,
    "input_mapping": {
      "change_request": "{{ steps.create_change.change_number }}",
      "target_env": "{{ environment }}"
    },
    "output_mapping": {
      "job_id": "$.platform_job_id",
      "job_status": "$.job_status"
    }
  }
]
```

**Déroulement runtime :**

| Phase | Valeur |
|-------|--------|
| Contexte d'exécution | `action_name = "deploy-app"`, `environment = "production"` |
| Step 1 — `input_mapping` résolu | `short_description = "Déploiement deploy-app — production"` |
| Step 1 — `raw_output` ServiceNow | `{"number": "CHG0012345", "sys_id": "abc123", "state": "new"}` |
| Step 1 — `output_mapping` extrait | `{"change_number": "CHG0012345", "sys_id": "abc123"}` |
| `_step_outputs["create_change"]` | `{"change_number": "CHG0012345", "sys_id": "abc123"}` |
| Step 2 — `input_mapping` résolu | `change_request = "CHG0012345"`, `target_env = "production"` |
| Step 2 — exécution AAP | Job lancé avec les paramètres résolus |
| Step 2 — `raw_output` AAP | `{"platform_job_id": 9876, "job_status": "successful"}` |
| `_step_outputs["aap_deploy"]` | `{"job_id": 9876, "job_status": "successful"}` |

---

## Relation `output_mapping` vs `OutputSchema`

Ces deux mécanismes sont **orthogonaux** : ils servent des objectifs différents et peuvent être utilisés indépendamment.

### Comparaison

| Aspect | `output_mapping` | `OutputSchema` |
|--------|-----------------|----------------|
| **Rôle** | Extraction runtime des données d'un step | Déclaration des variables disponibles dans l'UI |
| **Où défini** | Dans `execution_steps` de l'action workflow | Dans les schémas YAML (`seed_schemas/`) ou via l'API admin |
| **Quand utilisé** | Pendant l'exécution du workflow | Dans le VariablePicker (configuration de l'UI) |
| **Stockage** | CLOB JSON dans la table `CATALOG_ACTIONS` | Table `OUTPUT_SCHEMAS` |
| **Consommé par** | `OutputExtractor`, `StepTemplateResolver` | `OutputSchemaRegistry`, API `/available-variables/` |
| **Résultat** | `_step_outputs[step_id]` rempli | VariablePicker liste les variables disponibles |

### Relation entre les deux systèmes

```
output_mapping (runtime)              OutputSchema (déclaratif)
─────────────────────────             ────────────────────────────
execution_steps[i].output_mapping     output_schemas/models.py → OutputSchema
│ $.key → alias                      │ schémas YAML (seed_schemas/)
▼                                     ▼
OutputExtractor.extract()             OutputSchemaRegistry (cache)
→ _step_outputs[step_id]             → VariablePicker API
▼                                     ▼
StepTemplateResolver.resolve()        GET /api/v1/output-schemas/workflows/
→ input_mapping résolu                    {id}/available-variables/
```

### Cas d'utilisation

**Cas 1 — `output_mapping` sans `OutputSchema` :**
Le chaînage fonctionne à l'exécution, mais le VariablePicker ne liste pas les variables. L'utilisateur doit saisir `{{ steps.<step_id>.<field> }}` manuellement dans l'interface.

```json
// Step avec output_mapping mais sans OutputSchema
{
  "step_id": "my_step",
  "output_mapping": { "result": "$.data.value" }
  // → runtime OK, VariablePicker vide pour ce step
}
```

**Cas 2 — `OutputSchema` sans `output_mapping` (ou `output_mapping: {}`) :**
Le VariablePicker liste les variables disponibles (aide l'utilisateur à configurer les steps suivants), mais aucune donnée n'est transmise à l'exécution. Les références `{{ steps.<step_id>.<field> }}` retourneront `''`.

```yaml
# OutputSchema déclaré mais output_mapping absent dans le step
spec:
  output_fields:
    - name: change_number
      path: "$.number"
# → VariablePicker affiche "change_number", mais si output_mapping={}, la valeur sera ''
```

**Cas 3 — Les deux définis (configuration recommandée) :**
Cohérence complète : le VariablePicker liste les variables ET le chaînage transmet les valeurs correctement.

> **Bonne pratique :** les alias définis dans `output_mapping` doivent correspondre aux `name` des `output_fields` de l'`OutputSchema` associé pour une cohérence entre UI et runtime.

---

## Cas limites et comportements

### Tableau de référence

| Situation | Comportement |
|-----------|-------------|
| `step_id` absent sur un step | Le step s'exécute, mais ses sorties ne sont pas stockées dans `_step_outputs`. Toute référence `{{ steps.<step_id>. }}` retourne `''`. |
| Step SKIPPED (condition évaluée à `false`) | `_step_outputs[step_id] = {}` — le step est enregistré comme skippé, mais sans données. Références à ses champs retournent `''`. |
| Référence à un step futur ou inexistant | `StepTemplateResolver` retourne `''` sans lever d'exception. |
| Référence à un step existant mais champ absent | `_step_outputs[step_id]` existe mais ne contient pas le champ → retourne `''`. |
| `output_mapping` absent ou `{}` | `_step_outputs[step_id] = {}` si `step_id` défini. Chaînage non alimenté. |
| JSONPath introuvable dans `raw_output` | La clé est **présente** dans `_step_outputs[step_id]` avec la valeur `None`, finalisée en `''` lors de la résolution Jinja2. |
| Valeur `None` dans `_step_outputs[step_id][field]` | Finalisée en `''` lors de la résolution Jinja2. |
| Filtre Jinja2 non autorisé | Retourne la chaîne template non rendue (failsafe — ex: `"{{ steps.X.val \| upper }}"`) — pas d'exception levée. |

### Détails par cas

**Step sans `step_id` :**
```json
// Step sans step_id — exécuté mais non chaînable
{
  "order": 1,
  "name": "Step anonyme",
  "step_type": "service_call",
  "integration_type": "servicenow",
  "operation": "create_change",
  "output_mapping": { "change_number": "$.number" }
  // Pas de step_id → _step_outputs non mis à jour
}
```

**Step SKIPPED :**
```json
{
  "order": 2,
  "step_id": "optional_step",
  "condition": "{{ steps.create_change.change_number != '' }}",
  // Si condition = false :
  // → step SKIPPED
  // → _step_outputs["optional_step"] = {}
  // → {{ steps.optional_step.some_field }} retourne ''
}
```

**JSONPath inexistant :**
```json
// raw_output = {"data": {"value": 42}}
// output_mapping = {"result": "$.missing_key"}
// → "missing_key" absent dans raw_output
// → "result" absent de _step_outputs["my_step"]
// → {{ steps.my_step.result }} retourne ''
```

**Référence à un step futur :**
```json
// Step 1 tente de référencer Step 2 (non encore exécuté)
{
  "order": 1,
  "input_mapping": {
    "param": "{{ steps.step_2.some_field }}"
    // → steps.step_2 n'est pas dans _step_outputs (pas encore exécuté)
    // → retourne '' sans erreur
  }
}
```

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
