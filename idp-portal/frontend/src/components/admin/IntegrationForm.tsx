/**
 * IntegrationForm — création/édition d'intégration (Story 2.28, 4.9, 13.1, 24.2, 27.11, 31.11).
 * Story 54.8: Logique d'état extraite dans useIntegrationFormState.
 */

import { Form, Input, Modal, Alert, Select, Avatar, Space, Button, Upload, App, Tag, Tooltip } from 'antd';
import { UploadOutlined, ApiOutlined, InfoCircleOutlined, ExclamationCircleOutlined, WarningOutlined, ThunderboltOutlined, FileTextOutlined } from '@ant-design/icons';
import type { AuthFlow, IntegrationCreate, IntegrationUpdate, IntegrationResponse, TestConnectionResponse } from '../../types/api';
import { AUTH_FLOW_LABELS } from '../../types/api';
import { getIconUrl } from '../../utils/iconUrl';
import { HEALTH_CONFIG } from '../../utils/healthConfig';
import { useIntegrationTypes } from '../../hooks/useIntegrationTypes';
import { useVaultIntegrations } from '../../hooks/useVaultIntegrations';
import { formatLocalDateTime } from '../../utils/dateFormat';
import { AvailableActionsPanel } from './AvailableActionsPanel';
import { useIntegrationFormState } from '../../hooks/useIntegrationFormState';
import type { IntegrationFormValues } from '../../hooks/useIntegrationFormState';

export type { IntegrationFormValues };

/** Auth flow options for Select (Story 4.9 AC2). */
const AUTH_FLOW_OPTIONS: { value: AuthFlow; label: string }[] = (
  Object.entries(AUTH_FLOW_LABELS) as [AuthFlow, string][]
).map(([value, label]) => ({ value, label }));

export interface IntegrationFormProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (values: IntegrationCreate | IntegrationUpdate) => Promise<IntegrationResponse | void>;
  loading?: boolean;
  error?: string | null;
  editIntegration?: IntegrationResponse | null;
  onSuccess?: (integration: IntegrationResponse) => void;
  onHealthChecked?: (id: number, result: TestConnectionResponse) => void;
}

/** URL pattern: must start with http(s):// and have a valid hostname. */
const URL_PATTERN = /^https?:\/\/[a-zA-Z0-9][-a-zA-Z0-9.]*[a-zA-Z0-9]/;

/** Exemple multi-tables (servers, instances, databases) — docs/inventory-mapping-guide.md */
const INVENTORY_CONFIG_ENTITIES = `{
  "entities": {
    "servers": {
      "table": "DBOPS_SERVERS",
      "id_column": "SERVER_ID",
      "columns": {
        "name": "HOSTNAME",
        "environment": "ENV",
        "engine_type": "ENGINE"
      }
    },
    "instances": {
      "table": "DBOPS_INSTANCES",
      "id_column": "INSTANCE_ID",
      "columns": {
        "name": "INSTANCE_NAME",
        "environment": "ENV",
        "server_ref": "SERVER_ID",
        "db_ref": "DB_ID"
      }
    },
    "databases": {
      "table": "DBOPS_DATABASES",
      "id_column": "DB_ID",
      "columns": {
        "name": "DB_NAME",
        "environment": "ENV"
      }
    }
  }
}`;

/** Exemple une seule table — docs/inventory-mapping-guide.md */
const INVENTORY_CONFIG_FLAT = `{
  "flat_table": {
    "table": "DBOPS_INVENTORY",
    "columns": {
      "name": "NAME",
      "environment": "ENVIRONMENT",
      "type": "TYPE"
    }
  }
}`;

export function IntegrationForm({
  open, onCancel, onSubmit, loading, error, editIntegration, onSuccess, onHealthChecked,
}: IntegrationFormProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<IntegrationFormValues>();
  const isEdit = !!editIntegration;

  const {
    uploadedIconUrl, setUploadedIconUrl, fileList, setFileList, handleIconUpload,
    testLoading, handleTestConnection, healthStatus, healthCheckedAt, healthErrorMessage,
    watchedType, watchedIcon, isInventoryDb, isVaultType, isTokenFlow, isOauth2Flow, isApiKeyFlow,
    isInvalid, isDeprecated, isSubmitDisabled, editValues,
  } = useIntegrationFormState({ open, editIntegration, form, onHealthChecked });

  const { types: integrationTypes, loading: loadingTypes, isFallback } = useIntegrationTypes();
  const { vaultIntegrations } = useVaultIntegrations();
  const selectedTypeData = integrationTypes.find((t) => t.code === watchedType) ?? null;

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const typeData = integrationTypes.find((t) => t.code === values.type);
      if (!isEdit) {
        if (!typeData) { message.error("Ce type d'intégration n'existe pas"); return; }
        if (!typeData.is_active) { message.error("Ce type d'intégration est inactif et ne peut plus être utilisé"); return; }
      } else if (typeData && !typeData.is_active) {
        message.warning("Attention : le type de cette intégration est marqué comme inactif");
      }
      const effectiveIcon = uploadedIconUrl ?? values.icon?.trim() ?? (isEdit ? (editIntegration?.icon ?? null) : null) ?? null;
      const payload: IntegrationCreate | IntegrationUpdate = {
        type: values.type, name: values.name.trim(), base_url: values.base_url.trim(),
        credential_ref: isVaultType ? null : (values.credential_ref?.trim() || null),
        icon: effectiveIcon ?? null, auth_flow: values.auth_flow || null,
        secret_service_id: isVaultType ? null : (values.secret_service_id || null),
        token_url: isTokenFlow ? (values.token_url?.trim() || null) : null,
      };
      if (!isInventoryDb) {
        if (isOauth2Flow) payload.config = { scope: values.scope?.trim() || null };
        else if (isApiKeyFlow) payload.config = { header_name: values.header_name?.trim() || null };
      }
      if (isInventoryDb) {
        const schemaVal = values.schema?.trim() || null;
        const tableVal = values.table?.trim() || null;
        let config: Record<string, unknown> = {};
        if (values.config_advanced?.trim()) {
          try {
            const parsed = JSON.parse(values.config_advanced.trim()) as Record<string, unknown>;
            if (typeof parsed === 'object' && parsed !== null && (parsed.entities != null || parsed.flat_table != null)) {
              config = { ...parsed };
            } else {
              message.warning('Config JSON : utilisez "entities" (multi-tables) ou "flat_table" (une table). Voir le guide de mapping inventaire.');
              return;
            }
          } catch { message.error('Config JSON invalide. Vérifiez la syntaxe.'); return; }
        }
        if (schemaVal != null || tableVal != null) { config.schema = schemaVal; config.table = tableVal; }
        if (Object.keys(config).length > 0) (payload as IntegrationCreate).config = config;
      }
      const res = await onSubmit(payload);
      if (res && onSuccess) onSuccess(res);
    } catch (e) {
      if (e && typeof e === 'object' && 'errorFields' in e) return;
      throw e;
    }
  };

  const iconSrc = getIconUrl(uploadedIconUrl || watchedIcon);
  const iconPreview = <Avatar src={iconSrc || undefined} shape="square" size={32} icon={<ApiOutlined />} />;
  const activeTypes = integrationTypes.filter((t) => t.is_active);
  const platforms = activeTypes.filter((t) => t.integration_role === 'platform');
  const services = activeTypes.filter((t) => t.integration_role === 'service');
  const ungrouped = activeTypes.filter((t) => !t.integration_role);
  const typeOptions = [
    ...(platforms.length > 0 ? [{ label: 'Plateformes', options: platforms.map((t) => ({ value: t.code, label: t.name })) }] : []),
    ...(services.length > 0 ? [{ label: 'Services', options: services.map((t) => ({ value: t.code, label: t.name })) }] : []),
    ...(ungrouped.length > 0 ? [{ label: 'Autres', options: ungrouped.map((t) => ({ value: t.code, label: t.name })) }] : []),
  ];
  const defaultFormValues: IntegrationFormValues = {
    type: '', name: '', base_url: '', credential_ref: undefined, icon: null, auth_flow: undefined,
    schema: undefined, table: undefined, config_advanced: undefined, secret_service_id: undefined,
    token_url: undefined, scope: undefined, header_name: undefined,
  };

  return (
    <Modal open={open} title={isEdit ? "Modifier l'intégration" : 'Nouvelle intégration'} onCancel={onCancel} destroyOnHidden
      footer={<Space>
        <Button onClick={onCancel} disabled={loading}>Annuler</Button>
        <Button type="primary" onClick={handleSubmit} loading={loading} disabled={isSubmitDisabled}>{isEdit ? 'Enregistrer' : 'Créer'}</Button>
      </Space>}>
      {error && <Alert type="error" title={error} style={{ marginBottom: 16 }} showIcon />}
      {isEdit && isInvalid && (
        <Alert type="error" showIcon icon={<ExclamationCircleOutlined />} title="Intégration invalide"
          description={`Cette intégration est invalide. Le type '${editIntegration?.type}' n'existe pas dans le catalogue backend. Veuillez contacter un administrateur. Les modifications ne sont pas autorisées pour les intégrations invalides.`}
          style={{ marginBottom: 16 }} />
      )}
      {isEdit && isDeprecated && (
        <Alert type="warning" showIcon icon={<WarningOutlined />} title="Intégration dépréciée"
          description={`Attention : le type de cette intégration ('${editIntegration?.type}') est déprécié. Il est recommandé de migrer vers un type supporté. Vous pouvez encore modifier cette intégration, mais son utilisation dans de nouveaux workflows sera bloquée.`}
          style={{ marginBottom: 16 }} />
      )}
      {isFallback && <Alert type="warning" title="Impossible de charger les types depuis le backend. Mode dégradé activé — la liste peut être incomplète." style={{ marginBottom: 16 }} showIcon />}
      {isEdit && (
        <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} align="center">
          <Space align="center">
            <span>État de santé :</span>
            <Tooltip title={healthCheckedAt ? `Dernière vérification : ${formatLocalDateTime(healthCheckedAt)}${healthErrorMessage ? `\nErreur : ${healthErrorMessage}` : ''}` : 'Jamais vérifié'}>
              <Tag color={HEALTH_CONFIG[healthStatus].color} aria-label={HEALTH_CONFIG[healthStatus].ariaLabel}>{HEALTH_CONFIG[healthStatus].text}</Tag>
            </Tooltip>
            {healthCheckedAt && <span style={{ fontSize: 12, color: '#888' }}>{formatLocalDateTime(healthCheckedAt)}</span>}
          </Space>
          <Button icon={<ThunderboltOutlined />} loading={testLoading} aria-busy={testLoading} onClick={handleTestConnection} size="small">Tester la connexion</Button>
        </Space>
      )}
      <Form form={form} layout="vertical" preserve={false} initialValues={editValues ?? defaultFormValues} key={editIntegration ? `edit-${editIntegration.id}` : 'create'}>
        <Form.Item name="type" label="Type d'intégration" rules={[{ required: true, message: "Veuillez sélectionner un type d'intégration" }]}>
          <Select placeholder={loadingTypes ? 'Chargement des types...' : "Sélectionner un type d'intégration"} loading={loadingTypes} disabled={isEdit || loadingTypes} showSearch optionFilterProp="label" options={typeOptions} aria-label="Type d'intégration" />
        </Form.Item>
        {selectedTypeData?.integration_role && (
          <div style={{ marginBottom: 12 }}>
            <Tag color={selectedTypeData.integration_role === 'platform' ? 'blue' : 'green'}>{selectedTypeData.integration_role === 'platform' ? "Plateforme d'exécution" : 'Service consommé'}</Tag>
          </div>
        )}
        {isEdit && <Alert type="info" showIcon icon={<InfoCircleOutlined />} title="Le type d'une intégration ne peut pas être modifié après sa création" style={{ marginBottom: 16 }} />}
        <AvailableActionsPanel selectedType={selectedTypeData} />
        <Form.Item name="name" label="Nom" rules={[{ required: true, message: 'Le nom est requis' }, { whitespace: true, message: 'Le nom ne peut pas être vide' }]}>
          <Input placeholder="Nom de l'intégration" aria-label="Nom" />
        </Form.Item>
        {isInventoryDb && (<>
          <Form.Item name="schema" label="Schéma BD" tooltip="Nom du schéma Oracle contenant la table/vue d'inventaire (ex: DBOPS_INVENTORY). Vide = défaut backend." rules={[{ pattern: /^$|^[A-Za-z_][A-Za-z0-9_]*$/, message: 'Alphanumérique et underscore uniquement' }]}>
            <Input placeholder="ex: DBOPS_INVENTORY" aria-label="Schéma BD" />
          </Form.Item>
          <Form.Item name="table" label="Table ou vue" tooltip="Nom de la table ou vue avec colonnes NAME, ENVIRONMENT, TYPE. Vide = défaut backend." rules={[{ pattern: /^$|^[A-Za-z_][A-Za-z0-9_]*$/, message: 'Alphanumérique et underscore uniquement' }]}>
            <Input placeholder="ex: INVENTORY_TARGETS" aria-label="Table ou vue" />
          </Form.Item>
          <Form.Item
            name="config_advanced"
            label={
              <Space wrap>
                <span>Config JSON (avancé)</span>
                <Button
                  type="link"
                  size="small"
                  icon={<FileTextOutlined />}
                  onClick={() => form.setFieldsValue({ config_advanced: INVENTORY_CONFIG_ENTITIES })}
                  style={{ padding: 0, height: 'auto' }}
                >
                  Exemple multi-tables
                </Button>
                <Button
                  type="link"
                  size="small"
                  onClick={() => form.setFieldsValue({ config_advanced: INVENTORY_CONFIG_FLAT })}
                  style={{ padding: 0, height: 'auto' }}
                >
                  Exemple une table
                </Button>
              </Space>
            }
            tooltip="Optionnel. Multi-tables : entities.servers, entities.instances (server_ref, db_ref), entities.databases. Une table : flat_table. Si rempli, remplace Schéma BD / Table ou vue. Guide : docs/inventory-mapping-guide.md"
          >
            <Input.TextArea
              placeholder="Cliquez sur « Insérer un exemple » pour charger un modèle, puis adaptez les noms de tables/colonnes."
              rows={10}
              aria-label="Config JSON avancé"
              style={{ fontFamily: 'monospace', fontSize: 12 }}
            />
          </Form.Item>
        </>)}
        <Form.Item name="base_url" label="URL de base" rules={[{ required: true, validator: (_, v) => { const s = (v ?? '').toString().trim(); if (!s) return Promise.reject(new Error("L'URL de base est requise")); if (!URL_PATTERN.test(s)) return Promise.reject(new Error("L'URL doit être valide (commencer par http:// ou https://)")); return Promise.resolve(); } }]}>
          <Input placeholder="https://example.com/api" aria-label="URL de base" />
        </Form.Item>
        {isVaultType ? (
          <Alert type="info" showIcon icon={<InfoCircleOutlined />} title="Authentification Vault (secret 0)" description="L'authentification à Vault utilise le secret 0 fourni par les variables d'environnement (VAULT_TOKEN ou VAULT_ROLE_ID + VAULT_SECRET_ID). Aucun credential n'est stocké en base. Voir la documentation vault-bootstrap-guide pour la configuration." style={{ marginBottom: 16 }} />
        ) : (
          <Form.Item name="credential_ref" label="Référence credentials" help="Référence vers un secret Vault (ex: vault:secret/data/aap/prod#token). Le secret est résolu au moment de l'exécution. Aucun secret n'est stocké en base.">
            <Input placeholder="vault:secret/data/aap/prod#token" aria-label="Référence credentials" />
          </Form.Item>
        )}
        {!isVaultType && vaultIntegrations.length > 0 && (
          <Form.Item name="secret_service_id" label="Service de secrets" help="Sélectionnez l'instance Vault utilisée pour résoudre les secrets de cette intégration (optionnel, défaut = Vault principal via variables d'environnement)">
            <Select placeholder="Vault principal (défaut)" allowClear options={vaultIntegrations.map((v) => ({ label: v.name, value: v.id }))} aria-label="Service de secrets" />
          </Form.Item>
        )}
        <Form.Item name="auth_flow" label="Flow d'authentification">
          <Select placeholder="Sélectionner un flow (optionnel)" options={AUTH_FLOW_OPTIONS} allowClear aria-label="Flow d'authentification" />
        </Form.Item>
        {isTokenFlow && (
          <Form.Item name="token_url" label="URL du token" help="URL d'acquisition du token OAuth, si différente de l'URL de base (ex. serveur d'authentification séparé). Laissez vide pour utiliser l'URL de base." rules={[{ validator: (_, v) => { const s = (v ?? '').toString().trim(); if (!s) return Promise.resolve(); if (!URL_PATTERN.test(s)) return Promise.reject(new Error("L'URL doit être valide (commencer par http:// ou https://)")); return Promise.resolve(); } }]}>
            <Input placeholder="https://auth.example.com/oauth/token" aria-label="URL du token" />
          </Form.Item>
        )}
        {isOauth2Flow && (
          <Form.Item name="scope" label="Scope OAuth2" help="Scopes OAuth2 séparés par des espaces. Optionnel selon le serveur d'autorisation.">
            <Input placeholder="openid profile email" aria-label="Scope OAuth2" />
          </Form.Item>
        )}
        {isApiKeyFlow && (
          <Form.Item name="header_name" label="Nom du header" help="Nom du header HTTP pour la clé API (ex. X-API-Key, Authorization, X-Auth-Token). Défaut si vide : X-API-Key.">
            <Input placeholder="X-API-Key" aria-label="Nom du header" />
          </Form.Item>
        )}
        <Form.Item label="Icône" tooltip="Uploader une icône ou saisir une URL">
          <Space orientation="vertical" style={{ width: '100%' }}>
            <Upload accept="image/*" maxCount={1} fileList={fileList}
              beforeUpload={(file) => {
                if (!file.type.startsWith('image/')) { message.error('Vous ne pouvez uploader que des images!'); return Upload.LIST_IGNORE; }
                if (file.size / 1024 / 1024 >= 2) { message.error("L'image doit faire moins de 2MB!"); return Upload.LIST_IGNORE; }
                handleIconUpload(file); setFileList([file]); return false;
              }}
              onRemove={() => { setFileList([]); setUploadedIconUrl(null); form.setFieldsValue({ icon: undefined }); }}>
              <Button icon={<UploadOutlined />}>Uploader une icône</Button>
            </Upload>
            <Form.Item name="icon" noStyle><Input placeholder="...ou saisir URL de l'icône" aria-label="URL icône" /></Form.Item>
          </Space>
        </Form.Item>
        <Form.Item label="Aperçu" colon={false} style={{ marginBottom: 0 }}><Space align="center">{iconPreview}</Space></Form.Item>
      </Form>
    </Modal>
  );
}
