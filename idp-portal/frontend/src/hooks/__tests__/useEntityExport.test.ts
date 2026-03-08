/**
 * Tests for useEntityExport hook (Story 64.13, AC #4, #9).
 * Tests: successful download, API error notification.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { createElement } from 'react';
import { App } from 'antd';

// --- Mocks ---

const { mockNotificationError, mockApiFetchBlob } = vi.hoisted(() => ({
  mockNotificationError: vi.fn(),
  mockApiFetchBlob: vi.fn(),
}));

vi.mock('antd', async (importOriginal) => {
  const actual = await importOriginal<typeof import('antd')>();
  const MockedApp = Object.assign(actual.App, {
    useApp: () => ({
      notification: { error: mockNotificationError },
      message: {},
      modal: {},
    }),
  });
  return { ...actual, App: MockedApp };
});

vi.mock('../../services/api_client', () => ({
  apiFetchBlob: mockApiFetchBlob,
}));

// Mock browser download mechanics
const mockCreateObjectURL = vi.fn().mockReturnValue('blob:http://test/1');
const mockRevokeObjectURL = vi.fn();
const mockAnchorClick = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  mockCreateObjectURL.mockReturnValue('blob:http://test/1');
  // Stub URL APIs
  Object.defineProperty(window, 'URL', {
    value: { createObjectURL: mockCreateObjectURL, revokeObjectURL: mockRevokeObjectURL },
    writable: true,
  });
  // Stub anchor click to avoid JSDOM navigation
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(mockAnchorClick);
});

import { useEntityExport } from '../useEntityExport';

// Wrapper to provide App context
function wrapper({ children }: { children: React.ReactNode }) {
  return createElement(App, null, children);
}

describe('useEntityExport', () => {
  it('télécharge le fichier YAML en cas de succès', async () => {
    const mockBlob = new Blob(['yaml content'], { type: 'application/x-yaml' });
    mockApiFetchBlob.mockResolvedValue(mockBlob);

    const { result } = renderHook(
      () => useEntityExport('actions', 42, 'my-action'),
      { wrapper },
    );

    expect(result.current.loading).toBe(false);

    await act(async () => {
      await result.current.exportYaml();
    });

    expect(mockApiFetchBlob).toHaveBeenCalledWith('/admin/actions/42/export/yaml/');
    expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
    expect(mockAnchorClick).toHaveBeenCalled();
    expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:http://test/1');
    expect(result.current.loading).toBe(false);
    expect(mockNotificationError).not.toHaveBeenCalled();
  });

  it('affiche une notification d\'erreur en cas d\'échec API', async () => {
    mockApiFetchBlob.mockRejectedValue(new Error('API Error 500'));

    const { result } = renderHook(
      () => useEntityExport('integrations', 7, 'my-integration'),
      { wrapper },
    );

    await act(async () => {
      await result.current.exportYaml();
    });

    expect(mockApiFetchBlob).toHaveBeenCalledWith('/admin/integrations/7/export/yaml/');
    expect(mockNotificationError).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Erreur export YAML' }),
    );
    expect(result.current.loading).toBe(false);
    expect(mockCreateObjectURL).not.toHaveBeenCalled();
  });
});
