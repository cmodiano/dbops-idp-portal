/**
 * Tests for useWorkflowExportImport hook — Story 26.5 AC8
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import React from 'react';
import { App } from 'antd';
import type { Node, Edge } from '@xyflow/react';
import { useWorkflowExportImport } from '../useWorkflowExportImport';
import { START_NODE_ID, END_NODE_ID } from '../../utils/workflowConversion';

// Mock notification and modal for import tests
const mockNotification = { error: vi.fn(), success: vi.fn() };
const mockModal = { confirm: vi.fn(), error: vi.fn() };

vi.mock('antd', async (importOriginal) => {
  const actual = await importOriginal<typeof import('antd')>();
  const AppComponent = actual.App;
  return {
    ...actual,
    App: Object.assign(AppComponent, {
      useApp: () => ({ notification: mockNotification, modal: mockModal }),
    }),
  };
});

// Mock external modules
vi.mock('../../utils/workflowExport', () => ({
  exportWorkflowAsJSON: vi.fn(),
  exportWorkflowAsYAML: vi.fn(),
  exportWorkflowAsImage: vi.fn().mockResolvedValue(undefined),
  parseWorkflowFile: vi.fn(),
}));

vi.mock('../../services/logger', () => ({
  default: {
    debug: vi.fn(),
    error: vi.fn(),
  },
}));

import {
  exportWorkflowAsJSON,
  exportWorkflowAsYAML,
  exportWorkflowAsImage,
  parseWorkflowFile,
} from '../../utils/workflowExport';

const wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <App>{children}</App>
);

const createNodes = (): Node[] => [
  { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} },
  { id: 'step-1', type: 'workflowStep', position: { x: 0, y: 120 }, data: { action_id: 10, name: 'Test', retry_enabled: false, retry_max_attempts: null, retry_interval_seconds: null, retry_backoff_multiplier: null } },
  { id: END_NODE_ID, type: 'end', position: { x: 0, y: 300 }, data: {} },
];

const createEdges = (): Edge[] => [
  { id: 'e1', source: 'step-1', target: END_NODE_ID, sourceHandle: 'success' },
];

describe('useWorkflowExportImport', () => {
  const defaultParams = {
    nodes: createNodes(),
    edges: createEdges(),
    metadata: { name: 'test-workflow', description: 'desc', tags: ['tag1'] },
    reactFlowWrapperRef: { current: document.createElement('div') },
    onMetadataImport: vi.fn(),
    onWorkflowLoad: vi.fn(),
    onClearValidation: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns all expected properties', () => {
    const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });
    expect(result.current).toHaveProperty('exporting');
    expect(result.current).toHaveProperty('handleExportJSON');
    expect(result.current).toHaveProperty('handleExportYAML');
    expect(result.current).toHaveProperty('handleExportImage');
    expect(result.current).toHaveProperty('handleImportFile');
    expect(result.current).toHaveProperty('fileInputRef');
    expect(result.current).toHaveProperty('exportMenuItems');
  });

  it('handleExportJSON calls exportWorkflowAsJSON', () => {
    const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });
    act(() => {
      result.current.handleExportJSON();
    });
    expect(exportWorkflowAsJSON).toHaveBeenCalled();
  });

  it('handleExportYAML calls exportWorkflowAsYAML', () => {
    const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });
    act(() => {
      result.current.handleExportYAML();
    });
    expect(exportWorkflowAsYAML).toHaveBeenCalled();
  });

  it('handleExportImage sets exporting state and calls exportWorkflowAsImage', async () => {
    const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });
    expect(result.current.exporting).toBe(false);

    await act(async () => {
      await result.current.handleExportImage();
    });

    expect(exportWorkflowAsImage).toHaveBeenCalled();
    expect(result.current.exporting).toBe(false); // back to false after
  });

  it('handleExportImage handles errors gracefully', async () => {
    vi.mocked(exportWorkflowAsImage).mockRejectedValueOnce(new Error('Canvas error'));
    const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });

    await act(async () => {
      await result.current.handleExportImage();
    });

    expect(result.current.exporting).toBe(false);
  });

  it('handleImportFile rejects files larger than 5MB', () => {
    const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });

    const largeFile = new File(['x'.repeat(100)], 'large.json', { type: 'application/json' });
    Object.defineProperty(largeFile, 'size', { value: 6 * 1024 * 1024 });

    const event = {
      target: { files: [largeFile], value: 'large.json' },
    } as unknown as React.ChangeEvent<HTMLInputElement>;

    act(() => {
      result.current.handleImportFile(event);
    });

    // File should be rejected (no parseWorkflowFile called)
    expect(parseWorkflowFile).not.toHaveBeenCalled();
  });

  it('handleImportFile handles invalid format', async () => {
    vi.mocked(parseWorkflowFile).mockReturnValue({
      valid: false,
      errors: ['Invalid format'],
      data: null,
    });

    const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });

    const file = new File(['invalid'], 'bad.json', { type: 'application/json' });
    const event = {
      target: { files: [file], value: 'bad.json' },
    } as unknown as React.ChangeEvent<HTMLInputElement>;

    await act(async () => {
      result.current.handleImportFile(event);
      // Trigger FileReader onload
      await new Promise((resolve) => setTimeout(resolve, 100));
    });

    // parseWorkflowFile should have been called
    expect(parseWorkflowFile).toHaveBeenCalled();
  });

  it('exportMenuItems has 3 items (JSON, YAML, Image)', () => {
    const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });
    expect(result.current.exportMenuItems).toHaveLength(3);
    expect(result.current.exportMenuItems[0].key).toBe('json');
    expect(result.current.exportMenuItems[1].key).toBe('yaml');
    expect(result.current.exportMenuItems[2].key).toBe('image');
  });

  it('uses default metadata when metadata is undefined', () => {
    const params = { ...defaultParams, metadata: undefined };
    const { result } = renderHook(() => useWorkflowExportImport(params), { wrapper });

    act(() => {
      result.current.handleExportJSON();
    });

    // Should be called with default metadata
    expect(exportWorkflowAsJSON).toHaveBeenCalledWith(
      expect.anything(),
      expect.objectContaining({ name: 'workflow' })
    );
  });

  describe('handleImportFile — coverage extras', () => {
    it('does nothing when no file selected', () => {
      const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });

      const event = {
        target: { files: [], value: '' },
      } as unknown as React.ChangeEvent<HTMLInputElement>;

      act(() => {
        result.current.handleImportFile(event);
      });

      expect(parseWorkflowFile).not.toHaveBeenCalled();
    });

    it('imports directly when workflow is empty (no confirmation)', async () => {
      const emptyNodes: Node[] = [
        { id: START_NODE_ID, type: 'start', position: { x: 0, y: 0 }, data: {} },
        { id: END_NODE_ID, type: 'end', position: { x: 0, y: 300 }, data: {} },
      ];
      const onWorkflowLoad = vi.fn();
      const onMetadataImport = vi.fn();
      const params = {
        ...defaultParams,
        nodes: emptyNodes,
        edges: [],
        onWorkflowLoad,
        onMetadataImport,
      };

      vi.mocked(parseWorkflowFile).mockReturnValue({
        valid: true,
        errors: [],
        data: {
          version: '1.0',
          workflow: {
            name: 'Imported',
            description: 'desc',
            tags: ['t1'],
            steps: [{ step_id: 's1', step_type: 'service_call', name: 'Step', referenced_action_id: 1, order: 0 }],
          },
        },
      });

      const { result } = renderHook(() => useWorkflowExportImport(params), { wrapper });
      const file = new File(['{"version":"1.0"}'], 'import.json', { type: 'application/json' });
      const event = {
        target: { files: [file], value: 'import.json' },
      } as unknown as React.ChangeEvent<HTMLInputElement>;

      act(() => {
        result.current.handleImportFile(event);
      });

      await waitFor(() => {
        expect(onWorkflowLoad).toHaveBeenCalled();
      });
      expect(onMetadataImport).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'Imported', description: 'desc', tags: ['t1'] })
      );
      expect(mockModal.confirm).not.toHaveBeenCalled();
      expect(mockNotification.success).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Workflow importé avec succès' })
      );
    });

    it('shows confirm modal when workflow has nodes, then loads on Ok', async () => {
      let capturedOnOk: (() => void) | undefined;
      mockModal.confirm.mockImplementation((opts: { onOk?: () => void }) => {
        capturedOnOk = opts.onOk;
      });

      vi.mocked(parseWorkflowFile).mockReturnValue({
        valid: true,
        errors: [],
        data: {
          version: '1.0',
          workflow: {
            name: 'New',
            description: null,
            tags: [],
            steps: [{ step_id: 's1', step_type: 'service_call', name: 'S', referenced_action_id: 1, order: 0 }],
          },
        },
      });

      const onWorkflowLoad = vi.fn();
      const { result } = renderHook(() => useWorkflowExportImport({ ...defaultParams, onWorkflowLoad }), { wrapper });
      const file = new File(['{}'], 'w.json', { type: 'application/json' });
      const event = {
        target: { files: [file], value: 'w.json' },
      } as unknown as React.ChangeEvent<HTMLInputElement>;

      act(() => {
        result.current.handleImportFile(event);
      });

      await waitFor(() => {
        expect(mockModal.confirm).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'Remplacer le workflow actuel ?',
            okText: 'Remplacer',
          })
        );
      });

      act(() => {
        capturedOnOk?.();
      });

      await waitFor(() => {
        expect(onWorkflowLoad).toHaveBeenCalled();
      });
    });

    it('shows error when file is empty', async () => {
      const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });
      const file = new File([], 'empty.json', { type: 'application/json' });
      const event = {
        target: { files: [file], value: 'empty.json' },
      } as unknown as React.ChangeEvent<HTMLInputElement>;

      act(() => {
        result.current.handleImportFile(event);
      });

      await waitFor(() => {
        expect(mockNotification.error).toHaveBeenCalledWith(
          expect.objectContaining({ title: 'Le fichier est vide' })
        );
      });
    });

    it('shows error on FileReader error', async () => {
      const OriginalFileReader = global.FileReader;
      global.FileReader = class MockFileReader {
        onload: ((e: ProgressEvent<FileReader>) => void) | null = null;
        onerror: (() => void) | null = null;
        readAsText() {
          queueMicrotask(() => this.onerror?.());
        }
      } as unknown as typeof FileReader;

      const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });
      const file = new File(['x'], 'f.json', { type: 'application/json' });
      const event = {
        target: { files: [file], value: 'f.json' },
      } as unknown as React.ChangeEvent<HTMLInputElement>;

      act(() => {
        result.current.handleImportFile(event);
      });

      await waitFor(() => {
        expect(mockNotification.error).toHaveBeenCalledWith(
          expect.objectContaining({ title: 'Erreur lors de la lecture du fichier' })
        );
      });

      global.FileReader = OriginalFileReader;
    });

    it('shows modal.error when format is invalid', async () => {
      vi.mocked(parseWorkflowFile).mockReturnValue({
        valid: false,
        errors: ['Error 1', 'Error 2'],
        data: null,
      });

      const { result } = renderHook(() => useWorkflowExportImport(defaultParams), { wrapper });
      const file = new File(['invalid'], 'bad.json', { type: 'application/json' });
      const event = {
        target: { files: [file], value: 'bad.json' },
      } as unknown as React.ChangeEvent<HTMLInputElement>;

      act(() => {
        result.current.handleImportFile(event);
      });

      await waitFor(() => {
        expect(mockModal.error).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'Format de fichier invalide',
            okText: 'Compris',
          })
        );
      });
    });
  });
});
