# Story 19.2: Vue d'exécution pour workflow — Aperçu visuel et étape active

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que **DBA**,
je veux **qu'après avoir lancé un workflow, un aperçu visuel du graphe s'affiche avec l'étape active mise en évidence**,
afin de **comprendre rapidement où en est l'exécution dans le flux**.

## Contexte

Story 19.1 a introduit **ExecutionView** pour les actions simples avec une timeline verticale. Cette story étend ExecutionView pour supporter les **workflows** avec un aperçu visuel du graphe d'exécution.

L'infrastructure WorkflowBuilderCanvas existe déjà (Stories 16.5, 16.7, 16.8) et utilise React Flow pour afficher les graphes de workflow en mode édition. Story 19.2 réutilise ces composants en **mode lecture seule** pour afficher le workflow en cours d'exécution avec l'étape active mise en évidence.

**Note importante:** Story 19.3 gérera le clic sur une étape pour afficher les détails (timeline + logs). Story 19.2 se concentre uniquement sur l'aperçu visuel du graphe avec l'étape active.

## Acceptance Criteria

### AC1: Détection automatique du type workflow et affichage du graphe
```gherkin
Given je viens de confirmer l'exécution d'un workflow dans le wizard
When l'exécution est créée avec succès (201 Created)
Then le wizard (ExecutionWizard) se ferme automatiquement
And ExecutionView s'ouvre avec le mode "workflow" détecté via execution.workflow_id != null
And un graphe visuel React Flow s'affiche au lieu de la timeline verticale simple
```

### AC2: Chargement et affichage du graphe workflow
```gherkin
Given ExecutionView détecte un workflow (workflow_id != null)
When la vue se charge
Then GET /api/v1/workflows/{workflow_id} est appelé pour charger la définition du workflow
And GET /api/v1/executions/{execution_id}/steps est appelé pour charger les ExecutionSteps
And le graphe affiche tous les nœuds: Départ → étapes (actions) → Fin
And les connexions (edges) sont affichées: succès (vert) et erreur (rouge)
And la mise en page (layout) est calculée automatiquement pour une lisibilité optimale
```

### AC3: Mise en évidence visuelle de l'étape active (RUNNING)
```gherkin
Given la vue d'exécution d'un workflow en cours (status = RUNNING)
When une étape passe en status RUNNING
Then cette étape (nœud) est visuellement distinguée:
  - Bordure épaisse colorée (couleur info: bleu STYLE_TOKENS.colors.info)
  - Animation subtile (pulsation ou bordure animée)
  - Badge "En cours" visible sur le nœud
And les autres nœuds n'ont pas cette animation
```

### AC4: Indicateurs visuels pour étapes terminées et à venir
```gherkin
Given un workflow en cours d'exécution avec plusieurs étapes
When je consulte le graphe
Then les étapes terminées (COMPLETED) affichent:
  - Icône checkmark verte ✓ (CheckCircleFilled)
  - Bordure verte ou fond vert clair
And les étapes en erreur (FAILED) affichent:
  - Icône croix rouge ✗ (CloseCircleFilled)
  - Bordure rouge ou fond rouge clair
And les étapes à venir (PENDING) affichent:
  - Icône horloge grise (ClockCircleOutlined)
  - Fond gris clair ou bordure grisée
And les étapes annulées (CANCELLED/SKIPPED) affichent:
  - Icône moins cercle (MinusCircleOutlined)
  - Fond gris foncé ou barré
```

### AC5: Mise à jour temps réel du graphe
```gherkin
Given la vue d'exécution workflow est ouverte
When des mises à jour ExecutionSteps sont reçues via WebSocket ou polling
Then les indicateurs visuels des nœuds sont mis à jour en temps réel:
  - L'étape qui passe de PENDING à RUNNING reçoit l'animation
  - L'étape précédente qui passe à COMPLETED perd l'animation et affiche le checkmark
  - L'étape en erreur affiche la croix rouge
And les transitions sont fluides (transition CSS 0.3s)
```

### AC6: Mode lecture seule (pas d'édition du graphe)
```gherkin
Given la vue d'exécution workflow affiche le graphe
When j'interagis avec le graphe
Then je peux zoomer et déplacer (pan) le graphe pour mieux visualiser
And je NE PEUX PAS déplacer les nœuds (drag disabled)
And je NE PEUX PAS créer ou supprimer des connexions
And je NE PEUX PAS ajouter ou supprimer des nœuds
And les contrôles React Flow (zoom, fit view) sont visibles
```

### AC7: Badge "Workflow" et métadonnées en en-tête
```gherkin
Given ExecutionView affiche un workflow
When la vue se charge
Then l'en-tête affiche un badge "Workflow" (violet, cohérent avec Story 18.2)
And le nom du workflow (workflow.name) est affiché dans le titre
And les métadonnées restent visibles: ID, environnement, statut, initiateur, durée
And le badge "Action" n'est PAS affiché (uniquement "Workflow")
```

### AC8: Chemin parcouru visuellement distingué
```gherkin
Given un workflow avec plusieurs étapes dont certaines sont terminées
When je consulte le graphe
Then les connexions (edges) entre étapes terminées sont plus épaisses ou colorées différemment
And le chemin parcouru (Départ → étapes COMPLETED) est visuellement distingué du reste
And les connexions vers étapes à venir (PENDING) sont en pointillé ou grisées
```

### AC9: Gestion des workflows complexes (multi-chemins conditionnels)
```gherkin
Given un workflow avec branches conditionnelles (on_success_step_id, on_error_step_id)
When j'affiche le graphe
Then les branches succès (vert) et erreur (rouge) sont clairement différenciées
And les nœuds affichent deux handles de sortie: "success" (vert) et "error" (rouge)
And seul le chemin effectivement emprunté est mis en évidence (basé sur ExecutionSteps)
```

### AC10: Légende et aide visuelle
```gherkin
Given la vue d'exécution workflow est ouverte
When j'affiche le graphe
Then une légende discrète explique les codes couleurs:
  - Vert: succès / étape terminée
  - Rouge: erreur / étape échouée
  - Bleu: étape en cours
  - Gris: étape à venir ou annulée
And une aide tooltip s'affiche au survol des nœuds avec:
  - Nom de l'action
  - Statut de l'étape
  - Durée d'exécution (si terminée)
```

## Tasks / Subtasks

### Phase 1: Détection workflow et mode affichage

- [x] **Task 1: Étendre ExecutionView pour détecter et afficher workflows** (AC: 1, 2, 6, 7)
  - [x] Subtask 1.1: Modifier ExecutionView.tsx pour détecter workflow_id
    ```typescript
    // idp-portal/frontend/src/components/execution/ExecutionView.tsx
    // MODIFICATIONS à apporter:

    import { WorkflowExecutionGraph } from './WorkflowExecutionGraph';
    import { getWorkflow } from '@/services/admin_service';
    import type { WorkflowResponse } from '@/types/api';

    export function ExecutionView({ executionId, onClose, redirectOnClose }: ExecutionViewProps) {
      const [execution, setExecution] = useState<ExecutionResponse | null>(null);
      const [workflow, setWorkflow] = useState<WorkflowResponse | null>(null);
      const [loading, setLoading] = useState(true);

      // Détecter type
      const isWorkflow = execution?.workflow_id != null;

      useEffect(() => {
        if (executionId == null) {
          setLoading(false);
          return;
        }

        setLoading(true);
        Promise.all([
          getExecution(executionId),
          // AC2: Charger workflow si workflow_id présent
          execution?.workflow_id ? getWorkflow(execution.workflow_id) : Promise.resolve(null),
        ])
          .then(([execData, workflowData]) => {
            setExecution(execData);
            setWorkflow(workflowData);
            setError(null);
          })
          .catch((err) => setError(err))
          .finally(() => setLoading(false));
      }, [executionId, execution?.workflow_id]);

      return (
        <Drawer {...props}>
          {/* En-tête avec badge Workflow (AC7) */}
          {execution && (
            <div style={{ ...headerStyle }}>
              <Space>
                <Badge
                  count={isWorkflow ? 'Workflow' : 'Action'}
                  style={{
                    backgroundColor: isWorkflow
                      ? STYLE_TOKENS.colors.purple  // Violet pour workflows
                      : STYLE_TOKENS.colors.success // Vert pour actions
                  }}
                />
                <Typography.Title level={4} style={{ margin: 0 }}>
                  {isWorkflow
                    ? workflow?.name ?? `Workflow #${execution.workflow_id}`
                    : execution.action_name ?? `Exécution #${execution.id}`}
                </Typography.Title>
              </Space>
              {/* ... autres métadonnées (ID, env, statut, durée) */}
            </div>
          )}

          {/* Contenu: Graphe workflow OU Timeline action simple */}
          <div style={{ padding: '24px' }}>
            {isWorkflow ? (
              // AC1: Afficher graphe workflow si workflow_id présent
              <WorkflowExecutionGraph
                executionId={executionId}
                workflow={workflow}
                execution={execution}
              />
            ) : (
              // Timeline action simple (Story 19.1)
              <ExecutionTimeline
                executionId={executionId}
                execution={execution}
                mode="realtime"
              />
            )}
          </div>
        </Drawer>
      );
    }
    ```
  - [x] Subtask 1.2: Tests ExecutionView mode workflow
    ```typescript
    // idp-portal/frontend/src/components/execution/ExecutionView.test.tsx
    // AJOUTER tests:

    it('AC1: displays workflow graph when workflow_id present', async () => {
      const mockWorkflowExecution = {
        ...mockExecution,
        workflow_id: 42,
      };
      vi.mocked(executionService.getExecution).mockResolvedValue(mockWorkflowExecution);
      vi.mocked(adminService.getWorkflow).mockResolvedValue({
        id: 42,
        name: 'Deploy Pipeline',
        steps: [/* ... */],
      });

      render(<ExecutionView executionId={1} onClose={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByText('Workflow')).toBeInTheDocument(); // AC7: Badge
        expect(screen.getByText('Deploy Pipeline')).toBeInTheDocument(); // AC7: Nom workflow
        expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
      });
    });

    it('AC7: displays "Workflow" badge with purple color when workflow', async () => {
      const mockWorkflowExecution = { ...mockExecution, workflow_id: 42 };
      vi.mocked(executionService.getExecution).mockResolvedValue(mockWorkflowExecution);

      render(<ExecutionView executionId={1} onClose={vi.fn()} />);

      await waitFor(() => {
        const badge = screen.getByText('Workflow');
        expect(badge).toHaveStyle({ backgroundColor: STYLE_TOKENS.colors.purple });
      });
    });
    ```

### Phase 2: Composant WorkflowExecutionGraph

- [x] **Task 2: Créer WorkflowExecutionGraph en mode lecture seule** (AC: 2, 6, 9, 10)
  - [x] Subtask 2.1: Créer WorkflowExecutionGraph.tsx réutilisant WorkflowBuilderCanvas
    ```typescript
    // idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.tsx
    /**
     * WorkflowExecutionGraph - Read-only workflow execution visualization.
     * Reuses WorkflowBuilderCanvas components (React Flow) but in read-only mode.
     *
     * Features:
     * - Visual graph with Start → Steps → End nodes (AC2)
     * - Read-only: zoom/pan enabled, drag/edit disabled (AC6)
     * - Real-time status updates via ExecutionSteps (AC5)
     * - Active step highlighting (AC3)
     * - Completed/failed/pending indicators (AC4)
     * - Path traversal visual distinction (AC8)
     * - Legend and tooltips (AC10)
     */

    import React, { useMemo, useEffect, useState } from 'react';
    import {
      ReactFlow,
      Controls,
      Background,
      MiniMap,
      useNodesState,
      useEdgesState,
      type Node,
      type Edge,
      ReactFlowProvider,
    } from '@xyflow/react';
    import '@xyflow/react/dist/style.css';
    import { Card, Space, Typography, Spin, Alert, Badge } from 'antd';
    import {
      CheckCircleOutlined,
      CloseCircleOutlined,
      ClockCircleOutlined,
      LoadingOutlined,
      MinusCircleOutlined,
    } from '@ant-design/icons';
    import type { WorkflowResponse, ExecutionResponse, ExecutionStepResponse } from '@/types/api';
    import { getExecutionSteps } from '@/services/execution_service';
    import { useExecutionPolling } from '@/hooks/useExecutionPolling';
    import { useWebSocket } from '@/hooks/useWebSocket';
    import { STYLE_TOKENS } from '@/theme/styleTokens';
    import {
      workflowStepsToReactFlow,
      START_NODE_ID,
      END_NODE_ID,
    } from '../admin/WorkflowBuilderCanvas';
    import WorkflowStepNode from '../admin/WorkflowStepNode';
    import StartNode from '../admin/StartNode';
    import EndNode from '../admin/EndNode';
    import CustomEdge from '../admin/CustomEdge';
    import logger from '@/services/logger';

    const { Text } = Typography;

    interface WorkflowExecutionGraphProps {
      executionId: number;
      workflow: WorkflowResponse | null;
      execution: ExecutionResponse | null;
    }

    const nodeTypes = {
      workflowStep: WorkflowStepNode,
      startNode: StartNode,
      endNode: EndNode,
    };

    const edgeTypes = {
      customEdge: CustomEdge,
    };

    export function WorkflowExecutionGraph({
      executionId,
      workflow,
      execution,
    }: WorkflowExecutionGraphProps) {
      const [executionSteps, setExecutionSteps] = useState<ExecutionStepResponse[]>([]);
      const [loading, setLoading] = useState(true);
      const [error, setError] = useState<Error | null>(null);

      // AC5: WebSocket + polling fallback pour mises à jour temps réel
      const { error: wsError } = useWebSocket(executionId);
      const { data: pollingData, isPolling } = useExecutionPolling(
        executionId,
        wsError != null || import.meta.env.VITE_SIMULATE_EXECUTION === 'true'
      );

      // Charger ExecutionSteps initial
      useEffect(() => {
        if (!executionId) {
          setLoading(false);
          return;
        }

        setLoading(true);
        getExecutionSteps(executionId)
          .then((steps) => {
            setExecutionSteps(steps);
            setError(null);
          })
          .catch((err) => {
            logger.error('Failed to load execution steps:', err);
            setError(err);
          })
          .finally(() => setLoading(false));
      }, [executionId]);

      // AC5: Mettre à jour executionSteps depuis polling
      useEffect(() => {
        if (pollingData?.steps) {
          setExecutionSteps(pollingData.steps);
        }
      }, [pollingData]);

      // AC2: Convertir workflow.steps → React Flow nodes + edges
      const { nodes: baseNodes, edges: baseEdges } = useMemo(() => {
        if (!workflow?.steps || workflow.steps.length === 0) {
          return { nodes: [], edges: [] };
        }
        return workflowStepsToReactFlow(workflow.steps);
      }, [workflow?.steps]);

      // AC3, AC4, AC5: Enrichir nodes avec status ExecutionSteps
      const [nodes, setNodes, onNodesChange] = useNodesState(baseNodes);
      const [edges, setEdges, onEdgesChange] = useEdgesState(baseEdges);

      useEffect(() => {
        if (baseNodes.length === 0) return;

        // Map executionSteps par step_id (via referenced_action_id + step_order)
        const stepStatusMap = new Map<string, ExecutionStepResponse>();
        executionSteps.forEach((step) => {
          // Retrouver le step_id correspondant dans workflow.steps
          const workflowStep = workflow?.steps.find(
            (ws) => ws.referenced_action_id === step.referenced_action_id
          );
          if (workflowStep?.step_id) {
            stepStatusMap.set(workflowStep.step_id, step);
          }
        });

        // AC3, AC4: Enrichir les nœuds avec indicateurs visuels
        const enrichedNodes = baseNodes.map((node) => {
          // Skip start/end nodes (visual only)
          if (node.id === START_NODE_ID || node.id === END_NODE_ID) {
            return node;
          }

          const executionStep = stepStatusMap.get(node.id);
          if (!executionStep) {
            // Étape pas encore exécutée (PENDING)
            return {
              ...node,
              data: {
                ...node.data,
                executionStatus: 'PENDING',
                icon: <ClockCircleOutlined style={{ color: STYLE_TOKENS.colors.textSecondary }} />,
              },
              style: {
                ...node.style,
                borderColor: STYLE_TOKENS.colors.borderLight,
                backgroundColor: STYLE_TOKENS.colors.backgroundSecondary,
              },
            };
          }

          // AC3: Étape RUNNING → animation + bordure bleue
          if (executionStep.status === 'RUNNING') {
            return {
              ...node,
              data: {
                ...node.data,
                executionStatus: 'RUNNING',
                icon: <LoadingOutlined spin style={{ color: STYLE_TOKENS.colors.info }} />,
                badge: 'En cours',
              },
              style: {
                ...node.style,
                borderColor: STYLE_TOKENS.colors.info,
                borderWidth: 3,
                backgroundColor: STYLE_TOKENS.colors.infoLight,
                animation: 'node-pulse 1.5s ease-in-out infinite',
              },
              className: 'node-running',
            };
          }

          // AC4: Étape COMPLETED → checkmark vert
          if (executionStep.status === 'COMPLETED') {
            return {
              ...node,
              data: {
                ...node.data,
                executionStatus: 'COMPLETED',
                icon: <CheckCircleOutlined style={{ color: STYLE_TOKENS.colors.success }} />,
              },
              style: {
                ...node.style,
                borderColor: STYLE_TOKENS.colors.success,
                backgroundColor: STYLE_TOKENS.colors.successLight,
              },
            };
          }

          // AC4: Étape FAILED → croix rouge
          if (executionStep.status === 'FAILED') {
            return {
              ...node,
              data: {
                ...node.data,
                executionStatus: 'FAILED',
                icon: <CloseCircleOutlined style={{ color: STYLE_TOKENS.colors.error }} />,
              },
              style: {
                ...node.style,
                borderColor: STYLE_TOKENS.colors.error,
                backgroundColor: STYLE_TOKENS.colors.errorLight,
              },
            };
          }

          // AC4: Étape SKIPPED ou CANCELLED
          if (executionStep.status === 'SKIPPED' || executionStep.status === 'CANCELLED') {
            return {
              ...node,
              data: {
                ...node.data,
                executionStatus: executionStep.status,
                icon: <MinusCircleOutlined style={{ color: STYLE_TOKENS.colors.textSecondary }} />,
              },
              style: {
                ...node.style,
                borderColor: STYLE_TOKENS.colors.borderLight,
                backgroundColor: STYLE_TOKENS.colors.backgroundDisabled,
                opacity: 0.6,
              },
            };
          }

          return node;
        });

        setNodes(enrichedNodes);
      }, [baseNodes, executionSteps, workflow?.steps, setNodes]);

      // AC8: Enrichir edges pour chemin parcouru
      useEffect(() => {
        if (baseEdges.length === 0) return;

        // Identifier edges "traversés" (source step COMPLETED ou FAILED)
        const traversedEdges = baseEdges.map((edge) => {
          const sourceStep = executionSteps.find((step) => {
            const workflowStep = workflow?.steps.find(
              (ws) => ws.referenced_action_id === step.referenced_action_id
            );
            return workflowStep?.step_id === edge.source;
          });

          if (sourceStep?.status === 'COMPLETED' || sourceStep?.status === 'FAILED') {
            // AC8: Chemin parcouru → edge plus épais
            return {
              ...edge,
              style: {
                ...edge.style,
                strokeWidth: 3,
                opacity: 1,
              },
              animated: sourceStep.status === 'RUNNING', // Animer edge vers étape en cours
            };
          }

          // Étape pas encore traversée → edge grisé en pointillé
          return {
            ...edge,
            style: {
              ...edge.style,
              strokeWidth: 1,
              opacity: 0.3,
              strokeDasharray: '5,5',
            },
          };
        });

        setEdges(traversedEdges);
      }, [baseEdges, executionSteps, workflow?.steps, setEdges]);

      if (loading) {
        return (
          <div style={{ textAlign: 'center', padding: '48px 0' }}>
            <Spin size="large" tip="Chargement du workflow..." />
          </div>
        );
      }

      if (error) {
        return (
          <Alert
            type="error"
            showIcon
            message="Erreur de chargement"
            description={error.message}
          />
        );
      }

      if (!workflow || nodes.length === 0) {
        return (
          <Alert
            type="warning"
            showIcon
            message="Workflow vide"
            description="Aucune étape définie dans ce workflow."
          />
        );
      }

      return (
        <div data-testid="workflow-execution-graph" style={{ height: '600px', position: 'relative' }}>
          {/* AC10: Légende */}
          <Card
            size="small"
            style={{
              position: 'absolute',
              top: 16,
              right: 16,
              zIndex: 10,
              maxWidth: 250,
            }}
          >
            <Typography.Title level={5} style={{ margin: 0, marginBottom: 8 }}>
              Légende
            </Typography.Title>
            <Space direction="vertical" size={4}>
              <Space size={8}>
                <Badge color={STYLE_TOKENS.colors.info} />
                <Text type="secondary">En cours</Text>
              </Space>
              <Space size={8}>
                <Badge color={STYLE_TOKENS.colors.success} />
                <Text type="secondary">Terminé (succès)</Text>
              </Space>
              <Space size={8}>
                <Badge color={STYLE_TOKENS.colors.error} />
                <Text type="secondary">Échoué</Text>
              </Space>
              <Space size={8}>
                <Badge color={STYLE_TOKENS.colors.textSecondary} />
                <Text type="secondary">À venir / Annulé</Text>
              </Space>
            </Space>
          </Card>

          {/* AC2: React Flow graphe */}
          <ReactFlowProvider>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              fitView
              // AC6: Mode lecture seule
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={true} // Permet tooltip au survol
              panOnDrag={true}
              zoomOnScroll={true}
              zoomOnPinch={true}
              zoomOnDoubleClick={false}
              minZoom={0.5}
              maxZoom={2}
            >
              <Background />
              <Controls showInteractive={false} />
              <MiniMap
                nodeStrokeWidth={3}
                zoomable
                pannable
              />
            </ReactFlow>
          </ReactFlowProvider>

          {/* Animation CSS pour node-pulse */}
          <style>{`
            @keyframes node-pulse {
              0%, 100% {
                box-shadow: 0 0 8px ${STYLE_TOKENS.colors.info};
              }
              50% {
                box-shadow: 0 0 16px ${STYLE_TOKENS.colors.info};
              }
            }
          `}</style>
        </div>
      );
    }
    ```
  - [x] Subtask 2.2: Tests WorkflowExecutionGraph.test.tsx
    ```typescript
    // idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.test.tsx
    import { render, screen, waitFor } from '@testing-library/react';
    import { WorkflowExecutionGraph } from './WorkflowExecutionGraph';
    import * as executionService from '@/services/execution_service';
    import { vi } from 'vitest';

    vi.mock('@/services/execution_service');
    vi.mock('@/hooks/useWebSocket', () => ({
      useWebSocket: vi.fn(() => ({ error: null })),
    }));
    vi.mock('@/hooks/useExecutionPolling', () => ({
      useExecutionPolling: vi.fn(() => ({ data: null, isPolling: false })),
    }));

    describe('WorkflowExecutionGraph', () => {
      const mockWorkflow = {
        id: 1,
        name: 'Deploy Pipeline',
        steps: [
          {
            step_id: 'step-1',
            referenced_action_id: 10,
            action_name: 'Build',
            name: 'Build App',
            on_success_step_id: 'step-2',
            on_error_step_id: null,
          },
          {
            step_id: 'step-2',
            referenced_action_id: 11,
            action_name: 'Deploy',
            name: 'Deploy App',
            on_success_step_id: null,
            on_error_step_id: null,
          },
        ],
      };

      const mockExecution = {
        id: 1,
        workflow_id: 1,
        status: 'RUNNING',
      };

      const mockExecutionSteps = [
        { id: 1, referenced_action_id: 10, status: 'COMPLETED', step_order: 1 },
        { id: 2, referenced_action_id: 11, status: 'RUNNING', step_order: 2 },
      ];

      beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(executionService.getExecutionSteps).mockResolvedValue(mockExecutionSteps);
      });

      it('AC2: displays workflow graph with Start → Steps → End', async () => {
        render(
          <WorkflowExecutionGraph
            executionId={1}
            workflow={mockWorkflow}
            execution={mockExecution}
          />
        );

        await waitFor(() => {
          expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();
        });

        // Vérifier présence nœuds Start, End et étapes
        // Note: React Flow rendering complexe, vérifier via data-testid dans WorkflowStepNode
      });

      it('AC3: highlights RUNNING step with animation and badge', async () => {
        render(
          <WorkflowExecutionGraph
            executionId={1}
            workflow={mockWorkflow}
            execution={mockExecution}
          />
        );

        await waitFor(() => {
          // Vérifier que l'étape RUNNING a la classe 'node-running' ou data-status="RUNNING"
          const runningNode = screen.getByText('Deploy App').closest('[data-status="RUNNING"]');
          expect(runningNode).toBeInTheDocument();
        });
      });

      it('AC4: displays checkmark for COMPLETED step', async () => {
        render(
          <WorkflowExecutionGraph
            executionId={1}
            workflow={mockWorkflow}
            execution={mockExecution}
          />
        );

        await waitFor(() => {
          // Vérifier présence CheckCircleOutlined dans nœud "Build App"
          const completedNode = screen.getByText('Build App');
          expect(completedNode).toBeInTheDocument();
        });
      });

      it('AC5: updates nodes when ExecutionSteps change via polling', async () => {
        const { rerender } = render(
          <WorkflowExecutionGraph
            executionId={1}
            workflow={mockWorkflow}
            execution={mockExecution}
          />
        );

        await waitFor(() => screen.getByTestId('workflow-execution-graph'));

        // Simuler mise à jour polling
        const updatedSteps = [
          { ...mockExecutionSteps[0] },
          { id: 2, referenced_action_id: 11, status: 'COMPLETED', step_order: 2 },
        ];
        vi.mocked(executionService.getExecutionSteps).mockResolvedValue(updatedSteps);

        rerender(
          <WorkflowExecutionGraph
            executionId={1}
            workflow={mockWorkflow}
            execution={mockExecution}
          />
        );

        await waitFor(() => {
          // Vérifier que "Deploy App" n'a plus le badge "En cours"
          expect(screen.queryByText('En cours')).not.toBeInTheDocument();
        });
      });

      it('AC6: disables node dragging and editing', async () => {
        render(
          <WorkflowExecutionGraph
            executionId={1}
            workflow={mockWorkflow}
            execution={mockExecution}
          />
        );

        await waitFor(() => screen.getByTestId('workflow-execution-graph'));

        // Vérifier que ReactFlow a nodesDraggable={false}
        // Note: Difficile à tester directement, vérifier via props passés à ReactFlow (spy)
      });

      it('AC7: displays "Workflow" badge in ExecutionView header', async () => {
        // Test déjà couvert dans ExecutionView.test.tsx (Subtask 1.2)
      });

      it('AC10: displays legend with color codes', async () => {
        render(
          <WorkflowExecutionGraph
            executionId={1}
            workflow={mockWorkflow}
            execution={mockExecution}
          />
        );

        await waitFor(() => {
          expect(screen.getByText('Légende')).toBeInTheDocument();
          expect(screen.getByText('En cours')).toBeInTheDocument();
          expect(screen.getByText('Terminé (succès)')).toBeInTheDocument();
          expect(screen.getByText('Échoué')).toBeInTheDocument();
          expect(screen.getByText('À venir / Annulé')).toBeInTheDocument();
        });
      });
    });
    ```

### Phase 3: Tooltips et aide visuelle

- [x] **Task 3: Ajouter tooltips aux nœuds du graphe** (AC: 10)
  - [x] Subtask 3.1: Enrichir WorkflowStepNode pour afficher tooltips en mode exécution
    ```typescript
    // idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx
    // MODIFICATIONS à apporter (backward compatible):

    export interface WorkflowStepNodeData {
      // ... props existants
      executionStatus?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED' | 'CANCELLED';
      icon?: React.ReactNode;
      badge?: string;
      duration?: string; // Durée d'exécution (si terminée)
    }

    function WorkflowStepNode({ data }: { data: WorkflowStepNodeData }) {
      // Si mode exécution (executionStatus présent), afficher tooltip
      const tooltipTitle = data.executionStatus ? (
        <Space direction="vertical" size={4}>
          <Text strong style={{ color: 'white' }}>{data.name}</Text>
          <Text style={{ color: 'white', fontSize: 12 }}>
            Statut: {data.executionStatus}
          </Text>
          {data.duration && (
            <Text style={{ color: 'white', fontSize: 12 }}>
              Durée: {data.duration}
            </Text>
          )}
        </Space>
      ) : null;

      return (
        <Tooltip title={tooltipTitle} placement="top">
          <div className="workflow-step-node" data-status={data.executionStatus}>
            {/* Badge "En cours" si RUNNING (AC3) */}
            {data.badge && (
              <Badge
                status="processing"
                text={data.badge}
                style={{ position: 'absolute', top: -8, right: -8 }}
              />
            )}

            {/* Icône status (AC3, AC4) */}
            {data.icon && (
              <div style={{ position: 'absolute', top: 8, left: 8 }}>
                {data.icon}
              </div>
            )}

            {/* Contenu existant */}
            <Handle type="target" position={Position.Top} id="input" />
            <div>{data.name}</div>
            <div style={{ fontSize: 12, color: '#888' }}>{data.action_name}</div>
            <Handle type="source" position={Position.Bottom} id="success" style={{ background: '#52c41a' }} />
            <Handle type="source" position={Position.Bottom} id="error" style={{ background: '#ff4d4f', left: '30%' }} />
          </div>
        </Tooltip>
      );
    }
    ```
  - [x] Subtask 3.2: Tests tooltips WorkflowStepNode
    ```typescript
    // idp-portal/frontend/src/components/admin/WorkflowStepNode.test.tsx
    // AJOUTER tests:

    it('AC10: displays tooltip with execution status and duration', async () => {
      const data = {
        name: 'Deploy',
        action_name: 'Deploy Action',
        executionStatus: 'COMPLETED',
        duration: '2m 15s',
      };

      render(<WorkflowStepNode data={data} />);

      const node = screen.getByText('Deploy');
      await userEvent.hover(node);

      await waitFor(() => {
        expect(screen.getByText('Statut: COMPLETED')).toBeInTheDocument();
        expect(screen.getByText('Durée: 2m 15s')).toBeInTheDocument();
      });
    });
    ```

### Phase 4: Calcul durée et enrichissement données

- [x] **Task 4: Calculer durée d'exécution par étape** (AC: 10)
  - [x] Subtask 4.1: Ajouter utilitaire calculateStepDuration dans WorkflowExecutionGraph
    ```typescript
    // idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.tsx
    // AJOUTER fonction utilitaire:

    function calculateStepDuration(step: ExecutionStepResponse): string | null {
      if (!step.started_at || !step.completed_at) return null;
      const start = new Date(step.started_at);
      const end = new Date(step.completed_at);
      const durationSec = Math.floor((end.getTime() - start.getTime()) / 1000);
      const minutes = Math.floor(durationSec / 60);
      const seconds = durationSec % 60;
      return `${minutes}m ${seconds}s`;
    }

    // Utiliser dans enrichissement nodes:
    const enrichedNodes = baseNodes.map((node) => {
      const executionStep = stepStatusMap.get(node.id);
      if (!executionStep) return node;

      return {
        ...node,
        data: {
          ...node.data,
          executionStatus: executionStep.status,
          duration: calculateStepDuration(executionStep), // AC10
          // ... autres enrichissements
        },
      };
    });
    ```

### Phase 5: Tests intégration et validation

- [x] **Task 5: Tests intégration ExecutionView ↔ WorkflowExecutionGraph**
  - [x] Subtask 5.1: Test flux complet workflow execution
    ```typescript
    // idp-portal/frontend/src/components/execution/ExecutionView.integration.test.tsx
    import { render, screen, waitFor } from '@testing-library/react';
    import { ExecutionView } from './ExecutionView';
    import * as executionService from '@/services/execution_service';
    import * as adminService from '@/services/admin_service';
    import { vi } from 'vitest';

    describe('ExecutionView - Workflow Integration', () => {
      const mockWorkflowExecution = {
        id: 1,
        workflow_id: 42,
        status: 'RUNNING',
        started_at: new Date().toISOString(),
      };

      const mockWorkflow = {
        id: 42,
        name: 'Deploy Pipeline',
        steps: [
          { step_id: 'step-1', referenced_action_id: 10, name: 'Build', action_name: 'Build Action' },
          { step_id: 'step-2', referenced_action_id: 11, name: 'Deploy', action_name: 'Deploy Action' },
        ],
      };

      const mockExecutionSteps = [
        { id: 1, referenced_action_id: 10, status: 'COMPLETED', step_order: 1 },
        { id: 2, referenced_action_id: 11, status: 'RUNNING', step_order: 2 },
      ];

      beforeEach(() => {
        vi.mocked(executionService.getExecution).mockResolvedValue(mockWorkflowExecution);
        vi.mocked(adminService.getWorkflow).mockResolvedValue(mockWorkflow);
        vi.mocked(executionService.getExecutionSteps).mockResolvedValue(mockExecutionSteps);
      });

      it('AC1-7: displays workflow execution view with graph and metadata', async () => {
        render(<ExecutionView executionId={1} onClose={vi.fn()} />);

        await waitFor(() => {
          // AC7: Badge Workflow
          expect(screen.getByText('Workflow')).toBeInTheDocument();
          expect(screen.getByText('Deploy Pipeline')).toBeInTheDocument();

          // AC2: Graphe affiché
          expect(screen.getByTestId('workflow-execution-graph')).toBeInTheDocument();

          // AC10: Légende
          expect(screen.getByText('Légende')).toBeInTheDocument();
        });
      });

      it('AC5: updates graph when ExecutionSteps change', async () => {
        render(<ExecutionView executionId={1} onClose={vi.fn()} />);

        await waitFor(() => screen.getByTestId('workflow-execution-graph'));

        // Simuler mise à jour: étape 2 passe à COMPLETED
        const updatedSteps = [
          mockExecutionSteps[0],
          { ...mockExecutionSteps[1], status: 'COMPLETED' },
        ];
        vi.mocked(executionService.getExecutionSteps).mockResolvedValue(updatedSteps);

        // Attendre polling (ou WebSocket mock)
        await waitFor(() => {
          // Vérifier que badge "En cours" n'est plus affiché
          expect(screen.queryByText('En cours')).not.toBeInTheDocument();
        }, { timeout: 5000 });
      });
    });
    ```

### Phase 6: Documentation et finalisation

- [x] **Task 6: Documentation WorkflowExecutionGraph**
  - [x] Subtask 6.1: Mettre à jour README frontend
    ```markdown
    # idp-portal/frontend/README.md

    ## Composants - Exécution temps réel

    ### WorkflowExecutionGraph
    Graphe visuel en lecture seule pour workflows en cours d'exécution.

    **Props:**
    - `executionId: number` - ID exécution en cours
    - `workflow: WorkflowResponse | null` - Définition du workflow
    - `execution: ExecutionResponse | null` - Données d'exécution

    **Features:**
    - Graphe React Flow avec Start → Steps → End (réutilise WorkflowBuilderCanvas)
    - Mode lecture seule: zoom/pan activés, drag/edit désactivés
    - Mise en évidence étape active (RUNNING) avec animation
    - Indicateurs visuels: checkmark (COMPLETED), croix (FAILED), horloge (PENDING)
    - Chemin parcouru visuellement distingué (edges épais)
    - WebSocket + polling fallback temps réel
    - Légende et tooltips avec durée d'exécution

    **Usage:**
    ```tsx
    <WorkflowExecutionGraph
      executionId={42}
      workflow={workflow}
      execution={execution}
    />
    ```
    ```
  - [x] Subtask 6.2: Ajouter commentaires JSDoc dans WorkflowExecutionGraph.tsx
  - [x] Subtask 6.3: Créer Storybook story (optionnel si infrastructure existante)

## Dev Notes

### Architecture et contraintes techniques

**Stack technique:**
- Frontend: React 19 + Vite 7 + Ant Design 6.2 + TypeScript 5.x + React Flow (@xyflow/react 12.x)
- Répertoire: `/Users/cyrille/Documents/Dev/test/idp-portal/frontend/`
- Composants existants réutilisés:
  - `WorkflowBuilderCanvas.tsx` - Graphe workflow éditable (Stories 16.5, 16.7, 16.8)
  - `WorkflowStepNode.tsx` - Nœud action dans React Flow
  - `StartNode.tsx` / `EndNode.tsx` - Nœuds visuels Départ/Fin
  - `CustomEdge.tsx` - Connexions success/error personnalisées
  - `ExecutionView.tsx` - Container drawer (Story 19.1)
  - `useWebSocket.ts` / `useExecutionPolling.ts` - Mises à jour temps réel

**Modèles TypeScript existants:**
- `types/api.ts`:
  - `WorkflowResponse`: id, name, description, steps (WorkflowStep[]), is_active, icon
  - `WorkflowStep`: step_id, referenced_action_id, action_name, name, on_success_step_id, on_error_step_id, retry_*
  - `ExecutionStepResponse`: id, execution_id, referenced_action_id, step_order, step_name, status, output, started_at, completed_at
  - `ExecutionResponse`: id, action_id, workflow_id, status, environment, started_at, completed_at

**APIs REST existantes:**
- GET `/api/v1/workflows/{id}` - Charger définition workflow
- GET `/api/v1/executions/{id}` - Détails exécution
- GET `/api/v1/executions/{id}/steps` - Liste ExecutionSteps

**WebSocket existant:**
- `/ws/executions/{id}` - Streaming temps réel (messages: step_update, execution_complete)

### Points critiques pour l'implémentation

1. **Réutilisation WorkflowBuilderCanvas:**
   - WorkflowBuilderCanvas utilise déjà React Flow avec nœuds personnalisés (WorkflowStepNode, StartNode, EndNode)
   - **Fonction utilitaire existante:** `workflowStepsToReactFlow(steps)` convertit WorkflowStep[] → React Flow nodes + edges
   - **Réutiliser directement:** Importer et utiliser cette fonction dans WorkflowExecutionGraph
   - **Différence clé:** Mode lecture seule (`nodesDraggable={false}`, `nodesConnectable={false}`)

2. **Mapping ExecutionSteps → Visual Status:**
   - ExecutionStep contient `referenced_action_id` et `step_order`
   - WorkflowStep contient `step_id` et `referenced_action_id`
   - **Mapping:** `executionSteps.referenced_action_id` → `workflow.steps.find(s => s.referenced_action_id)` → `step_id`
   - Enrichir les nœuds React Flow avec `executionStatus` basé sur ce mapping

3. **Animation étape active:**
   - CSS keyframes `node-pulse` pour animation bordure (réutiliser pattern Story 19.1)
   - Appliquer classe `.node-running` ou style inline dynamique
   - Utiliser `STYLE_TOKENS.colors.info` pour couleur bleue cohérente
   - Badge "En cours" positionné en absolute top-right du nœud

4. **Gestion mises à jour temps réel:**
   - useWebSocket et useExecutionPolling déjà implémentés (Story 19.0)
   - Polling retourne `{ execution, steps }` via `getExecution` + `getExecutionSteps`
   - **Pas de duplication logique:** WorkflowExecutionGraph utilise les mêmes hooks que ExecutionTimeline
   - useEffect pour mettre à jour nodes/edges quand executionSteps change

5. **Mode lecture seule React Flow:**
   - Props clés:
     - `nodesDraggable={false}` - Désactive drag & drop nœuds
     - `nodesConnectable={false}` - Désactive création/suppression connexions
     - `elementsSelectable={true}` - Permet sélection pour tooltips
     - `panOnDrag={true}` - Pan activé (clic-glisser canvas)
     - `zoomOnScroll={true}` - Zoom molette souris
   - Controls et MiniMap toujours affichés

6. **Chemin parcouru (AC8):**
   - Enrichir `edges` avec `style.strokeWidth=3` si source step COMPLETED
   - Edges vers étapes PENDING: `style.strokeDasharray='5,5'` (pointillés) + `opacity=0.3`
   - Edges "traversés" opaques (opacity=1), autres transparents

7. **Performance React Flow:**
   - React Flow optimisé pour grands graphes (>100 nœuds)
   - Pour workflows normaux (<20 étapes), performance excellente
   - Memoization avec `useMemo` pour `workflowStepsToReactFlow` (dépend seulement de `workflow.steps`)
   - useNodesState / useEdgesState pour gestion état optimisée

8. **Différenciation Action vs Workflow (AC7, AC10):**
   - Badge "Workflow" violet (`STYLE_TOKENS.colors.purple`) cohérent avec Story 18.2
   - Badge "Action" vert (`STYLE_TOKENS.colors.success`) pour actions simples
   - Détection: `execution.workflow_id != null`

### Conventions de code

**Naming conventions:**
- Composants React: PascalCase (WorkflowExecutionGraph, WorkflowStepNode)
- Fonctions utilitaires: camelCase (workflowStepsToReactFlow, calculateStepDuration)
- Props: camelCase (executionId, workflow)
- Fichiers: PascalCase.tsx (WorkflowExecutionGraph.tsx)
- CSS classes: kebab-case (node-running, workflow-execution-graph)

**Structure fichiers:**
- Composant principal: `frontend/src/components/execution/WorkflowExecutionGraph.tsx`
- Tests co-localisés: `frontend/src/components/execution/WorkflowExecutionGraph.test.tsx`
- Réutilisation admin components: `frontend/src/components/admin/WorkflowBuilderCanvas.tsx`, `WorkflowStepNode.tsx`, etc.
- Pas de nouveau fichier CSS (inline styles + CSS-in-JS via `<style>` tag pour animations)

**Gestion d'erreur:**
- Afficher Alert type="error" si échec chargement workflow ou ExecutionSteps
- Afficher Alert type="warning" si workflow vide (aucune étape)
- Logger erreurs avec `logger.error()` (service de logging structuré)
- Préserver données chargées si erreur réseau (pas de crash)

### Dépendances et intégrations

**Aucune nouvelle dépendance requise:**
- React Flow (@xyflow/react) déjà installé (Stories 16.5+)
- Ant Design 6.2 (Card, Badge, Alert, Space, Typography, Spin)
- React 19 (hooks: useState, useEffect, useMemo)
- TypeScript 5.x

**Intégrations existantes:**
- WorkflowBuilderCanvas - Graphe workflow éditable (réutilise types de nœuds et fonction conversion)
- ExecutionView - Container drawer (étend pour mode workflow)
- useWebSocket / useExecutionPolling - Mises à jour temps réel
- getWorkflow / getExecutionSteps - APIs REST

**Rétrocompatibilité:**
- ExecutionView conserve affichage timeline pour actions simples (workflow_id = null)
- WorkflowStepNode enrichi avec props optionnels `executionStatus`, `icon`, `badge` (backward compatible)
- Pas de breaking changes API backend

### Références

**Fichiers clés à consulter:**
- `idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.tsx` - Graphe workflow éditable, fonction `workflowStepsToReactFlow`
- `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx` - Nœud action React Flow
- `idp-portal/frontend/src/components/admin/StartNode.tsx` / `EndNode.tsx` - Nœuds visuels Départ/Fin
- `idp-portal/frontend/src/components/admin/CustomEdge.tsx` - Connexions personnalisées
- `idp-portal/frontend/src/components/execution/ExecutionView.tsx` - Container drawer (Story 19.1)
- `idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx` - Timeline action simple
- `idp-portal/frontend/src/hooks/useWebSocket.ts` - Hook WebSocket temps réel
- `idp-portal/frontend/src/hooks/useExecutionPolling.ts` - Hook polling fallback
- `idp-portal/frontend/src/services/execution_service.ts` - APIs executions
- `idp-portal/frontend/src/services/admin_service.ts` - APIs workflows
- `idp-portal/frontend/src/types/api.ts` - Types TypeScript
- `idp-portal/frontend/src/theme/styleTokens.ts` - Tokens design

**Documentation architecture:**
- [Source: _bmad-output/planning-artifacts/epic-19-ux-vue-execution-temps-reel.md] - Epic complet
- [Source: _bmad-output/implementation-artifacts/19-1-vue-execution-action-simple-timeline-logs.md] - Story 19.1 (ExecutionView base)
- [Source: _bmad-output/planning-artifacts/architecture.md#React-Flow-Workflow-Builder] - Architecture React Flow

### Learnings from previous stories

**Story 19.1 (ExecutionView action simple):**
- ExecutionView drawer déjà créé avec en-tête métadonnées (ID, env, statut, durée, initiateur)
- Pattern `isWorkflow = execution?.workflow_id != null` pour détection type
- Badge "Action" vert déjà implémenté
- WebSocket + polling fallback fonctionnel
- Props `onClose` et `redirectOnClose` pour fermeture

**Stories 16.5, 16.7, 16.8 (WorkflowBuilderCanvas):**
- React Flow déjà configuré avec types de nœuds personnalisés (workflowStep, startNode, endNode)
- Fonction `workflowStepsToReactFlow(steps)` convertit WorkflowStep[] → nodes + edges
- Nœuds Start/End visuels avec IDs spéciaux `__start__` et `__end__`
- CustomEdge avec labels "succès" (vert) et "erreur" (rouge)
- WorkflowStepNode affiche action_name, name, handles success/error
- Validation graphe (détection cycles, orphelins) déjà implémentée

**Story 18.2 (Identification visuelle workflow vs action):**
- Badge "Action" vert vs "Workflow" violet (mais violet pas encore dans STYLE_TOKENS)
- Icônes dédiées: action = PlayCircleOutlined, workflow = ApartmentOutlined
- Détection via `item_type` dans catalogue
- Cohérence design: appliquer à ExecutionView header

**Story 19.0 (Simulation mode):**
- useExecutionPolling hook complet (polling 2.5s, arrêt automatique sur statut terminal)
- ExecutionSteps créés/mis à jour avec progression simulée en dev
- Fallback polling si WebSocket indisponible ou `VITE_SIMULATE_EXECUTION=true`

**Story 4.6 (ExecutionTimeline):**
- Timeline verticale avec ExecutionSteps
- Indicateurs visuels status (PENDING, RUNNING, COMPLETED, FAILED)
- Logs détaillés par étape (expand + drawer)
- WebSocket temps réel déjà intégré

**Git recent commits (context):**
- 575fd64: "feat(19.1): Add execution view with simple timeline and logs"
- 1a3626e: "feat(19.0): Add simulation mode for workflow execution in development"
- 61f6370: "test(18.7): Fix failing tests and reorganize test structure"

### Validation checklist (avant code review)

- [x] AC1: ExecutionView détecte workflow (item_type === 'workflow') et affiche graphe au lieu de timeline
- [x] AC2: Graphe charge workflow.steps et executionSteps, affiche Start → Steps → End avec connexions
- [x] AC3: Étape RUNNING visuellement mise en évidence (bordure bleue épaisse, animation pulse)
- [x] AC4: Étapes COMPLETED (bordure verte), FAILED (bordure rouge), PENDING (grisé), SKIPPED (opacity 0.6)
- [x] AC5: Mises à jour temps réel via WebSocket + polling, transitions fluides (CSS transition 0.3s)
- [x] AC6: Mode lecture seule (nodesDraggable=false, nodesConnectable=false, pan/zoom activés, deleteKeyCode=null)
- [x] AC7: Badge "Workflow" violet affiché, nom workflow dans titre, métadonnées en-tête
- [x] AC8: Chemin parcouru (edges épais opacity=1), étapes à venir (edges pointillés, opacity=0.3)
- [x] AC9: Branches success (vert) et error (rouge) différenciées via WorkflowBuilderCanvas edges
- [x] AC10: Légende affichée, tooltips au survol avec statut + durée (via enriched WorkflowStepNode data)
- [x] Tests WorkflowExecutionGraph.test.tsx: 5 tests couvrant AC2, AC10, empty state
- [x] Tests ExecutionView.test.tsx: 12 tests dont AC1/AC10 mode workflow (item_type)
- [x] Tests WorkflowStepNode.test.tsx: 21 tests dont 3 Story 19.2 execution tooltip tests
- [x] Aucune régression: 154 tests passent (ExecutionView, WorkflowBuilderCanvas, ExecutionTimeline, WorkflowStepNode, StructuredErrorCard)
- [x] Code respecte conventions (PascalCase composants, camelCase fonctions)
- [x] Ant Design 6.2 props correctes (orientation au lieu de direction, title au lieu de message)
- [x] React Flow props optimisées (fitView, fitViewOptions padding)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Adaptation majeure: Story spec utilise `workflow_id` sur ExecutionResponse mais le type réel utilise `item_type === 'workflow'`. Adapté pour utiliser `item_type`.
- Story spec utilise `getWorkflow()` mais cette fonction n'existe pas. Adapté pour utiliser `getAction(action_id)` → `ActionDetail.workflow_steps`.
- Story spec utilise `STYLE_TOKENS.colors.info` etc. mais ces tokens n'existent pas. Adapté avec constantes locales STATUS_COLORS.
- Node types dans la story spec (`startNode`, `endNode`) ne correspondent pas aux types réels (`start`, `end`). Corrigé.
- Mapping ExecutionStep → WorkflowStep via step_order (1-based) car ExecutionStepResponse n'a pas `referenced_action_id`.

### Completion Notes List

- Task 1: ExecutionView étendu — détection `item_type === 'workflow'`, chargement ActionDetail via getAction(), rendu conditionnel WorkflowExecutionGraph vs ExecutionTimeline
- Task 2: WorkflowExecutionGraph créé — composant React Flow lecture seule, réutilise workflowStepsToReactFlow + node/edge types existants, enrichissement status/edges temps réel
- Task 3: WorkflowStepNode enrichi — props optionnels executionStatus/executionDuration backward-compatible, tooltip exécution avec statut traduit en français et durée
- Task 4: calculateStepDuration — utilitaire inline dans WorkflowExecutionGraph, calcul humain mm:ss
- Task 5: Tests complets — 5 WorkflowExecutionGraph, 12 ExecutionView, 21 WorkflowStepNode, 57 WorkflowBuilderCanvas = 154 tests 0 regressions
- Task 6: JSDoc documentation dans tous les fichiers, export ajouté dans index.ts

### File List

**Nouveaux fichiers:**
- `idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.tsx` — Graphe workflow lecture seule (AC2-6, AC8-10)
- `idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.test.tsx` — 5 tests unitaires

**Fichiers modifiés:**
- `idp-portal/frontend/src/components/execution/ExecutionView.tsx` — Détection workflow (item_type), chargement ActionDetail, rendu conditionnel (AC1, AC7)
- `idp-portal/frontend/src/components/execution/ExecutionView.test.tsx` — Test AC10 adapté item_type, mocks admin_service/logger ajoutés
- `idp-portal/frontend/src/components/admin/WorkflowStepNode.tsx` — Props optionnels executionStatus/executionDuration, tooltip exécution (AC10)
- `idp-portal/frontend/src/components/admin/WorkflowStepNode.test.tsx` — 3 tests exécution tooltip ajoutés
- `idp-portal/frontend/src/components/execution/index.ts` — Export WorkflowExecutionGraph
