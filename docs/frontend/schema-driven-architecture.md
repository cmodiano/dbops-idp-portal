# Architecture schema-driven — Le frontend pilote par le backend

**Date :** 2026-03-18

Ce document explique le principe fondamental de l'architecture IDP-Portal : **le frontend ne contient aucune logique metier**. Toute la configuration, la validation et le comportement dynamique sont definis dans le backend via des JSON Schemas et des registries, puis consommes par le frontend via l'API capabilities.

---

## Table des matieres

1. [Principe fondamental](#principe-fondamental)
2. [Ce que le frontend ne fait pas](#ce-que-le-frontend-ne-fait-pas)
3. [Ce que le frontend fait](#ce-que-le-frontend-fait)
4. [Flux complet : du registry au formulaire](#flux-complet--du-registry-au-formulaire)
5. [Les 3 mecanismes schema-driven](#les-3-mecanismes-schema-driven)
6. [Impact sur le developpement](#impact-sur-le-developpement)
7. [Architecture en couches du frontend](#architecture-en-couches-du-frontend)

---

## Principe fondamental

```
┌─────────────────────────────────────────────────────────────────────┐
│                          BACKEND                                     │
│                                                                      │
│   Registries (Python)          API Capabilities         Base de      │
│   ┌──────────────────┐    ┌──────────────────────┐    donnees       │
│   │ PlatformRegistry │───►│ /capabilities/       │    ┌──────────┐  │
│   │ ServiceDefRegistry│──►│   integrations/      │    │PARAMETERS│  │
│   │ GateRegistry     │───►│ /capabilities/       │    │_SCHEMA   │  │
│   │ WorkflowStepReg  │──►│   workflow-steps/    │    │(JSON)    │  │
│   └──────────────────┘    └──────────────────────┘    └──────────┘  │
│                                                                      │
│   SOURCE DE VERITE : schemas, regles, types, contraintes            │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ JSON (HTTP REST)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND                                    │
│                                                                      │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐  │
│   │ capabilities_    │───►│ useDynamicForm   │───►│ renderField  │  │
│   │ service.ts       │    │ (schema → fields)│    │ Input.tsx    │  │
│   └──────────────────┘    └──────────────────┘    └──────────────┘  │
│                                                                      │
│   ROLE : afficher, collecter les saisies, envoyer au backend        │
└─────────────────────────────────────────────────────────────────────┘
```

**Le backend est la source de verite unique.** Il definit :
- Quelles plateformes existent et leurs schemas de configuration
- Quels services sont disponibles et quelles operations ils supportent
- Quels gates peuvent etre utilises dans les workflows
- Quels types de steps existent et leurs contraintes
- Quels parametres chaque action attend (via `PARAMETERS_SCHEMA` en BD)

**Le frontend est un consommateur generique.** Il :
- Interroge l'API capabilities pour decouvrir les elements disponibles
- Transforme les JSON Schemas en formulaires dynamiques
- Affiche les composants UI appropries selon le type de chaque champ
- Envoie les donnees saisies au backend sans les interpreter

---

## Ce que le frontend ne fait pas

| Responsabilite | Pourquoi le frontend n'en a pas la charge |
|---------------|-------------------------------------------|
| Connaitre la liste des plateformes | Decouverte dynamique via `GET /capabilities/integrations/` |
| Connaitre la liste des services et operations | Decouverte dynamique via `GET /capabilities/integrations/` |
| Connaitre les types de gates | Decouverte dynamique via `GET /capabilities/workflow-steps/` (variants du step `gate`) |
| Valider les parametres d'execution | Validation faite par le backend avec `jsonschema` — le frontend applique des regles `required` basiques |
| Definir les champs d'un formulaire | Les champs sont derives du `parameters_schema` JSON Schema |
| Gerer les regles metier (impact, maintenance) | Regles definies et evaluees cote backend |
| Connaitre les workflows d'approbation | Le backend decide si une approbation est necessaire |
| Dispatcher les executions vers les plateformes | Le backend utilise les registries pour router |

**Consequence pratique :** quand un developpeur ajoute une nouvelle plateforme, un nouveau service ou un nouveau gate dans le backend, **aucune modification du code frontend n'est necessaire**. Le frontend decouvre automatiquement les nouveaux elements via l'API capabilities.

---

## Ce que le frontend fait

Le frontend a un role precis et limite :

### 1. Decouverte des capabilities

Le service `capabilities_service.ts` appelle les endpoints capabilities au chargement des pages qui en ont besoin :

```typescript
// src/services/capabilities_service.ts

// Decouvrir les plateformes et services disponibles
const { platforms, services } = await getIntegrationsCapabilities();

// Decouvrir les types de steps et leurs variants (gates)
const { step_types, common_schema } = await getWorkflowStepsCapabilities();
```

### 2. Generation dynamique de formulaires

Le hook `useDynamicForm` convertit un JSON Schema en liste de champs de formulaire :

```typescript
// src/hooks/useDynamicForm.ts
const { parameterFields } = useDynamicForm({ schema: action.parameters_schema });
// parameterFields: ParameterField[] — un element par propriete du schema
```

La conversion est **purement mecanique** — aucune interpretation metier :

| Propriete du schema | Ce que le frontend en fait |
|--------------------|---------------------------|
| `type: "string"` | Rend un `<Input>` |
| `type: "integer"` | Rend un `<InputNumber step={1}>` |
| `type: "boolean"` | Rend un `<Switch>` |
| `enum: [...]` | Rend un `<Select>` avec les options |
| `format: "date"` | Rend un `<DatePicker>` |
| `source: "inventory"` | Rend un `<Select>` alimente par `GET /inventory/{type}` |
| `title` | Utilise comme label du champ |
| `description` | Affiche comme texte d'aide |
| `required` | Ajoute une regle de validation `required` au formulaire |
| `default` | Pre-remplit le champ |

### 3. Rendu des composants UI

Le composant `renderFieldInput.tsx` mappe chaque type de champ vers le composant Ant Design correspondant. C'est un **switch sur le type** — pas de logique metier :

```typescript
// src/components/catalog/renderFieldInput.tsx
function renderFieldInput(field: ParameterField): ReactNode {
    if (field.inventorySource) {
        return <Select /* alimente par l'API inventaire */ />;
    }
    switch (field.type) {
        case 'string':    return <Input />;
        case 'integer':   return <InputNumber step={1} />;
        case 'number':    return <InputNumber />;
        case 'boolean':   return <Switch />;
        case 'date':      return <DatePicker />;
        case 'select':    return <Select options={field.enum} />;
        case 'array':     return <Select mode="tags" />;
        // ...
    }
}
```

### 4. Collecte et envoi des donnees

Le frontend collecte les valeurs saisies par l'utilisateur et les envoie au backend tel quel. Il ne transforme pas, ne valide pas et n'interprete pas les donnees metier.

---

## Flux complet : du registry au formulaire

Voici le parcours complet d'un champ de formulaire, de sa definition dans le backend jusqu'a son affichage dans le frontend.

### Exemple : ajout d'un champ `"threshold"` dans un gate

**1. Backend — Definition dans le registry (`executions/gates/registry.py`)**

```python
gate_registry.register(GateDefinition(
    gate_type="my_gate",
    config_schema={
        "type": "object",
        "properties": {
            "threshold": {
                "type": "integer",
                "title": "Seuil",
                "minimum": 0,
                "maximum": 100,
                "default": 80,
            }
        },
        "required": ["threshold"],
    },
    # ...
))
```

**2. API — Exposition via capabilities (`capabilities/views.py`)**

Le endpoint `GET /api/v1/capabilities/workflow-steps/` itere automatiquement sur `gate_registry` et retourne :

```json
{
  "step_types": [{
    "code": "gate",
    "variants": [{
      "code": "my_gate",
      "label": "Mon gate",
      "config_schema": {
        "type": "object",
        "properties": {
          "threshold": {
            "type": "integer",
            "title": "Seuil",
            "minimum": 0,
            "maximum": 100,
            "default": 80
          }
        },
        "required": ["threshold"]
      }
    }]
  }]
}
```

**3. Frontend — Decouverte et rendu**

```
capabilities_service.ts                     useDynamicForm                    renderFieldInput
┌──────────────────────┐    ┌─────────────────────────────┐    ┌──────────────────────────┐
│ GET /capabilities/   │───►│ extractParameterFields()    │───►│ type="integer"           │
│   workflow-steps/    │    │                             │    │ → <InputNumber           │
│                      │    │ config_schema → [           │    │     step={1}             │
│ Recoit le            │    │   { name: "threshold",     │    │     min={0} max={100}    │
│ config_schema        │    │     type: "integer",       │    │     defaultValue={80} /> │
│ du gate              │    │     label: "Seuil",        │    │                          │
│                      │    │     required: true,        │    │ + label "Seuil"          │
│                      │    │     minimum: 0,            │    │ + regle required         │
│                      │    │     maximum: 100,          │    │                          │
│                      │    │     default: 80 }          │    │                          │
│                      │    │ ]                          │    │                          │
└──────────────────────┘    └─────────────────────────────┘    └──────────────────────────┘
```

**Resultat final :** un champ `InputNumber` avec label "Seuil", bornes 0-100, valeur par defaut 80, marque obligatoire. **Tout cela sans ecrire une seule ligne de code frontend.**

---

## Les 3 mecanismes schema-driven

### 1. Formulaires d'action (parameters_schema)

Les actions du catalogue definissent leurs parametres via un `PARAMETERS_SCHEMA` stocke en base de donnees (table `ACTIONS_CATALOG`). Ce schema pilote le formulaire de saisie dans le wizard d'execution.

```
ACTIONS_CATALOG.PARAMETERS_SCHEMA    →    useDynamicForm()    →    Formulaire execution
       (BD, JSON Schema)                   (hook React)              (Ant Design)
```

Voir [Guide JSON Schemas](json-schemas-guide.md) pour la documentation detaillee.

### 2. Configuration des integrations (runtime_config_schema)

Chaque plateforme definit un `runtime_config_schema` qui pilote le formulaire de configuration dans l'ecran d'administration des integrations.

```
PlatformDefinition.runtime_config_schema    →    Formulaire integration admin
        (registry Python)                          (Ant Design)
```

### 3. Workflow builder (config_schema + variants)

Le workflow builder utilise les schemas des step types et de leurs variants (gates) pour generer les panneaux de configuration de chaque etape.

```
WorkflowStepDefinition.config_schema    →    StepConfigPanel
GateDefinition.config_schema (variant)  →    (workflow builder)
```

---

## Impact sur le developpement

### Pour les developpeurs backend

Quand vous ajoutez ou modifiez un element extensible :

| Action | Consequence frontend |
|--------|---------------------|
| Ajouter une plateforme dans `platform_registry` | Apparait automatiquement dans les dropdowns d'integration |
| Ajouter un service dans `service_definition_registry` | Apparait automatiquement dans le workflow builder |
| Ajouter un gate dans `gate_registry` | Apparait comme variant du step `gate` dans le workflow builder |
| Modifier un `config_schema` | Les formulaires se mettent a jour automatiquement |
| Ajouter une operation a un service | L'operation apparait dans les options du step `service_call` |
| Modifier un `input_schema` d'operation | Le formulaire de l'operation se met a jour |

**Aucune PR frontend necessaire** — sauf si un nouveau type de widget UI est requis (ex: un composant de rendu qui n'existe pas encore dans `renderFieldInput.tsx`).

### Pour les developpeurs frontend

Le code frontend ne doit **jamais** :

- Hardcoder une liste de plateformes, services ou gates
- Implementer une logique de validation metier
- Conditionner l'affichage d'un champ selon une logique metier (sauf via `ui_hints`)
- Interpreter les valeurs saisies par l'utilisateur

Le code frontend **peut** :

- Ajouter un nouveau type de widget dans `renderFieldInput.tsx` si le backend introduit un nouveau `ui_widget`
- Optimiser le rendu ou la mise en cache des donnees capabilities
- Ameliorer l'UX des formulaires generes (animations, validations cote client basiques)

### Exemple de ce qu'il ne faut PAS faire

```typescript
// INTERDIT — logique metier hardcodee dans le frontend
if (platform === 'aap') {
    showField('template_id');
} else if (platform === 'github_actions') {
    showField('workflow_file');
}

// CORRECT — le backend definit les champs via action_config_schema
// Le frontend rend tous les champs declares dans le schema, sans condition
const { parameterFields } = useDynamicForm({ schema: platform.action_config_schema });
```

---

## Architecture en couches du frontend

Le frontend suit une architecture 3 couches stricte :

```
Pages / Components              Hooks                    Services              API Client
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐
│ AdminPage        │───►│ useDynamicForm   │───►│ capabilities_    │───►│ api_client.ts │
│ CatalogPage      │    │ useWebSocket     │    │   service.ts     │    │               │
│ WorkflowBuilder  │    │ useExecution*    │    │ catalog_service  │    │ apiFetch()    │
│ ExecutionDetail  │    │ useInventory*    │    │ execution_core   │    │ apiFetchRaw() │
└──────────────────┘    └──────────────────┘    └──────────────────┘    └───────┬───────┘
                                                                               │
                                                                          fetch() HTTP
                                                                               │
                                                                    Backend Django /api/v1
```

### Regles d'architecture

| Regle | Description |
|-------|-------------|
| **R1** | Les composants n'appellent **jamais** `fetch()` directement |
| **R2** | Les composants utilisent des hooks ou des services |
| **R3** | Les services passent **toujours** par `api_client.ts` |
| **R4** | `api_client.ts` gere l'authentification, le refresh 401, les retries 429/503 |
| **R5** | Les formulaires sont toujours generes a partir de JSON Schemas, jamais hardcodes |

### Fichiers cles

| Fichier | Role |
|---------|------|
| `services/capabilities_service.ts` | Appelle les endpoints capabilities |
| `hooks/useDynamicForm.ts` | Convertit JSON Schema → `ParameterField[]` |
| `components/catalog/renderFieldInput.tsx` | Mappe `ParameterField.type` → composant Ant Design |
| `utils/parametersSchema.ts` | Conversion bidirectionnelle schema ↔ editeur admin |
| `types/api.ts` | Types TypeScript pour les reponses API (generes a partir des contrats backend) |

---

## Voir aussi

- [Guide pratique — Ajouter des plateformes, services et gates](../backend/adding-platforms-services-gates.md)
- [Architecture d'extension backend](../backend/development-extensibility.md)
- [Guide JSON Schemas](json-schemas-guide.md)
- [Architecture frontend](architecture-consumption.md)
