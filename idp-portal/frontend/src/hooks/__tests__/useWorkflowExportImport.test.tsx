/**
 * Tests for useWorkflowExportImport hook — Story 26.5 AC8
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { App } from 'antd';
import type { Node, Edge } from '@xyflow/react';
import { useWorkflowExportImport } from '../useWorkflowExportImport';
import { START_NODE_ID, END_NODE_ID } from '../../utils/workflowConversion';

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
});
