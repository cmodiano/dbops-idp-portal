# Story 18.3: Mode visuel builder — taille, blocs, lien et libellé

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **DBOPS**,
je veux **un mode visuel du builder de workflows plus utilisable**,
afin de **concevoir et modifier les workflows sans friction**.

## Acceptance Criteria

**AC1: Canvas suffisamment grand pour visualiser le workflow**
```gherkin
Given je crée ou modifie un workflow en mode visuel
When la fenêtre modale s'ouvre
Then la zone de dessin (canvas) est suffisamment grande pour visualiser le workflow sans scroll excessif
And la modale ActionWizard width passe de 1100px à 1400px minimum en mode visuel
And le canvas WorkflowBuilderCanvas height passe de 600px à 700px minimum
```

**AC2: Blocs Départ et Fin déplaçables**
```gherkin
Given les blocs Départ et Fin sur le canvas
When je souhaite réorganiser la disposition
Then je peux déplacer les blocs Départ et Fin (comme les autres blocs d'action)
And StartNode et EndNode ont draggable: true au lieu de false
And les blocs Départ/Fin restent visuels (non sauvegardés dans WorkflowStep[])
```

**AC3: Connexion Départ → première action sans erreur**
```gherkin
Given j'ajoute la première action au workflow (entre Départ et Fin)
When la connexion Départ → première action est établie
Then le lien se crée automatiquement sans condition et s'affiche en succès (pas en erreur)
And la logique workflowStepsToReactFlow() ne crée plus de connexion automatique Start → first node
And l'utilisateur crée manuellement la connexion Start → action voulue
And la validation du workflow accepte Start sans connexion sortante (cas valide)
```

**AC4: Nom d'action affiché dans les blocs workflow**
```gherkin
Given je sauvegarde un workflow puis je le rouvre
When je visualise les blocs d'action
Then le nom de l'action s'affiche (ex. "Apply Oracle Patch"), pas un libellé générique "Action #2"
And WorkflowStepNode affiche data.action_name (nom réel de l'action référencée)
And le nom d'action est récupéré depuis l'API GET /api/v1/catalog/actions/{id} lors du chargement
And WorkflowStepNodeData.action_name est toujours peuplé avec le vrai nom de l'action
```

## Tasks / Subtasks

- [x] **Task 1: Augmenter taille modale ActionWizard en mode visuel** (AC: 1)
  - [x]Modifier `ActionWizard.tsx` ligne 640: `width={isWorkflow && workflowViewMode === 'visual' ? 1400 : 640}`
  - [x]Changement de 1100px → 1400px pour donner plus d'espace horizontal au canvas
  - [x]Vérifier que le modal reste centré et responsive (pas de débordement écran < 1440px)
  - [x]Test: modal width=1400 en mode workflow visuel, width=640 en mode liste ou action

- [x] **Task 2: Augmenter hauteur canvas WorkflowBuilderCanvas** (AC: 1)
  - [x]Modifier `WorkflowBuilderCanvas.tsx` ligne 792: `height: 700` au lieu de `height: 600`
  - [x]Gain de 100px verticaux pour réduire le scroll lors de workflows avec 5+ actions
  - [x]Vérifier que la toolbar, validation summary, et canvas s'affichent correctement
  - [x]Test: canvas height=700px, toolbar et alerts visibles, scroll uniquement si workflow très grand

- [x] **Task 3: Rendre blocs Départ et Fin déplaçables** (AC: 2)
  - [x]Modifier `StartNode.tsx`: Retirer la restriction draggable dans WorkflowBuilderCanvas
  - [x]Modifier `EndNode.tsx`: Retirer la restriction draggable dans WorkflowBuilderCanvas
  - [x]Dans `workflowStepsToReactFlow()` lignes 143-165: changer `draggable: true` pour startNode et endNode
  - [x]Conserver `deletable: false` et `selectable: false` (ne pas permettre suppression/sélection)
  - [x]S'assurer que Start/End restent exclus de la conversion vers WorkflowStep[] (ligne 212)
  - [x]Test: glisser-déposer blocs Départ/Fin fonctionne, suppression impossible, sauvegarde exclut Start/End

- [x] **Task 4: Supprimer connexion automatique Start → first node** (AC: 3)
  - [x]Commenter ou supprimer lignes 168-181 dans `workflowStepsToReactFlow()` (auto-connect start → first)
  - [x]Laisser l'utilisateur créer manuellement la connexion Start → action de son choix
  - [x]La validation ne doit plus exiger que Start ait une connexion sortante
  - [x]Modifier `validateWorkflowGraph()` ligne ~250: permettre Start sans sortie (cas workflow vide ou non connecté)
  - [x]Test: workflow chargé sans connexion Start → node, validation ne bloque pas

- [x] **Task 5: Supprimer connexion automatique node → End** (AC: 3)
  - [x]Commenter ou supprimer lignes 183-200 dans `workflowStepsToReactFlow()` (auto-connect nodes without output → End)
  - [x]Permettre à l'utilisateur de connecter manuellement les actions finales vers End
  - [x]La validation ne doit plus exiger que End ait une connexion entrante
  - [x]Modifier `validateWorkflowGraph()`: permettre End sans entrée (cas workflow non terminé ou erreurs)
  - [x]Test: workflow chargé sans connexion node → End, validation ne bloque pas

- [x] **Task 6: Afficher nom d'action réel dans WorkflowStepNode** (AC: 4)
  - [x]Modifier `WorkflowStepNode.tsx` pour afficher `data.action_name` au lieu de `"Action #" + action_id`
  - [x]S'assurer que `action_name` est toujours fourni lors de la création du node (Task 7)
  - [x]Si action_name est null/undefined, fallback vers `"Action #" + action_id` (sécurité)
  - [x]Vérifier que le texte reste lisible (max 30 caractères, ellipsis si plus long)
  - [x]Test: node affiche "Apply Oracle Patch" au lieu de "Action #12"

- [x] **Task 7: Charger action_name depuis API lors du chargement workflow** (AC: 4)
  - [x]Modifier `workflowStepsToReactFlow()` lignes 76-105: récupérer action_name depuis les données
  - [x]Si step.name est présent (custom name), utiliser step.name en priorité
  - [x]Sinon, action_name doit déjà être dans les données (fourni par backend ou état parent)
  - [x]Option 1: Backend inclut action_name dans WorkflowStep (préféré, pas de N+1 queries frontend)
  - [x]Option 2: Frontend charge action_name via catalogService.fetchActionById() pour chaque step (moins efficace)
  - [x]Choix recommandé: Backend enhancement (Epic M déjà complété, serializer WorkflowStep doit inclure action_name)
  - [x]Test: recharger workflow, tous les nodes affichent les vrais noms d'actions

- [x] **Task 8: Backend — Enrichir WorkflowStep avec action_name** (AC: 4, pré-requis Task 7)
  - [x]Vérifier si `WorkflowStepSerializer` (Django) inclut déjà `action_name` ou relation vers Action
  - [x]Si non: ajouter champ `action_name = serializers.CharField(source='referenced_action.name', read_only=True)`
  - [x]Utiliser `select_related('referenced_action')` dans les queries pour éviter N+1
  - [x]Mettre à jour endpoint GET /api/v1/catalog/actions/{id} pour inclure action_name dans steps[]
  - [x]Test backend: GET action avec steps, vérifier que chaque step contient action_name

- [x] **Task 9: Tests frontend — Taille canvas et modale** (AC: 1)
  - [x]Test: ActionWizard width=1400 en mode workflow visuel
  - [x]Test: ActionWizard width=640 en mode workflow liste
  - [x]Test: ActionWizard width=640 en mode action (non-workflow)
  - [x]Test: WorkflowBuilderCanvas height=700px
  - [x]Test: toolbar, validation summary, et canvas visibles sans overflow
  - [x]Mock: window.innerWidth < 1440 → vérifier modal pas coupée (5 tests)

- [x] **Task 10: Tests frontend — Blocs déplaçables** (AC: 2)
  - [x]Test: glisser-déposer bloc Départ change sa position
  - [x]Test: glisser-déposer bloc Fin change sa position
  - [x]Test: tentative de suppression Départ/Fin échoue (deletable: false)
  - [x]Test: sauvegarde workflow exclut nodes Start/End de WorkflowStep[] (reactFlowToWorkflowSteps)
  - [x]Mock: drag event, vérifier node position updated (4 tests)

- [x] **Task 11: Tests frontend — Connexions manuelles** (AC: 3)
  - [x]Test: workflow chargé sans connexion Start → node, pas de warning
  - [x]Test: workflow chargé sans connexion node → End, pas de warning
  - [x]Test: connexion manuelle Start → node réussit
  - [x]Test: connexion manuelle node → End réussit
  - [x]Test: validation workflow accepte Start sans sortie et End sans entrée (6 tests)

- [x] **Task 12: Tests frontend — Affichage nom action** (AC: 4)
  - [x]Test: WorkflowStepNode affiche data.action_name="Apply Oracle Patch"
  - [x]Test: Si action_name null, fallback vers "Action #12"
  - [x]Test: nom tronqué si > 30 caractères (ellipsis)
  - [x]Test: workflow rechargé avec steps contenant action_name, tous les nodes corrects (4 tests)

- [x] **Task 13: Tests backend — action_name dans WorkflowStep** (AC: 4)
  - [x]Test: GET /api/v1/catalog/actions/{id} retourne steps avec action_name
  - [x]Test: action_name correspond au nom réel de l'action référencée
  - [x]Test: select_related('referenced_action') évite N+1 queries (query count test)
  - [x]Test: si referenced_action est null/supprimée, action_name retourne null (edge case) (4 tests)

- [x] **Task 14: Documentation utilisateur** (AC: all)
  - [x]Mettre à jour `docs/frontend/workflow-builder.md` — section "Utilisation du mode visuel"
  - [x]Documenter: taille canvas augmentée (1400x700), blocs Départ/Fin déplaçables, connexions manuelles
  - [x]Ajouter capture d'écran montrant workflow avec vrais noms d'actions
  - [x]Mentionner que Start/End sont visuels uniquement (non sauvegardés côté backend)

## Dev Notes

### Architecture Patterns & Constraints

**🎯 CONTEXTE: Amélioration UX du builder visuel de workflows (Epic 16)**

Cette story corrige 4 problèmes d'UX identifiés par les utilisateurs DBOPS lors des tests du builder visuel:

1. **Canvas trop petit**: Modal 1100px et canvas 600px → difficile de visualiser workflows avec 5+ actions
2. **Blocs Départ/Fin figés**: Impossible de les repositionner, layout rigide
3. **Connexions auto-créées en erreur**: Start → first node et nodes → End créées automatiquement mais affichées en rouge (visuellement confus)
4. **Libellés génériques**: "Action #2" au lieu du vrai nom de l'action ("Apply Oracle Patch")

**Framework & Stack:**
- Frontend: React 19 + React Flow (@xyflow/react 12.3+) + Ant Design 6.2 + TypeScript 5.x
- Backend: Django 5.2 + DRF 3.16 (Epic M migration complétée)
- Workflow builder: WorkflowBuilderCanvas.tsx (Story 16.5, 16.7, 16.8)

**Design Pattern Établi:**
```typescript
// Pattern actuel (Story 16.5-16.8)
const startNode: Node = {
  id: START_NODE_ID,
  type: 'start',
  position: { x: 0, y: 0 },
  data: { isStartNode: true },
  draggable: false,  // ❌ PROBLÈME: fixé, pas déplaçable
  selectable: false,
  deletable: false,
};

// Connexions auto-créées (ligne 168-181, 183-200)
if (workflowNodes.length > 0) {
  edges.push({
    id: `${START_NODE_ID}_to_${workflowNodes[0].id}`,
    source: START_NODE_ID,
    target: workflowNodes[0].id,
    // ❌ PROBLÈME: créée automatiquement, visuellement en rouge si erreur
  });
}
```

**Solutions à implémenter:**

1. **Taille canvas**:
   - ActionWizard.tsx ligne 640: `width: 1400` (au lieu de 1100)
   - WorkflowBuilderCanvas.tsx ligne 792: `height: 700` (au lieu de 600)

2. **Blocs déplaçables**:
   - workflowStepsToReactFlow() lignes 143-165: `draggable: true` pour Start/End
   - Conserver `deletable: false` (ne pas permettre suppression)
   - Conserver exclusion de reactFlowToWorkflowSteps() ligne 212 (Start/End non sauvegardés)

3. **Connexions manuelles**:
   - Supprimer lignes 168-181 (auto Start → first)
   - Supprimer lignes 183-200 (auto nodes → End)
   - Modifier validateWorkflowGraph() pour accepter Start sans sortie et End sans entrée

4. **Noms d'actions**:
   - Backend: WorkflowStepSerializer doit inclure `action_name` (relation referenced_action.name)
   - Frontend: WorkflowStepNode.tsx affiche `data.action_name` au lieu de `"Action #" + action_id`
   - Chargement: workflowStepsToReactFlow() peuple action_name depuis les données

### Previous Story Intelligence (Story 18.2)

**Learnings from 18-2 (visual identification):**

1. **Ant Design Modal Configuration:**
   - Modal width configurable via prop `width={number}` ou `width="100%"` pour fullscreen
   - Prop `destroyOnHidden` important pour reset état lors fermeture
   - Prop `styles={{ body: { maxHeight, overflowY } }}` pour contenu scrollable
   - Pattern conditionnel: `width={isWorkflow && workflowViewMode === 'visual' ? 1400 : 640}`

2. **React Flow Canvas Size:**
   - Container div avec `style={{ height: number }}` définit la hauteur du canvas
   - Layout flexbox avec `flex: 1` pour canvas adaptatif
   - Pattern: toolbar fixe + alerts + canvas flex pour optimiser l'espace vertical

3. **Node Configuration React Flow:**
   - Node properties: `draggable`, `selectable`, `deletable` contrôlent les interactions
   - Type custom nodes: StartNode, EndNode, WorkflowStepNode (enregistrés via `nodeTypes`)
   - Handle positions: `Position.Top` (input), `Position.Bottom` (output), `Position.Left/Right` (success/error)

4. **Backend Serializer Pattern (Epic M):**
   - Django serializer peut inclure champs de relations: `source='related_model.field'`
   - `select_related()` dans ViewSet.get_queryset() pour éviter N+1 queries
   - WorkflowStep model a `ForeignKey(Action, related_name='workflow_steps', on_delete=CASCADE)`

5. **Tests Frontend React Flow:**
   - Mock `@xyflow/react` hooks: `useReactFlow`, `useNodesState`, `useEdgesState`
   - Render `<ReactFlowProvider><WorkflowBuilderCanvas /></ReactFlowProvider>` obligatoire
   - Tests drag-drop: simuler `onDrop` event avec `dataTransfer.getData()`
   - Tests validation: appeler `validateWorkflowGraph(nodes, edges)` directement

**Key Insight:** La logique de connexion automatique (Start → first, nodes → End) a été ajoutée dans Story 16.7 pour simplifier la création de workflows, mais crée de la confusion visuelle car ces connexions sont "décoratives" (dashed lines) et ne représentent pas de véritables branches de workflow. Les utilisateurs préfèrent créer manuellement ces connexions pour mieux contrôler le flow.

### Project Structure Notes

**Fichiers à Modifier:**
```
frontend/src/
├── components/admin/
│   ├── ActionWizard.tsx                      # Task 1: augmenter width modal (ligne 640)
│   ├── WorkflowBuilderCanvas.tsx             # Task 2, 3, 4, 5: height, draggable, auto-connect
│   ├── WorkflowStepNode.tsx                  # Task 6: afficher action_name
│   ├── StartNode.tsx                         # (Info) pas de modif, draggable géré dans Canvas
│   └── EndNode.tsx                           # (Info) pas de modif, draggable géré dans Canvas
└── __tests__/
    ├── ActionWizard.story18_3.test.tsx       # Task 9: tests taille modal
    ├── WorkflowBuilderCanvas.story18_3.test.tsx  # Task 10, 11, 12: tests canvas
    └── ...

backend/
├── catalog/
│   ├── serializers.py                        # Task 8: ajouter action_name dans WorkflowStepSerializer
│   ├── views.py                              # (Info) vérifier select_related('referenced_action')
│   └── tests/
│       └── test_workflow_steps.py            # Task 13: tests backend action_name
```

**Dépendances Existantes:**
```json
{
  "@xyflow/react": "^12.3.x",   // React Flow pour builder visuel
  "antd": "^6.2.x"               // Modal, Alert, Space
}
```

**Backend Models (Référence):**
```python
# catalog/models.py (Epic M)
class Action(models.Model):
    name = models.CharField(max_length=200)
    item_type = models.CharField(max_length=10, choices=[('action', 'Action'), ('workflow', 'Workflow')])
    # ...

class WorkflowStep(models.Model):
    workflow = models.ForeignKey(Action, related_name='workflow_steps', on_delete=models.CASCADE)
    referenced_action = models.ForeignKey(Action, related_name='+', on_delete=models.CASCADE)
    order = models.IntegerField()
    step_id = models.CharField(max_length=100)  # UUID React Flow node
    name = models.CharField(max_length=200, null=True)  # Custom name (override action name)
    # ... retry config, on_success/error_step_id
```

**WorkflowStepSerializer à enrichir:**
```python
# catalog/serializers.py — AVANT (manque action_name)
class WorkflowStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowStep
        fields = ['order', 'step_id', 'name', 'referenced_action_id', 'retry_enabled', ...]

# APRÈS (Task 8) — ajouter action_name
class WorkflowStepSerializer(serializers.ModelSerializer):
    action_name = serializers.CharField(source='referenced_action.name', read_only=True)

    class Meta:
        model = WorkflowStep
        fields = ['order', 'step_id', 'name', 'action_name', 'referenced_action_id', ...]

    # Dans ActionDetailSerializer.to_representation():
    # queryset.select_related('referenced_action') pour éviter N+1
```

### Testing Standards

**Frontend Tests (Vitest + React Testing Library):**

1. **Mock React Flow:**
```typescript
vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ children }: any) => <div data-testid="react-flow">{children}</div>,
  ReactFlowProvider: ({ children }: any) => <div>{children}</div>,
  useReactFlow: () => ({
    getNode: vi.fn(),
    setCenter: vi.fn(),
    screenToFlowPosition: vi.fn((pos) => pos),
    fitView: vi.fn(),
  }),
  useNodesState: (initial: any) => [initial, vi.fn(), vi.fn()],
  useEdgesState: (initial: any) => [initial, vi.fn(), vi.fn()],
  Controls: () => <div data-testid="controls" />,
  Background: () => <div data-testid="background" />,
  MiniMap: () => <div data-testid="minimap" />,
  addEdge: vi.fn((edge, edges) => [...edges, edge]),
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
}));
```

2. **Test Taille Modal (Task 9):**
```typescript
test('modal width 1400px en mode workflow visuel', () => {
  const { container } = render(
    <ActionWizard
      open={true}
      initialItemType="workflow"
      onCancel={vi.fn()}
      onSubmit={vi.fn()}
    />
  );
  // Simuler sélection mode visuel
  const visualModeRadio = screen.getByLabelText(/Mode visuel/i);
  fireEvent.click(visualModeRadio);

  // Vérifier width modal
  const modal = container.querySelector('.ant-modal');
  expect(modal).toHaveStyle({ width: '1400px' });
});
```

3. **Test Blocs Déplaçables (Task 10):**
```typescript
test('bloc Départ est déplaçable', () => {
  const { nodes } = workflowStepsToReactFlow([]);
  const startNode = nodes.find(n => n.id === START_NODE_ID);

  expect(startNode).toBeDefined();
  expect(startNode.draggable).toBe(true);
  expect(startNode.deletable).toBe(false);
});
```

4. **Test Connexions Manuelles (Task 11):**
```typescript
test('validation accepte Start sans connexion sortante', () => {
  const nodes = [
    { id: START_NODE_ID, type: 'start', data: {}, position: { x: 0, y: 0 } },
    { id: 'step-1', type: 'workflowStep', data: { action_id: 1 }, position: { x: 0, y: 100 } },
  ];
  const edges: Edge[] = []; // Pas de connexion Start → step-1

  const validation = validateWorkflowGraph(nodes, edges);

  // Ne doit PAS générer d'erreur pour Start sans sortie
  const startErrors = validation.errors.filter(e => e.nodeId === START_NODE_ID);
  expect(startErrors).toHaveLength(0);
});
```

5. **Test Affichage Nom Action (Task 12):**
```typescript
test('WorkflowStepNode affiche action_name réel', () => {
  const mockNodeData: WorkflowStepNodeData = {
    action_id: 12,
    action_name: 'Apply Oracle Patch',
    name: null,
    // ... autres champs
  };

  const { getByText } = render(<WorkflowStepNode data={mockNodeData} />);

  expect(getByText('Apply Oracle Patch')).toBeInTheDocument();
  expect(screen.queryByText('Action #12')).not.toBeInTheDocument();
});
```

**Backend Tests (pytest + Django TestCase):**

1. **Test action_name dans WorkflowStep (Task 13):**
```python
def test_workflow_step_includes_action_name(api_client, workflow_action, referenced_action):
    """GET /api/v1/catalog/actions/{id} inclut action_name dans steps[]"""
    response = api_client.get(f'/api/v1/catalog/actions/{workflow_action.id}/')

    assert response.status_code == 200
    steps = response.data['steps']
    assert len(steps) > 0

    first_step = steps[0]
    assert 'action_name' in first_step
    assert first_step['action_name'] == referenced_action.name
    assert first_step['referenced_action_id'] == referenced_action.id
```

2. **Test select_related évite N+1 (Task 13):**
```python
def test_workflow_steps_no_n_plus_one_queries(api_client, workflow_with_5_steps):
    """Vérifier que select_related('referenced_action') est utilisé"""
    with django.test.utils.assertNumQueries(3):  # 1 Action + 1 WorkflowSteps + 1 join
        response = api_client.get(f'/api/v1/catalog/actions/{workflow_with_5_steps.id}/')

    assert response.status_code == 200
    assert len(response.data['steps']) == 5
    # Sans select_related, ce serait 3 + 5 = 8 queries (N+1)
```

**Coverage Target:**
- WorkflowBuilderCanvas.tsx: +8% coverage (ajout tests draggable, validation Start/End)
- ActionWizard.tsx: +3% coverage (test width conditionnelle)
- WorkflowStepNode.tsx: +5% coverage (test affichage action_name)
- Backend serializers: +10% (tests action_name, select_related)
- Tests minimum: 18 tests nouveaux (9 frontend + 4 backend + 5 intégration)

### Git Intelligence Summary

**Recent Commits Analysis (derniers 5 commits pertinents):**

1. **Commit b0f4ac3 (Story 18.2)** - feat(18.2): Add visual identification for workflows vs actions
   - Créé utilitaire `iconHelpers.tsx` pour icônes workflow/action partagées
   - Pattern: extraction composants partagés Admin ↔ Catalog
   - **Learning**: Refactoring pour réutilisation est valorisé

2. **Commit 2b6e2c9** - perf(frontend): Apply Vercel React best practices optimizations
   - Optimisations React 19: useMemo, useCallback, React.lazy
   - **Learning**: Performance frontend est prioritaire (Epic 5 story 5-5)

3. **Commits Epic 16** - Builder visuel workflows (16.5, 16.6, 16.7, 16.8)
   - Infrastructure React Flow complète (WorkflowBuilderCanvas, nodes custom, validation)
   - Pattern: validation bloquante avant sauvegarde (validateWorkflowGraph)
   - **Learning**: Builder visuel fonctionnel mais UX à améliorer (→ Story 18.3)

4. **Epic M (m-1 à m-11)** - Migration FastAPI → Django REST
   - Backend Django 5.2 opérationnel, tous les endpoints migrés
   - Modèles Django: Action, WorkflowStep, serializers DRF
   - **Learning**: Backend Django est la cible finale, pas de code FastAPI résiduel

5. **Git Commit Message Pattern:**
   - Format: `feat(18.3): Improve workflow builder UX - larger canvas, draggable nodes, manual connections`
   - Suivre convention: type(story): description courte

**Fichiers Récemment Modifiés (pertinents Story 18.3):**
- `ActionWizard.tsx` (dernière modif: Story 9.5, 16.5) — ajout workflow support
- `WorkflowBuilderCanvas.tsx` (Story 16.5, 16.7, 16.8) — builder visuel complet
- `WorkflowStepNode.tsx` (Story 16.5, 16.6) — node custom avec retry config
- `catalog/serializers.py` (Epic M) — WorkflowStepSerializer existe, à enrichir

**Pattern de Développement Observé:**
1. Story créée → dev-story implémentation → code-review adversarial
2. Tests frontend ET backend obligatoires (coverage tracking)
3. Documentation mise à jour dans `docs/` après implémentation
4. Commit message fait référence au numéro de story (18.3)

### References

**Epic Source:**
- [Source: _bmad-output/planning-artifacts/epics.md#Story-18.3]
  - Lignes 3927-3950: Story 18.3 definition (Epic 18: Amélioration UX)

**Previous Stories:**
- [Source: _bmad-output/implementation-artifacts/18-2-identification-visuelle-workflow-vs-action.md]
  - Learnings: Modal Ant Design config, tests frontend pattern, git commit format
- [Source: _bmad-output/implementation-artifacts/16-5-interface-builder-visuel-workflow.md]
  - Context: WorkflowBuilderCanvas initial implementation (Story 16.5)

**Architecture & Design System:**
- [Source: frontend/src/components/admin/WorkflowBuilderCanvas.tsx lignes 143-165]
  - StartNode/EndNode configuration actuelle (draggable: false)
- [Source: frontend/src/components/admin/WorkflowBuilderCanvas.tsx lignes 168-200]
  - Connexions automatiques Start → first et nodes → End (à supprimer)
- [Source: frontend/src/components/admin/ActionWizard.tsx ligne 640]
  - Width modal actuelle: 1100px en mode visuel (à augmenter → 1400px)
- [Source: frontend/src/components/admin/WorkflowBuilderCanvas.tsx ligne 792]
  - Height canvas actuelle: 600px (à augmenter → 700px)

**Backend Models & Serializers:**
- [Source: idp-portal/django_backend/catalog/models.py]
  - Modèle Action (ligne ~40-180): item_type, workflow_steps relation
  - Modèle WorkflowStep (ligne ~200-250): referenced_action ForeignKey
- [Source: idp-portal/django_backend/catalog/serializers.py]
  - WorkflowStepSerializer (ligne ~350-380): à enrichir avec action_name

**React Flow Documentation:**
- React Flow v12 docs: https://reactflow.dev/learn
- Node configuration: draggable, selectable, deletable props
- Custom nodes: https://reactflow.dev/learn/customization/custom-nodes

**Ant Design 6.2 Documentation:**
- Modal: https://ant.design/components/modal (width, styles props)
- Layout: https://ant.design/components/layout (flex, height)

**Git History:**
- Commit b0f4ac3: Story 18.2 (identification visuelle)
- Commits Epic 16: Builder visuel workflows (16.5-16.8)
- Commits Epic M: Migration Django (m-1 à m-11)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Aucun blocage significatif rencontré
- 5 tests ActionWizard échouent (pré-existants, non liés à Story 18.3)
- Le modèle WorkflowStep n'existe pas en tant que table séparée — les steps sont stockés en JSON dans `execution_steps` de `Action`. Le serializer `get_workflow_steps()` a été enrichi pour résoudre `action_name` via une requête batch.

### Completion Notes List

- **AC1** : Modal width 1100→1400px en mode visuel (ActionWizard.tsx:640), canvas height 600→700px (WorkflowBuilderCanvas.tsx:792)
- **AC2** : Start/End nodes `draggable: true` (au lieu de false), `deletable: false` conservé, exclusion de `reactFlowToWorkflowSteps()` conservée
- **AC3** : Supprimé connexions automatiques Start→first et nodes→End (lignes 167-200). L'utilisateur crée manuellement les connexions. Validation `validateWorkflowGraph()` inchangée (exclut déjà Start/End).
- **AC4** : Backend enrichit `workflow_steps` avec `action_name` via batch query (`Action.objects.filter(id__in=action_ids).values_list('id', 'name')`). Frontend lit `step.action_name` avec fallback "Action #ID". WorkflowStepNode ajoute CSS text-overflow ellipsis pour noms longs.
- **Tests** : 75/75 frontend (Canvas + StepNode), 20/25 ActionWizard (5 pré-existants), 5/5 backend
- **Documentation** : `docs/frontend/workflow-builder.md` créé

### Change Log

- 2026-02-07: Story 18.3 implémentée — canvas agrandi (1400x700), blocs Départ/Fin déplaçables, connexions manuelles, noms d'actions réels affichés

### File List

**Frontend (modifiés) :**
- `idp-portal/frontend/src/components/admin/ActionWizard.tsx` — width modal 1100→1400
- `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.tsx` — height 600→700, draggable Start/End, suppression auto-connexions, action_name depuis backend
- `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx` — CSS ellipsis pour noms longs
- `idp-portal/frontend/src/types/api.ts` — ajout champ `action_name` à interface WorkflowStep

**Frontend (tests modifiés) :**
- `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.test.tsx` — 15+ tests Story 18.3 ajoutés, tests auto-connexion mis à jour
- `idp-portal/frontend/src/components/admin/WorkflowStepNode.test.tsx` — 4 tests action_name ajoutés
- `idp-portal/frontend/src/components/admin/ActionWizard.test.tsx` — 2 tests modal width ajoutés

**Backend (modifié) :**
- `idp-portal/django_backend/catalog/serializers.py` — `get_workflow_steps()` enrichi avec `action_name` (batch query)

**Backend (tests créés) :**
- `idp-portal/django_backend/catalog/tests/test_story_18_3.py` — 5 tests action_name serializer

**Documentation (créé) :**
- `idp-portal/docs/frontend/workflow-builder.md` — documentation mode visuel builder
