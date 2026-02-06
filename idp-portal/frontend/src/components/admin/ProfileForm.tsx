/**
 * ProfileForm — create/edit profile (Story 2.9, AC #1, #2, #4).
 * Story 2.10: section « Actions autorisées » + Environnements en édition (AC1–AC4).
 * Story 2.11: section « Targets autorisés » (AC1–AC3).
 * Modal with name, description, ad_group, is_admin, is_auditor; when edit: actions + targets permissions.
 */

import { useEffect, useState } from 'react';
import { Form, Input, Modal, Alert, Switch, Radio, Select } from 'antd';
import type {
  ProfileCreate,
  ProfileUpdate,
  ProfileResponse,
  ProfileActionsType,
  ProfileActionPermissionsUpdate,
  ProfileTargetsType,
  ProfileTargetPermissionsUpdate,
} from '../../types/api';
import { getProfileActions, putProfileActions, getProfileTargets, putProfileTargets } from '../../services/profiles_service';
import { listActions, getTags } from '../../services/admin_service';
import { MOCK_TARGET_OPTIONS } from '../../utils/profileOptions';
import { useEnvironments } from '../../hooks/useEnvironments';

const { TextArea } = Input;

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
  targets_type?: ProfileTargetsType;
  target_names?: string[];
  target_patterns?: string[];
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
  
  // Story 13.7: Load environments from inventory
  const { environmentOptions, loading: environmentsLoading } = useEnvironments();

  useEffect(() => {
    if (!open) return;
    form.resetFields();
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
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
      });
      queueMicrotask(() => setLoadingActions(true));
      Promise.all([
        getProfileActions(editProfile.id),
        getProfileTargets(editProfile.id),
        listActions(),
        getTags(),
      ])
        .then(([perms, targetsPerms, actions, tags]) => {
          form.setFieldsValue({
            actions_type: perms.actions_type,
            action_ids: perms.action_ids ?? [],
            tag_patterns: perms.tag_patterns ?? [],
            environments: perms.environments ?? [],
            targets_type: targetsPerms.targets_type,
            target_names: targetsPerms.target_names ?? [],
            target_patterns: targetsPerms.target_patterns ?? [],
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
      const tt = values.targets_type ?? 'all';
      const targetsPayload: ProfileTargetPermissionsUpdate = {
        targets_type: tt,
        target_names: tt === 'list' ? (values.target_names ?? []) : [],
        target_patterns: tt === 'pattern' ? (values.target_patterns ?? []) : [],
      };
      try {
        await putProfileActions(editProfile.id, actionsPayload);
        await putProfileTargets(editProfile.id, targetsPayload);
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
        <Alert type="error" title={error} style={{ marginBottom: 16 }} showIcon />
      )}
      {permError && (
        <Alert type="warning" title={permError} style={{ marginBottom: 16 }} showIcon />
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
                <Radio value="list">Liste d'actions</Radio>
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
            <Form.Item name="environments" label="Environnements autorisés">
              <Select
                mode="multiple"
                placeholder={environmentsLoading ? "Chargement..." : "Sélectionnez les environnements"}
                options={environmentOptions.map((e) => ({ value: e.value.toUpperCase(), label: e.label }))}
                loading={environmentsLoading}
              />
            </Form.Item>

            <div style={{ marginTop: 16, marginBottom: 8, fontWeight: 500 }}>Targets autorisés</div>
            <Form.Item name="targets_type" label="Type" rules={[{ required: true }]}>
              <Radio.Group>
                <Radio value="list">Liste explicite</Radio>
                <Radio value="pattern">Pattern</Radio>
                <Radio value="all">Tous (*)</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item
              noStyle
              shouldUpdate={(prev, curr) => prev?.targets_type !== curr?.targets_type}
            >
              {({ getFieldValue }) =>
                getFieldValue('targets_type') === 'list' ? (
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
                ) : getFieldValue('targets_type') === 'pattern' ? (
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
                ) : null
              }
            </Form.Item>
          </>
        )}
      </Form>
    </Modal>
  );
}
