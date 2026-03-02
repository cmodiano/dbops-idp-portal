/**
 * Tests for useIntegrationFormState hook (Story 54.8 AC#8).
 * Covers: état initial, reset à la fermeture, init en mode edit,
 * flags calculés, handler health check.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import type { IntegrationResponse, TestConnectionResponse } from '../../types/api';
import { ApiError } from '../../services/api_client';
import type { FormInstance } from 'antd';
import type { IntegrationFormValues } from '../useIntegrationFormState';

// --- Mocks ---

const mockMessageSuccess = vi.fn();
const mockMessageError = vi.fn();

const mockFormWatchValues: Record<string, unknown> = {};

vi.mock('antd', () => ({
  App: {
    useApp: () => ({
      message: { success: mockMessageSuccess, error: mockMessageError },
      notification: {},
      modal: {},
    }),
  },
  Form: {
    useWatch: (name: string) => mockFormWatchValues[name] ?? undefined,
  },
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ accessToken: 'test-token' }),
}));

vi.mock('../../services/integrations_service', () => ({
  testConnection: vi.fn(),
}));

import { testConnection } from '../../services/integrations_service';
import { useIntegrationFormState } from '../useIntegrationFormState';

const mockedTestConnection = vi.mocked(testConnection);

// --- Helpers ---

function createMockForm(): FormInstance<IntegrationFormValues> {
  return {
    setFieldsValue: vi.fn(),
    resetFields: vi.fn(),
    getFieldValue: vi.fn(),
    validateFields: vi.fn(),
    getFieldsValue: vi.fn(),
    setFields: vi.fn(),
    scrollToField: vi.fn(),
    isFieldTouched: vi.fn(),
    isFieldsTouched: vi.fn(),
    isFieldValidating: vi.fn(),
    getFieldError: vi.fn(),
    getFieldWarning: vi.fn(),
    getFieldsError: vi.fn(),
    submit: vi.fn(),
  } as unknown as FormInstance<IntegrationFormValues>;
}

function makeIntegration(overrides: Partial<IntegrationResponse> = {}): IntegrationResponse {
  return {
    id: 1, type: 'aap', name: 'My AAP',
    base_url: 'https://aap.example.com', credential_ref: null,
    icon: null, auth_flow: null, token_url: null,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

// --- Tests ---

describe('useIntegrationFormState', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    for (const key of Object.keys(mockFormWatchValues)) {
      delete mockFormWatchValues[key];
    }
  });

  // ---- 3.2 : état initial quand open=false ----

  it('returns correct initial state when open=false', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({ open: false, editIntegration: null, form }),
    );

    expect(result.current.uploadedIconUrl).toBeNull();
    expect(result.current.fileList).toEqual([]);
    expect(result.current.localHealth).toBeNull();
    expect(result.current.testLoading).toBe(false);
    expect(result.current.watchedType).toBe('');
    expect(result.current.watchedAuthFlow).toBeNull();
    expect(result.current.watchedIcon).toBeNull();
    expect(result.current.isInventoryDb).toBe(false);
    expect(result.current.isVaultType).toBe(false);
    expect(result.current.isTokenFlow).toBe(false);
    expect(result.current.isOauth2Flow).toBe(false);
    expect(result.current.isApiKeyFlow).toBe(false);
    expect(result.current.isInvalid).toBe(false);
    expect(result.current.isDeprecated).toBe(false);
    expect(result.current.isSubmitDisabled).toBe(false);
    expect(result.current.editValues).toBeNull();
  });

  it('exposes all expected handler functions', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({ open: false, editIntegration: null, form }),
    );

    expect(typeof result.current.setUploadedIconUrl).toBe('function');
    expect(typeof result.current.setFileList).toBe('function');
    expect(typeof result.current.setLocalHealth).toBe('function');
    expect(typeof result.current.handleIconUpload).toBe('function');
    expect(typeof result.current.handleTestConnection).toBe('function');
  });

  // ---- 3.3 : reset des états ----

  it('resets localHealth when open changes to false', () => {
    const form = createMockForm();
    const integration = makeIntegration();
    const { result, rerender } = renderHook(
      ({ open }: { open: boolean }) =>
        useIntegrationFormState({ open, editIntegration: integration, form }),
      { initialProps: { open: true } },
    );

    act(() => {
      result.current.setLocalHealth({ status: 'ok', checked_at: '2026-01-01T00:00:00Z', error_message: null });
    });
    expect(result.current.localHealth).not.toBeNull();

    act(() => { rerender({ open: false }); });

    expect(result.current.localHealth).toBeNull();
  });

  it('resets localHealth when editIntegration changes', () => {
    const form = createMockForm();
    const { result, rerender } = renderHook(
      ({ id }: { id: number }) =>
        useIntegrationFormState({ open: true, editIntegration: makeIntegration({ id }), form }),
      { initialProps: { id: 1 } },
    );

    act(() => {
      result.current.setLocalHealth({ status: 'error', checked_at: '2026-01-01T00:00:00Z', error_message: 'timeout' });
    });

    act(() => { rerender({ id: 2 }); });

    expect(result.current.localHealth).toBeNull();
  });

  it('calls form.resetFields when opening in create mode', () => {
    const form = createMockForm();
    const { rerender } = renderHook(
      ({ open }: { open: boolean }) =>
        useIntegrationFormState({ open, editIntegration: null, form }),
      { initialProps: { open: false } },
    );

    act(() => { rerender({ open: true }); });

    expect(form.resetFields).toHaveBeenCalled();
  });

  it('resets icon state synchronously when opening in edit mode', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: makeIntegration(), form }),
    );

    expect(result.current.uploadedIconUrl).toBeNull();
    expect(result.current.fileList).toEqual([]);
  });

  it('calls form.setFieldsValue via setTimeout when opening in edit mode', () => {
    vi.useFakeTimers();
    try {
      const form = createMockForm();
      const integration = makeIntegration({ type: 'aap', name: 'AAP Production' });

      renderHook(() =>
        useIntegrationFormState({ open: true, editIntegration: integration, form }),
      );

      act(() => { vi.runAllTimers(); });

      expect(form.setFieldsValue).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'aap', name: 'AAP Production' }),
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it('resets icon when modal reopens in create mode', async () => {
    const form = createMockForm();
    const { result, rerender } = renderHook(
      ({ open }: { open: boolean }) =>
        useIntegrationFormState({ open, editIntegration: null, form }),
      { initialProps: { open: true } },
    );

    act(() => { result.current.setUploadedIconUrl('https://cdn.example.com/icon.png'); });
    act(() => { rerender({ open: false }); });
    expect(result.current.uploadedIconUrl).toBe('https://cdn.example.com/icon.png'); // not reset on close

    act(() => { rerender({ open: true }); });

    // Flush microtask from queueMicrotask
    await act(async () => { await Promise.resolve(); });

    expect(result.current.uploadedIconUrl).toBeNull();
  });

  // ---- 3.4 : initialisation en mode edit avec editIntegration ----

  it('returns editValues when open=true with editIntegration', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({
        open: true,
        editIntegration: makeIntegration({
          type: 'servicenow', name: 'ServiceNow Prod',
          base_url: 'https://sn.example.com', auth_flow: 'token',
          token_url: 'https://auth.example.com/token',
        }),
        form,
      }),
    );

    expect(result.current.editValues?.type).toBe('servicenow');
    expect(result.current.editValues?.name).toBe('ServiceNow Prod');
    expect(result.current.editValues?.base_url).toBe('https://sn.example.com');
    expect(result.current.editValues?.auth_flow).toBe('token');
    expect(result.current.editValues?.token_url).toBe('https://auth.example.com/token');
  });

  it('returns null editValues when open=false', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({ open: false, editIntegration: makeIntegration(), form }),
    );
    expect(result.current.editValues).toBeNull();
  });

  it('maps inventory_db config schema/table to editValues', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({
        open: true,
        editIntegration: makeIntegration({ config: { schema: 'MY_SCHEMA', table: 'MY_TABLE' } }),
        form,
      }),
    );

    expect(result.current.editValues?.schema).toBe('MY_SCHEMA');
    expect(result.current.editValues?.table).toBe('MY_TABLE');
  });

  it('serializes config.entities to config_advanced in editValues', () => {
    const form = createMockForm();
    const entities = { servers: { table: 'SERVERS' } };
    const { result } = renderHook(() =>
      useIntegrationFormState({
        open: true,
        editIntegration: makeIntegration({ config: { entities } }),
        form,
      }),
    );

    const parsed = JSON.parse(result.current.editValues?.config_advanced ?? '{}');
    expect(parsed.entities).toEqual(entities);
  });

  it('extracts scope from config for oauth2_client_credentials', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({
        open: true,
        editIntegration: makeIntegration({ auth_flow: 'oauth2_client_credentials', config: { scope: 'openid profile' } }),
        form,
      }),
    );
    expect(result.current.editValues?.scope).toBe('openid profile');
  });

  it('extracts header_name from config for api_key', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({
        open: true,
        editIntegration: makeIntegration({ auth_flow: 'api_key', config: { header_name: 'X-Auth-Token' } }),
        form,
      }),
    );
    expect(result.current.editValues?.header_name).toBe('X-Auth-Token');
  });

  // ---- Derived health state ----

  it('derives health fields from editIntegration when no localHealth', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({
        open: true,
        editIntegration: makeIntegration({
          health_status: 'error',
          health_checked_at: '2026-01-15T10:00:00Z',
          health_error_message: 'refused',
        }),
        form,
      }),
    );

    expect(result.current.healthStatus).toBe('error');
    expect(result.current.healthCheckedAt).toBe('2026-01-15T10:00:00Z');
    expect(result.current.healthErrorMessage).toBe('refused');
  });

  it('localHealth overrides editIntegration health fields', () => {
    const form = createMockForm();
    const integration = makeIntegration({ health_status: 'error', health_checked_at: '2026-01-15T10:00:00Z' });
    const { result } = renderHook(() =>
      useIntegrationFormState({
        open: true,
        editIntegration: integration,
        form,
      }),
    );

    act(() => {
      result.current.setLocalHealth({ status: 'ok', checked_at: '2026-01-20T12:00:00Z', error_message: null });
    });

    expect(result.current.healthStatus).toBe('ok');
    expect(result.current.healthCheckedAt).toBe('2026-01-20T12:00:00Z');
    expect(result.current.healthErrorMessage).toBeNull();
  });

  it('returns healthStatus="unknown" when no data available', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, form }),
    );

    expect(result.current.healthStatus).toBe('unknown');
    expect(result.current.healthCheckedAt).toBeNull();
    expect(result.current.healthErrorMessage).toBeNull();
  });

  // ---- 3.5 : flags calculés ----

  it('computes isInvalid=true and isSubmitDisabled=true when status="invalid"', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: makeIntegration({ status: 'invalid' }), form }),
    );

    expect(result.current.isInvalid).toBe(true);
    expect(result.current.isSubmitDisabled).toBe(true);
  });

  it('computes isDeprecated=true and isSubmitDisabled=false when status="deprecated"', () => {
    const form = createMockForm();
    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: makeIntegration({ status: 'deprecated' }), form }),
    );

    expect(result.current.isDeprecated).toBe(true);
    expect(result.current.isInvalid).toBe(false);
    expect(result.current.isSubmitDisabled).toBe(false);
  });

  it('computes isInventoryDb=true when watchedType is "inventory_db"', () => {
    mockFormWatchValues['type'] = 'inventory_db';
    const form = createMockForm();
    const { result } = renderHook(() => useIntegrationFormState({ open: true, form }));

    expect(result.current.isInventoryDb).toBe(true);
    expect(result.current.isVaultType).toBe(false);
  });

  it('computes isVaultType=true when watchedType is "vault"', () => {
    mockFormWatchValues['type'] = 'vault';
    const form = createMockForm();
    const { result } = renderHook(() => useIntegrationFormState({ open: true, form }));

    expect(result.current.isVaultType).toBe(true);
    expect(result.current.isInventoryDb).toBe(false);
  });

  it('normalizes type to lowercase for flag computation', () => {
    mockFormWatchValues['type'] = 'INVENTORY_DB';
    const form = createMockForm();
    const { result } = renderHook(() => useIntegrationFormState({ open: true, form }));

    expect(result.current.isInventoryDb).toBe(true);
  });

  it('computes isTokenFlow=true for token auth_flow', () => {
    mockFormWatchValues['auth_flow'] = 'token';
    const form = createMockForm();
    const { result } = renderHook(() => useIntegrationFormState({ open: true, form }));

    expect(result.current.isTokenFlow).toBe(true);
    expect(result.current.isOauth2Flow).toBe(false);
    expect(result.current.isApiKeyFlow).toBe(false);
  });

  it('computes isTokenFlow=true and isOauth2Flow=true for oauth2_client_credentials', () => {
    mockFormWatchValues['auth_flow'] = 'oauth2_client_credentials';
    const form = createMockForm();
    const { result } = renderHook(() => useIntegrationFormState({ open: true, form }));

    expect(result.current.isTokenFlow).toBe(true);
    expect(result.current.isOauth2Flow).toBe(true);
    expect(result.current.isApiKeyFlow).toBe(false);
  });

  it('computes isApiKeyFlow=true for api_key auth_flow', () => {
    mockFormWatchValues['auth_flow'] = 'api_key';
    const form = createMockForm();
    const { result } = renderHook(() => useIntegrationFormState({ open: true, form }));

    expect(result.current.isApiKeyFlow).toBe(true);
    expect(result.current.isTokenFlow).toBe(false);
    expect(result.current.isOauth2Flow).toBe(false);
  });

  it('computes isTokenFlow=true for basic_then_token auth_flow', () => {
    mockFormWatchValues['auth_flow'] = 'basic_then_token';
    const form = createMockForm();
    const { result } = renderHook(() => useIntegrationFormState({ open: true, form }));

    expect(result.current.isTokenFlow).toBe(true);
  });

  it('all flow flags are false when auth_flow is null', () => {
    const form = createMockForm();
    const { result } = renderHook(() => useIntegrationFormState({ open: true, form }));

    expect(result.current.isTokenFlow).toBe(false);
    expect(result.current.isOauth2Flow).toBe(false);
    expect(result.current.isApiKeyFlow).toBe(false);
  });

  // ---- 3.6 : handleTestConnection ----

  it('handleTestConnection calls testConnection and updates localHealth on success', async () => {
    const form = createMockForm();
    const onHealthChecked = vi.fn();
    const testResult: TestConnectionResponse = { status: 'ok', message: null, checked_at: '2026-01-20T12:00:00Z' };
    mockedTestConnection.mockResolvedValue(testResult);
    const integration = makeIntegration({ id: 42 });

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: integration, form, onHealthChecked }),
    );

    await act(async () => { await result.current.handleTestConnection(); });

    expect(mockedTestConnection).toHaveBeenCalledWith(42);
    expect(result.current.localHealth).toEqual({ status: 'ok', checked_at: '2026-01-20T12:00:00Z', error_message: null });
    expect(onHealthChecked).toHaveBeenCalledWith(42, testResult);
    expect(mockMessageSuccess).toHaveBeenCalledWith('Connexion réussie');
    expect(result.current.testLoading).toBe(false);
  });

  it('handleTestConnection shows error message on failed connection', async () => {
    const form = createMockForm();
    mockedTestConnection.mockResolvedValue({ status: 'error', message: 'Connection refused', checked_at: '2026-01-20T12:00:00Z' });
    const integration = makeIntegration({ id: 42 });

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: integration, form }),
    );

    await act(async () => { await result.current.handleTestConnection(); });

    expect(result.current.localHealth?.status).toBe('error');
    expect(mockMessageError).toHaveBeenCalledWith(expect.stringContaining('Connection refused'));
    expect(result.current.testLoading).toBe(false);
  });

  it('handleTestConnection shows ApiError message when service throws', async () => {
    const form = createMockForm();
    mockedTestConnection.mockRejectedValue(new ApiError('Network failure', 503));

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: makeIntegration({ id: 42 }), form }),
    );

    await act(async () => { await result.current.handleTestConnection(); });

    expect(mockMessageError).toHaveBeenCalledWith('Network failure');
    expect(result.current.testLoading).toBe(false);
    expect(result.current.localHealth).toBeNull();
  });

  it('handleTestConnection shows fallback error on unknown exception', async () => {
    const form = createMockForm();
    mockedTestConnection.mockRejectedValue(new Error('unexpected'));

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: makeIntegration({ id: 42 }), form }),
    );

    await act(async () => { await result.current.handleTestConnection(); });

    expect(mockMessageError).toHaveBeenCalledWith('Impossible de tester la connexion');
  });

  it('handleTestConnection does nothing when editIntegration is null', async () => {
    const form = createMockForm();

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: null, form }),
    );

    await act(async () => { await result.current.handleTestConnection(); });

    expect(mockedTestConnection).not.toHaveBeenCalled();
  });

  // ---- handleIconUpload ----

  it('handleIconUpload sets uploadedIconUrl and calls form.setFieldsValue on success', async () => {
    const form = createMockForm();
    const iconUrl = 'https://cdn.example.com/icons/test.png';
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ data: { icon_url: iconUrl } }),
    } as Response);

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: null, form }),
    );

    const file = new File(['data'], 'test.png', { type: 'image/png' });
    await act(async () => { await result.current.handleIconUpload(file); });

    expect(result.current.uploadedIconUrl).toBe(iconUrl);
    expect(form.setFieldsValue).toHaveBeenCalledWith({ icon: iconUrl });
    expect(mockMessageSuccess).toHaveBeenCalledWith('Icône uploadée avec succès');
    fetchSpy.mockRestore();
  });

  it('handleIconUpload shows error message on non-OK response', async () => {
    const form = createMockForm();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      json: async () => ({ error: { message: 'Fichier trop volumineux' } }),
    } as Response);

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: null, form }),
    );

    const file = new File(['data'], 'test.png', { type: 'image/png' });
    await act(async () => { await result.current.handleIconUpload(file); });

    expect(result.current.uploadedIconUrl).toBeNull();
    expect(mockMessageError).toHaveBeenCalledWith('Fichier trop volumineux');
    fetchSpy.mockRestore();
  });

  it('handleIconUpload shows fallback error message when response has no error.message', async () => {
    const form = createMockForm();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      json: async () => ({}),
    } as Response);

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: null, form }),
    );

    const file = new File(['data'], 'test.png', { type: 'image/png' });
    await act(async () => { await result.current.handleIconUpload(file); });

    expect(mockMessageError).toHaveBeenCalledWith("Échec de l'upload");
    fetchSpy.mockRestore();
  });

  it('handleIconUpload shows error on network failure', async () => {
    const form = createMockForm();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: null, form }),
    );

    const file = new File(['data'], 'test.png', { type: 'image/png' });
    await act(async () => { await result.current.handleIconUpload(file); });

    expect(mockMessageError).toHaveBeenCalledWith("Erreur lors de l'upload de l'icône");
    fetchSpy.mockRestore();
  });

  it('handleIconUpload sends Authorization header when accessToken is present', async () => {
    const form = createMockForm();
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ data: { icon_url: 'https://cdn.example.com/icon.png' } }),
    } as Response);

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: null, form }),
    );

    const file = new File(['data'], 'test.png', { type: 'image/png' });
    await act(async () => { await result.current.handleIconUpload(file); });

    const [, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect((options.headers as Record<string, string>)['Authorization']).toBe('Bearer test-token');
    fetchSpy.mockRestore();
  });

  it('sets testLoading=true during connection then false when done', async () => {
    const form = createMockForm();
    let resolveConnection!: (val: TestConnectionResponse) => void;
    mockedTestConnection.mockReturnValue(
      new Promise<TestConnectionResponse>((resolve) => { resolveConnection = resolve; }),
    );

    const { result } = renderHook(() =>
      useIntegrationFormState({ open: true, editIntegration: makeIntegration({ id: 42 }), form }),
    );

    act(() => { void result.current.handleTestConnection(); });
    expect(result.current.testLoading).toBe(true);

    await act(async () => {
      resolveConnection({ status: 'ok', message: null, checked_at: '2026-01-20T00:00:00Z' });
    });

    expect(result.current.testLoading).toBe(false);
  });
});
