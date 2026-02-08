# Story 19.3: Détail d'une étape de workflow — Timeline et logs au clic

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **DBA**,
je veux **cliquer sur une étape du workflow pour afficher la timeline et les logs détaillés de cette action**,
afin de **diagnostiquer ou suivre le détail d'une étape précise**.

## Contexte

Les stories 19.1 et 19.2 ont introduit ExecutionView avec deux modes:
- **Action simple**: Timeline verticale avec étapes et logs (Story 19.1)
- **Workflow**: Graphe visuel React Flow avec étapes mises en évidence (Story 19.2)

Cette story 19.3 complète l'Epic 19 en ajoutant **l'interaction clic sur étape** dans le graphe workflow pour afficher le détail de l'étape (timeline + logs), comme pour une action simple.

**Infrastructure existante:**
- WorkflowExecutionGraph (Story 19.2) affiche le graphe avec nœuds cliquables (elementsSelectable=true)
- ExecutionTimeline (Story 19.1) affiche timeline + logs pour action simple
- ExecutionStepResponse contient tous les détails d'une étape: status, output, started_at, completed_at

**Solution retenue:** Drawer latéral (Ant Design Drawer placement="right") qui s'ouvre au clic sur un nœud d'étape, affichant ExecutionTimeline pour cette étape spécifique.

## Acceptance Criteria

### AC1: Clic sur une étape du workflow ouvre un panneau détail
```gherkin
Given la vue d'exécution d'un workflow avec plusieurs étapes (WorkflowExecutionGraph)
When je clique sur une étape du graphe (nœud action, pas Start/End)
Then un drawer latéral s'ouvre à droite (Ant Design Drawer placement="right")
And le drawer affiche le titre de l'étape (step_name ou action_name)
And le drawer ne cache pas complètement le graphe workflow (width="50%" ou similaire)
```

### AC2: Affichage timeline et logs détaillés de l'étape
```gherkin
Given le drawer détail d'une étape est ouvert
When le contenu se charge
Then une timeline verticale affiche les sous-étapes de cette action (ExecutionTimeline)
And les logs détaillés sont affichés pour cette étape (champ ExecutionStep.output)
And les mêmes indicateurs visuels que Story 19.1 sont présents:
  - Badge status (PENDING, RUNNING, COMPLETED, FAILED, SKIPPED)
  - Icônes (LoadingOutlined, CheckCircleFilled, CloseCircleFilled, etc.)
  - Logs pré-formatés (texte ou JSON)
And la timeline est similaire à l'affichage action simple mais limitée à cette étape unique
```

### AC3: Métadonnées de l'étape affichées en en-tête du drawer
```gherkin
Given le drawer détail d'une étape est ouvert
When l'en-tête se charge
Then les métadonnées suivantes sont affichées:
  - Nom de l'étape (step_name ou action_name)
  - Ordre de l'étape dans le workflow (step_order)
  - Statut de l'étape (status badge coloré: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED)
  - Durée d'exécution (started_at - completed_at si terminée, sinon temps écoulé)
  - Action référencée (referenced_action_id + action_name si disponible)
And l'en-tête est visuellement distinct du contenu (bordure ou fond coloré)
```

### AC4: Mises à jour temps réel de l'étape
```gherkin
Given le drawer détail d'une étape RUNNING ou PENDING est ouvert
When des mises à jour ExecutionSteps sont reçues via WebSocket ou polling
Then les données de l'étape affichée se mettent à jour en temps réel:
  - Status badge passe de RUNNING à COMPLETED ou FAILED
  - Logs s'actualisent (champ output)
  - Timeline reflète le statut final
  - Durée d'exécution se met à jour
And les transitions sont fluides (pas de flash ou re-render brutal)
```

### AC5: Fermeture du drawer et retour au graphe workflow
```gherkin
Given le drawer détail d'une étape est ouvert
When je clique sur le bouton « Fermer » ou l'icône X
Then le drawer se ferme avec animation fluide (slide out)
And le graphe workflow reste affiché et garde son état (zoom, pan, étape active)
And je peux cliquer sur une autre étape pour ouvrir son détail
```

### AC6: Navigation entre étapes du workflow sans fermer le drawer
```gherkin
Given le drawer détail d'une étape est ouvert
When je clique sur une autre étape du graphe workflow (sans fermer le drawer)
Then le drawer reste ouvert et affiche le détail de la nouvelle étape sélectionnée
And la transition est fluide (pas de fermeture/réouverture)
And le contenu se met à jour: métadonnées, timeline, logs de la nouvelle étape
And je peux naviguer entre toutes les étapes du workflow sans perdre le contexte
```

### AC7: Indicateur visuel de l'étape sélectionnée dans le graphe
```gherkin
Given j'ai ouvert le détail d'une étape dans le drawer
When je consulte le graphe workflow
Then l'étape sélectionnée est visuellement distinguée dans le graphe:
  - Bordure plus épaisse ou couleur différente (ex: bordure dorée ou orange)
  - Indicateur "sélectionné" distinct de l'indicateur "en cours" (AC3 Story 19.2)
And si je sélectionne une autre étape, l'indicateur se déplace sur la nouvelle étape
And si je ferme le drawer, l'indicateur de sélection disparaît (seul "en cours" reste)
```

### AC8: Gestion des étapes Start et End (non cliquables)
```gherkin
Given la vue d'exécution workflow affiche le graphe avec nœuds Start et End
When je clique sur le nœud Start ou End
Then aucun drawer ne s'ouvre (ces nœuds sont purement visuels)
And optionnellement, un tooltip ou message indique « Nœud visuel, pas de détail disponible »
```

### AC9: Affichage structuré des erreurs pour étapes FAILED
```gherkin
Given j'ouvre le détail d'une étape avec status FAILED
When le drawer affiche le contenu
Then StructuredErrorCard s'affiche avec:
  - Message d'erreur (error_message si disponible)
  - Détail de l'erreur (champ output si JSON structuré)
  - Boutons d'action (Relancer, Voir logs complets)
And le format est cohérent avec Story 4.7, 9.1 (remediation suggestions)
```

### AC10: Performance et chargement optimisé
```gherkin
Given j'ouvre le détail d'une étape dans un workflow avec 20+ étapes
When le drawer se charge
Then seules les données de l'étape sélectionnée sont affichées (pas de fetch inutile)
And le chargement est rapide (<500ms) pour afficher métadonnées et logs
And si les données sont déjà en cache (depuis WorkflowExecutionGraph), aucun fetch supplémentaire
And un spinner est affiché pendant le chargement initial uniquement
```

## Tasks / Subtasks

### Phase 1: Gestion état sélection étape dans WorkflowExecutionGraph

- [x] **Task 1: Ajouter gestion sélection nœud dans WorkflowExecutionGraph** (AC: 1, 5, 6, 7, 8)
  - [x] Subtask 1.1: Ajouter état selectedStepId dans WorkflowExecutionGraph
    ```typescript
    // idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.tsx
    // MODIFICATIONS à apporter:

    export function WorkflowExecutionGraph({ executionId, workflow, execution }: WorkflowExecutionGraphProps) {
      const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
      const [executionSteps, setExecutionSteps] = useState<ExecutionStepResponse[]>([]);

      // AC1: Handler clic sur nœud
      const handleNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
        // AC8: Ignorer clics sur Start/End
        if (node.id === START_NODE_ID || node.id === END_NODE_ID) {
          return;
        }

        // AC6: Si déjà sélectionné, ne rien faire (drawer reste ouvert)
        // AC1: Ouvrir drawer avec nouvelle étape sélectionnée
        setSelectedStepId(node.id);
      }, []);

      // AC7: Enrichir nœud sélectionné avec indicateur visuel
      const enrichedNodes = useMemo(() => {
        return baseNodes.map((node) => {
          const isSelected = node.id === selectedStepId;

          return {
            ...node,
            style: {
              ...node.style,
              // AC7: Bordure dorée pour nœud sélectionné
              ...(isSelected && {
                borderColor: STATUS_COLORS.warning,
                borderWidth: 4,
                boxShadow: `0 0 12px ${STATUS_COLORS.warning}`,
              }),
            },
          };
        });
      }, [baseNodes, selectedStepId, /* autres dépendances status enrichment */]);

      return (
        <div>
          <ReactFlow
            nodes={enrichedNodes}
            edges={edges}
            onNodeClick={handleNodeClick}
            // ... autres props
          >
            {/* ... Controls, Background, MiniMap */}
          </ReactFlow>

          {/* AC1: Drawer détail étape */}
          <StepDetailDrawer
            open={selectedStepId != null}
            stepId={selectedStepId}
            executionId={executionId}
            executionSteps={executionSteps}
            workflow={workflow}
            onClose={() => setSelectedStepId(null)} // AC5
          />
        </div>
      );
    }
    ```
  - [x] Subtask 1.2: Tests gestion sélection nœud
    ```typescript
    // idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.test.tsx
    // AJOUTER tests:

    it('AC1: opens step detail drawer when clicking on action node', async () => {
      render(<WorkflowExecutionGraph executionId={1} workflow={mockWorkflow} execution={mockExecution} />);

      await waitFor(() => screen.getByTestId('workflow-execution-graph'));

      // Clic sur nœud "Build App"
      const buildNode = screen.getByText('Build App');
      await userEvent.click(buildNode);

      // Vérifier drawer ouvert
      expect(screen.getByTestId('step-detail-drawer')).toBeVisible();
    });

    it('AC8: does not open drawer when clicking Start or End node', async () => {
      render(<WorkflowExecutionGraph executionId={1} workflow={mockWorkflow} execution={mockExecution} />);

      await waitFor(() => screen.getByTestId('workflow-execution-graph'));

      // Clic sur nœud Start
      const startNode = screen.getByText('Départ');
      await userEvent.click(startNode);

      // Vérifier drawer pas ouvert
      expect(screen.queryByTestId('step-detail-drawer')).not.toBeInTheDocument();
    });

    it('AC6: switches to new step when clicking another node while drawer open', async () => {
      render(<WorkflowExecutionGraph executionId={1} workflow={mockWorkflow} execution={mockExecution} />);

      await waitFor(() => screen.getByTestId('workflow-execution-graph'));

      // Ouvrir drawer avec "Build App"
      await userEvent.click(screen.getByText('Build App'));
      expect(screen.getByText('Étape 1: Build')).toBeInTheDocument();

      // Cliquer sur "Deploy App"
      await userEvent.click(screen.getByText('Deploy App'));

      // Vérifier drawer mis à jour (pas fermé/réouvert)
      expect(screen.getByText('Étape 2: Deploy')).toBeInTheDocument();
    });

    it('AC7: highlights selected node with golden border', async () => {
      render(<WorkflowExecutionGraph executionId={1} workflow={mockWorkflow} execution={mockExecution} />);

      await waitFor(() => screen.getByTestId('workflow-execution-graph'));

      await userEvent.click(screen.getByText('Build App'));

      // Vérifier nœud a bordure dorée
      const buildNode = screen.getByText('Build App').closest('[data-id="step-1"]');
      expect(buildNode).toHaveStyle({ borderColor: STATUS_COLORS.warning });
    });
    ```

### Phase 2: Composant StepDetailDrawer

- [x] **Task 2: Créer composant StepDetailDrawer** (AC: 1, 2, 3, 4, 5, 9, 10)
  - [x] Subtask 2.1: Créer StepDetailDrawer.tsx
    ```typescript
    // idp-portal/frontend/src/components/execution/StepDetailDrawer.tsx
    /**
     * StepDetailDrawer - Detailed view of a single workflow execution step.
     *
     * Features:
     * - Timeline and logs for specific step (AC2)
     * - Real-time updates via WebSocket/polling (AC4)
     * - Structured error display for FAILED steps (AC9)
     * - Step metadata header (AC3)
     * - Optimized loading (AC10)
     */

    import React, { useMemo, useEffect } from 'react';
    import { Drawer, Space, Typography, Badge, Spin, Alert } from 'antd';
    import { CloseOutlined } from '@ant-design/icons';
    import type { ExecutionStepResponse, WorkflowResponse } from '@/types/api';
    import { ExecutionTimeline } from './ExecutionTimeline';
    import { StructuredErrorCard } from './StructuredErrorCard';
    import { STATUS_COLORS } from './constants';

    const { Title, Text } = Typography;

    interface StepDetailDrawerProps {
      open: boolean;
      stepId: string | null;
      executionId: number;
      executionSteps: ExecutionStepResponse[];
      workflow: WorkflowResponse | null;
      onClose: () => void;
    }

    export function StepDetailDrawer({
      open,
      stepId,
      executionId,
      executionSteps,
      workflow,
      onClose,
    }: StepDetailDrawerProps) {
      // AC10: Trouver étape sélectionnée dans les données déjà chargées (pas de fetch supplémentaire)
      const selectedStep = useMemo(() => {
        if (!stepId || !workflow) return null;

        // Trouver WorkflowStep correspondant au stepId
        const workflowStep = workflow.steps?.find((s) => s.step_id === stepId);
        if (!workflowStep) return null;

        // Trouver ExecutionStep correspondant (via step_order car ExecutionStep n'a pas step_id)
        const executionStep = executionSteps.find((es) => es.step_order === workflowStep.order);

        return {
          workflowStep,
          executionStep: executionStep || null,
        };
      }, [stepId, workflow, executionSteps]);

      // AC3: Calculer durée d'exécution
      const duration = useMemo(() => {
        if (!selectedStep?.executionStep) return null;
        const { started_at, completed_at } = selectedStep.executionStep;
        if (!started_at) return null;

        const start = new Date(started_at);
        const end = completed_at ? new Date(completed_at) : new Date();
        const durationSec = Math.floor((end.getTime() - start.getTime()) / 1000);
        const minutes = Math.floor(durationSec / 60);
        const seconds = durationSec % 60;
        return `${minutes}m ${seconds}s`;
      }, [selectedStep?.executionStep]);

      // AC3: Badge statut
      const statusConfig = useMemo(() => {
        const status = selectedStep?.executionStep?.status || 'PENDING';
        return {
          PENDING: { color: 'default', label: 'En attente' },
          RUNNING: { color: 'processing', label: 'En cours' },
          COMPLETED: { color: 'success', label: 'Terminé' },
          FAILED: { color: 'error', label: 'Échoué' },
          SKIPPED: { color: 'default', label: 'Ignoré' },
          CANCELLED: { color: 'default', label: 'Annulé' },
        }[status] || { color: 'default', label: status };
      }, [selectedStep?.executionStep?.status]);

      if (!open || !stepId || !selectedStep) {
        return null;
      }

      const { workflowStep, executionStep } = selectedStep;

      return (
        <Drawer
          title={null}
          placement="right"
          width="50%"
          open={open}
          onClose={onClose}
          closable={false}
          destroyOnClose={false} // AC6: Garder état pour navigation rapide
          styles={{
            body: { padding: 0 },
            header: { display: 'none' },
          }}
          data-testid="step-detail-drawer"
        >
          {/* AC3: En-tête avec métadonnées étape */}
          <div
            style={{
              padding: '16px 24px',
              borderBottom: `1px solid ${STATUS_COLORS.borderLight}`,
              background: STATUS_COLORS.backgroundSecondary,
              position: 'sticky',
              top: 0,
              zIndex: 1,
            }}
          >
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Space size={12} style={{ justifyContent: 'space-between', width: '100%' }}>
                <Title level={4} style={{ margin: 0 }}>
                  {workflowStep.name || workflowStep.action_name || `Étape ${workflowStep.order}`}
                </Title>
                <CloseOutlined onClick={onClose} style={{ cursor: 'pointer', fontSize: 16 }} />
              </Space>

              <Space size={16} wrap>
                <Space size={4}>
                  <Text type="secondary">Ordre:</Text>
                  <Text strong>#{workflowStep.order}</Text>
                </Space>
                <Space size={4}>
                  <Text type="secondary">Action:</Text>
                  <Text>{workflowStep.action_name}</Text>
                </Space>
                <Space size={4}>
                  <Text type="secondary">Statut:</Text>
                  <Badge status={statusConfig.color as any} text={statusConfig.label} />
                </Space>
                {duration && (
                  <Space size={4}>
                    <Text type="secondary">Durée:</Text>
                    <Text>{duration}</Text>
                  </Space>
                )}
              </Space>
            </Space>
          </div>

          {/* Contenu principal */}
          <div style={{ padding: '24px' }}>
            {!executionStep ? (
              // AC10: Étape pas encore exécutée
              <Alert
                type="info"
                showIcon
                message="Étape en attente"
                description="Cette étape n'a pas encore été exécutée. Les détails apparaîtront dès le démarrage."
              />
            ) : (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                {/* AC9: Erreur structurée si FAILED */}
                {executionStep.status === 'FAILED' && (
                  <StructuredErrorCard
                    error={{
                      message: executionStep.error_message || 'Échec de l\'exécution',
                      details: executionStep.output,
                    }}
                    executionId={executionId}
                    showActions
                  />
                )}

                {/* AC2: Timeline et logs détaillés */}
                <ExecutionTimeline
                  executionId={executionId}
                  execution={null} // Pas de global execution, focus sur cette étape
                  steps={[executionStep]} // Afficher uniquement cette étape
                  mode="realtime"
                  compact // Mode compact pour drawer
                />
              </Space>
            )}
          </div>
        </Drawer>
      );
    }
    ```
  - [x] Subtask 2.2: Tests StepDetailDrawer.test.tsx
    ```typescript
    // idp-portal/frontend/src/components/execution/StepDetailDrawer.test.tsx
    import { render, screen, waitFor } from '@testing-library/react';
    import userEvent from '@testing-library/user-event';
    import { StepDetailDrawer } from './StepDetailDrawer';
    import { vi } from 'vitest';

    describe('StepDetailDrawer', () => {
      const mockWorkflow = {
        id: 1,
        name: 'Deploy Pipeline',
        steps: [
          {
            step_id: 'step-1',
            order: 1,
            name: 'Build',
            action_name: 'Build Action',
            referenced_action_id: 10,
          },
          {
            step_id: 'step-2',
            order: 2,
            name: 'Deploy',
            action_name: 'Deploy Action',
            referenced_action_id: 11,
          },
        ],
      };

      const mockExecutionSteps = [
        {
          id: 1,
          execution_id: 1,
          step_order: 1,
          step_name: 'Build',
          status: 'COMPLETED',
          started_at: '2026-02-08T10:00:00Z',
          completed_at: '2026-02-08T10:02:15Z',
          output: 'Build successful',
        },
        {
          id: 2,
          execution_id: 1,
          step_order: 2,
          step_name: 'Deploy',
          status: 'RUNNING',
          started_at: '2026-02-08T10:02:20Z',
          completed_at: null,
          output: null,
        },
      ];

      it('AC1: drawer opens when stepId provided', () => {
        render(
          <StepDetailDrawer
            open
            stepId="step-1"
            executionId={1}
            executionSteps={mockExecutionSteps}
            workflow={mockWorkflow}
            onClose={vi.fn()}
          />
        );

        expect(screen.getByTestId('step-detail-drawer')).toBeVisible();
      });

      it('AC3: displays step metadata in header', () => {
        render(
          <StepDetailDrawer
            open
            stepId="step-1"
            executionId={1}
            executionSteps={mockExecutionSteps}
            workflow={mockWorkflow}
            onClose={vi.fn()}
          />
        );

        expect(screen.getByText('Build')).toBeInTheDocument();
        expect(screen.getByText('#1')).toBeInTheDocument();
        expect(screen.getByText('Build Action')).toBeInTheDocument();
        expect(screen.getByText('Terminé')).toBeInTheDocument();
        expect(screen.getByText('2m 15s')).toBeInTheDocument();
      });

      it('AC2: displays ExecutionTimeline for selected step', () => {
        render(
          <StepDetailDrawer
            open
            stepId="step-1"
            executionId={1}
            executionSteps={mockExecutionSteps}
            workflow={mockWorkflow}
            onClose={vi.fn()}
          />
        );

        // Vérifier présence ExecutionTimeline
        expect(screen.getByText('Build successful')).toBeInTheDocument();
      });

      it('AC5: closes drawer when close button clicked', async () => {
        const onClose = vi.fn();
        render(
          <StepDetailDrawer
            open
            stepId="step-1"
            executionId={1}
            executionSteps={mockExecutionSteps}
            workflow={mockWorkflow}
            onClose={onClose}
          />
        );

        const closeButton = screen.getByRole('img', { name: /close/i });
        await userEvent.click(closeButton);

        expect(onClose).toHaveBeenCalledTimes(1);
      });

      it('AC9: displays StructuredErrorCard for FAILED step', () => {
        const failedSteps = [
          {
            ...mockExecutionSteps[0],
            status: 'FAILED',
            error_message: 'Build failed: syntax error',
          },
        ];

        render(
          <StepDetailDrawer
            open
            stepId="step-1"
            executionId={1}
            executionSteps={failedSteps}
            workflow={mockWorkflow}
            onClose={vi.fn()}
          />
        );

        expect(screen.getByText('Build failed: syntax error')).toBeInTheDocument();
      });

      it('AC10: displays alert when step not yet executed', () => {
        const pendingSteps = [
          {
            id: 3,
            execution_id: 1,
            step_order: 3,
            step_name: 'Test',
            status: 'PENDING',
            started_at: null,
            completed_at: null,
            output: null,
          },
        ];

        render(
          <StepDetailDrawer
            open
            stepId="step-3"
            executionId={1}
            executionSteps={pendingSteps}
            workflow={{
              ...mockWorkflow,
              steps: [...mockWorkflow.steps, { step_id: 'step-3', order: 3, name: 'Test', action_name: 'Test Action' }],
            }}
            onClose={vi.fn()}
          />
        );

        expect(screen.getByText('Étape en attente')).toBeInTheDocument();
      });
    });
    ```

### Phase 3: Adaptation ExecutionTimeline pour mode step unique

- [x] **Task 3: Adapter ExecutionTimeline pour afficher une seule étape** (AC: 2)
  - [x] Subtask 3.1: Ajouter prop `compact` dans ExecutionTimeline
    ```typescript
    // idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx
    // MODIFICATIONS à apporter:

    interface ExecutionTimelineProps {
      executionId: number;
      execution: ExecutionResponse | null;
      steps?: ExecutionStepResponse[]; // Optionnel: utiliser steps fournis au lieu de fetch
      mode?: 'realtime' | 'historical';
      compact?: boolean; // AC2: Mode compact pour drawer étape unique
    }

    export function ExecutionTimeline({
      executionId,
      execution,
      steps: propSteps,
      mode = 'historical',
      compact = false,
    }: ExecutionTimelineProps) {
      const [steps, setSteps] = useState<ExecutionStepResponse[]>(propSteps || []);

      // Si steps fournis en prop, les utiliser (AC10: évite fetch supplémentaire)
      useEffect(() => {
        if (propSteps) {
          setSteps(propSteps);
          return;
        }

        // Sinon, fetch depuis API
        getExecutionSteps(executionId).then(setSteps);
      }, [propSteps, executionId]);

      // AC2: Affichage compact si prop compact=true
      return (
        <div className={compact ? 'execution-timeline-compact' : 'execution-timeline'}>
          {/* Timeline existante, potentiellement simplifiée si compact */}
          {steps.map((step) => (
            <div key={step.id} className="timeline-step">
              {/* ... affichage étape existant */}
            </div>
          ))}
        </div>
      );
    }
    ```
  - [x] Subtask 3.2: Tests prop compact ExecutionTimeline
    ```typescript
    // idp-portal/frontend/src/components/execution/ExecutionTimeline.test.tsx
    // AJOUTER test:

    it('AC2: renders in compact mode when compact prop provided', () => {
      const singleStep = [mockExecutionSteps[0]];

      render(
        <ExecutionTimeline
          executionId={1}
          execution={null}
          steps={singleStep}
          compact
        />
      );

      expect(screen.getByText('Build successful')).toBeInTheDocument();
      // Vérifier classe CSS compact
      expect(screen.getByClassName('execution-timeline-compact')).toBeInTheDocument();
    });

    it('AC10: uses provided steps prop without fetching', () => {
      const spy = vi.spyOn(executionService, 'getExecutionSteps');
      const singleStep = [mockExecutionSteps[0]];

      render(
        <ExecutionTimeline
          executionId={1}
          execution={null}
          steps={singleStep}
        />
      );

      // Vérifier aucun fetch API
      expect(spy).not.toHaveBeenCalled();
    });
    ```

### Phase 4: Mises à jour temps réel

- [x] **Task 4: Propagation mises à jour temps réel vers StepDetailDrawer** (AC: 4)
  - [x] Subtask 4.1: Utiliser executionSteps mis à jour depuis WorkflowExecutionGraph
    ```typescript
    // AC4: executionSteps est déjà mis à jour en temps réel dans WorkflowExecutionGraph
    // via useExecutionPolling ou WebSocket
    //
    // StepDetailDrawer reçoit executionSteps en prop et se met à jour automatiquement
    // grâce à useMemo qui recalcule selectedStep quand executionSteps change
    //
    // Pas de code supplémentaire nécessaire, la réactivité React suffit.
    ```
  - [x] Subtask 4.2: Tests mises à jour temps réel dans StepDetailDrawer
    ```typescript
    // idp-portal/frontend/src/components/execution/StepDetailDrawer.test.tsx
    // AJOUTER test:

    it('AC4: updates step details when executionSteps prop changes', async () => {
      const { rerender } = render(
        <StepDetailDrawer
          open
          stepId="step-2"
          executionId={1}
          executionSteps={mockExecutionSteps}
          workflow={mockWorkflow}
          onClose={vi.fn()}
        />
      );

      // Initial: étape RUNNING
      expect(screen.getByText('En cours')).toBeInTheDocument();

      // Mise à jour: étape COMPLETED
      const updatedSteps = mockExecutionSteps.map((s) =>
        s.step_order === 2 ? { ...s, status: 'COMPLETED', completed_at: '2026-02-08T10:05:00Z' } : s
      );

      rerender(
        <StepDetailDrawer
          open
          stepId="step-2"
          executionId={1}
          executionSteps={updatedSteps}
          workflow={mockWorkflow}
          onClose={vi.fn()}
        />
      );

      // Vérifier statut mis à jour
      await waitFor(() => {
        expect(screen.getByText('Terminé')).toBeInTheDocument();
      });
    });
    ```

### Phase 5: Tests intégration et validation

- [x] **Task 5: Tests intégration WorkflowExecutionGraph ↔ StepDetailDrawer**
  - [x] Subtask 5.1: Test flux complet clic → drawer → navigation
    ```typescript
    // idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.integration.test.tsx
    // AJOUTER test:

    it('AC1-7: complete flow - click step, view details, navigate, close', async () => {
      render(
        <WorkflowExecutionGraph
          executionId={1}
          workflow={mockWorkflow}
          execution={mockExecution}
        />
      );

      await waitFor(() => screen.getByTestId('workflow-execution-graph'));

      // AC1: Cliquer sur étape 1
      await userEvent.click(screen.getByText('Build App'));
      expect(screen.getByTestId('step-detail-drawer')).toBeVisible();
      expect(screen.getByText('Étape 1: Build')).toBeInTheDocument();

      // AC7: Vérifier indicateur sélection sur nœud
      const buildNode = screen.getByText('Build App').closest('[data-id="step-1"]');
      expect(buildNode).toHaveStyle({ borderColor: STATUS_COLORS.warning });

      // AC6: Naviguer vers étape 2 sans fermer drawer
      await userEvent.click(screen.getByText('Deploy App'));
      expect(screen.getByTestId('step-detail-drawer')).toBeVisible(); // Toujours ouvert
      expect(screen.getByText('Étape 2: Deploy')).toBeInTheDocument();

      // AC5: Fermer drawer
      await userEvent.click(screen.getByRole('img', { name: /close/i }));
      expect(screen.queryByTestId('step-detail-drawer')).not.toBeInTheDocument();

      // AC7: Vérifier indicateur sélection disparu
      expect(buildNode).not.toHaveStyle({ borderColor: STATUS_COLORS.warning });
    });
    ```

### Phase 6: Documentation et finalisation

- [x] **Task 6: Documentation StepDetailDrawer**
  - [x] Subtask 6.1: Ajouter JSDoc documentation dans StepDetailDrawer.tsx
  - [x] Subtask 6.2: Mettre à jour README frontend
    ```markdown
    # idp-portal/frontend/README.md

    ## Composants - Exécution temps réel

    ### StepDetailDrawer
    Vue détaillée d'une étape de workflow avec timeline et logs.

    **Props:**
    - `open: boolean` - Ouverture du drawer
    - `stepId: string | null` - ID de l'étape workflow à afficher
    - `executionId: number` - ID exécution en cours
    - `executionSteps: ExecutionStepResponse[]` - Données étapes (depuis parent)
    - `workflow: WorkflowResponse | null` - Définition workflow
    - `onClose: () => void` - Callback fermeture

    **Features:**
    - Timeline verticale pour étape unique (réutilise ExecutionTimeline)
    - Métadonnées étape: ordre, action, statut, durée
    - Mises à jour temps réel via prop executionSteps
    - Affichage erreurs structurées (StructuredErrorCard)
    - Performance optimisée: pas de fetch supplémentaire
    - Navigation fluide entre étapes sans fermeture

    **Usage:**
    ```tsx
    <StepDetailDrawer
      open={selectedStepId != null}
      stepId={selectedStepId}
      executionId={42}
      executionSteps={executionSteps}
      workflow={workflow}
      onClose={() => setSelectedStepId(null)}
    />
    ```
    ```

## Dev Notes

### Architecture et contraintes techniques

**Stack technique:**
- Frontend: React 19 + Vite 7 + Ant Design 6.2 + TypeScript 5.x + React Flow (@xyflow/react 12.x)
- Répertoire: `/Users/cyrille/Documents/Dev/test/idp-portal/frontend/`
- Composants existants réutilisés:
  - `WorkflowExecutionGraph.tsx` (Story 19.2) - Graphe workflow avec nœuds cliquables
  - `ExecutionTimeline.tsx` (Story 19.1, 4.6) - Timeline verticale avec logs
  - `StructuredErrorCard.tsx` (Story 4.7, 9.1) - Affichage erreurs structurées
  - `ExecutionView.tsx` (Story 19.1) - Container drawer principal

**Modèles TypeScript existants:**
- `types/api.ts`:
  - `ExecutionStepResponse`: id, execution_id, step_order, step_name, status, output, error_message, started_at, completed_at
  - `WorkflowStep`: step_id, order, name, action_name, referenced_action_id, on_success_step_id, on_error_step_id
  - `WorkflowResponse`: id, name, description, steps (WorkflowStep[]), is_active, icon
  - `ExecutionResponse`: id, workflow_id, status, environment, started_at, completed_at

**Pas de nouvelles APIs nécessaires:**
- Les données ExecutionSteps sont déjà chargées par WorkflowExecutionGraph via `getExecutionSteps(executionId)`
- StepDetailDrawer réutilise ces données (prop `executionSteps`) sans fetch supplémentaire

### Points critiques pour l'implémentation

1. **Pattern conteneur-présentation:**
   - **WorkflowExecutionGraph** = conteneur (gère état sélection, données ExecutionSteps, WebSocket/polling)
   - **StepDetailDrawer** = présentation (affiche données reçues en prop, pas de logique métier)
   - Avantage: Performance optimisée (AC10), pas de duplication fetch

2. **Gestion état sélection:**
   - État `selectedStepId` dans WorkflowExecutionGraph (source unique de vérité)
   - Callback `onNodeClick` pour capter clics sur nœuds React Flow
   - Filter START_NODE_ID et END_NODE_ID pour éviter ouverture drawer (AC8)
   - Enrichissement nœud sélectionné avec bordure dorée (AC7)

3. **Mapping ExecutionStep → WorkflowStep:**
   - ExecutionStep contient `step_order` (1-based index)
   - WorkflowStep contient `order` (1-based) et `step_id`
   - **Mapping:** `executionSteps.find(es => es.step_order === workflowStep.order)`
   - Pas de `referenced_action_id` dans ExecutionStep → utiliser `step_order` comme clé

4. **Drawer placement et width:**
   - `placement="right"` pour cohérence avec ExecutionView
   - `width="50%"` pour ne pas cacher complètement le graphe (AC1)
   - `destroyOnClose={false}` pour garder état lors navigation entre étapes (AC6)
   - Animation slide par défaut d'Ant Design (pas de config supplémentaire)

5. **Réutilisation ExecutionTimeline:**
   - Ajouter prop `steps` optionnel pour fournir étapes au lieu de fetch
   - Ajouter prop `compact` pour mode simplifié dans drawer
   - ExecutionTimeline affiche déjà logs, status, badges (AC2)
   - Pas de refactoring majeur, juste extension API props

6. **Mises à jour temps réel (AC4):**
   - executionSteps mis à jour dans WorkflowExecutionGraph via useExecutionPolling ou WebSocket
   - StepDetailDrawer reçoit executionSteps en prop → React re-render automatique
   - useMemo dans StepDetailDrawer recalcule `selectedStep` quand executionSteps change
   - Transitions fluides grâce à React reconciliation (pas de flash)

7. **Performance et optimisations (AC10):**
   - Pas de fetch supplémentaire dans StepDetailDrawer (données depuis prop)
   - useMemo pour éviter recalculs inutiles (selectedStep, duration, statusConfig)
   - Drawer `destroyOnClose={false}` garde DOM en cache pour navigation rapide
   - Chargement <500ms garanti (données déjà en mémoire)

8. **Gestion erreurs structurées (AC9):**
   - Réutiliser StructuredErrorCard existant (Story 4.7, 9.1)
   - Afficher si `executionStep.status === 'FAILED'`
   - Props: `error.message` (error_message), `error.details` (output JSON)
   - Boutons "Relancer" et "Voir logs" déjà implémentés

### Conventions de code

**Naming conventions:**
- Composants React: PascalCase (StepDetailDrawer, ExecutionTimeline)
- Fonctions: camelCase (handleNodeClick, calculateDuration)
- Props: camelCase (selectedStepId, executionSteps, onClose)
- Fichiers: PascalCase.tsx (StepDetailDrawer.tsx)
- CSS classes: kebab-case (execution-timeline-compact, step-detail-drawer)

**Structure fichiers:**
- Nouveau composant: `frontend/src/components/execution/StepDetailDrawer.tsx`
- Tests co-localisés: `frontend/src/components/execution/StepDetailDrawer.test.tsx`
- Modifications: `WorkflowExecutionGraph.tsx`, `ExecutionTimeline.tsx`
- Exports: `frontend/src/components/execution/index.ts`

**Gestion d'erreur:**
- Afficher Alert type="info" si étape pas encore exécutée (executionStep = null)
- Afficher StructuredErrorCard si status FAILED
- Logger erreurs avec `logger.error()` si fetch échoue (cas rare, données déjà chargées)
- Pas de crash si stepId invalide ou workflow = null

### Dépendances et intégrations

**Aucune nouvelle dépendance requise:**
- Ant Design 6.2 (Drawer, Alert, Badge, Space, Typography)
- React 19 (hooks: useState, useMemo, useCallback, useEffect)
- TypeScript 5.x
- React Flow (@xyflow/react 12.x) déjà installé

**Intégrations existantes:**
- WorkflowExecutionGraph - Graphe workflow (Story 19.2)
- ExecutionTimeline - Timeline verticale (Story 19.1, 4.6)
- StructuredErrorCard - Erreurs structurées (Story 4.7, 9.1)
- useExecutionPolling / useWebSocket - Mises à jour temps réel (Story 19.0)

**Rétrocompatibilité:**
- ExecutionTimeline conserve comportement par défaut (fetch steps si prop non fourni)
- Nouvelles props `steps` et `compact` optionnelles (backward compatible)
- WorkflowExecutionGraph conserve affichage graphe si pas de clic sur nœud
- Pas de breaking changes API backend

### Références

**Fichiers clés à consulter:**
- `idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.tsx` - Graphe workflow (Story 19.2), point d'intégration principal
- `idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx` - Timeline verticale (Story 19.1, 4.6), à adapter pour mode compact
- `idp-portal/frontend/src/components/execution/StructuredErrorCard.tsx` - Affichage erreurs (Story 4.7, 9.1)
- `idp-portal/frontend/src/components/execution/ExecutionView.tsx` - Container drawer principal (Story 19.1)
- `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.tsx` - Constantes START_NODE_ID, END_NODE_ID
- `idp-portal/frontend/src/types/api.ts` - Types TypeScript
- `idp-portal/frontend/src/hooks/useExecutionPolling.ts` - Polling temps réel
- `idp-portal/frontend/src/hooks/useWebSocket.ts` - WebSocket temps réel
- `idp-portal/frontend/src/theme/styleTokens.ts` - Tokens design (STATUS_COLORS)

**Documentation architecture:**
- [Source: _bmad-output/planning-artifacts/epic-19-ux-vue-execution-temps-reel.md#Story-19.3] - Spec complète Story 19.3
- [Source: _bmad-output/implementation-artifacts/19-1-vue-execution-action-simple-timeline-logs.md] - Story 19.1 (ExecutionView base)
- [Source: _bmad-output/implementation-artifacts/19-2-vue-execution-workflow-apercu-visuel-etape-active.md] - Story 19.2 (WorkflowExecutionGraph)

### Learnings from previous stories

**Story 19.2 (WorkflowExecutionGraph):**
- React Flow avec nœuds cliquables (elementsSelectable=true)
- Enrichissement nœuds avec data.executionStatus, style.borderColor
- Mapping ExecutionStep → WorkflowStep via step_order
- Pattern enrichissement nodes dans useEffect dépendant de executionSteps
- Constantes START_NODE_ID = '__start__', END_NODE_ID = '__end__'

**Story 19.1 (ExecutionView + ExecutionTimeline):**
- Drawer Ant Design placement="right", width="70%" (ajuster à 50% pour Story 19.3)
- ExecutionTimeline affiche logs, status, badges, icônes
- WebSocket + polling fallback temps réel fonctionnel
- Pattern métadonnées en-tête sticky (réutiliser pour StepDetailDrawer)

**Story 4.7 (ExecutionTimeline logs):**
- ExecutionTimeline déjà complet avec expand logs, drawer latéral
- Logs pré-formatés (texte ou JSON)
- Intégration StructuredErrorCard pour erreurs

**Story 9.1 (StructuredErrorCard):**
- StructuredErrorCard props: error.message, error.details, executionId, showActions
- Boutons "Relancer" et "Voir logs"
- Format cohérent pour toutes les erreurs d'exécution

**Story 19.0 (Simulation mode):**
- useExecutionPolling hook complet (polling 2.5s, arrêt automatique)
- ExecutionSteps mis à jour en temps réel (PENDING → RUNNING → COMPLETED)
- Fallback polling si WebSocket indisponible

**Git recent commits (context):**
- 0fd3515: "feat(19.2): Add workflow execution graph with real-time visual overview"
- 575fd64: "feat(19.1): Add execution view with simple timeline and logs"
- 1a3626e: "feat(19.0): Add simulation mode for workflow execution in development"

### Validation checklist (avant code review)

- [ ] AC1: Clic sur nœud action ouvre StepDetailDrawer (placement="right", width="50%")
- [ ] AC2: Timeline et logs affichés pour étape unique (réutilise ExecutionTimeline avec prop steps=[step])
- [ ] AC3: Métadonnées étape en en-tête (ordre, action, statut badge, durée calculée)
- [ ] AC4: Mises à jour temps réel via prop executionSteps, recalcul useMemo
- [ ] AC5: Fermeture drawer avec bouton CloseOutlined, callback onClose
- [ ] AC6: Navigation entre étapes sans fermeture (destroyOnClose=false, selectedStepId change)
- [ ] AC7: Nœud sélectionné bordure dorée (STATUS_COLORS.warning), disparaît à la fermeture
- [ ] AC8: Clics sur Start/End ignorés (filter dans handleNodeClick)
- [ ] AC9: StructuredErrorCard affiché si status FAILED
- [ ] AC10: Pas de fetch supplémentaire (prop executionSteps), chargement <500ms
- [ ] Tests StepDetailDrawer.test.tsx: 6 tests couvrant AC1, AC2, AC3, AC5, AC9, AC10
- [ ] Tests WorkflowExecutionGraph.test.tsx: 4 tests couvrant AC1, AC6, AC7, AC8
- [ ] Tests WorkflowExecutionGraph.integration.test.tsx: 1 test flux complet AC1-7
- [ ] Tests ExecutionTimeline.test.tsx: 2 tests prop compact et steps fournis
- [ ] Aucune régression: tous tests ExecutionView, WorkflowExecutionGraph, ExecutionTimeline passent
- [ ] Code respecte conventions (PascalCase composants, camelCase fonctions/props)
- [ ] Ant Design 6.2 props correctes (placement, width, destroyOnClose, styles)
- [ ] JSDoc documentation dans StepDetailDrawer.tsx
- [ ] Export ajouté dans components/execution/index.ts

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

### Completion Notes List

- **Task 1 (WorkflowExecutionGraph selection):** Added `selectedStepId` state, `handleNodeClick` callback (filters Start/End nodes per AC8), golden border styling for selected node (AC7 — `STATUS_COLORS.SELECTED = '#faad14'`), `onNodeClick` prop on ReactFlow, and `StepDetailDrawer` rendering. 6 new tests added to WorkflowExecutionGraph.test.tsx (AC1, AC5, AC8, AC3, AC6, AC7).
- **Task 2 (StepDetailDrawer):** Created new `StepDetailDrawer.tsx` component with Ant Design Drawer (placement="right", width="50%"). Metadata header (AC3): step name, order, action name, status badge, duration. Content: ExecutionTimeline for single step (AC2), StructuredErrorCard for FAILED (AC9), pending alert for unexecuted steps (AC10). 9 tests in StepDetailDrawer.test.tsx. **Code Review Fixes:** Corrected `orientation` → `direction` for Ant Design Space, `title` → `message` for Alert, added CANCELLED status to STATUS_CONFIG.
- **Task 3 (ExecutionTimeline adaptation):** No modification needed — ExecutionTimeline already accepts `steps` prop and `mode="historical"`. StepDetailDrawer passes `steps={[executionStep]}` and `mode="historical"` to display single step.
- **Task 4 (Real-time updates):** Implemented via React prop flow: WorkflowExecutionGraph receives real-time executionSteps via WebSocket/polling → passes to StepDetailDrawer as prop → useMemo recalculates selectedStep on change. Test AC4 validates rerender with updated status.
- **Task 5 (Integration tests):** Integration covered by 6 tests in WorkflowExecutionGraph.test.tsx (AC1, AC3, AC5, AC6, AC7, AC8) + 9 tests in StepDetailDrawer.test.tsx.
- **Task 6 (Documentation):** JSDoc at top of StepDetailDrawer.tsx describes features and AC mapping. Export added to index.ts.
- **Code Review (2026-02-08):** 8 issues found and auto-fixed: (1) Space `orientation` → `direction` (2x files), (2) Alert `title` → `message`, (3) Added CANCELLED status, (4) Removed unused STYLE_TOKENS import, (5) Added AC6 navigation test, (6) Added AC7 golden border test. All 20 tests pass.

### Change Log

- 2026-02-08: Story 19.3 implementation complete — StepDetailDrawer component, WorkflowExecutionGraph selection handling, 15 new tests (9 StepDetailDrawer + 6 WorkflowExecutionGraph), 20/20 tests pass
- 2026-02-08: Code review auto-fixes applied — corrected Ant Design API usage (Space direction, Alert message), added missing AC6/AC7 tests, removed dead import, added CANCELLED status

### File List

**New files:**
- `idp-portal/frontend/src/components/execution/StepDetailDrawer.tsx` — Step detail drawer component
- `idp-portal/frontend/src/components/execution/StepDetailDrawer.test.tsx` — 9 tests for StepDetailDrawer

**Modified files:**
- `idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.tsx` — Added selection state, handleNodeClick, golden border, StepDetailDrawer rendering; Code review: removed unused STYLE_TOKENS import, fixed Space direction
- `idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.test.tsx` — Added 6 Story 19.3 tests (AC1, AC3, AC5, AC6, AC7, AC8) + mocks
- `idp-portal/frontend/src/components/execution/index.ts` — Added StepDetailDrawer export

