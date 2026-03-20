# Guide JSON Schemas — Paramètres dynamiques et règles d'impact

Ce guide documente le flux complet `parameters_schema` → formulaire d'exécution dynamique, les fonctions de conversion, les champs d'inventaire et la validation backend.

---

## Table des matières

1. [Vue d'ensemble du flux](#vue-densemble-du-flux)
2. [Format `parameters_schema`](#format-parameters_schema)
3. [Interface `ParametersJsonSchema` et `ParameterDefinition`](#interfaces-typescript)
4. [`schemaToParameterList()` — Schéma → éditeur visuel](#schematoparameterlist)
5. [`parameterListToSchema()` — Éditeur visuel → schéma](#parameterlisttoschema)
6. [`useDynamicForm` et `extractParameterFields()` — Formulaire d'exécution](#usedynamicform)
7. [Rendu des champs (`renderFieldInput`)](#rendu-des-champs)
8. [Champs d'inventaire](#champs-dinventaire)
9. [`impactRulesSchema.ts` — Règles d'impact](#impactrulesschema)
10. [Validation backend via `jsonschema`](#validation-backend)

---

## Vue d'ensemble du flux

```
┌─────────────────────────────────────────────────────────────────┐
│  BACKEND — Table ACTIONS_CATALOG                                │
│  Colonne PARAMETERS_SCHEMA (CLOB/JSON)                          │
│  Stocke un JSON Schema draft-07                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ GET /api/v1/catalog/actions/{id}
                           ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│  ADMIN — Éditeur visuel de paramètres                                          │
│  src/utils/parametersSchema.ts                                                 │
│                                                                                │
│  schemaToParameterList(schema)  ◄── lecture depuis BD → affichage éditeur     │
│  parameterListToSchema(list)    ──► sauvegarde éditeur → PATCH /admin/actions  │
└──────────────────────────┬─────────────────────────────────────────────────────┘
                           │ action.parameters_schema (JSON Schema)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  WIZARD D'EXÉCUTION — Formulaire dynamique                       │
│  src/hooks/useDynamicForm.ts                                     │
│                                                                  │
│  extractParameterFields(schema) → ParameterField[]              │
│  useDynamicForm({ schema })     → { parameterFields }           │
└──────────────────────────┬───────────────────────────────────────┘
                           │ parameterFields: ParameterField[]
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  RENDU DES CHAMPS                                                │
│  src/components/catalog/renderFieldInput.tsx                    │
│                                                                  │
│  Compose les composants Ant Design selon ParameterField.type    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Format `parameters_schema`

Le schéma est un JSON Schema draft-07 stocké dans la colonne `PARAMETERS_SCHEMA` de la table `ACTIONS_CATALOG`.

**Format attendu :**

```json
{
  "type": "object",
  "properties": {
    "<nom_paramètre>": {
      "type": "string|number|integer|boolean",
      "description": "Description affichée à l'utilisateur",
      "default": "<valeur_défaut>",
      ...extensions IDP...
    }
  },
  "required": ["<nom_paramètre_obligatoire>"]
}
```

**Exemple complet :**

```json
{
  "type": "object",
  "properties": {
    "environment": {
      "type": "string",
      "enum": ["DEV", "QA", "PROD"],
      "description": "Environnement cible d'exécution"
    },
    "target_db": {
      "type": "string",
      "source": "inventory",
      "inventory_type": "databases",
      "inventory_value_column": "db_name",
      "description": "Base de données cible"
    },
    "maintenance_date": {
      "type": "string",
      "format": "date",
      "description": "Date de maintenance planifiée"
    },
    "max_connections": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000,
      "default": 100
    },
    "confirm": {
      "type": "boolean",
      "default": false,
      "description": "Confirmer l'exécution en production"
    }
  },
  "required": ["environment", "target_db"]
}
```

---

## Interfaces TypeScript

**Fichier :** `src/utils/parametersSchema.ts` et `src/types/api.ts`

### `ParametersJsonSchema`

Représentation minimale du JSON Schema côté frontend.

```typescript
interface ParametersJsonSchema {
  type?: string;                                        // "object"
  properties?: Record<string, Record<string, unknown>>; // propriétés du schéma
  required?: string[];                                  // noms des champs obligatoires
  [key: string]: unknown;                               // compatibilité Record<string, unknown>
}
```

### `ParameterDefinition`

Représentation d'un paramètre dans **l'éditeur visuel admin** (différent de `ParameterField` utilisé dans le wizard).

```typescript
interface ParameterDefinition {
  name: string;
  type: 'string' | 'number' | 'integer' | 'boolean' | 'date' | 'date-time' | 'select';
  required: boolean;
  default?: string;              // Valeur par défaut (toujours string dans l'éditeur)
  description?: string;
  enum?: string[];               // Options pour type 'select'
  source?: 'inventory' | 'manual';
  inventory_type?: 'databases' | 'servers' | 'instances';
  inventory_value_column?: string;
}
```

### `ParameterField`

Représentation d'un champ dans le **formulaire d'exécution** (généré par `useDynamicForm`).

```typescript
interface ParameterField {
  name: string;
  type: 'string' | 'number' | 'integer' | 'boolean' | 'date' | 'date-time' | 'select' | 'array';
  label: string;                 // Utilise prop.title ou name si absent
  description?: string;
  required: boolean;
  enum?: string[];
  pattern?: string;
  minimum?: number;
  maximum?: number;
  default?: unknown;             // Valeur typée (pas string)
  inventorySource?: 'databases' | 'servers' | 'instances';
  inventoryValueColumn?: string;
}
```

**Différences clés :**
- `ParameterDefinition` est utilisé dans l'**éditeur admin** (sauvegarde vers BD)
- `ParameterField` est utilisé dans le **wizard d'exécution** (rendu formulaire)
- `ParameterField` supporte le type `'array'` que `ParameterDefinition` ne supporte pas
- `ParameterField.default` est typé `unknown` (valeur réelle), `ParameterDefinition.default` est `string`

---

## `schemaToParameterList()`

**Fichier :** `src/utils/parametersSchema.ts`

Convertit un JSON Schema stocké en base de données en une liste `ParameterDefinition[]` pour l'éditeur visuel admin.

```typescript
function schemaToParameterList(
  schema: ParametersJsonSchema | null | undefined
): ParameterDefinition[]
```

### Logique de conversion

1. Si `schema` est `null`, `undefined` ou non-objet → retourne `[]`
2. Itère sur `Object.keys(schema.properties)` (préserve l'ordre de déclaration)
3. Pour chaque propriété, déduit le type avec `schemaPropToParamType()` :

**Table de mapping type schéma → `ParameterDefinition.type` :**

| Condition dans le schéma | `ParameterDefinition.type` |
|--------------------------|---------------------------|
| `prop.enum` est un tableau | `'select'` |
| `type: "string"` + `format: "date"` | `'date'` |
| `type: "string"` + `format: "date-time"` | `'date-time'` |
| `type: "number"` | `'number'` |
| `type: "integer"` | `'integer'` |
| `type: "boolean"` | `'boolean'` |
| Tout autre cas (dont `type: "string"`) | `'string'` |

4. Extrait `source`, `inventory_type`, `inventory_value_column` si présents
5. Marque `required: true` si le nom apparaît dans `schema.required[]`

### Exemple

```typescript
import { schemaToParameterList } from '@/utils/parametersSchema';

const schema = {
  type: "object",
  properties: {
    env: { type: "string", enum: ["DEV", "PROD"], description: "Environnement" },
    db_name: { type: "string", source: "inventory", inventory_type: "databases", inventory_value_column: "db_name" },
    count: { type: "integer", default: 10 }
  },
  required: ["env", "db_name"]
};

const list = schemaToParameterList(schema);
// Résultat :
// [
//   { name: "env",     type: "select",  required: true,  enum: ["DEV", "PROD"], description: "Environnement" },
//   { name: "db_name", type: "string",  required: true,  source: "inventory", inventory_type: "databases", inventory_value_column: "db_name" },
//   { name: "count",   type: "integer", required: false, default: "10" }
// ]
```

---

## `parameterListToSchema()`

**Fichier :** `src/utils/parametersSchema.ts`

Convertit une liste `ParameterDefinition[]` (sortie de l'éditeur visuel admin) en JSON Schema pour l'API backend.

```typescript
function parameterListToSchema(
  list: ParameterDefinition[]
): ParametersJsonSchema | null
```

Retourne `null` si la liste est vide ou ne contient que des entrées avec des noms vides.

### Logique de conversion

**Table de mapping `ParameterDefinition.type` → propriété JSON Schema :**

| `ParameterDefinition.type` | JSON Schema property |
|---------------------------|---------------------|
| `'select'` + enum non vide | `{ type: "string", enum: [...] }` |
| `'date'` | `{ type: "string", format: "date" }` |
| `'date-time'` | `{ type: "string", format: "date-time" }` |
| `'integer'` | `{ type: "integer" }` |
| `'number'` | `{ type: "number" }` |
| `'boolean'` | `{ type: "boolean" }` |
| `'string'` (défaut) | `{ type: "string" }` |

**Règles sur `source` :**
- `source: "inventory"` → écrit `source`, `inventory_type`, `inventory_value_column` dans le schéma
- `source: "manual"` → **non écrit** dans le schéma (compatibilité backward — champ texte libre par défaut)

**Conversion des valeurs par défaut :**
- `type: 'number'` / `'integer'` → parse en nombre (`Math.floor` pour integer)
- `type: 'boolean'` → `"true"` → `true`, `"false"` → `false`
- Autres → valeur string telle quelle

### Exemple

```typescript
import { parameterListToSchema } from '@/utils/parametersSchema';

const list = [
  { name: "env",     type: "select",  required: true,  enum: ["DEV", "PROD"] },
  { name: "db_name", type: "string",  required: true,  source: "inventory", inventory_type: "databases", inventory_value_column: "db_name" },
  { name: "count",   type: "integer", required: false, default: "10" }
];

const schema = parameterListToSchema(list);
// Résultat :
// {
//   type: "object",
//   properties: {
//     env:     { type: "string", enum: ["DEV", "PROD"] },
//     db_name: { type: "string", source: "inventory", inventory_type: "databases", inventory_value_column: "db_name" },
//     count:   { type: "integer", default: 10 }
//   },
//   required: ["env", "db_name"]
// }
```

---

## `useDynamicForm`

**Fichier :** `src/hooks/useDynamicForm.ts`

Hook React qui génère la liste des champs de formulaire à partir d'un `parameters_schema` JSON Schema.

```typescript
const { parameterFields } = useDynamicForm({ schema: action.parameters_schema });
```

Utilise `useMemo` pour ne recalculer que si `schema` change.

### `extractParameterFields(schema)`

Fonction pure interne (aussi exportée pour tests) qui fait la conversion réelle.

```typescript
function extractParameterFields(
  schema: Record<string, unknown> | null
): ParameterField[]
```

**Algorithme :**

1. Si `schema` est `null` → retourne `[]`
2. Extrait `schema.properties` et `schema.required`
3. Pour chaque entrée dans `Object.entries(properties)` :
   - Déduit le type : `enum` → `'select'`, `type: "array"` → `'array'`, `format: "date"` → `'date'`, etc.
   - Extrait `label` depuis `prop.title` ou utilise `name` si absent
   - Extrait `inventorySource` : vérifie `source === "inventory"` et que `inventory_type` est dans `['databases', 'servers', 'instances']`
   - Extrait `inventoryValueColumn` si `source === "inventory"`
   - Log un warning si `inventory_type` est absent ou inconnu

### Exemple d'utilisation dans un composant

```typescript
import { useDynamicForm } from '@/hooks/useDynamicForm';
import { renderFieldInput } from '@/components/catalog/renderFieldInput';

function ExecutionParametersStep({ action, form }) {
  const { parameterFields } = useDynamicForm({
    schema: action.parameters_schema
  });

  return (
    <Form form={form}>
      {parameterFields.map(field => (
        <Form.Item
          key={field.name}
          name={field.name}
          label={field.label}
          rules={[{ required: field.required }]}
        >
          {renderFieldInput(field)}
        </Form.Item>
      ))}
    </Form>
  );
}
```

---

## Rendu des champs

**Fichier :** `src/components/catalog/renderFieldInput.tsx`

Sélectionne le composant Ant Design approprié selon `ParameterField.type`.

| `ParameterField.type` | `inventorySource` défini | Composant Ant Design rendu |
|----------------------|--------------------------|---------------------------|
| `'string'` | Non | `<Input>` |
| `'number'` | Non | `<InputNumber>` |
| `'integer'` | Non | `<InputNumber step={1}>` |
| `'boolean'` | Non | `<Switch>` |
| `'date'` | Non | `<DatePicker>` (format `YYYY-MM-DD`) |
| `'date-time'` | Non | `<DatePicker showTime>` (format ISO) |
| `'select'` | Non | `<Select>` avec options depuis `field.enum` |
| `'array'` | Non | `<Select mode="tags">` |
| Tout type | Oui | `<Select>` peuplé par `useInventorySchema` via `GET /api/v1/inventory/{type}` |

**Champ d'inventaire :** Si `inventorySource` est défini (`'databases'`, `'servers'` ou `'instances'`), `renderFieldInput` rend un `<Select>` dont les options sont chargées dynamiquement depuis l'API d'inventaire, filtré par `inventoryValueColumn`.

---

## Champs d'inventaire

Les champs d'inventaire permettent de peupler un dropdown de formulaire depuis des données réelles de l'inventaire (bases de données, serveurs, instances).

### Structure dans le JSON Schema

```json
{
  "target_db": {
    "type": "string",
    "source": "inventory",
    "inventory_type": "databases",
    "inventory_value_column": "db_name",
    "description": "Base de données cible"
  }
}
```

### Extensions non-standard (hors JSON Schema draft-07)

| Propriété | Valeurs | Description |
|-----------|---------|-------------|
| `source` | `"inventory"` | Marque le champ comme dropdown d'inventaire |
| `source` | `"manual"` | Champ texte libre (non écrit dans le schéma — compat backward) |
| `inventory_type` | `"databases"` \| `"servers"` \| `"instances"` | Type de ressource dans l'inventaire |
| `inventory_value_column` | ex: `"db_name"`, `"server_hostname"` | Colonne utilisée comme valeur dans le dropdown |

### Flux complet d'un champ inventaire

```
1. Admin définit source=inventory dans l'éditeur
   → parameterListToSchema() écrit source, inventory_type, inventory_value_column

2. Stocké en BD : { "type": "string", "source": "inventory", "inventory_type": "databases", ... }

3. Wizard d'exécution : useDynamicForm() → extractParameterFields()
   → détecte source=inventory → set inventorySource="databases"

4. renderFieldInput() détecte inventorySource → rend <Select>
   → useInventorySchema() appelle GET /api/v1/inventory/databases
   → options : liste des bases de données réelles

5. Utilisateur sélectionne une BD → valeur envoyée via POST /executions
```

### Endpoint inventaire

```
GET /api/v1/inventory/{type}?environment={env}

Paramètres :
  type        : databases | servers | instances | environments
  environment : filtre optionnel (ex: "DEV", "PROD")
  server_names: filtre optionnel (liste de serveurs)
  engine_type : filtre optionnel (Oracle, SQL Server, DB2)

Retour : { data: InventoryItem[] }
  InventoryItem : { id: string, name: string, environment: string | null, ...metadata }
```

**Cache :** `execution_inventory.ts` maintient un cache en mémoire (5 min) + sessionStorage comme fallback si erreur 503.

---

## `impactRulesSchema.ts`

**Fichier :** `src/utils/impactRulesSchema.ts`

Gestion des règles d'impact (JSON objet `impact_rules` stocké dans `ACTIONS_CATALOG`).

### Format JSON stocké en BD

```json
{
  "DEV":  { "level": "low",      "criteria": "Aucun critère spécifique" },
  "QA":   { "level": "medium",   "criteria": "Tests de non-régression requis" },
  "PROD": { "level": "critical", "criteria": "Fenêtre de maintenance obligatoire" }
}
```

### `impactRulesToList(rules)`

Convertit le JSON objet en liste `ImpactRuleDefinition[]` pour l'éditeur visuel.

```typescript
function impactRulesToList(
  rules: ImpactRulesJson | null | undefined
): ImpactRuleDefinition[]

// Exemple :
impactRulesToList({
  "DEV":  { level: "low",      criteria: "..." },
  "PROD": { level: "critical" }
})
// → [
//   { id: "rule-DEV",  environment: "DEV",  level: "low",      criteria: "..." },
//   { id: "rule-PROD", environment: "PROD", level: "critical", criteria: null }
// ]
```

- L'`id` est calculé comme `rule-{environment}` (déterministe)
- Les niveaux invalides sont remplacés par `'low'`

### `listToImpactRules(list)`

Convertit la liste de l'éditeur en JSON objet pour le backend.

```typescript
function listToImpactRules(
  list: ImpactRuleDefinition[]
): ImpactRulesJson | null

// Retourne null si la liste est vide
// criteria omis si vide
```

### Type `ImpactLevel`

```typescript
type ImpactLevel = 'low' | 'medium' | 'high' | 'critical';
```

| Niveau | Couleur convention | Usage |
|--------|-------------------|-------|
| `low` | Vert | Opérations sans risque |
| `medium` | Orange | Impact limité, fenêtre recommandée |
| `high` | Rouge | Impact significatif, approbation requise |
| `critical` | Rouge foncé | Impact majeur, fenêtre de maintenance obligatoire |

---

## Validation backend

### Validation de `parameters_schema`

**Fichier :** `idp-portal/django_backend/catalog/validators.py`

Le backend valide le JSON Schema au `PATCH /api/v1/admin/actions/{id}` via la bibliothèque Python `jsonschema` (draft-07).

**Format attendu :**

```json
{
  "type": "object",
  "properties": { ... },
  "required": [...]
}
```

**Cas de rejet (HTTP 400) :**
- La racine n'est pas un objet JSON
- `type !== "object"` au niveau racine
- `properties` n'est pas un objet
- Les valeurs de `properties` ne sont pas des objets JSON Schema valides

**Exemple d'erreur 400 :**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "parameters_schema is not a valid JSON Schema",
    "details": {
      "parameters_schema": "Additional properties are not allowed ('unknownKey' was unexpected)"
    }
  }
}
```

### Validation de `config` pour les intégrations

**Fichier :** `idp-portal/django_backend/integrations/validators.py`

Même mécanisme pour le champ `config` de la table `INTEGRATIONS`. Le schéma de validation est spécifique à chaque `connector_type`.

### Validation en exécution

Lors de la soumission d'une exécution (`POST /api/v1/executions`), le backend valide que les `parameters` fournis sont conformes au `parameters_schema` de l'action. Une erreur de validation retourne HTTP 400 avec les détails du champ invalide.

---

## Voir aussi

- [Architecture Frontend](./architecture-consumption.md) — Structure `src/`, couches, hooks, services
- [Intégration API](./api-integration.md) — `api_client.ts` et services
- [Contrats API Frontend](../api/contracts-frontend.md) — Endpoints consommés
