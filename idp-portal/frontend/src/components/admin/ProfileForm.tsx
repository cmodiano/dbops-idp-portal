/**
 * ProfileForm — create/edit profile (Story 2.9, AC #1, #2, #4).
 * Story 2.10: section « Actions autorisées » + Environnements en édition (AC1–AC4).
 * Story 2.11: section « Targets autorisés » (AC1–AC3).
 * Story 23.7: Radio options for All servers / Oracle / SQL with filter_by_attribute.
 * Modal with name, description, ad_group, is_admin, is_auditor; when edit: actions + targets permissions.
 */

import { useEffect, useMemo, useState } from 'react';
import { Form, Input, Modal, Alert, Switch, Radio, Select } from 'antd';
import { CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import type {
  ProfileCreate,
  ProfileUpdate,
  ProfileResponse,
  ProfileActionsType,
  ProfileActionPermissionsUpdate,
  ProfileTargetPermissionsUpdate,
  ProfileTargetPermissionsResponse,
} from '../../types/api';
import { getProfileActions, putProfileActions, getProfileTargets, putProfileTargets } from '../../services/profiles_service';
import { getAdminActions, getTags } from '../../services/admin_service';
import { MOCK_TARGET_OPTIONS } from '../../utils/profileOptions';
import { useEnvironments } from '../../hooks/useEnvironments';

const { TextArea } = Input;

// Story 23.7 - Targets mode discriminator for UI display
export type TargetsMode = 'all' | 'all-oracle' | 'all-sql' | 'list' | 'pattern' | 'advanced';

/**
 * Story 23.7 - Detect targets mode from profile target permissions response.
 * Returns 'all-oracle', 'all-sql' for engine-specific filters, 'advanced' for unsupported filters.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function detectTargetsMode(targetsPerms: ProfileTargetPermissionsResponse): TargetsMode {
  const { targets_type, filter_by_attribute } = targetsPerms;

  if (targets_type === 'list') return 'list';
  if (targets_type === 'pattern') return 'pattern';

  // ALL without filter (null or undefined)
  if (targets_type === 'all' && !filter_by_attribute) return 'all';

  // ALL with filter_by_attribute
  if (targets_type === 'all' && filter_by_attribute) {
    const keys = Object.keys(filter_by_attribute);

    // Empty object → treat as 'all' (no filter)
    if (keys.length === 0) return 'all';

    // Exactly one key: engine_type
    if (keys.length === 1 && keys[0] === 'engine_type') {
      const engineValues = filter_by_attribute.engine_type;

      // Exactly one value
      if (engineValues && engineValues.length === 1) {
        const engineType = engineValues[0].toLowerCase();
        if (engineType === 'oracle') return 'all-oracle';
        if (engineType === 'sqlserver' || engineType === 'sql') return 'all-sql';
      }
    }

    // Unsupported filter structure (multi-keys, multi-values, unknown values)
    return 'advanced';
  }

  return 'all';
}

// Story 23.7 - Compute filter_by_attribute from targetsMode
function getFilterByAttribute(mode: TargetsMode): Record<string, string[]> | null {
  if (mode === 'all-oracle') return { engine_type: ['oracle'] };
  if (mode === 'all-sql') return { engine_type: ['sqlserver'] };
  return null;
}

// Story 23.7 - Compute targets_type from targetsMode
function getTargetsTypeFromMode(mode: TargetsMode): 'all' | 'list' | 'pattern' {
  if (mode === 'list') return 'list';
  if (mode === 'pattern') return 'pattern';
  return 'all';
}

export interface ProfileFormValues {
  name: string;
  description?: string | null;
  ad_group: string;
  is_admin: boolean;
  is_auditor: boolean;
  actions_type?: ProfileActionsType;
  action_ids?: number[];
  tag_patterns?: string[];
  environments?: string[];
  target_names?: string[];
  target_patterns?: string[];
  exclusion_patterns?: string[]; // Story 25.6
}

export interface ProfileFormProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (values: ProfileCreate | ProfileUpdate) => Promise<ProfileResponse | void>;
  loading?: boolean;
  error?: string | null;
  editProfile?: ProfileResponse | null;
  onSuccess?: (profile: ProfileResponse) => void;
}

export function ProfileForm({
  open,
  onCancel,
  onSubmit,
  loading,
  error,
  editProfile,
  onSuccess,
}: ProfileFormProps) {
  const [form] = Form.useForm<ProfileFormValues>();
  const isEdit = !!editProfile;
  const [actionsOptions, setActionsOptions] = useState<{ id: number; name: string }[]>([]);
  const [tagsOptions, setTagsOptions] = useState<string[]>([]);
  const [loadingActions, setLoadingActions] = useState(false);
  // Story 23.7 - Targets mode state
  const [targetsMode, setTargetsMode] = useState<TargetsMode>('all');

  // Story 13.7: Load environments from inventory
  const { environmentOptions, loading: environmentsLoading } = useEnvironments();

  // Story 21.6, AC6: Detect environments not in inventory for warning
  const watchedEnvironments = Form.useWatch('environments', form);
  const unknownEnvironments = useMemo(() => {
    if (!watchedEnvironments?.length || !environmentOptions.length) return [];
    const validEnvs = new Set(environmentOptions.map((e) => e.value.toLowerCase()));
    return watchedEnvironments.filter(
      (env: string) => !validEnvs.has(env.toLowerCase()),
    );
  }, [watchedEnvironments, environmentOptions]);

  useEffect(() => {
    if (!open) return;
    form.resetFields();
    // Story 23.7 - Reset targets mode
    setTargetsMode('all');
    if (editProfile) {
      form.setFieldsValue({
        name: editProfile.name,
        description: editProfile.description ?? undefined,
        ad_group: editProfile.ad_group,
        is_admin: editProfile.is_admin,
        is_auditor: editProfile.is_auditor,
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: [],
        target_names: [],
        target_patterns: [],
        exclusion_patterns: [], // Story 25.6
      });
      queueMicrotask(() => setLoadingActions(true));
      Promise.all([
        getProfileActions(editProfile.id),
        getProfileTargets(editProfile.id),
        getAdminActions().then((r) => r.data),
        getTags(),
      ])
        .then(([perms, targetsPerms, actions, tags]) => {
          // Story 23.7 - Load targets permissions and detect mode from filter_by_attribute
          const mode = detectTargetsMode(targetsPerms);
          setTargetsMode(mode);
          form.setFieldsValue({
            actions_type: perms.actions_type,
            action_ids: perms.action_ids ?? [],
            tag_patterns: perms.tag_patterns ?? [],
            environments: perms.environments ?? [],
            target_names: targetsPerms.target_names ?? [],
            target_patterns: targetsPerms.target_patterns ?? [],
            exclusion_patterns: targetsPerms.exclusion_patterns ?? [], // Story 25.6
          });
          setActionsOptions(actions.map((a) => ({ id: a.id, name: a.name })));
          setTagsOptions(tags.map((t) => t.name));
        })
        .catch(() => {
          setActionsOptions([]);
          setTagsOptions([]);
        })
        .finally(() => setLoadingActions(false));
    } else {
      // Story 23.7 - Default for new profile
      setTargetsMode('all');
      form.setFieldsValue({ is_admin: false, is_auditor: false });
    }
  }, [open, editProfile, form]);

  const [permError, setPermError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setPermError(null);
    const values = await form.validateFields();
    const payload: ProfileCreate | ProfileUpdate = {
      name: values.name.trim(),
      description: values.description?.trim() || null,
      ad_group: values.ad_group.trim(),
      is_admin: values.is_admin,
      is_auditor: values.is_auditor,
    };
    const res = await onSubmit(payload);
    if (isEdit && editProfile) {
      const at = values.actions_type ?? 'all';
      const actionsPayload: ProfileActionPermissionsUpdate = {
        actions_type: at,
        action_ids: at === 'list' ? (values.action_ids ?? []) : [],
        tag_patterns: at === 'pattern' ? (values.tag_patterns ?? []) : [],
        environments: values.environments ?? [],
      };
      // Story 23.7 - Include filter_by_attribute for engine-based filtering
      const tt = getTargetsTypeFromMode(targetsMode);
      const targetsPayload: ProfileTargetPermissionsUpdate = {
        targets_type: tt,
        target_names: tt === 'list' ? (values.target_names ?? []) : [],
        target_patterns: tt === 'pattern' ? (values.target_patterns ?? []) : [],
        filter_by_attribute: getFilterByAttribute(targetsMode),
        exclusion_patterns: values.exclusion_patterns ?? [], // Story 25.6
      };
      try {
        await Promise.all([
          putProfileActions(editProfile.id, actionsPayload),
          putProfileTargets(editProfile.id, targetsPayload),
        ]);
      } catch {
        setPermError('Profil mis à jour, mais erreur lors de la sauvegarde des permissions. Réessayez en éditant le profil.');
        if (res && onSuccess) onSuccess(res);
        return;
      }
    }
    if (res && onSuccess) onSuccess(res);
  };

  return (
    <Modal
      open={open}
      title={isEdit ? 'Modifier le profil' : 'Nouveau profil'}
      onCancel={onCancel}
      onOk={handleSubmit}
      confirmLoading={loading}
      destroyOnHidden
      okText={isEdit ? 'Enregistrer' : 'Créer'}
      cancelText="Annuler"
      cancelButtonProps={{ disabled: loading }}
    >
      {error && (
        <Alert type="error" message={error} style={{ marginBottom: 16 }} showIcon />
      )}
      {permError && (
        <Alert type="warning" message={permError} style={{ marginBottom: 16 }} showIcon />
      )}
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          name="name"
          label="Nom"
          rules={[{ required: true, message: 'Le nom est requis' }, { whitespace: true, message: 'Le nom ne peut pas être vide' }]}
        >
          <Input placeholder="ex. Assurance" />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <TextArea rows={2} placeholder="Description du profil" />
        </Form.Item>
        <Form.Item
          name="ad_group"
          label="Groupe AD"
          rules={[{ required: true, message: 'Le groupe AD est requis' }, { whitespace: true, message: 'Le groupe AD ne peut pas être vide' }]}
        >
          <Input placeholder="ex. GRP-IDP-ASSURANCE" />
        </Form.Item>
        <Form.Item name="is_admin" label="Administrateur" valuePropName="checked">
          <Switch />
        </Form.Item>
        <Form.Item name="is_auditor" label="Auditeur" valuePropName="checked">
          <Switch />
        </Form.Item>

        {isEdit && (
          <>
            <div style={{ marginTop: 16, marginBottom: 8, fontWeight: 500 }}>Actions autorisées</div>
            <Form.Item name="actions_type" label="Type" rules={[{ required: true }]}>
              <Radio.Group>
                <Radio value="list">Liste d&apos;actions</Radio>
                <Radio value="pattern">Pattern par tags</Radio>
                <Radio value="all">Toutes (*)</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item
              noStyle
              shouldUpdate={(prev, curr) => prev?.actions_type !== curr?.actions_type}
            >
              {({ getFieldValue }) =>
                getFieldValue('actions_type') === 'list' ? (
                  <Form.Item name="action_ids" label="Actions">
                    <Select
                      mode="multiple"
                      placeholder="Sélectionner des actions"
                      loading={loadingActions}
                      options={actionsOptions.map((a) => ({ value: a.id, label: a.name }))}
                      filterOption={(input, opt) =>
                        (opt?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
                      }
                    />
                  </Form.Item>
                ) : getFieldValue('actions_type') === 'pattern' ? (
                  <Form.Item name="tag_patterns" label="Tags (pattern)">
                    <Select
                      mode="multiple"
                      placeholder="ex. oracle, provisioning"
                      loading={loadingActions}
                      options={tagsOptions.map((t) => ({ value: t, label: t }))}
                      filterOption={(input, opt) =>
                        (opt?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
                      }
                    />
                  </Form.Item>
                ) : null
              }
            </Form.Item>
            {unknownEnvironments.length > 0 && (
              <Alert
                type="warning"
                message="Attention : environnements non reconnus"
                description={`Les environnements suivants ne sont pas dans l'inventaire : ${unknownEnvironments.join(', ')}. Validation finale au backend.`}
                showIcon
                style={{ marginBottom: 8 }}
              />
            )}
            <Form.Item name="environments" label="Environnements autorisés">
              <Select
                mode="multiple"
                placeholder={environmentsLoading ? "Chargement..." : "Sélectionnez les environnements"}
                options={environmentOptions.map((e) => ({ value: e.value.toUpperCase(), label: e.label }))}
                loading={environmentsLoading}
              />
            </Form.Item>

            {/* Story 23.7 - Section Targets autorisés avec filter by engine type */}
            <div style={{ marginTop: 16, marginBottom: 8, fontWeight: 500 }}>Targets autorisés</div>
            {/* Story 23.7 - Radio options for All servers / Oracle / SQL with filter_by_attribute */}
            <Radio.Group
              value={targetsMode}
              onChange={(e) => {
                const newMode = e.target.value as TargetsMode;
                setTargetsMode(newMode);
                if (newMode === 'all' || newMode === 'all-oracle' || newMode === 'all-sql') {
                  form.setFieldsValue({ target_names: [], target_patterns: [] });
                }
              }}
              style={{ width: '100%', marginBottom: 16 }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Radio value="all">Tous les serveurs</Radio>
                <Radio value="all-oracle">Tous les serveurs Oracle</Radio>
                <Radio value="all-sql">Tous les serveurs SQL</Radio>
                <Radio value="list">Liste de serveurs spécifiques</Radio>
                <Radio value="pattern">Pattern de serveurs</Radio>
              </div>
            </Radio.Group>

            {/* Story 23.7 - Alerts informatifs selon targetsMode */}
            {targetsMode === 'all' && (
              <Alert
                type="info"
                showIcon
                icon={<CheckCircleOutlined />}
                closable={false}
                title="Accès complet à tous les serveurs (tous types, tous environnements)"
                style={{ marginBottom: 16 }}
              />
            )}
            {targetsMode === 'all-oracle' && (
              <Alert
                type="info"
                showIcon
                icon={<CheckCircleOutlined />}
                closable={false}
                title="Accès à tous les serveurs Oracle (tous environnements)"
                style={{ marginBottom: 16 }}
              />
            )}
            {targetsMode === 'all-sql' && (
              <Alert
                type="info"
                showIcon
                icon={<CheckCircleOutlined />}
                closable={false}
                title="Accès à tous les serveurs SQL (tous environnements)"
                style={{ marginBottom: 16 }}
              />
            )}
            {targetsMode === 'advanced' && (
              <Alert
                type="warning"
                showIcon
                icon={<WarningOutlined />}
                closable={false}
                title="Ce profil utilise des filtres avancés non supportés par l'interface. L'édition réinitialisera ces filtres."
                style={{ marginBottom: 16 }}
              />
            )}

            {/* Story 23.7 - Conditional target fields */}
            {targetsMode === 'list' && (
              <Form.Item
                name="target_names"
                label="Targets"
                rules={[
                  {
                    validator: (_, value) =>
                      value?.length
                        ? Promise.resolve()
                        : Promise.reject(new Error('Sélectionnez au moins un target.')),
                  },
                ]}
              >
                <Select
                  mode="multiple"
                  placeholder="Sélectionner des targets (ex. assurance-db01)"
                  options={MOCK_TARGET_OPTIONS.map((t) => ({ value: t, label: t }))}
                  filterOption={(input, opt) =>
                    (opt?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
                  }
                />
              </Form.Item>
            )}
            {targetsMode === 'pattern' && (
              <Form.Item
                name="target_patterns"
                label="Patterns (ex. assurance-*)"
                rules={[
                  {
                    validator: (_, value) =>
                      value?.length
                        ? Promise.resolve()
                        : Promise.reject(new Error('Saisissez au moins un pattern.')),
                  },
                ]}
              >
                <Select
                  mode="tags"
                  placeholder="ex. assurance-*, infra-*"
                  tokenSeparators={[',']}
                />
              </Form.Item>
            )}
            
            {/* Story 25.6: Exclusion patterns (deny explicit) */}
            <Form.Item
              name="exclusion_patterns"
              label="Patterns d'exclusion"
              tooltip="Cibles à exclure même si elles matchent les règles d'inclusion (sémantique: allow first, then exclude)"
              rules={[
                {
                  validator: (_, value) => {
                    if (!value || value.length === 0) return Promise.resolve();
                    
                    // Code review fix: Enforce max 100 patterns (performance limit)
                    const MAX_PATTERNS = 100;
                    if (value.length > MAX_PATTERNS) {
                      return Promise.reject(new Error(`Maximum ${MAX_PATTERNS} patterns autorisés (limite de performance)`));
                    }
                    
                    // Code review fix: Validate patterns for glob syntax (warn about regex-like patterns)
                    const regexLikePatterns = value.filter((p: string) => 
                      p.includes('\\') || p.includes('.+') || p.includes('.*') || /\{\d+,\d+\}/.test(p)
                    );
                    if (regexLikePatterns.length > 0) {
                      return Promise.reject(
                        new Error(`Patterns invalides (syntaxe regex détectée): ${regexLikePatterns.join(', ')}. Utilisez la syntaxe glob: *, ?, [abc]`)
                      );
                    }
                    
                    // Code review fix: Basic pattern validation (must contain wildcard or be exact name)
                    const invalidPatterns = value.filter((p: string) => {
                      const trimmed = p.trim();
                      // Empty patterns
                      if (!trimmed) return true;
                      // Valid: contains glob wildcards OR is a simple name (no special chars except dash/underscore)
                      const hasWildcard = trimmed.includes('*') || trimmed.includes('?') || /\[.*\]/.test(trimmed);
                      const isSimpleName = /^[A-Za-z0-9_-]+$/.test(trimmed);
                      return !(hasWildcard || isSimpleName);
                    });
                    
                    if (invalidPatterns.length > 0) {
                      return Promise.reject(
                        new Error(`Patterns invalides: ${invalidPatterns.join(', ')}. Utilisez *, ?, [abc] ou noms exacts`)
                      );
                    }
                    
                    return Promise.resolve();
                  },
                },
              ]}
            >
              <Select
                mode="tags"
                placeholder="ex: PROD-CRITICAL-*, DR-*"
                tokenSeparators={[',']}
              />
            </Form.Item>
          </>
        )}
      </Form>
    </Modal>
  );
}
