/**
 * IntegrationForm — création/édition d'intégration (Story 2.28, 4.9, 13.1, 24.2, 27.11).
 * Story 24.2: Type restreint au catalogue backend (Select), actions disponibles, mode édition disabled, validation type actif.
 * Story 13.1: Si type = inventory_db, champs Schéma et Table (config) pour inventaire BD.
 * Story 27.11: credential_ref masqué si type vault, texte d'aide secret 0, champ secret_service_id pour types != vault.
 */

import { useEffect, useState } from 'react';
import { Form, Input, Modal, Alert, Select, Avatar, Space, Button, Upload, App, Tag } from 'antd';
import { useAuth } from '../../contexts/AuthContext';
import type { UploadFile } from 'antd';
import { UploadOutlined, ApiOutlined, InfoCircleOutlined, ExclamationCircleOutlined, WarningOutlined } from '@ant-design/icons';
import type { AuthFlow, IntegrationCreate, IntegrationUpdate, IntegrationResponse } from '../../types/api';
import { AUTH_FLOW_LABELS } from '../../types/api';
import { getIconUrl } from '../../utils/iconUrl';
import { useIntegrationTypes } from '../../hooks/useIntegrationTypes';
import { useVaultIntegrations } from '../../hooks/useVaultIntegrations';
import { AvailableActionsPanel } from './AvailableActionsPanel';

/** Auth flow options for Select (Story 4.9 AC2). */
const AUTH_FLOW_OPTIONS: { value: AuthFlow; label: string }[] = (
  Object.entries(AUTH_FLOW_LABELS) as [AuthFlow, string][]
).map(([value, label]) => ({ value, label }));

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
}

export interface IntegrationFormProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (values: IntegrationCreate | IntegrationUpdate) => Promise<IntegrationResponse | void>;
  loading?: boolean;
  error?: string | null;
  editIntegration?: IntegrationResponse | null;
  onSuccess?: (integration: IntegrationResponse) => void;
}

/** URL pattern: must start with http(s):// and have a valid hostname. */
const URL_PATTERN = /^https?:\/\/[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9]/;

export function IntegrationForm({
  open,
  onCancel,
  onSubmit,
  loading,
  error,
  editIntegration,
  onSuccess,
}: IntegrationFormProps) {
  const { message } = App.useApp();
  const { accessToken } = useAuth();
  const [form] = Form.useForm<IntegrationFormValues>();
  const isEdit = !!editIntegration;
  const [uploadedIconUrl, setUploadedIconUrl] = useState<string | null>(null);
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  // Story 24.2 AC1: Fetch integration types from backend catalogue
  const { types: integrationTypes, loading: loadingTypes, isFallback } = useIntegrationTypes();

  const watchIcon = Form.useWatch('icon', form);
  const watchType = Form.useWatch('type', form);
  const isInventoryDb = (watchType ?? '').trim().toLowerCase() === 'inventory_db';
  const isVaultType = (watchType ?? '').trim().toLowerCase() === 'vault';

  // Story 27.11: Load Vault integrations for secret service dropdown
  const { vaultIntegrations } = useVaultIntegrations();

  // Story 24.3: Status-based UI restrictions
  const editStatus = editIntegration?.status;
  const isInvalid = editStatus === 'invalid';
  const isDeprecated = editStatus === 'deprecated';
  const isSubmitDisabled = isInvalid;

  // Story 24.2 AC3: Find selected type data for actions display
  const selectedTypeData = integrationTypes.find((t) => t.code === watchType) ?? null;

  // Valeurs pour préremplir en édition (stable pour initialValues / key)
  const editConfig = editIntegration?.config as { schema?: string; table?: string; entities?: unknown; flat_table?: unknown } | undefined;
  const editValues =
    open && editIntegration
      ? {
          type: editIntegration.type,
          name: editIntegration.name,
          base_url: editIntegration.base_url,
          credential_ref: editIntegration.credential_ref ?? undefined,
          icon: editIntegration.icon ?? undefined,
          auth_flow: editIntegration.auth_flow ?? undefined,
          schema: editConfig?.schema ?? undefined,
          table: editConfig?.table ?? undefined,
          config_advanced:
            editConfig?.entities != null || editConfig?.flat_table != null
              ? JSON.stringify(editConfig, null, 2)
              : undefined,
          secret_service_id: editIntegration.secret_service_id ?? undefined,
        }
      : null;

  useEffect(() => {
    if (!open) return;
    if (editIntegration) {
      setUploadedIconUrl(null);
      setFileList([]);
      const t = setTimeout(() => {
        const cfg = editIntegration.config as {
          schema?: string;
          table?: string;
          entities?: Record<string, unknown>;
          flat_table?: Record<string, unknown>;
        } | undefined;
        form.setFieldsValue({
          type: editIntegration.type,
          name: editIntegration.name,
          base_url: editIntegration.base_url,
          credential_ref: editIntegration.credential_ref ?? undefined,
          icon: editIntegration.icon ?? undefined,
          auth_flow: editIntegration.auth_flow ?? undefined,
          schema: cfg?.schema ?? undefined,
          table: cfg?.table ?? undefined,
          config_advanced:
            cfg?.entities != null || cfg?.flat_table != null
              ? JSON.stringify(cfg, null, 2)
              : undefined,
          secret_service_id: editIntegration.secret_service_id ?? undefined,
        });
      }, 0);
      return () => clearTimeout(t);
    } else {
      form.resetFields();
      queueMicrotask(() => {
        setUploadedIconUrl(null);
        setFileList([]);
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
      });
    }
  }, [open, editIntegration, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();

      // Story 24.2 AC7: Validate selected type is active
      const typeData = integrationTypes.find((t) => t.code === values.type);

      if (!isEdit) {
        // LOW-2 fix: Specific error messages
        if (!typeData) {
          message.error("Ce type d'intégration n'existe pas");
          return;
        }
        if (!typeData.is_active) {
          message.error("Ce type d'intégration est inactif et ne peut plus être utilisé");
          return;
        }
      } else {
        // MEDIUM-5 fix: Warn if editing an integration with inactive type
        if (typeData && !typeData.is_active) {
          message.warning("Attention : le type de cette intégration est marqué comme inactif");
        }
      }

      // Always send icon so backend persists it (undefined is omitted by JSON.stringify).
      // Create: uploadedIconUrl or form URL field. Edit: same, or fallback to existing integration icon.
      const effectiveIcon =
        uploadedIconUrl ??
        values.icon?.trim() ??
        (isEdit ? (editIntegration?.icon ?? null) : null) ??
        null;
      const payload: IntegrationCreate | IntegrationUpdate = {
        type: values.type,
        name: values.name.trim(),
        base_url: values.base_url.trim(),
        credential_ref: isVaultType ? null : (values.credential_ref?.trim() || null),
        icon: effectiveIcon ?? null,
        auth_flow: values.auth_flow || null,
        secret_service_id: isVaultType ? null : (values.secret_service_id || null),
      };
      if (isInventoryDb) {
        if (values.config_advanced?.trim()) {
          try {
            const parsed = JSON.parse(values.config_advanced.trim()) as Record<string, unknown>;
            if (typeof parsed === 'object' && parsed !== null && (parsed.entities != null || parsed.flat_table != null)) {
              (payload as IntegrationCreate).config = parsed;
            } else {
              message.warning('Config JSON : utilisez "entities" (multi-tables) ou "flat_table" (une table). Voir le guide de mapping inventaire.');
              return;
            }
          } catch {
            message.error('Config JSON invalide. Vérifiez la syntaxe.');
            return;
          }
        } else if (values.schema?.trim() || values.table?.trim()) {
          (payload as IntegrationCreate).config = {
            schema: values.schema?.trim() || null,
            table: values.table?.trim() || null,
          };
        }
      }
      const res = await onSubmit(payload);
      if (res && onSuccess) onSuccess(res);
    } catch (e) {
      const isValidation = e && typeof e === 'object' && 'errorFields' in e;
      if (isValidation) return;
      throw e;
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

  const iconSrc = getIconUrl(uploadedIconUrl || watchIcon);
  const iconPreview = iconSrc ? (
    <Avatar src={iconSrc} shape="square" size={32} icon={<ApiOutlined />} />
  ) : (
    <Avatar shape="square" size={32} icon={<ApiOutlined />} />
  );

  // Story 29.1: Build Select options grouped by integration_role
  const activeTypes = integrationTypes.filter((t) => t.is_active);
  const platforms = activeTypes.filter((t) => t.integration_role === 'platform');
  const services = activeTypes.filter((t) => t.integration_role === 'service');
  const ungrouped = activeTypes.filter((t) => !t.integration_role);

  const typeOptions = [
    ...(platforms.length > 0
      ? [{ label: 'Plateformes', options: platforms.map((t) => ({ value: t.code, label: t.name })) }]
      : []),
    ...(services.length > 0
      ? [{ label: 'Services', options: services.map((t) => ({ value: t.code, label: t.name })) }]
      : []),
    // Fix MEDIUM-5: Wrap ungrouped in a consistent group structure
    ...(ungrouped.length > 0
      ? [{ label: 'Autres', options: ungrouped.map((t) => ({ value: t.code, label: t.name })) }]
      : []),
  ];

  return (
    <Modal
      open={open}
      title={isEdit ? "Modifier l'intégration" : 'Nouvelle intégration'}
      onCancel={onCancel}
      destroyOnHidden
      footer={
        <Space>
          <Button onClick={onCancel} disabled={loading}>
            Annuler
          </Button>
          <Button type="primary" onClick={handleSubmit} loading={loading} disabled={isSubmitDisabled}>
            {isEdit ? 'Enregistrer' : 'Créer'}
          </Button>
        </Space>
      }
    >
      {error && (
        <Alert type="error" title={error} style={{ marginBottom: 16 }} showIcon />
      )}
      {/* Story 24.3: Alert if integration is invalid */}
      {isEdit && isInvalid && (
        <Alert
          type="error"
          showIcon
          icon={<ExclamationCircleOutlined />}
          message="Intégration invalide"
          description={`Cette intégration est invalide. Le type '${editIntegration?.type}' n'existe pas dans le catalogue backend. Veuillez contacter un administrateur. Les modifications ne sont pas autorisées pour les intégrations invalides.`}
          style={{ marginBottom: 16 }}
        />
      )}
      {/* Story 24.3: Alert if integration is deprecated */}
      {isEdit && isDeprecated && (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          message="Intégration dépréciée"
          description={`Attention : le type de cette intégration ('${editIntegration?.type}') est déprécié. Il est recommandé de migrer vers un type supporté. Vous pouvez encore modifier cette intégration, mais son utilisation dans de nouveaux workflows sera bloquée.`}
          style={{ marginBottom: 16 }}
        />
      )}
      {/* Story 24.2 AC2: Warning when using fallback types */}
      {isFallback && (
        <Alert
          type="warning"
          title="Impossible de charger les types depuis le backend. Mode dégradé activé — la liste peut être incomplète."
          style={{ marginBottom: 16 }}
          showIcon
        />
      )}
      <Form
        form={form}
        layout="vertical"
        preserve={false}
        initialValues={
          editValues ?? {
            type: undefined,
            name: '',
            base_url: '',
            credential_ref: undefined,
            icon: null,
            auth_flow: undefined,
            schema: undefined,
            table: undefined,
            config_advanced: undefined,
            secret_service_id: undefined,
          }
        }
        key={editIntegration ? `edit-${editIntegration.id}` : 'create'}
      >
        {/* Story 24.2 AC2: Select replaces AutoComplete */}
        <Form.Item
          name="type"
          label="Type d'intégration"
          rules={[{ required: true, message: "Veuillez sélectionner un type d'intégration" }]}
        >
          <Select
            placeholder={loadingTypes ? 'Chargement des types...' : "Sélectionner un type d'intégration"}
            loading={loadingTypes}
            disabled={isEdit || loadingTypes}
            showSearch
            optionFilterProp="label"
            options={typeOptions}
            aria-label="Type d'intégration"
          />
        </Form.Item>

        {/* Story 29.1: Badge showing integration role */}
        {selectedTypeData?.integration_role && (
          <div style={{ marginBottom: 12 }}>
            <Tag color={selectedTypeData.integration_role === 'platform' ? 'blue' : 'green'}>
              {selectedTypeData.integration_role === 'platform' ? "Plateforme d'exécution" : 'Service consommé'}
            </Tag>
          </div>
        )}

        {/* Story 24.2 AC6: Info message when type is disabled in edit mode */}
        {isEdit && (
          <Alert
            type="info"
            showIcon
            icon={<InfoCircleOutlined />}
            message="Le type d'une intégration ne peut pas être modifié après sa création"
            style={{ marginBottom: 16 }}
          />
        )}

        {/* Story 24.2 AC3, AC4, AC8: Available actions panel */}
        <AvailableActionsPanel selectedType={selectedTypeData} />

        <Form.Item
          name="name"
          label="Nom"
          rules={[
            { required: true, message: 'Le nom est requis' },
            { whitespace: true, message: 'Le nom ne peut pas être vide' },
          ]}
        >
          <Input placeholder="Nom de l'intégration" aria-label="Nom" />
        </Form.Item>
        {isInventoryDb && (
          <>
            <Form.Item
              name="schema"
              label="Schéma BD"
              tooltip="Nom du schéma Oracle contenant la table/vue d'inventaire (ex: DBOPS_INVENTORY). Vide = défaut backend."
              rules={[{ pattern: /^$|^[A-Za-z_][A-Za-z0-9_]*$/, message: 'Alphanumérique et underscore uniquement' }]}
            >
              <Input placeholder="ex: DBOPS_INVENTORY" aria-label="Schéma BD" />
            </Form.Item>
            <Form.Item
              name="table"
              label="Table ou vue"
              tooltip="Nom de la table ou vue avec colonnes NAME, ENVIRONMENT, TYPE. Vide = défaut backend."
              rules={[{ pattern: /^$|^[A-Za-z_][A-Za-z0-9_]*$/, message: 'Alphanumérique et underscore uniquement' }]}
            >
              <Input placeholder="ex: INVENTORY_TARGETS" aria-label="Table ou vue" />
            </Form.Item>
            <Form.Item
              name="config_advanced"
              label="Config JSON (avancé)"
              tooltip="Optionnel. Pour plusieurs tables : servers, instances (table de jointure avec server_id et db_id), databases. Les concepts server_ref et db_ref dans instances mappent vers vos colonnes (ex. SERVER_ID, DB_ID). Si rempli, remplace Schéma BD / Table ou vue. Voir docs/inventory-mapping-guide.md."
            >
              <Input.TextArea
                placeholder={`{\n  "entities": {\n    "servers": { "table": "DBOPS_SERVERS", "id_column": "SERVER_ID", "columns": { "name": "HOSTNAME", "environment": "ENV", "engine_type": "ENGINE" } },\n    "instances": { "table": "DBOPS_INSTANCES", "id_column": "INSTANCE_ID", "columns": { "name": "INSTANCE_NAME", "environment": "ENV", "server_ref": "SERVER_ID", "db_ref": "DB_ID" } },\n    "databases": { "table": "DBOPS_DATABASES", "id_column": "DB_ID", "columns": { "name": "DB_NAME", "environment": "ENV" } }\n  }\n}`}
                rows={8}
                aria-label="Config JSON avancé"
                style={{ fontFamily: 'monospace', fontSize: 12 }}
              />
            </Form.Item>
          </>
        )}
        <Form.Item
          name="base_url"
          label="URL de base"
          rules={[
            {
              required: true,
              validator: (_, v) => {
                const s = (v ?? '').toString().trim();
                if (!s) return Promise.reject(new Error("L'URL de base est requise"));
                if (!URL_PATTERN.test(s)) {
                  return Promise.reject(new Error("L'URL doit être valide (commencer par http:// ou https://)"));
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <Input placeholder="https://example.com/api" aria-label="URL de base" />
        </Form.Item>
        {/* Story 27.11: credential_ref masqué pour type vault, texte d'aide pour types non-vault */}
        {isVaultType ? (
          <Alert
            type="info"
            showIcon
            icon={<InfoCircleOutlined />}
            message="Authentification Vault (secret 0)"
            description="L'authentification à Vault utilise le secret 0 fourni par les variables d'environnement (VAULT_TOKEN ou VAULT_ROLE_ID + VAULT_SECRET_ID). Aucun credential n'est stocké en base. Voir la documentation vault-bootstrap-guide pour la configuration."
            style={{ marginBottom: 16 }}
          />
        ) : (
          <Form.Item
            name="credential_ref"
            label="Référence credentials"
            help="Référence vers un secret Vault (ex: vault:secret/data/aap/prod#token). Le secret est résolu au moment de l'exécution. Aucun secret n'est stocké en base."
          >
            <Input
              placeholder="vault:secret/data/aap/prod#token"
              aria-label="Référence credentials"
            />
          </Form.Item>
        )}
        {/* Story 27.11: Sélection du service de secrets pour types non-vault */}
        {!isVaultType && vaultIntegrations.length > 0 && (
          <Form.Item
            name="secret_service_id"
            label="Service de secrets"
            help="Sélectionnez l'instance Vault utilisée pour résoudre les secrets de cette intégration (optionnel, défaut = Vault principal via variables d'environnement)"
          >
            <Select
              placeholder="Vault principal (défaut)"
              allowClear
              options={vaultIntegrations.map((v) => ({ label: v.name, value: v.id }))}
              aria-label="Service de secrets"
            />
          </Form.Item>
        )}
        <Form.Item name="auth_flow" label="Flow d'authentification">
          <Select
            placeholder="Sélectionner un flow (optionnel)"
            options={AUTH_FLOW_OPTIONS}
            allowClear
            aria-label="Flow d'authentification"
          />
        </Form.Item>
        <Form.Item label="Icône" tooltip="Uploader une icône ou saisir une URL">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Upload
              accept="image/*"
              maxCount={1}
              fileList={fileList}
              beforeUpload={(file) => {
                const isImage = file.type.startsWith('image/');
                if (!isImage) {
                  message.error('Vous ne pouvez uploader que des images!');
                  return Upload.LIST_IGNORE;
                }
                const isLt2M = file.size / 1024 / 1024 < 2;
                if (!isLt2M) {
                  message.error("L'image doit faire moins de 2MB!");
                  return Upload.LIST_IGNORE;
                }
                handleIconUpload(file);
                setFileList([file]);
                return false;
              }}
              onRemove={() => {
                setFileList([]);
                setUploadedIconUrl(null);
                form.setFieldsValue({ icon: undefined });
              }}
            >
              <Button icon={<UploadOutlined />}>Uploader une icône</Button>
            </Upload>
            <Form.Item name="icon" noStyle>
              <Input
                placeholder="...ou saisir URL de l'icône"
                aria-label="URL icône"
              />
            </Form.Item>
          </Space>
        </Form.Item>
        <Form.Item label="Aperçu" colon={false} style={{ marginBottom: 0 }}>
          <Space align="center">{iconPreview}</Space>
        </Form.Item>
      </Form>
    </Modal>
  );
}
