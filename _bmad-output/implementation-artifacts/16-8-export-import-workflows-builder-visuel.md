# Story 16.8: Export/Import de workflows depuis le builder visuel

Status: done

## Change Log

- **2026-02-06**: Story créée — Contexte complet extrait de l'Epic 16 et analyse exhaustive de l'implémentation actuelle (WorkflowBuilderCanvas.tsx, Stories 16.5-16.7 complétées). État actuel : Builder visuel opérationnel avec validation complète (start/end nodes, custom edges, validation report, save blocking), React Flow 11, conversion bidirectionnelle WorkflowStep[] ↔ React Flow nodes/edges. Gaps identifiés : export JSON/YAML/PNG, import avec validation, confirmation remplacement workflow. Technologies identifiées : html2canvas pour screenshot PNG, js-yaml pour export/import YAML, JSON.stringify/parse natif, validation JSON Schema. Ready for dev.
- **2026-02-06**: Implementation complete — 9/9 tasks done. Export JSON/YAML/PNG, import avec validation schema+métier, confirmation remplacement, chargement dans canvas. 81 tests (43 component + 38 utility) pass. Dependencies: js-yaml 4.1.0, html2canvas 1.4.1. No regressions on existing 36 tests.
- **2026-02-06**: Code review adversarial — 13 issues trouvés (6 HIGH, 4 MEDIUM, 3 LOW). 10 issues AUTO-CORRIGÉS : (H1) fichier .bak supprimé, (H2) validation taille fichier 5MB, (H3) reject erreur PNG, (H4) test ARIA file input, (H5) race condition fitView → requestAnimationFrame, (H6) clear validation on import, (M1) ordre champs export, (M2) console.debug logging, (M3) error details export image, (M4) 3 edge case tests. Tests finaux : 41/41 utility + 44/44 component = 85 tests ✅

## Story

En tant que **DBOPS gérant des workflows**,
je veux **exporter et importer des workflows depuis le builder visuel**,
afin que **je puisse partager, versionner et réutiliser des workflows complexes**.

## Acceptance Criteria

### AC1 — Menu export avec trois options

**Given** je suis dans le builder visuel avec un workflow créé
**When** je clique sur le bouton "Exporter"
**Then** un menu s'affiche avec les options :
  - "Exporter en JSON" (format technique)
  - "Exporter en YAML" (format lisible)
  - "Exporter l'image" (capture du canvas)

### AC2 — Export JSON complet

**Given** je suis dans le builder visuel
**When** je sélectionne "Exporter en JSON"
**Then** un fichier JSON est téléchargé contenant :
  - La structure complète du workflow (étapes, connexions, retry)
  - Les métadonnées (nom, description, tags)
  - La version du format d'export (pour compatibilité future)

**Format attendu** :
```json
{
  "version": "1.0",
  "workflow": {
    "name": "Nom du workflow",
    "description": "Description du workflow",
    "tags": ["tag1", "tag2"],
    "steps": [
      {
        "step_id": "uuid",
        "referenced_action_id": 123,
        "name": "Nom de l'étape",
        "on_success_step_id": "uuid-next",
        "on_error_step_id": "uuid-error",
        "retry_enabled": true,
        "retry_max_attempts": 3,
        "retry_interval_seconds": 60,
        "retry_backoff_multiplier": 2.0
      }
    ]
  }
}
```

### AC3 — Export image PNG du canvas

**Given** je suis dans le builder visuel
**When** je sélectionne "Exporter l'image"
**Then** une image PNG du canvas est générée et téléchargée
**And** l'image contient :
  - Tous les nœuds et connexions visibles
  - Les légendes (vert = succès, rouge = erreur)
  - Le nom du workflow en en-tête

### AC4 — Import via dialogue fichier

**Given** je suis dans le builder visuel
**When** je clique sur le bouton "Importer"
**Then** un dialogue de sélection de fichier s'ouvre
**And** j'ai la possibilité de sélectionner un fichier JSON ou YAML

### AC5 — Import JSON/YAML valide

**Given** je suis dans le builder visuel
**When** je sélectionne un fichier JSON/YAML valide pour import
**Then** le workflow est chargé dans le canvas
**And** tous les nœuds et connexions sont restaurés
**And** les options de retry sont restaurées
**And** un message de confirmation s'affiche : "Workflow importé avec succès"

### AC6 — Import invalide avec erreur détaillée

**Given** je suis dans le builder visuel
**When** je sélectionne un fichier JSON/YAML invalide pour import
**Then** un message d'erreur s'affiche : "Format de fichier invalide"
**And** les détails de l'erreur sont affichés (parsing error, validation schema error, etc.)
**And** le workflow actuel n'est pas modifié

### AC7 — Confirmation remplacement workflow existant

**Given** je suis dans le builder visuel avec un workflow existant
**When** j'importe un nouveau workflow
**Then** un dialogue de confirmation s'affiche : "Voulez-vous remplacer le workflow actuel ?"
**And** si je confirme, le workflow actuel est remplacé
**And** si j'annule, l'import est annulé

## Tasks / Subtasks

- [x] Task 1 (AC: 1) — Bouton "Exporter" avec menu Dropdown
  - [x]1.1 Ajouter bouton "Exporter" dans WorkflowBuilderCanvas toolbar (à côté de "Valider")
  - [x]1.2 Créer menu Dropdown Ant Design avec 3 options : JSON, YAML, Image
  - [x]1.3 Icônes : ExportOutlined (JSON), FileTextOutlined (YAML), PictureOutlined (Image)
  - [x]1.4 Styliser selon design system (aligned toolbar buttons)

- [x] Task 2 (AC: 2) — Export JSON avec métadonnées
  - [x]2.1 Créer fonction exportWorkflowAsJSON(nodes, edges, workflowMetadata)
  - [x]2.2 Convertir React Flow nodes/edges → WorkflowStep[] (réutiliser reactFlowToWorkflowSteps)
  - [x]2.3 Wrapper dans objet avec version: "1.0", workflow: { name, description, tags, steps }
  - [x]2.4 JSON.stringify avec indentation (2 spaces) pour lisibilité
  - [x]2.5 Générer filename : `${workflow_name}_${date}.json` (sanitize name)
  - [x]2.6 Télécharger via createObjectURL + <a download>
  - [x]2.7 Cleanup URL après téléchargement (revokeObjectURL)

- [x] Task 3 (AC: 1, 3) — Export YAML lisible
  - [x]3.1 Installer bibliothèque js-yaml (version stable 2026)
  - [x]3.2 Créer fonction exportWorkflowAsYAML(nodes, edges, workflowMetadata)
  - [x]3.3 Réutiliser même structure JSON que Task 2
  - [x]3.4 Convertir avec yaml.dump({ version, workflow }, { indent: 2, lineWidth: 120 })
  - [x]3.5 Générer filename : `${workflow_name}_${date}.yaml`
  - [x]3.6 Télécharger comme Task 2.6-2.7

- [x] Task 4 (AC: 3) — Export image PNG du canvas
  - [x]4.1 Installer bibliothèque html2canvas (version stable 2026, vérifier compatibilité React Flow)
  - [x]4.2 Créer fonction exportWorkflowAsImage(reactFlowInstance, workflowName)
  - [x]4.3 Récupérer viewport bounds via reactFlowInstance.getViewport()
  - [x]4.4 Capturer canvas React Flow avec html2canvas(reactFlowRef.current, { backgroundColor: '#fff' })
  - [x]4.5 Ajouter header avec workflow name via canvas.getContext('2d').fillText()
  - [x]4.6 Ajouter légende : "🟢 Succès | 🔴 Erreur | ↻ Retry activé"
  - [x]4.7 Convertir canvas → PNG blob → téléchargement
  - [x]4.8 Filename : `${workflow_name}_${date}.png`

- [x] Task 5 (AC: 4) — Bouton "Importer" avec dialogue fichier
  - [x]5.1 Ajouter bouton "Importer" dans toolbar (avant "Exporter")
  - [x]5.2 Icône ImportOutlined
  - [x]5.3 Créer <input type="file" accept=".json,.yaml,.yml" /> caché
  - [x]5.4 onClick bouton → trigger input.click()
  - [x]5.5 onChange input → lire fichier avec FileReader API

- [x] Task 6 (AC: 5, 6) — Import et validation JSON/YAML
  - [x]6.1 Créer fonction parseWorkflowFile(file) → Promise<WorkflowImport>
  - [x]6.2 Détection extension (.json vs .yaml/.yml)
  - [x]6.3 Parsing JSON : JSON.parse() avec try-catch
  - [x]6.4 Parsing YAML : yaml.load() avec try-catch
  - [x]6.5 Validation format avec JSON Schema (version, workflow.name, workflow.steps structure)
  - [x]6.6 Validation métier : step_id uniques, on_success/error_step_id référencent des steps existants
  - [x]6.7 Retourner { valid: boolean, data: WorkflowImport | null, errors: string[] }

- [x] Task 7 (AC: 7) — Confirmation remplacement workflow
  - [x]7.1 Détecter si workflow actuel existe (nodes.length > 0)
  - [x]7.2 Si existe, afficher Modal.confirm avec message "Voulez-vous remplacer le workflow actuel ?"
  - [x]7.3 Options : "Remplacer" (danger), "Annuler" (default)
  - [x]7.4 Si "Annuler" → return sans charger
  - [x]7.5 Si "Remplacer" → charger le workflow importé

- [x] Task 8 (AC: 5) — Chargement workflow dans canvas
  - [x]8.1 Créer fonction loadWorkflowIntoCanvas(importedWorkflow, setNodes, setEdges)
  - [x]8.2 Convertir WorkflowStep[] → React Flow nodes/edges (réutiliser workflowStepsToReactFlow)
  - [x]8.3 setNodes(newNodes) et setEdges(newEdges)
  - [x]8.4 Centrer viewport sur le workflow chargé (fitView avec padding)
  - [x]8.5 Afficher notification succès : "Workflow importé avec succès"
  - [x]8.6 Mettre à jour workflowMetadata (name, description, tags) dans le wizard

- [x] Task 9 (AC: 1-7) — Tests
  - [x]9.1 Tests export JSON : structure correcte, métadonnées présentes, filename sanitized
  - [x]9.2 Tests export YAML : format lisible, structure identique à JSON
  - [x]9.3 Tests export PNG : canvas capturé, header et légende présents
  - [x]9.4 Tests import JSON valide : workflow chargé, nodes/edges restaurés, retry config OK
  - [x]9.5 Tests import YAML valide : identique à JSON
  - [x]9.6 Tests import invalide : JSON malformé → erreur parsing, schema invalide → erreur validation
  - [x]9.7 Tests confirmation remplacement : workflow existant → modal affiché, annulation → pas de changement
  - [x]9.8 Tests accessibilité : ARIA labels, focus management, keyboard navigation
  - [x]9.9 Tests non-régression : 72 tests existants Stories 16.5-16.7 toujours passing

## Dev Notes

### Contexte et prérequis (Epic 16, Stories 16.2-16.7)

- **Story 16.2** (done) : Modèle de données étendu avec champs branches (on_success_step_id, on_error_step_id) et retry
- **Story 16.3** (done) : Moteur d'exécution avec support branches conditionnelles
- **Story 16.4** (done) : Moteur de retry avec backoff exponentiel
- **Story 16.5** (done) : Builder visuel opérationnel avec React Flow, validation BFS/DFS, conversion bidirectionnelle
- **Story 16.6** (done) : Configuration retry dans builder visuel avec badge et tooltip
- **Story 16.7** (done) : Validation visuelle (start/end nodes, custom edges, validation report panel, save blocking)

### État actuel de la conversion bidirectionnelle (Story 16.5, 16.7)

Le fichier `WorkflowBuilderCanvas.tsx` contient déjà les fonctions de conversion complètes et testées :

#### workflowStepsToReactFlow(steps: WorkflowStep[]) → { nodes, edges }

**Localisation** : WorkflowBuilderCanvas.tsx, lignes 61-149

**Fonctionnalités** :
```typescript
export function workflowStepsToReactFlow(steps: WorkflowStep[]): { nodes: Node[]; edges: Edge[] } {
  // 1. Convert steps → workflow nodes (type: 'workflowStep')
  const workflowNodes: Node[] = steps.map((step, index) => ({
    id: step.step_id ?? `step-${index}`,
    type: 'workflowStep',
    position: { x: (index % 4) * 280, y: Math.floor(index / 4) * 200 + 120 },
    data: {
      action_id: step.referenced_action_id,
      action_name: step.name ?? `Action #${step.referenced_action_id}`,
      name: step.name,
      retry_enabled: step.retry_enabled ?? false,
      retry_max_attempts: step.retry_max_attempts ?? null,
      retry_interval_seconds: step.retry_interval_seconds ?? null,
      retry_backoff_multiplier: step.retry_backoff_multiplier ?? null,
      on_success_step_id: step.on_success_step_id ?? null,
      on_error_step_id: step.on_error_step_id ?? null,
      // ... lookup step names for tooltip
    }
  }));

  // 2. Create edges from on_success/error_step_id
  const edges: Edge[] = [];
  steps.forEach((step) => {
    if (step.on_success_step_id) {
      edges.push({
        id: `${sourceId}_success_${step.on_success_step_id}`,
        source: sourceId,
        target: step.on_success_step_id,
        sourceHandle: 'success',
        type: 'customEdge',
        style: { stroke: '#52c41a' },  // Green
      });
    }
    if (step.on_error_step_id) {
      edges.push({
        id: `${sourceId}_error_${step.on_error_step_id}`,
        source: sourceId,
        target: step.on_error_step_id,
        sourceHandle: 'error',
        type: 'customEdge',
        style: { stroke: '#ff4d4f' },  // Red
      });
    }
  });

  // 3. Inject start/end visual nodes (Story 16.7)
  const startNode: Node = { id: START_NODE_ID, type: 'start', ... };
  const endNode: Node = { id: END_NODE_ID, type: 'end', ... };

  return { nodes: [startNode, ...workflowNodes, endNode], edges };
}
```

**Note importante pour Story 16.8** :
- Les nœuds start/end (id: `__start__`, `__end__`) sont **visuels uniquement**
- Ils doivent être **exclus** de l'export JSON/YAML
- Filter : `nodes.filter((n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID)`

#### reactFlowToWorkflowSteps(nodes: Node[], edges: Edge[]) → WorkflowStep[]

**Localisation** : WorkflowBuilderCanvas.tsx, lignes 152-203

**Fonctionnalités** :
```typescript
export function reactFlowToWorkflowSteps(nodes: Node[], edges: Edge[]): WorkflowStep[] {
  // 1. Exclude start/end visual nodes
  const workflowNodes = nodes.filter(
    (n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID
  );

  // 2. Convert nodes → steps
  return workflowNodes.map((node) => {
    const nodeData = node.data as WorkflowStepNodeData;

    // Find success/error connections from edges
    const successEdge = edges.find(
      (e) => e.source === node.id && e.sourceHandle === 'success'
    );
    const errorEdge = edges.find(
      (e) => e.source === node.id && e.sourceHandle === 'error'
    );

    return {
      step_id: node.id,
      referenced_action_id: nodeData.action_id,
      name: nodeData.name,
      on_success_step_id: successEdge?.target ?? null,
      on_error_step_id: errorEdge?.target ?? null,
      retry_enabled: nodeData.retry_enabled ?? false,
      retry_max_attempts: nodeData.retry_max_attempts ?? null,
      retry_interval_seconds: nodeData.retry_interval_seconds ?? null,
      retry_backoff_multiplier: nodeData.retry_backoff_multiplier ?? null,
    } satisfies WorkflowStep;
  });
}
```

**Utilisation pour Story 16.8** :
- **Export** : reactFlowToWorkflowSteps(nodes, edges) → WorkflowStep[] → JSON/YAML
- **Import** : JSON/YAML → WorkflowStep[] → workflowStepsToReactFlow() → canvas

### Format d'export/import unifié

#### Structure JSON/YAML (version 1.0)

```typescript
interface WorkflowExport {
  version: string;  // "1.0" — Permet évolution future du format
  workflow: {
    name: string;
    description: string | null;
    tags: string[];
    steps: WorkflowStep[];
  };
}
```

**Exemple JSON** :
```json
{
  "version": "1.0",
  "workflow": {
    "name": "Patching Oracle Production",
    "description": "Workflow de patching avec validation et rollback",
    "tags": ["oracle", "production", "patching"],
    "steps": [
      {
        "step_id": "550e8400-e29b-41d4-a716-446655440000",
        "referenced_action_id": 42,
        "name": "Backup base avant patch",
        "on_success_step_id": "550e8400-e29b-41d4-a716-446655440001",
        "on_error_step_id": "550e8400-e29b-41d4-a716-446655440099",
        "retry_enabled": true,
        "retry_max_attempts": 3,
        "retry_interval_seconds": 60,
        "retry_backoff_multiplier": 2.0
      },
      {
        "step_id": "550e8400-e29b-41d4-a716-446655440001",
        "referenced_action_id": 43,
        "name": "Appliquer le patch",
        "on_success_step_id": null,
        "on_error_step_id": "550e8400-e29b-41d4-a716-446655440099",
        "retry_enabled": false,
        "retry_max_attempts": null,
        "retry_interval_seconds": null,
        "retry_backoff_multiplier": null
      },
      {
        "step_id": "550e8400-e29b-41d4-a716-446655440099",
        "referenced_action_id": 44,
        "name": "Rollback et alerte",
        "on_success_step_id": null,
        "on_error_step_id": null,
        "retry_enabled": false,
        "retry_max_attempts": null,
        "retry_interval_seconds": null,
        "retry_backoff_multiplier": null
      }
    ]
  }
}
```

**Exemple YAML équivalent** :
```yaml
version: '1.0'
workflow:
  name: Patching Oracle Production
  description: Workflow de patching avec validation et rollback
  tags:
    - oracle
    - production
    - patching
  steps:
    - step_id: 550e8400-e29b-41d4-a716-446655440000
      referenced_action_id: 42
      name: Backup base avant patch
      on_success_step_id: 550e8400-e29b-41d4-a716-446655440001
      on_error_step_id: 550e8400-e29b-41d4-a716-446655440099
      retry_enabled: true
      retry_max_attempts: 3
      retry_interval_seconds: 60
      retry_backoff_multiplier: 2.0
    - step_id: 550e8400-e29b-41d4-a716-446655440001
      referenced_action_id: 43
      name: Appliquer le patch
      on_success_step_id: null
      on_error_step_id: 550e8400-e29b-41d4-a716-446655440099
      retry_enabled: false
      retry_max_attempts: null
      retry_interval_seconds: null
      retry_backoff_multiplier: null
    - step_id: 550e8400-e29b-41d4-a716-446655440099
      referenced_action_id: 44
      name: Rollback et alerte
      on_success_step_id: null
      on_error_step_id: null
      retry_enabled: false
      retry_max_attempts: null
      retry_interval_seconds: null
      retry_backoff_multiplier: null
```

### JSON Schema pour validation import

```typescript
const WorkflowExportSchema = {
  type: 'object',
  required: ['version', 'workflow'],
  properties: {
    version: { type: 'string', enum: ['1.0'] },
    workflow: {
      type: 'object',
      required: ['name', 'steps'],
      properties: {
        name: { type: 'string', minLength: 1, maxLength: 200 },
        description: { type: ['string', 'null'], maxLength: 1000 },
        tags: {
          type: 'array',
          items: { type: 'string', minLength: 1, maxLength: 50 },
          maxItems: 20,
        },
        steps: {
          type: 'array',
          minItems: 1,
          maxItems: 100,  // Limite raisonnable
          items: {
            type: 'object',
            required: ['step_id', 'referenced_action_id', 'name'],
            properties: {
              step_id: { type: 'string', minLength: 1 },
              referenced_action_id: { type: 'integer', minimum: 1 },
              name: { type: ['string', 'null'], maxLength: 200 },
              on_success_step_id: { type: ['string', 'null'] },
              on_error_step_id: { type: ['string', 'null'] },
              retry_enabled: { type: 'boolean' },
              retry_max_attempts: { type: ['integer', 'null'], minimum: 1, maximum: 10 },
              retry_interval_seconds: { type: ['integer', 'null'], minimum: 1, maximum: 3600 },
              retry_backoff_multiplier: { type: ['number', 'null'], minimum: 1.0, maximum: 10.0 },
            },
          },
        },
      },
    },
  },
};
```

**Validation métier supplémentaire** :
1. **step_id uniques** : Chaque step_id doit être unique dans le workflow
2. **Références valides** : on_success_step_id et on_error_step_id doivent référencer des step_id existants ou être null
3. **Pas de cycles immédiats** : on_success_step_id !== step_id (auto-référence interdite)
4. **Retry cohérent** : Si retry_enabled = true, alors retry_max_attempts > 0, retry_interval_seconds > 0, retry_backoff_multiplier >= 1.0

### Bibliothèques requises

#### js-yaml (pour export/import YAML)

**Version recommandée 2026** : js-yaml 4.1.0+ (stable, largement utilisée)

**Installation** :
```bash
npm install js-yaml
npm install --save-dev @types/js-yaml
```

**Usage** :
```typescript
import yaml from 'js-yaml';

// Export YAML
const yamlString = yaml.dump(workflowExport, {
  indent: 2,
  lineWidth: 120,
  noRefs: true,  // Évite les références circulaires
});

// Import YAML
try {
  const parsed = yaml.load(yamlContent) as WorkflowExport;
  // Validation ensuite
} catch (e) {
  // Erreur de parsing YAML
}
```

#### html2canvas (pour export PNG)

**Version recommandée 2026** : html2canvas 1.4.1+ (compatible avec React Flow 11)

**Installation** :
```bash
npm install html2canvas
npm install --save-dev @types/html2canvas
```

**Usage avec React Flow** :
```typescript
import html2canvas from 'html2canvas';

async function exportWorkflowAsImage(
  reactFlowWrapper: HTMLDivElement,
  workflowName: string
): Promise<void> {
  // Capturer le canvas React Flow
  const canvas = await html2canvas(reactFlowWrapper, {
    backgroundColor: '#ffffff',
    scale: 2,  // Haute résolution
    logging: false,
  });

  // Ajouter header et légende
  const finalCanvas = document.createElement('canvas');
  finalCanvas.width = canvas.width;
  finalCanvas.height = canvas.height + 100;  // +100px pour header

  const ctx = finalCanvas.getContext('2d')!;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, finalCanvas.width, finalCanvas.height);

  // Header
  ctx.font = 'bold 24px sans-serif';
  ctx.fillStyle = '#000000';
  ctx.fillText(workflowName, 20, 40);

  // Légende
  ctx.font = '14px sans-serif';
  ctx.fillStyle = '#52c41a';
  ctx.fillText('🟢 Succès', 20, 70);
  ctx.fillStyle = '#ff4d4f';
  ctx.fillText('🔴 Erreur', 150, 70);
  ctx.fillStyle = '#1890ff';
  ctx.fillText('↻ Retry activé', 280, 70);

  // Canvas workflow
  ctx.drawImage(canvas, 0, 100);

  // Téléchargement
  finalCanvas.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${sanitizeFilename(workflowName)}_${formatDate(new Date())}.png`;
    a.click();
    URL.revokeObjectURL(url);
  });
}
```

**Alternatives si html2canvas incompatible avec React Flow** :
- `react-to-print` (si React Flow supporte le print mode)
- `dom-to-image-more` (fork maintenu de dom-to-image)
- Canvas natif React Flow export (vérifier API React Flow 11)

### Architecture de la solution Story 16.8

#### Composants impactés

```
WorkflowBuilderCanvas.tsx (root component)
├── Toolbar (zone buttons existante)
│   ├── "Importer" button (NOUVEAU) → ImportOutlined
│   ├── "Exporter" button (NOUVEAU) → Dropdown menu (JSON, YAML, Image)
│   └── "Valider" button (EXISTANT)
├── <input type="file" /> (NOUVEAU - caché)
└── Functions utilitaires (NOUVEAU)
    ├── exportWorkflowAsJSON()
    ├── exportWorkflowAsYAML()
    ├── exportWorkflowAsImage()
    ├── parseWorkflowFile()
    ├── validateWorkflowImport()
    └── loadWorkflowIntoCanvas()
```

#### Flux export (JSON/YAML)

```
User click "Exporter" → Dropdown menu
  ↓
User sélectionne "JSON" ou "YAML"
  ↓
1. Conversion canvas → WorkflowStep[]
   - reactFlowToWorkflowSteps(nodes, edges)
   - Exclusion des nœuds start/end
  ↓
2. Création objet WorkflowExport
   - { version: "1.0", workflow: { name, description, tags, steps } }
  ↓
3. Sérialisation
   - JSON : JSON.stringify(obj, null, 2)
   - YAML : yaml.dump(obj, { indent: 2 })
  ↓
4. Téléchargement
   - Blob creation (type: application/json ou text/yaml)
   - createObjectURL → <a download> → click → revokeObjectURL
```

#### Flux export (Image PNG)

```
User click "Exporter" → "Image"
  ↓
1. Capture canvas React Flow
   - html2canvas(reactFlowWrapper, { backgroundColor: '#fff', scale: 2 })
  ↓
2. Création canvas final avec header
   - Canvas width/height étendu (+100px header)
   - Dessiner header (workflow name)
   - Dessiner légende (🟢 Succès | 🔴 Erreur | ↻ Retry)
   - Dessiner workflow canvas capturé
  ↓
3. Export PNG
   - canvas.toBlob() → createObjectURL → download → revokeObjectURL
```

#### Flux import (JSON/YAML)

```
User click "Importer" → <input file> dialog
  ↓
User sélectionne fichier .json ou .yaml
  ↓
1. Lecture fichier
   - FileReader.readAsText()
  ↓
2. Parsing
   - JSON : JSON.parse()
   - YAML : yaml.load()
  ↓
3. Validation
   - JSON Schema validation (structure)
   - Validation métier (step_id uniques, références valides)
  ↓
4. Confirmation remplacement si workflow existant
   - Modal.confirm("Voulez-vous remplacer le workflow actuel ?")
  ↓
5. Chargement dans canvas
   - workflowStepsToReactFlow(importedSteps)
   - setNodes(newNodes), setEdges(newEdges)
   - fitView() pour centrer
   - Notification succès
  ↓
6. Mise à jour métadonnées
   - Mettre à jour workflow name, description, tags dans ActionWizard
```

### Guardrails (anti-erreurs dev / LLM)

- **Exclure start/end** : TOUJOURS filter `nodes.filter((n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID)` avant export
- **Sanitize filenames** : Remplacer caractères interdits (/, \, :, *, ?, ", <, >, |) par underscore
- **Cleanup URLs** : TOUJOURS revokeObjectURL après download pour éviter memory leaks
- **Validation stricte** : Ne PAS charger un workflow invalide dans le canvas (risque de corruption état)
- **Confirmation obligatoire** : TOUJOURS demander confirmation avant de remplacer un workflow existant
- **Format date cohérent** : Utiliser format ISO 8601 simplifié `YYYY-MM-DD_HH-mm-ss` pour filenames
- **Gestion erreurs parsing** : Attraper TOUTES les exceptions (JSON.parse, yaml.load) et afficher erreur utilisateur-friendly
- **Type safety** : WorkflowExport interface stricte avec tous les champs requis
- **Null-safety** : Gérer tous les champs nullables (on_success_step_id, retry_*, description, tags)
- **Performance** : html2canvas peut être lent sur gros workflows → afficher spinner pendant capture
- **Accessibilité** : ARIA labels sur boutons export/import, focus management dans modales
- **Tests de non-régression** : S'assurer que les 72 tests existants passent toujours après ajout export/import

### Testing Strategy

**Tests unitaires** (`frontend/src/utils/workflowExport.test.ts`) :
1. exportWorkflowAsJSON : structure correcte, version présente, métadonnées complètes
2. exportWorkflowAsYAML : format lisible, structure identique à JSON
3. parseWorkflowFile : JSON valide parsé correctement, YAML valide parsé correctement
4. validateWorkflowImport : schema validation (version manquante → erreur, steps vide → erreur)
5. validateWorkflowImport : validation métier (step_id doublons → erreur, référence invalide → erreur)
6. sanitizeFilename : caractères interdits remplacés, espaces → underscores
7. formatDate : format ISO 8601 simplifié

**Tests composant** (`frontend/src/components/admin/WorkflowBuilderCanvas.test.tsx`) :
1. Bouton "Exporter" affiche menu Dropdown avec 3 options
2. Click "Exporter en JSON" → téléchargement fichier JSON
3. Click "Exporter en YAML" → téléchargement fichier YAML
4. Click "Exporter l'image" → téléchargement PNG (mock html2canvas)
5. Bouton "Importer" ouvre dialogue fichier
6. Import JSON valide → workflow chargé, nodes/edges restaurés
7. Import YAML valide → workflow chargé identique à JSON
8. Import JSON invalide → erreur affichée, workflow inchangé
9. Import avec workflow existant → modal confirmation affiché
10. Confirmation remplacement → workflow remplacé
11. Annulation remplacement → workflow inchangé

**Tests intégration** (`frontend/src/components/admin/ActionWizard.test.tsx`) :
1. Export workflow → Import → Workflow identique (round-trip)
2. Export JSON → Import YAML → Workflow identique (interopérabilité)
3. Export avec retry config → Import → Retry config restauré
4. Export avec branches conditionnelles → Import → Branches restaurées
5. Export workflow vide → Import → Erreur validation

**Tests accessibilité** :
1. ARIA labels sur boutons Export/Import
2. Navigation clavier dans Dropdown menu
3. Focus management dans Modal.confirm
4. Annonce screen reader lors téléchargement réussi

**Tests performance** :
1. Export workflow 50 steps → < 500ms
2. Import workflow 50 steps → < 1s
3. Export image workflow 20 steps → < 3s (html2canvas peut être lent)

### Project Structure Notes

- **Fichier nouveau** : `idp-portal/frontend/src/utils/workflowExport.ts` (fonctions export/import)
- **Fichier nouveau** : `idp-portal/frontend/src/utils/workflowValidation.ts` (JSON Schema validation)
- **Fichier modifié** : `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.tsx` (boutons export/import, intégration)
- **Tests nouveaux** : `workflowExport.test.ts`, `workflowValidation.test.ts`
- **Tests modifiés** : `WorkflowBuilderCanvas.test.tsx` (tests export/import), `ActionWizard.test.tsx` (round-trip)
- **Package.json modifié** : Ajouter `js-yaml` et `html2canvas` avec leurs types

### Previous Story Intelligence (Story 16.7)

- **Story 16.7** (done) : Validation visuelle complète (start/end nodes, custom edges, validation report panel, save blocking)
- **Patterns établis** :
  - Toolbar buttons avec Ant Design (Button, Dropdown, Modal)
  - Conversion bidirectionnelle WorkflowStep[] ↔ React Flow nodes/edges
  - Validation complète avant sauvegarde (validateWorkflowGraph)
  - Notification utilisateur (message.success, Modal.error)
  - Tests exhaustifs (72 tests passants)

**Insights pour Story 16.8** :
- **Réutiliser** reactFlowToWorkflowSteps et workflowStepsToReactFlow (déjà testés et validés)
- **Suivre** le pattern de validation existant (JSON Schema + validation métier)
- **Cohérence UI** : Boutons Export/Import à côté de "Valider" dans toolbar
- **Tester** la non-régression : 72 tests Story 16.5-16.7 doivent toujours passer

### Git Intelligence

**Commits récents (Epic 16)** :
1. `290c116` - feat(16.7): Add workflow path validation and visual feedback
   - Validation complète (start/end, custom edges, report panel)
   - 67/67 tests pass
   - **Pattern** : Feature complète avec validation UI

2. `df9b703` - docs(16.6): Update story status to done after code review
   - Documentation rigoureuse
   - **Pattern** : Change log détaillé dans story file

3. `7648151` - fix(16.6): Code review fixes — Ant Design props, null-safety, i18n, validation
   - Correctifs Ant Design 6.2, null-safety stricte
   - **Pattern** : Correctifs ciblés post-review

**Insights pour Story 16.8** :
- **Commit feature complet** : `feat(16.8): Add workflow export/import (JSON/YAML/PNG)`
- **Tests avant commit** : S'assurer que tous les tests passent (existants + nouveaux)
- **Documentation** : Mettre à jour change log avec détails implémentation
- **Code review anticipé** : Ant Design 6.2 props, null-safety stricte, error handling robuste

### Latest Tech Information (js-yaml 4.1, html2canvas 1.4, React Flow 11)

**js-yaml 4.1.0 (2026)** :
- **API stable** : yaml.dump() et yaml.load() inchangées depuis version 3.x
- **Options recommandées** :
  ```typescript
  yaml.dump(obj, {
    indent: 2,        // Indentation lisible
    lineWidth: 120,   // Évite lignes trop longues
    noRefs: true,     // Évite références circulaires
    sortKeys: false,  // Préserve ordre des clés
  })
  ```
- **Sécurité** : yaml.load() safe par défaut (pas d'exécution code arbitraire)
- **Performance** : Parsing YAML ~2x plus lent que JSON, mais acceptable pour workflows < 100 steps

**html2canvas 1.4.1 (2026)** :
- **Compatibilité React Flow 11** : Fonctionne avec SVG + Canvas hybride
- **Options recommandées** :
  ```typescript
  html2canvas(element, {
    backgroundColor: '#ffffff',
    scale: 2,           // Haute résolution (Retina)
    logging: false,     // Désactiver logs console
    useCORS: true,      // Si images externes (icônes, etc.)
  })
  ```
- **Performance** : ~1-3s pour canvas 20 nodes (acceptable avec spinner)
- **Limitations** : Ne capture pas les animations CSS, transformations 3D

**React Flow 11 (utilisé dans le projet)** :
- **useReactFlow hook** : `fitView()` pour centrer viewport après import
- **getViewport()** : Récupérer position/zoom actuel
- **Pas d'API export native** : html2canvas reste la meilleure option

**Ant Design 6.2 (projet)** :
- **Dropdown** : `<Dropdown menu={{ items }} trigger={['click']}>`
- **Modal.confirm** : `Modal.confirm({ title, content, okText, cancelText, onOk, onCancel })`
- **message.success** : Notification toast non-bloquante
- **Upload (non utilisé ici)** : Préférer <input type="file" /> pour plus de contrôle

**Best practices 2026** :
- **JSON over YAML pour machines** : Plus rapide, moins de bugs parsing
- **YAML over JSON pour humains** : Plus lisible, commentaires possibles (optionnel v2.0)
- **PNG export optionnel** : Utile pour documentation, mais ne peut pas être réimporté
- **Versionning du format** : `version: "1.0"` permet évolution future sans breaking changes
- **Validation stricte** : Ne JAMAIS charger un workflow invalide (risque corruption)

**Sécurité** :
- **js-yaml 4.1** : Pas de vulnérabilités connues (février 2026), safe par défaut
- **html2canvas 1.4** : Pas de vulnérabilités connues
- **Sanitization filenames** : OBLIGATOIRE pour éviter path traversal (/, \, ..)
- **Validation côté serveur** : Même si validation client, backend doit AUSSI valider le workflow

### References

- [Source: _bmad-output/implementation-artifacts/epic-16-builder-workflow-visuel.md#Story-16.8] — Spécification complète de la story
- [Source: _bmad-output/implementation-artifacts/16-5-interface-builder-visuel-workflow.md] — Builder visuel avec conversion bidirectionnelle
- [Source: _bmad-output/implementation-artifacts/16-7-visualisation-validation-chemins-builder-visuel.md] — Validation complète et UI patterns
- [Source: idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.tsx] — Conversion workflowStepsToReactFlow et reactFlowToWorkflowSteps
- [Source: _bmad-output/planning-artifacts/architecture.md] — Architecture globale et patterns
- [js-yaml Documentation](https://github.com/nodeca/js-yaml) — Export/import YAML
- [html2canvas Documentation](https://html2canvas.hertzen.com/) — Capture canvas PNG
- [JSON Schema](https://json-schema.org/) — Validation format export
- [React Flow Documentation](https://reactflow.dev) — fitView, getViewport

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- All 43 component tests pass (36 existing + 7 new Story 16.8)
- All 38 utility tests pass (new workflowExport.test.ts)
- Pre-existing failures in AuditPage, ExecutionsPage, RemediationRulesEditor (unrelated to Story 16.8)

### Completion Notes List

- **Task 1**: Bouton "Exporter" Dropdown Ant Design avec 3 options (JSON/YAML/Image) + icônes ExportOutlined, FileTextOutlined, PictureOutlined. Bouton "Importer" avec ImportOutlined.
- **Task 2**: Export JSON via buildWorkflowExport() → JSON.stringify(, null, 2) → Blob download. Réutilise reactFlowToWorkflowSteps. Version "1.0", metadata (name, description, tags), filename sanitized.
- **Task 3**: Export YAML via js-yaml 4.1.0 yaml.dump() avec indent: 2, lineWidth: 120, noRefs: true. Même structure que JSON.
- **Task 4**: Export PNG via html2canvas (import dynamique). Canvas final avec header (workflow name) + légende (Succès/Erreur/Retry) + capture React Flow. Loading state pendant capture.
- **Task 5**: Input file caché (accept=".json,.yaml,.yml"), onClick bouton Importer → trigger input.click(), FileReader API.
- **Task 6**: parseWorkflowFile() avec détection extension, parsing JSON/YAML, validation schema (version, name, steps structure) + validation métier (step_id uniques, références valides, auto-référence interdite, retry cohérent). 38 tests unitaires.
- **Task 7**: Modal.confirm si workflow existant (nodes.length > 0). "Remplacer" (danger) / "Annuler". Si annuler → pas de modification.
- **Task 8**: loadWorkflowIntoCanvas() via workflowStepsToReactFlow() → setNodes/setEdges → fitView. Callback onMetadataImport pour propager name/description/tags au parent.
- **Task 9**: 81 tests total (43 component + 38 utility). Tests export JSON/YAML structure, round-trip, validation schema/métier, boutons UI, dropdown menu, ARIA labels, accessibility.

### File List

- **NEW**: `idp-portal/frontend/src/utils/workflowExport.ts` — Export/import utilities (JSON/YAML/PNG, validation, filename helpers) + 10 code review fixes
- **NEW**: `idp-portal/frontend/src/utils/workflowExport.test.ts` — 41 unit tests (38 original + 3 edge cases from code review)
- **MODIFIED**: `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.tsx` — Import/Export buttons, dropdown menu, file import, metadata props + 7 code review fixes
- **MODIFIED**: `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.test.tsx` — 8 new Story 16.8 tests (44 total) including ARIA file input test
- **MODIFIED**: `idp-portal/frontend/package.json` — Added js-yaml 4.1.0, html2canvas 1.4.1, @types/js-yaml, @types/html2canvas
- **MODIFIED**: `idp-portal/frontend/package-lock.json` — Lock file updated
- **DELETED**: `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx.bak` — Backup file removed (code review H1)
- **MODIFIED**: `_bmad-output/implementation-artifacts/sprint-status.yaml` — Story status: review → done
- **MODIFIED**: `_bmad-output/implementation-artifacts/16-8-export-import-workflows-builder-visuel.md` — Tasks marked complete, code review fixes applied, status done
