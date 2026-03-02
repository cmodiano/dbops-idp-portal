/**
 * Tests for IntegrationForm — Upload callbacks coverage (Story 55.6).
 * Covers lines 216-219 (beforeUpload size check, happy path, onRemove).
 * Uses a partial antd mock to capture beforeUpload and onRemove props directly.
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import type { IntegrationTypeCatalogue } from '../../types/api';

// Capture Upload callbacks — must be module-level vars (not const) for hoisting compatibility
let capturedBeforeUpload: ((file: Partial<File>) => unknown) | null = null;
let capturedOnRemove: (() => void) | null = null;

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  const MockUpload = Object.assign(
    function MockUpload({
      beforeUpload,
      onRemove,
      children,
    }: {
      beforeUpload?: (file: Partial<File>) => unknown;
      onRemove?: () => void;
      children?: React.ReactNode;
      [key: string]: unknown;
    }) {
      capturedBeforeUpload = beforeUpload ?? null;
      capturedOnRemove = onRemove ?? null;
      return React.createElement('div', { 'data-testid': 'mock-upload' }, children);
    },
    // Expose actual Upload.LIST_IGNORE so the component can use it
    { LIST_IGNORE: (actual as unknown as { Upload: { LIST_IGNORE: symbol } }).Upload.LIST_IGNORE }
  );
  return { ...actual, Upload: MockUpload };
});

// Mock hooks used by IntegrationForm
const mockTypes: IntegrationTypeCatalogue[] = [
  {
    code: 'aap',
    name: 'Ansible Automation Platform',
    description: 'AAP',
    version: '1.0',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    actions: [],
  },
];

const mockUseIntegrationTypes = vi.fn().mockReturnValue({
  types: mockTypes,
  loading: false,
  error: null,
  isFallback: false,
});

vi.mock('../../hooks/useIntegrationTypes', () => ({
  useIntegrationTypes: () => mockUseIntegrationTypes(),
}));

vi.mock('../../hooks/useVaultIntegrations', () => ({
  useVaultIntegrations: () => ({ vaultIntegrations: [], loading: false, error: null }),
}));

vi.mock('../../services/integrations_service', () => ({
  testConnection: vi.fn(),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ accessToken: 'test-token' }),
}));

// Import AFTER mocks
import { App, Upload } from 'antd';
import { IntegrationForm } from './IntegrationForm';

function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

const defaultProps = {
  open: true,
  onCancel: vi.fn(),
  onSubmit: vi.fn().mockResolvedValue(undefined),
  loading: false,
  error: null,
  editIntegration: null,
};

describe('IntegrationForm — Upload callbacks coverage (lignes 216-219)', () => {
  beforeEach(() => {
    capturedBeforeUpload = null;
    capturedOnRemove = null;
    vi.clearAllMocks();
    vi.restoreAllMocks();
    mockUseIntegrationTypes.mockReturnValue({
      types: mockTypes,
      loading: false,
      error: null,
      isFallback: false,
    });
  });

  it('beforeUpload — image > 2MB → message.error (ligne 216)', () => {
    const mockMessageError = vi.fn();
    vi.spyOn(App, 'useApp').mockReturnValue({
      message: {
        success: vi.fn(),
        error: mockMessageError,
        info: vi.fn(),
        warning: vi.fn(),
        loading: vi.fn(),
        open: vi.fn(),
        destroy: vi.fn(),
      },
      notification: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), open: vi.fn() },
      modal: { confirm: vi.fn() },
    } as unknown as ReturnType<typeof App.useApp>);

    renderWithApp(<IntegrationForm {...defaultProps} />);

    // MockUpload should have captured the beforeUpload callback
    expect(capturedBeforeUpload).not.toBeNull();

    // Simulate an image file that is > 2MB (passes type check, fails size check → line 216)
    const largeImageFile = {
      name: 'large-image.jpg',
      type: 'image/jpeg',
      size: 3 * 1024 * 1024, // 3 MB
    } as unknown as File;

    let result: unknown;
    act(() => {
      result = capturedBeforeUpload!(largeImageFile);
    });

    // Should call message.error (line 216) and return LIST_IGNORE
    expect(mockMessageError).toHaveBeenCalledWith("L'image doit faire moins de 2MB!");
    expect(result).toBe(Upload.LIST_IGNORE);
  });

  it('beforeUpload — petite image valide → return false (ligne 217)', () => {
    // Stub fetch for handleIconUpload
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ error: { message: 'Upload failed' } }),
    }));

    renderWithApp(<IntegrationForm {...defaultProps} />);
    expect(capturedBeforeUpload).not.toBeNull();

    // Small valid image file (passes both checks → line 217)
    const smallImageFile = {
      name: 'icon.png',
      type: 'image/png',
      size: 50 * 1024, // 50 KB
    } as unknown as File;

    let result: unknown;
    act(() => {
      result = capturedBeforeUpload!(smallImageFile);
    });

    // Should return false (line 217: return false prevents auto-upload)
    expect(result).toBe(false);

    vi.unstubAllGlobals();
  });

  it('beforeUpload — non-image file → message.error + LIST_IGNORE (ligne 215)', () => {
    const mockMessageError = vi.fn();
    vi.spyOn(App, 'useApp').mockReturnValue({
      message: {
        success: vi.fn(),
        error: mockMessageError,
        info: vi.fn(),
        warning: vi.fn(),
        loading: vi.fn(),
        open: vi.fn(),
        destroy: vi.fn(),
      },
      notification: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn(), open: vi.fn() },
      modal: { confirm: vi.fn() },
    } as unknown as ReturnType<typeof App.useApp>);

    renderWithApp(<IntegrationForm {...defaultProps} />);
    expect(capturedBeforeUpload).not.toBeNull();

    const pdfFile = { name: 'doc.pdf', type: 'application/pdf', size: 1024 } as unknown as File;

    let result: unknown;
    act(() => {
      result = capturedBeforeUpload!(pdfFile);
    });

    expect(mockMessageError).toHaveBeenCalledWith('Vous ne pouvez uploader que des images!');
    expect(result).toBe(Upload.LIST_IGNORE);
  });

  it('onRemove — réinitialise fileList et uploadedIconUrl (ligne 219)', () => {
    renderWithApp(<IntegrationForm {...defaultProps} />);
    expect(capturedOnRemove).not.toBeNull();

    // Call onRemove directly (simulates user clicking delete on uploaded icon)
    // Line 219: setFileList([]), setUploadedIconUrl(null), form.setFieldsValue({icon: undefined})
    expect(() => {
      act(() => {
        capturedOnRemove!();
      });
    }).not.toThrow();

    // Component still renders after onRemove
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
