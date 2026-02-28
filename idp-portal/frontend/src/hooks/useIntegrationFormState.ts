/**
 * useIntegrationFormState — Gestion centralisée de l'état de IntegrationForm (Story 54.8).
 * Extrait de IntegrationForm.tsx : états (icon upload, health check),
 * Form.useWatch, flags dérivés, et useEffect d'init/reset.
 */
import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';
import { Form, App } from 'antd';
import type { FormInstance } from 'antd';
import type { UploadFile } from 'antd';
import type { AuthFlow, IntegrationResponse, HealthStatus, TestConnectionResponse } from '../types/api';
import { useAuth } from '../contexts/AuthContext';
import { testConnection } from '../services/integrations_service';
import { ApiError } from '../services/api_client';

/** Extract string from config, avoiding fragile double casts. */
function getConfigString(config: Record<string, unknown> | undefined, key: string): string | undefined {
  const value = config?.[key];
  return typeof value === 'string' ? value : undefined;
}

/** Build the form values object from an IntegrationResponse (single source of truth for init & reset). */
function buildFormValues(integration: IntegrationResponse): IntegrationFormValues {
  const cfg = integration.config as {
    schema?: string;
    table?: string;
    entities?: Record<string, unknown>;
    flat_table?: Record<string, unknown>;
  } | undefined;
  return {
    type: integration.type,
    name: integration.name,
    base_url: integration.base_url,
    credential_ref: integration.credential_ref ?? undefined,
    icon: integration.icon ?? undefined,
    auth_flow: integration.auth_flow ?? undefined,
    schema: cfg?.schema ?? undefined,
    table: cfg?.table ?? undefined,
    config_advanced:
      cfg?.entities != null || cfg?.flat_table != null
        ? JSON.stringify(cfg, null, 2)
        : undefined,
    secret_service_id: integration.secret_service_id ?? undefined,
    token_url: integration.token_url ?? undefined,
    scope: integration.auth_flow === 'oauth2_client_credentials'
      ? getConfigString(integration.config as Record<string, unknown>, 'scope')
      : undefined,
    header_name: integration.auth_flow === 'api_key'
      ? getConfigString(integration.config as Record<string, unknown>, 'header_name')
      : undefined,
  };
}

export interface LocalHealthState {
  status: HealthStatus;
  checked_at: string | null;
  error_message: string | null;
}

export interface IntegrationFormValues {
  type: string;
  name: string;
  base_url: string;
  credential_ref?: string | null;
  icon?: string | null;
  auth_flow?: AuthFlow | null;
  schema?: string | null;
  table?: string | null;
  config_advanced?: string | null;
  secret_service_id?: number | null;
  token_url?: string | null;
  scope?: string | null;
  header_name?: string | null;
}

export interface UseIntegrationFormStateParams {
  open: boolean;
  editIntegration?: IntegrationResponse | null;
  form: FormInstance<IntegrationFormValues>;
  onHealthChecked?: (id: number, result: TestConnectionResponse) => void;
}

export interface UseIntegrationFormStateReturn {
  // Icon upload
  uploadedIconUrl: string | null;
  setUploadedIconUrl: Dispatch<SetStateAction<string | null>>;
  fileList: UploadFile[];
  setFileList: Dispatch<SetStateAction<UploadFile[]>>;
  handleIconUpload: (file: File) => Promise<void>;

  // Health check (Story 51.4)
  localHealth: LocalHealthState | null;
  setLocalHealth: Dispatch<SetStateAction<LocalHealthState | null>>;
  testLoading: boolean;
  handleTestConnection: () => Promise<void>;
  healthStatus: HealthStatus;
  healthCheckedAt: string | null;
  healthErrorMessage: string | null;

  // Watched form values
  watchedType: string;
  watchedAuthFlow: AuthFlow | null;
  watchedIcon: string | null;

  // Computed flags
  isInventoryDb: boolean;
  isVaultType: boolean;
  isTokenFlow: boolean;
  isOauth2Flow: boolean;
  isApiKeyFlow: boolean;
  isInvalid: boolean;
  isDeprecated: boolean;
  isSubmitDisabled: boolean;

  // Edit mode values for Form initialValues
  editValues: IntegrationFormValues | null;
}

export function useIntegrationFormState({
  open,
  editIntegration,
  form,
  onHealthChecked,
}: UseIntegrationFormStateParams): UseIntegrationFormStateReturn {
  const { message } = App.useApp();
  const { accessToken } = useAuth();

  // --- Icon upload state ---
  const [uploadedIconUrl, setUploadedIconUrl] = useState<string | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  // --- Health check state (Story 51.4) ---
  const [localHealth, setLocalHealth] = useState<LocalHealthState | null>(null);
  const [testLoading, setTestLoading] = useState(false);

  // Reset local health when modal closes or integration changes
  useEffect(() => {
    setLocalHealth(null);
  }, [open, editIntegration]);

  const handleTestConnection = async () => {
    if (!editIntegration?.id) return;
    setTestLoading(true);
    try {
      const result = await testConnection(editIntegration.id);
      setLocalHealth({
        status: result.status,
        checked_at: result.checked_at,
        error_message: result.message,
      });
      onHealthChecked?.(editIntegration.id, result);
      if (result.status === 'ok') {
        message.success('Connexion réussie');
      } else {
        message.error(`Connexion échouée : ${result.message ?? 'Erreur inconnue'}`);
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Impossible de tester la connexion';
      message.error(msg);
    } finally {
      setTestLoading(false);
    }
  };

  const handleIconUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const headers: Record<string, string> = {};
      if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

      const response = await fetch('/api/v1/admin/integrations/upload-icon/', {
        method: 'POST',
        body: formData,
        credentials: 'include',
        headers,
      });

      if (!response.ok) {
        const errorData = await response.json();
        message.error(errorData.error?.message || "Échec de l'upload");
        return;
      }

      const result = await response.json();
      const iconUrl = result.data?.icon_url;
      if (iconUrl) {
        setUploadedIconUrl(iconUrl);
        form.setFieldsValue({ icon: iconUrl });
        message.success('Icône uploadée avec succès');
      }
    } catch {
      message.error("Erreur lors de l'upload de l'icône");
    }
  };

  // --- Watched form values ---
  const watchedIcon = Form.useWatch('icon', form) ?? null;
  const watchedType = Form.useWatch('type', form) ?? '';
  const watchedAuthFlow = (Form.useWatch('auth_flow', form) as AuthFlow | undefined) ?? null;

  // --- Computed flags ---
  const normalizedType = watchedType.trim().toLowerCase();
  const isInventoryDb = normalizedType === 'inventory_db';
  const isVaultType = normalizedType === 'vault';
  const isTokenFlow = watchedAuthFlow === 'token' || watchedAuthFlow === 'basic_then_token' || watchedAuthFlow === 'oauth2_client_credentials';
  const isOauth2Flow = watchedAuthFlow === 'oauth2_client_credentials';
  const isApiKeyFlow = watchedAuthFlow === 'api_key';

  const editStatus = editIntegration?.status;
  const isInvalid = editStatus === 'invalid';
  const isDeprecated = editStatus === 'deprecated';
  // Deprecated integrations can still be edited/saved; only invalid ones block submission.
  const isSubmitDisabled = isInvalid;

  // --- Derived health state ---
  const healthStatus: HealthStatus = localHealth?.status ?? editIntegration?.health_status ?? 'unknown';
  const healthCheckedAt = localHealth?.checked_at ?? editIntegration?.health_checked_at ?? null;
  const healthErrorMessage = localHealth?.error_message ?? editIntegration?.health_error_message ?? null;

  // --- Edit mode values for Form initialValues ---
  const editValues: IntegrationFormValues | null =
    open && editIntegration ? buildFormValues(editIntegration) : null;

  // --- Init / reset effect ---
  useEffect(() => {
    if (!open) return;
    if (editIntegration) {
      setUploadedIconUrl(null);
      setFileList((prev) => (prev.length === 0 ? prev : []));
      const t = setTimeout(() => {
        form.setFieldsValue(buildFormValues(editIntegration));
      }, 0);
      return () => clearTimeout(t);
    } else {
      let cancelled = false;
      form.resetFields();
      queueMicrotask(() => {
        if (cancelled) return;
        setUploadedIconUrl(null);
        setFileList((prev) => (prev.length === 0 ? prev : []));
      });
      form.setFieldsValue({
        type: undefined,
        name: '',
        base_url: '',
        credential_ref: undefined,
        icon: undefined,
        auth_flow: undefined,
        schema: undefined,
        table: undefined,
        config_advanced: undefined,
        secret_service_id: undefined,
        token_url: undefined,
        scope: undefined,
        header_name: undefined,
      });
      return () => { cancelled = true; };
    }
  }, [open, editIntegration, form]);

  return {
    uploadedIconUrl,
    setUploadedIconUrl,
    fileList,
    setFileList,
    handleIconUpload,
    localHealth,
    setLocalHealth,
    testLoading,
    handleTestConnection,
    healthStatus,
    healthCheckedAt,
    healthErrorMessage,
    watchedType,
    watchedAuthFlow,
    watchedIcon,
    isInventoryDb,
    isVaultType,
    isTokenFlow,
    isOauth2Flow,
    isApiKeyFlow,
    isInvalid,
    isDeprecated,
    isSubmitDisabled,
    editValues,
  };
}
