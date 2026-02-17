/**
 * useWorkflowExportImport — Story 26.5 AC3
 *
 * Extracted from WorkflowBuilderCanvas.tsx.
 * Encapsulates export JSON/YAML/image and import file logic.
 */
import { useCallback, useMemo, useRef, useState } from 'react';
import { App, List } from 'antd';
import {
  CloseCircleOutlined,
  ExportOutlined,
  FileTextOutlined,
  PictureOutlined,
} from '@ant-design/icons';
import type { Node, Edge } from '@xyflow/react';
import {
  reactFlowToWorkflowSteps,
  START_NODE_ID,
  END_NODE_ID,
  workflowStepsToReactFlow,
} from '../utils/workflowConversion';
import {
  exportWorkflowAsJSON,
  exportWorkflowAsYAML,
  exportWorkflowAsImage,
  parseWorkflowFile,
  type WorkflowMetadata,
} from '../utils/workflowExport';
import logger from '../services/logger';

export interface UseWorkflowExportImportParams {
  nodes: Node[];
  edges: Edge[];
  metadata: WorkflowMetadata | undefined;
  reactFlowWrapperRef: React.RefObject<HTMLDivElement | null>;
  onMetadataImport?: (metadata: WorkflowMetadata) => void;
  onWorkflowLoad?: (nodes: Node[], edges: Edge[]) => void;
  onClearValidation?: () => void;
}

export interface UseWorkflowExportImportReturn {
  exporting: boolean;
  handleExportJSON: () => void;
  handleExportYAML: () => void;
  handleExportImage: () => Promise<void>;
  handleImportFile: (event: React.ChangeEvent<HTMLInputElement>) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  exportMenuItems: Array<{ key: string; label: string; icon: React.ReactNode; onClick: () => void }>;
}

export function useWorkflowExportImport({
  nodes,
  edges,
  metadata,
  reactFlowWrapperRef,
  onMetadataImport,
  onWorkflowLoad,
  onClearValidation,
}: UseWorkflowExportImportParams): UseWorkflowExportImportReturn {
  const { notification, modal } = App.useApp();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [exporting, setExporting] = useState(false);

  const getMetadata = useCallback((): WorkflowMetadata => {
    return metadata ?? { name: 'workflow', description: null, tags: [] };
  }, [metadata]);

  const handleExportJSON = useCallback(() => {
    const currentSteps = reactFlowToWorkflowSteps(nodes, edges);
    logger.debug('Export JSON', { stepCount: currentSteps.length, workflowName: getMetadata().name });
    exportWorkflowAsJSON(currentSteps, getMetadata());
    notification.success({ title: 'Export JSON réussi', duration: 3 });
  }, [nodes, edges, getMetadata, notification]);

  const handleExportYAML = useCallback(() => {
    const currentSteps = reactFlowToWorkflowSteps(nodes, edges);
    logger.debug('Export YAML', { stepCount: currentSteps.length, workflowName: getMetadata().name });
    exportWorkflowAsYAML(currentSteps, getMetadata());
    notification.success({ title: 'Export YAML réussi', duration: 3 });
  }, [nodes, edges, getMetadata, notification]);

  const handleExportImage = useCallback(async () => {
    if (!reactFlowWrapperRef.current) return;
    setExporting(true);
    try {
      await exportWorkflowAsImage(reactFlowWrapperRef.current, getMetadata().name);
      notification.success({ title: 'Export image réussi', duration: 3 });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur inconnue';
      notification.error({
        title: 'Erreur lors de l\'export image',
        description: errorMessage,
        duration: 5,
      });
      logger.error('Export image error', { error: err instanceof Error ? err.message : String(err) });
    } finally {
      setExporting(false);
    }
  }, [reactFlowWrapperRef, getMetadata, notification]);

  const loadImportedWorkflow = useCallback((importData: NonNullable<ReturnType<typeof parseWorkflowFile>['data']>) => {
    const { nodes: newNodes, edges: newEdges } = workflowStepsToReactFlow(importData.workflow.steps);

    logger.debug('Workflow imported', { stepCount: importData.workflow.steps.length, workflowName: importData.workflow.name });

    onClearValidation?.();

    if (onWorkflowLoad) {
      onWorkflowLoad(newNodes, newEdges);
    }

    if (onMetadataImport) {
      onMetadataImport({
        name: importData.workflow.name,
        description: importData.workflow.description,
        tags: importData.workflow.tags,
      });
    }
    notification.success({ title: 'Workflow importé avec succès', duration: 3 });
  }, [onWorkflowLoad, onMetadataImport, onClearValidation, notification]);

  const handleImportFile = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file size (max 5MB)
    const maxSizeBytes = 5 * 1024 * 1024;
    if (file.size > maxSizeBytes) {
      notification.error({
        title: 'Fichier trop volumineux',
        description: `La taille maximale autorisée est de 5 MB. Votre fichier fait ${(file.size / 1024 / 1024).toFixed(2)} MB.`,
        duration: 5,
      });
      event.target.value = '';
      return;
    }

    const extension = '.' + file.name.split('.').pop()?.toLowerCase();
    const reader = new FileReader();

    reader.onload = (e) => {
      const content = e.target?.result as string;
      if (!content) {
        notification.error({ title: 'Le fichier est vide', duration: 5 });
        return;
      }

      const result = parseWorkflowFile(content, extension);
      if (!result.valid || !result.data) {
        modal.error({
          title: 'Format de fichier invalide',
          width: 600,
          content: (
            <List
              size="small"
              dataSource={result.errors}
              renderItem={(err: string) => (
                <List.Item>
                  <CloseCircleOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />
                  {err}
                </List.Item>
              )}
            />
          ),
          okText: 'Compris',
        });
        return;
      }

      const importData = result.data;

      // Check if current workflow has nodes → confirm replacement
      const currentWorkflowNodes = nodes.filter(
        (n) => n.id !== START_NODE_ID && n.id !== END_NODE_ID
      );
      if (currentWorkflowNodes.length > 0) {
        modal.confirm({
          title: 'Remplacer le workflow actuel ?',
          content: 'Le workflow actuel sera remplacé par le workflow importé. Cette action est irréversible.',
          okText: 'Remplacer',
          okButtonProps: { danger: true },
          cancelText: 'Annuler',
          onOk: () => loadImportedWorkflow(importData),
        });
      } else {
        loadImportedWorkflow(importData);
      }
    };

    reader.onerror = () => {
      notification.error({ title: 'Erreur lors de la lecture du fichier', duration: 5 });
    };

    reader.readAsText(file);
    // Reset input so the same file can be re-imported
    event.target.value = '';
  }, [nodes, notification, modal, loadImportedWorkflow]);

  const exportMenuItems = useMemo(() => [
    { key: 'json', label: 'Exporter en JSON', icon: <ExportOutlined />, onClick: handleExportJSON },
    { key: 'yaml', label: 'Exporter en YAML', icon: <FileTextOutlined />, onClick: handleExportYAML },
    { key: 'image', label: 'Exporter l\'image', icon: <PictureOutlined />, onClick: handleExportImage },
  ], [handleExportJSON, handleExportYAML, handleExportImage]);

  return {
    exporting,
    handleExportJSON,
    handleExportYAML,
    handleExportImage,
    handleImportFile,
    fileInputRef,
    exportMenuItems,
  };
}
