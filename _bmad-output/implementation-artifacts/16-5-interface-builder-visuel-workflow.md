# Story 16.5: Interface de builder visuel de workflow

Status: done

## Change Log

- **2026-02-06**: Story créée - Contexte complet extrait de l'Epic 16 et des stories 16.2-16.4. Analyse complète de l'architecture frontend existante (WorkflowStepsEditor avec @dnd-kit) et recherche React Flow 2026. Prêt pour implémentation.
- **2026-02-06**: Implémentation complète — React Flow v12+ installé, WorkflowBuilderCanvas avec palette d'actions, drag-and-drop, connexions succès/erreur, panneau de configuration, suppression nœuds/edges, validation de graphe (orphelins, boucles), synchronisation bidirectionnelle avec WorkflowStepsEditor, toggle mode liste/visuel dans ActionWizard. 28 tests unitaires et d'intégration passent, 18/23 tests ActionWizard passent (5 pre-existing failures). TypeScript compilation clean.
- **2026-02-06**: Code review adversarial — 15 problèmes identifiés (8 CRITICAL + 7 MEDIUM), tous corrigés automatiquement : self-loop blocking (AC8), debounced sync (avoid infinite loop), TypeScript build errors (unused imports/theme), node collision offset (drag-and-drop UX), drawer auto-focus (accessibility), retrocompatibility warning (step_id migration). Commit créé : `9ca3283` feat(16.5): Add visual workflow builder with React Flow. Tests WorkflowBuilderCanvas 28/28 ✅. Story marquée `done`.

## Story

En tant que **DBOPS créant un workflow**,
je veux **une interface graphique pour créer et modifier des workflows avec drag-and-drop**,
afin que **je puisse visualiser et configurer facilement les branches conditionnelles et les chemins d'exécution**.

## Acceptance Criteria

### AC1 — Canvas graphique avec zone de travail interactive

**Given** je suis sur la page de création/édition de workflow,
**When** je sélectionne l'onglet "Builder visuel",
**Then** un canvas graphique s'affiche avec :
  - Une zone de travail zoomable et pannable (support tactile et molette souris)
  - Une palette d'actions disponibles (liste des actions publiées)
  - Des outils de connexion pour créer des liens entre les étapes

### AC2 — Drag-and-drop d'actions depuis la palette

**Given** je suis dans le builder visuel,
**When** je fais glisser une action depuis la palette vers le canvas,
**Then** un nouveau nœud d'étape apparaît sur le canvas,
**And** le nœud affiche :
  - Le nom de l'action
  - L'icône de la technologie (Oracle, SQL Server, etc.)
  - Des ports de connexion (entrée, sortie succès, sortie erreur)

### AC3 — Création de connexions (branches succès)

**Given** je suis dans le builder visuel avec des étapes créées,
**When** je clique sur le port "succès" d'une étape et le connecte au port "entrée" d'une autre étape,
**Then** une flèche verte apparaît entre les deux étapes,
**And** le système met à jour `on_success_step_id` de la première étape.

### AC4 — Création de connexions (branches erreur)

**Given** je suis dans le builder visuel avec des étapes créées,
**When** je clique sur le port "erreur" d'une étape et le connecte au port "entrée" d'une autre étape,
**Then** une flèche rouge apparaît entre les deux étapes,
**And** le système met à jour `on_error_step_id` de la première étape.

### AC5 — Panneau de configuration d'étape

**Given** je suis dans le builder visuel,
**When** je double-clique sur un nœud d'étape,
**Then** un panneau latéral s'ouvre avec :
  - Les détails de l'action (nom, description, paramètres)
  - Les options de retry (activé/désactivé, nombre de tentatives, intervalle)
  - Les options de branchement (étape suivante en succès, étape suivante en erreur)

### AC6 — Suppression de connexion

**Given** je suis dans le builder visuel,
**When** je supprime une connexion entre deux étapes,
**Then** la flèche disparaît,
**And** le champ correspondant (`on_success_step_id` ou `on_error_step_id`) est mis à NULL.

### AC7 — Suppression de nœud

**Given** je suis dans le builder visuel,
**When** je supprime un nœud d'étape,
**Then** le nœud disparaît du canvas,
**And** toutes les connexions vers/depuis ce nœud sont supprimées,
**And** le système valide que le workflow reste valide (au moins une étape de départ).

### AC8 — Validation et sauvegarde du workflow

**Given** je suis dans le builder visuel,
**When** je sauvegarde le workflow,
**Then** le système valide :
  - Toutes les étapes ont au moins une connexion de sortie (succès ou erreur)
  - Il n'y a pas de chemins orphelins (étapes non atteignables depuis le début)
  - Il n'y a pas de boucles infinies
**And** affiche les erreurs de validation directement sur le canvas (nœuds en rouge).

## Tasks / Subtasks

- [x] Task 1 (AC: 1) — Installation et configuration de React Flow
  - [x] 1.1 Installer React Flow v12+ (`npm install @xyflow/react` ou `reactflow`)
  - [x] 1.2 Créer composant `WorkflowBuilderCanvas.tsx` avec imports React Flow
  - [x] 1.3 Configurer le provider React Flow avec contrôles zoom/pan
  - [x] 1.4 Créer la palette latérale avec liste des actions publiées (réutiliser `getEligibleActionsForWorkflow()`)
  - [x] 1.5 Ajouter le toggle/onglet "Builder visuel" dans ActionWizard Step 2 (actuellement WorkflowStepsEditor)

- [x] Task 2 (AC: 2) — Drag-and-drop d'actions depuis la palette vers le canvas
  - [x] 2.1 Implémenter `onDragStart`, `onDragOver`, `onDrop` pour ajouter un nœud depuis la palette
  - [x] 2.2 Créer un composant `WorkflowStepNode` personnalisé avec :
    - Nom de l'action
    - Icône technologie (moteur/plateforme)
    - 3 handles : entrée (top), sortie succès (bottom-left, vert), sortie erreur (bottom-right, rouge)
  - [x] 2.3 Générer un `step_id` unique pour chaque nœud créé (réutiliser `generateStepId()` de WorkflowStepsEditor)
  - [x] 2.4 Positionner le nœud à l'emplacement du drop sur le canvas

- [x] Task 3 (AC: 3, 4) — Création de connexions entre nœuds (branches)
  - [x] 3.1 Configurer `onConnect` pour créer des edges entre handles
  - [x] 3.2 Styliser les edges : vert pour succès, rouge pour erreur (utiliser `style` ou `className` conditionnelle)
  - [x] 3.3 Mapper les connexions vers le modèle de données :
    - Handle "success" → met à jour `on_success_step_id` du nœud source
    - Handle "error" → met à jour `on_error_step_id` du nœud source
  - [x] 3.4 Ajouter un type d'edge custom avec label (optionnel : "succès" / "erreur")

- [x] Task 4 (AC: 5) — Panneau latéral de configuration d'étape
  - [x] 4.1 Créer composant `StepConfigPanel.tsx` avec Ant Design Drawer
  - [x] 4.2 Afficher les détails de l'action sélectionnée (nom, description, icône)
  - [x] 4.3 Intégrer les champs de configuration existants (actuellement dans WorkflowStepsEditor Card) :
    - Nom d'affichage (name)
    - Retry (retry_enabled, retry_max_attempts, retry_interval_seconds, retry_backoff_multiplier)
    - Branches (on_success_step_id, on_error_step_id) — affichage en lecture seule (modifiable via canvas)
  - [x] 4.4 Ouvrir le drawer au double-clic sur un nœud (événement `onNodeDoubleClick`)

- [x] Task 5 (AC: 6, 7) — Suppression de connexions et nœuds
  - [x] 5.1 Implémenter `onEdgesDelete` pour supprimer une edge et mettre à jour le champ correspondant (on_success_step_id | on_error_step_id) à NULL
  - [x] 5.2 Implémenter `onNodesDelete` pour supprimer un nœud et toutes ses connexions
  - [x] 5.3 Valider qu'il reste au moins une étape après suppression (bloquer si dernière étape)
  - [x] 5.4 Ajouter un bouton "Supprimer" dans le StepConfigPanel (alternative au clic sur nœud + Delete)

- [x] Task 6 (AC: 8) — Validation du workflow et sauvegarde
  - [x] 6.1 Réutiliser la validation existante de `catalog/validation.py` (backend) :
    - Cycle detection (DFS)
    - Vérification des références step_id
    - Au moins un point de sortie (on_success_step_id ou on_error_step_id = NULL)
  - [x] 6.2 Implémenter une validation frontend côté canvas :
    - Nœuds sans sortie → bordure orange (warning)
    - Nœuds orphelins (non atteignables) → bordure rouge (error)
    - Boucles infinies détectées → bordure rouge sur les nœuds de la boucle
  - [x] 6.3 Afficher un message de validation avant sauvegarde (bloquer si erreurs critiques)
  - [x] 6.4 Convertir les nodes et edges React Flow vers le format WorkflowStep[] pour l'API

- [x] Task 7 (AC: 1-8) — Synchronisation bidirectionnelle avec WorkflowStepsEditor
  - [x] 7.1 Charger les WorkflowStep[] existants et les convertir en nodes et edges React Flow
  - [x] 7.2 Permettre le basculement entre "Mode liste" (WorkflowStepsEditor actuel) et "Mode visuel" (React Flow)
  - [x] 7.3 Synchroniser les modifications : chaque changement dans le builder visuel met à jour les WorkflowStep[]
  - [x] 7.4 Préserver la rétrocompatibilité : workflows existants sans step_id doivent pouvoir être chargés (générer step_id si absent)

- [x] Task 8 (AC: 1-8) — Tests
  - [x] 8.1 Tests unitaires : conversion WorkflowStep[] ↔ React Flow (nodes, edges)
  - [x] 8.2 Tests d'intégration : drag-and-drop d'action, création de connexion, suppression
  - [x] 8.3 Tests de validation : détection de nœuds orphelins, boucles infinies
  - [x] 8.4 Tests d'accessibilité : navigation clavier, ARIA labels

## Dev Notes

### Contexte et prérequis (Epic 16, Stories 16.2-16.4)

- **Story 16.2** (done) : Modèle de données étendu avec branches (on_success_step_id, on_error_step_id) et retry
- **Story 16.3** (done) : Moteur d'exécution WorkflowRuntime avec branches conditionnelles
- **Story 16.4** (done) : Moteur de retry avec backoff exponentiel
- **WorkflowStepsEditor actuel** : Interface liste avec drag-and-drop vertical (@dnd-kit), champs branches/retry déjà implémentés (Story 16.2 review)

### État actuel de l'interface workflow (WorkflowStepsEditor)

Le fichier `idp-portal/frontend/src/components/admin/WorkflowStepsEditor.tsx` contient :
- **Liste verticale** d'étapes avec réordonnancement drag-and-drop (@dnd-kit)
- **Champs implémentés** (Story 16.2) : step_id, on_success_step_id, on_error_step_id, retry_enabled, retry_max_attempts, retry_interval_seconds, retry_backoff_multiplier
- **Validation** : au moins 1 étape, referenced_action_id requis
- **AutoComplete** : sélection d'actions publiées via `getEligibleActionsForWorkflow()`

**Point d'intégration** : Ajouter un onglet/toggle dans ActionWizard Step 2 pour basculer entre "Mode liste" (WorkflowStepsEditor actuel) et "Mode visuel" (nouveau canvas React Flow).

### React Flow : bibliothèque recommandée (Epic 16 notes)

**Bibliothèque** : React Flow v12+ (https://reactflow.dev)
- **Installation** : `npm install @xyflow/react` ou `reactflow` (v12+)
- **Features** : Drag-and-drop nodes, custom nodes/edges, zoom/pan, mini-map, controls
- **Exemples officiels** :
  - [Drag and Drop Example](https://reactflow.dev/examples/interaction/drag-and-drop)
  - [Workflow Builder](https://reactflow.dev/examples/layout/workflow-builder)
  - [Workflow Editor Template](https://reactflow.dev/ui/templates/workflow-editor)

**Note** : Le projet utilise déjà @dnd-kit pour WorkflowStepsEditor. React Flow a son propre système de drag-and-drop, donc pas de conflit.

### Architecture du builder visuel

#### Composants principaux

```
WorkflowBuilderCanvas.tsx (nouveau)
├── ReactFlowProvider
│   └── ReactFlow
│       ├── Controls (zoom, fit view)
│       ├── MiniMap (optionnel)
│       ├── Background
│       └── Custom Nodes (WorkflowStepNode)
├── ActionPalette (sidebar gauche)
│   └── Liste des actions publiées (drag source)
└── StepConfigPanel (Drawer latéral droit)
    └── Configuration de l'étape sélectionnée
```

#### Modèle de données : WorkflowStep ↔ React Flow

**WorkflowStep (API)** :
```typescript
interface WorkflowStep {
  order: number;
  step_id: string | null;
  name: string | null;
  referenced_action_id: number;
  on_success_step_id: string | null;
  on_error_step_id: string | null;
  retry_enabled: boolean;
  retry_max_attempts: number | null;
  retry_interval_seconds: number | null;
  retry_backoff_multiplier: number | null;
}
```

**React Flow Node** :
```typescript
interface WorkflowNode extends Node {
  id: string; // step_id
  type: 'workflowStep';
  position: { x: number; y: number };
  data: {
    action_id: number;
    action_name: string;
    action_engine: string;
    action_platform: string;
    name: string | null; // display name
    retry_enabled: boolean;
    // ... autres champs retry
  };
}
```

**React Flow Edge** :
```typescript
interface WorkflowEdge extends Edge {
  id: string; // `${source}_${edgeType}_${target}`
  source: string; // step_id source
  target: string; // step_id target
  sourceHandle: 'success' | 'error';
  type: 'smoothstep' | 'default';
  animated: boolean;
  style: { stroke: string }; // vert ou rouge
  label?: string; // "succès" | "erreur"
}
```

#### Conversion WorkflowStep[] → React Flow (nodes + edges)

```typescript
function workflowStepsToReactFlow(
  steps: WorkflowStep[],
  actions: ActionListItem[]
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = steps.map((step, index) => {
    const action = actions.find(a => a.id === step.referenced_action_id);
    return {
      id: step.step_id ?? `step-${index}`,
      type: 'workflowStep',
      position: { x: index * 250, y: 100 }, // Layout initial simple (horizontal)
      data: {
        action_id: step.referenced_action_id,
        action_name: action?.name ?? 'Action inconnue',
        action_engine: action?.engine ?? '',
        action_platform: action?.platform ?? '',
        name: step.name,
        retry_enabled: step.retry_enabled,
        retry_max_attempts: step.retry_max_attempts,
        retry_interval_seconds: step.retry_interval_seconds,
        retry_backoff_multiplier: step.retry_backoff_multiplier,
      },
    };
  });

  const edges: Edge[] = [];
  steps.forEach((step) => {
    if (step.on_success_step_id) {
      edges.push({
        id: `${step.step_id}_success_${step.on_success_step_id}`,
        source: step.step_id!,
        target: step.on_success_step_id,
        sourceHandle: 'success',
        type: 'smoothstep',
        animated: false,
        style: { stroke: '#52c41a' }, // vert
        label: 'succès',
      });
    }
    if (step.on_error_step_id) {
      edges.push({
        id: `${step.step_id}_error_${step.on_error_step_id}`,
        source: step.step_id!,
        target: step.on_error_step_id,
        sourceHandle: 'error',
        type: 'smoothstep',
        animated: false,
        style: { stroke: '#ff4d4f' }, // rouge
        label: 'erreur',
      });
    }
  });

  return { nodes, edges };
}
```

#### Conversion React Flow → WorkflowStep[]

```typescript
function reactFlowToWorkflowSteps(
  nodes: Node[],
  edges: Edge[]
): WorkflowStep[] {
  return nodes.map((node, index) => {
    const successEdge = edges.find(
      e => e.source === node.id && e.sourceHandle === 'success'
    );
    const errorEdge = edges.find(
      e => e.source === node.id && e.sourceHandle === 'error'
    );

    return {
      order: index + 1,
      step_id: node.id,
      name: node.data.name,
      referenced_action_id: node.data.action_id,
      on_success_step_id: successEdge?.target ?? null,
      on_error_step_id: errorEdge?.target ?? null,
      retry_enabled: node.data.retry_enabled ?? false,
      retry_max_attempts: node.data.retry_max_attempts ?? null,
      retry_interval_seconds: node.data.retry_interval_seconds ?? null,
      retry_backoff_multiplier: node.data.retry_backoff_multiplier ?? null,
    };
  });
}
```

### Custom Node : WorkflowStepNode

```typescript
import { Handle, Position } from '@xyflow/react';

interface WorkflowStepNodeData {
  action_name: string;
  action_engine: string;
  action_platform: string;
  name: string | null;
  retry_enabled: boolean;
}

const WorkflowStepNode: React.FC<NodeProps<WorkflowStepNodeData>> = ({ data }) => {
  return (
    <div style={{
      border: '1px solid #d9d9d9',
      borderRadius: 8,
      padding: 12,
      background: '#fff',
      minWidth: 200
    }}>
      <Handle type="target" position={Position.Top} id="input" />

      <div style={{ fontWeight: 600 }}>{data.name ?? data.action_name}</div>
      <div style={{ fontSize: 12, color: '#8c8c8c' }}>
        {data.action_engine} / {data.action_platform}
      </div>
      {data.retry_enabled && (
        <div style={{ fontSize: 11, color: '#1890ff' }}>Retry activé</div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        id="success"
        style={{ left: '30%', background: '#52c41a' }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="error"
        style={{ left: '70%', background: '#ff4d4f' }}
      />
    </div>
  );
};

const nodeTypes = {
  workflowStep: WorkflowStepNode,
};
```

### Intégration dans ActionWizard (Step 2)

**Actuellement (Step 2)** : `WorkflowStepsEditor` affiché directement si `itemType === 'workflow'`.

**Après Story 16.5** : Ajouter un toggle/onglet pour choisir le mode :
- **Mode liste** : WorkflowStepsEditor actuel (bon pour workflows simples/linéaires)
- **Mode visuel** : WorkflowBuilderCanvas (recommandé pour workflows avec branches)

```tsx
// Dans ActionWizard Step 2
{itemType === 'workflow' && (
  <Space direction="vertical" style={{ width: '100%' }}>
    <Radio.Group value={viewMode} onChange={(e) => setViewMode(e.target.value)}>
      <Radio.Button value="list">Mode liste</Radio.Button>
      <Radio.Button value="visual">Mode visuel</Radio.Button>
    </Radio.Group>

    {viewMode === 'list' ? (
      <WorkflowStepsEditor
        steps={workflowSteps}
        onChange={setWorkflowSteps}
        disabled={isReadOnly}
      />
    ) : (
      <WorkflowBuilderCanvas
        steps={workflowSteps}
        onChange={setWorkflowSteps}
        disabled={isReadOnly}
      />
    )}
  </Space>
)}
```

### Validation du workflow (AC8)

**Backend** : La validation de `catalog/validation.py` (Story 16.2) est déjà implémentée :
- Cycle detection (DFS)
- Références step_id valides
- Au moins un point de sortie (on_success_step_id ou on_error_step_id = NULL)

**Frontend** : Implémenter une validation visuelle côté canvas :

```typescript
function validateWorkflowGraph(nodes: Node[], edges: Edge[]): ValidationResult {
  const errors: ValidationError[] = [];

  // 1. Vérifier que chaque nœud a au moins une connexion de sortie
  nodes.forEach((node) => {
    const hasSuccessEdge = edges.some(e => e.source === node.id && e.sourceHandle === 'success');
    const hasErrorEdge = edges.some(e => e.source === node.id && e.sourceHandle === 'error');

    if (!hasSuccessEdge && !hasErrorEdge) {
      errors.push({
        nodeId: node.id,
        type: 'warning',
        message: `Étape "${node.data.action_name}" n'a pas de chemin de sortie`,
      });
    }
  });

  // 2. Détecter les nœuds orphelins (non atteignables depuis le début)
  const reachableNodes = new Set<string>();
  const startNode = nodes[0]; // Première étape = point d'entrée
  const queue = [startNode.id];

  while (queue.length > 0) {
    const current = queue.shift()!;
    reachableNodes.add(current);

    edges
      .filter(e => e.source === current)
      .forEach(e => {
        if (!reachableNodes.has(e.target)) {
          queue.push(e.target);
        }
      });
  }

  nodes.forEach((node) => {
    if (!reachableNodes.has(node.id)) {
      errors.push({
        nodeId: node.id,
        type: 'error',
        message: `Étape "${node.data.action_name}" n'est pas atteignable depuis le début`,
      });
    }
  });

  // 3. Détecter les boucles infinies (DFS avec cycle detection)
  // Réutiliser l'algorithme de catalog/validation.py

  return {
    valid: errors.filter(e => e.type === 'error').length === 0,
    errors,
  };
}
```

**Affichage visuel** :
- Nœuds avec erreur : bordure rouge (`borderColor: '#ff4d4f'`)
- Nœuds avec warning : bordure orange (`borderColor: '#fa8c16'`)
- Tooltip au survol affichant le message d'erreur

### Layout automatique (optionnel, amélioration future)

Pour les workflows complexes, un layout automatique (dagre, elk) peut être utile. Pour la V1, un layout horizontal simple suffit (x = index * 250).

**Amélioration future** (hors scope Story 16.5) :
- Installer `dagre` ou `elkjs` pour layout automatique
- Bouton "Réorganiser automatiquement" dans le canvas

### Accessibilité (WCAG 2.1 AA)

- **Navigation clavier** : React Flow supporte nativement Tab pour naviguer entre nœuds
- **ARIA labels** : Ajouter `aria-label` sur les handles et nœuds
- **Contraste** : S'assurer que les couleurs (vert succès, rouge erreur) ont un contraste suffisant (vérifier avec Wave ou axe DevTools)
- **Screen reader** : Ajouter `role="img"` sur les nœuds et `aria-describedby` pour les tooltips

### Performance (Epic 16 notes)

- **50+ étapes** : React Flow est optimisé pour des graphes de 100+ nœuds (virtualization activée par défaut)
- **Drag-and-drop** : Utiliser `useMemo` pour les nodes et edges pour éviter les re-renders inutiles
- **Validation** : Lancer la validation uniquement lors de la sauvegarde (pas en temps réel pendant l'édition)

### Responsive (Epic 16 notes)

Le builder fonctionne sur écrans larges (min 1280px) comme défini dans l'UX Design. Pas de version mobile requise pour cette story.

### Guardrails (anti-erreurs dev / LLM)

- **Ne pas dupliquer** la validation backend (`catalog/validation.py`) : réutiliser la même logique en TypeScript
- **Ne pas casser** WorkflowStepsEditor : le mode liste doit rester fonctionnel et synchronisé avec le mode visuel
- **Ne pas oublier** de générer un `step_id` pour chaque nœud créé (réutiliser `generateStepId()` de WorkflowStepsEditor)
- **Rétrocompatibilité** : workflows existants sans `step_id` doivent pouvoir être chargés (générer step_id si absent)
- **Pas de nouvelle dépendance lourde** : React Flow est la seule dépendance ajoutée (package léger, ~500kb gzipped)
- **Tests visuels** : tester avec des workflows réels (3-5 étapes, branches, retry) pour valider l'UX

### Testing Strategy

**Tests unitaires** (`frontend/src/components/admin/WorkflowBuilderCanvas.test.tsx`) :
1. Conversion WorkflowStep[] → React Flow (nodes, edges)
2. Conversion React Flow → WorkflowStep[]
3. Validation de graphe : détection nœuds orphelins, boucles infinies

**Tests d'intégration** (`frontend/src/components/admin/WorkflowBuilderCanvas.integration.test.tsx`) :
1. Drag-and-drop d'une action depuis la palette vers le canvas
2. Création d'une connexion success entre deux nœuds
3. Création d'une connexion error entre deux nœuds
4. Suppression d'une connexion
5. Suppression d'un nœud
6. Sauvegarde d'un workflow avec validation (success + error)

**Tests d'accessibilité** :
1. Navigation clavier (Tab, Enter, Delete)
2. ARIA labels présents (handles, nœuds)
3. Contraste des couleurs (vert succès, rouge erreur)

### Project Structure Notes

- **Nouveau composant** : `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.tsx`
- **Nouveau composant** : `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx` (custom node)
- **Nouveau composant** : `idp-portal/frontend/src/components/admin/StepConfigPanel.tsx` (Drawer)
- **Nouveau composant** : `idp-portal/frontend/src/components/admin/ActionPalette.tsx` (sidebar)
- **Modifié** : `idp-portal/frontend/src/components/admin/ActionWizard.tsx` (ajout toggle Mode liste/visuel)
- **Tests** : `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.test.tsx`

### Previous Story Intelligence

- **Story 16.2** : Modèle de données étendu validé. WorkflowStepsEditor déjà mis à jour avec champs branches/retry. Validation backend (`catalog/validation.py`) implémentée (cycle detection, références step_id).
- **Story 16.3** : Moteur d'exécution WorkflowRuntime opérationnel. Pas de modification frontend nécessaire pour cette story.
- **Story 16.4** : Moteur de retry opérationnel. Indication "Retry activé" à afficher dans le WorkflowStepNode.
- **Patterns établis** :
  - Utilisation de @dnd-kit pour drag-and-drop dans WorkflowStepsEditor (pas de conflit avec React Flow)
  - Ant Design 6.2 pour tous les composants UI (Drawer, Radio, Button, Alert)
  - `getEligibleActionsForWorkflow()` pour charger les actions publiées
  - `generateStepId()` pour générer des step_id uniques (crypto.randomUUID())
  - Validation inline avec `status="error"` sur les champs (Ant Design)

### Git Intelligence

**Commits récents (Epic 16)** :
1. `f67fc75` - feat(16.4): Add retry engine with exponential backoff for workflow steps
   - Ajout de `_execute_step_with_retry()` dans WorkflowRuntime
   - Tests de retry avec backoff exponentiel
   - **Pattern** : Tests unitaires complets (26 tests) + tests d'intégration (4 tests)

2. `10e174f` - feat(4.12): Complete workflow step parameters implementation with adapter payload preparation
   - Préparation de payload adapter avec step_parameters
   - **Pattern** : Validation complète avant implémentation (AC5 COMPLÉTÉ)

3. `5d56444` - fix(16.3): harden branching resolution and audit path trace
   - Correction de bugs rétrocompatibilité branches
   - Ajout de `path_trace` pour auditabilité (AC4)
   - **Pattern** : Review adversarial détecte bugs subtils (partial branch keys)

4. `9ae48e4` - feat(16.3): Moteur d'exécution workflows avec branches conditionnelles
   - Création de WorkflowRuntime avec branching logic
   - Loop detection (max 100 transitions)
   - **Pattern** : TDD red-green-refactor approach

5. `033f007` - fix(16.2): harden workflow branches/retry validation and editor
   - Validation backend renforcée (step_id unicité/obligation)
   - UI admin étendue pour branches + retry
   - **Pattern** : Code review identifie manques UI (AC: "pas de changement nécessaire" → correction)

**Insights pour Story 16.5** :
- **TDD est la norme** : écrire les tests avant l'implémentation (red-green-refactor)
- **Code review AI détecte des bugs subtils** : prévoir des tests de régression (ex: partial branch keys)
- **Validation complète** : backend + frontend + tests d'intégration
- **Rétrocompatibilité critique** : workflows existants sans branches/retry doivent continuer à fonctionner
- **Audit trail SOC1** : tous les événements doivent être loggés (path_trace, correlation_id)

### Latest Tech Information (React Flow 2026)

**React Flow v12+ (2026)** :
- **Package** : `@xyflow/react` (nouveau nom depuis v12, remplace `reactflow`)
- **Version stable** : 12.3+ (vérifier `npm show @xyflow/react version`)
- **Breaking changes** :
  - Import : `import { ReactFlow, ... } from '@xyflow/react';` (au lieu de `reactflow`)
  - CSS : `import '@xyflow/react/dist/style.css';` (au lieu de `reactflow/dist/style.css`)
  - Node/Edge types : utiliser les types génériques `Node<T>`, `Edge<T>`

**Installation** :
```bash
npm install @xyflow/react
```

**Documentation officielle 2026** :
- [React Flow Docs](https://reactflow.dev)
- [Drag and Drop Example](https://reactflow.dev/examples/interaction/drag-and-drop)
- [Workflow Builder](https://reactflow.dev/examples/layout/workflow-builder)
- [Workflow Editor Template](https://reactflow.dev/ui/templates/workflow-editor)

**Best practices 2026** :
- Utiliser `useMemo` pour nodes et edges (éviter re-renders)
- Activer `fitView` au chargement initial (zoom automatique sur le graphe)
- Utiliser `useNodesState` et `useEdgesState` pour gérer l'état local
- Configurer `connectionLineStyle` pour styliser les lignes pendant le drag
- Ajouter `MiniMap` et `Controls` pour une meilleure UX

**Exemple minimal** :
```tsx
import { ReactFlow, Controls, Background, MiniMap } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

const WorkflowBuilderCanvas: React.FC = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  return (
    <div style={{ width: '100%', height: '600px' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
      >
        <Controls />
        <MiniMap />
        <Background />
      </ReactFlow>
    </div>
  );
};
```

**Performance tips 2026** :
- `nodesDraggable={true}` : permet de déplacer les nœuds (activé par défaut)
- `elevateNodesOnSelect={true}` : améliore la visibilité du nœud sélectionné
- `proOptions={{ hideAttribution: true }}` : masquer le watermark (nécessite licence Pro, ou garder attribution gratuite)

**Sécurité** :
- Pas de vulnérabilités connues en février 2026
- Package maintenu activement (dernière release : janvier 2026)
- Compatible React 19+ (déjà utilisé dans le projet : `"react": "^19.2.0"`)

### References

- [Source: _bmad-output/implementation-artifacts/epic-16-builder-workflow-visuel.md#Story-16.5]
- [Source: _bmad-output/implementation-artifacts/16-2-modele-donnees-workflows-branches-et-retry.md] (modèle WorkflowStep)
- [Source: _bmad-output/implementation-artifacts/16-3-moteur-execution-branches-conditionnelles.md] (WorkflowRuntime)
- [Source: _bmad-output/implementation-artifacts/16-4-moteur-retry-backoff-exponentiel.md] (retry config)
- [Source: idp-portal/frontend/src/components/admin/WorkflowStepsEditor.tsx] (implémentation actuelle mode liste)
- [Source: idp-portal/frontend/src/components/admin/ActionWizard.tsx] (intégration Step 2)
- [Source: idp-portal/django_backend/catalog/validation.py] (validation backend à réutiliser)
- [React Flow Documentation](https://reactflow.dev) — Workflow builder tutorials 2026
- [React Flow Drag and Drop](https://reactflow.dev/examples/interaction/drag-and-drop) — Exemple officiel

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

N/A

### Completion Notes List

- Installé `@xyflow/react` (React Flow v12+) — seule nouvelle dépendance
- Créé 4 nouveaux composants : WorkflowBuilderCanvas, WorkflowStepNode, ActionPalette, StepConfigPanel
- Fonctions utilitaires exportées : `workflowStepsToReactFlow()`, `reactFlowToWorkflowSteps()`, `validateWorkflowGraph()`
- Validation graphe : détection cycles (DFS), nœuds orphelins, connexions sortie manquantes — miroir de `catalog/validation.py`
- Toggle Mode liste / Mode visuel intégré dans ActionWizard Step 2 avec `Radio.Group`
- Modal ActionWizard s'élargit dynamiquement (640px → 1100px) en mode visuel
- 28 tests unitaires et d'intégration passent (WorkflowBuilderCanvas.test.tsx)
- 18/23 tests ActionWizard passent (5 échecs pre-existing liés à `checkActionNameAvailable` async validator timing — problème d'infrastructure de test sur la branche develop)
- TypeScript compilation clean (0 erreurs)
- Synchronisation bidirectionnelle WorkflowStep[] ↔ React Flow nodes/edges opérationnelle

### File List

**Nouveaux fichiers :**
- `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.tsx` — Composant principal canvas React Flow avec palette, config panel, validation
- `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.test.tsx` — 28 tests (unit, integration, accessibility)
- `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx` — Custom React Flow node (3 handles: input, success, error)
- `idp-portal/frontend/src/components/admin/ActionPalette.tsx` — Sidebar avec actions draggable et recherche
- `idp-portal/frontend/src/components/admin/StepConfigPanel.tsx` — Drawer Ant Design pour config étape (nom, retry, suppression)

**Fichiers modifiés :**
- `idp-portal/frontend/src/components/admin/ActionWizard.tsx` — Import WorkflowBuilderCanvas, état workflowViewMode, toggle Radio.Group, largeur modal dynamique
- `idp-portal/frontend/src/components/admin/ActionWizard.test.tsx` — Mock `@xyflow/react` ajouté
- `idp-portal/frontend/package.json` — Dépendance `@xyflow/react` ajoutée
- `idp-portal/frontend/package-lock.json` — Lock file mis à jour
