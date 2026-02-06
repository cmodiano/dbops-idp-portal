/**
 * ProfileWizard — Wizard 3 étapes pour création/édition de profil avec permissions (Story 2.25, AC #1–#7).
 *
 * Étapes : (1) Général, (2) Permissions Actions, (3) Permissions Targets.
 * Pattern: ActionWizard (Story 2.22).
 */

import { useEffect, useState } from 'react';
import { Modal, Steps, Button, Form, Input, Select, Radio, Switch, Alert, Space, App } from 'antd';
import type {
  ProfileCreate,
  ProfileUpdate,
  ProfileResponse,
  ProfileActionsType,
  ProfileActionPermissionsUpdate,
  ProfileTargetsType,
  ProfileTargetPermissionsUpdate,
} from '../../types/api';
import {
  createProfile,
  updateProfile,
  getProfileActions,
  getProfileTargets,
  putProfileActions,
  putProfileTargets,
} from '../../services/profiles_service';
import { listActions, getTags } from '../../services/admin_service';
import { ENVIRONMENT_OPTIONS, MOCK_TARGET_OPTIONS } from '../../utils/profileOptions';

const { TextArea } = Input;

const STEP_ITEMS = [
  { title: 'Général', content: 'Nom, groupe AD, flags' },
  { title: 'Permissions Actions', content: 'Actions et environnements autorisés' },
  { title: 'Permissions Targets', content: 'Targets autorisés' },
];

interface ProfileWizardValues {
  name: string;
  description?: string | null;
  ad_group: string;
  is_admin: boolean;
  is_auditor: boolean;
  actions_type: ProfileActionsType;
  action_ids: number[];
  tag_patterns: string[];
  environments: string[];
  targets_type: ProfileTargetsType;
  target_names: string[];
  target_patterns: string[];
}

export interface ProfileWizardProps {
  open: boolean;
  onCancel: () => void;
  editProfile?: ProfileResponse | null;
  onSuccess?: (profile: ProfileResponse) => void;
}

export function ProfileWizard({
  open,
  onCancel,
  editProfile,
  onSuccess,
}: ProfileWizardProps) {
  const { notification } = App.useApp();
  const [form] = Form.useForm<ProfileWizardValues>();
  const [currentStep, setCurrentStep] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loadingData, setLoadingData] = useState(false);

  const [actionsOptions, setActionsOptions] = useState<{ id: number; name: string }[]>([]);
  const [tagsOptions, setTagsOptions] = useState<string[]>([]);

  const isEditMode = !!editProfile;

  // Load reference data (actions, tags) when modal opens
  useEffect(() => {
    if (!open) return;

    if (editProfile) {
      // Edit mode: load profile + permissions + reference data
      setLoadingData(true);
      Promise.all([
        getProfileActions(editProfile.id),
        getProfileTargets(editProfile.id),
        listActions(),
        getTags(),
      ])
        .then(([actionsPerms, targetsPerms, actions, tags]) => {
          form.setFieldsValue({
            name: editProfile.name,
            description: editProfile.description ?? '',
            ad_group: editProfile.ad_group,
            is_admin: editProfile.is_admin,
            is_auditor: editProfile.is_auditor,
            actions_type: actionsPerms.actions_type,
            action_ids: actionsPerms.action_ids ?? [],
            tag_patterns: actionsPerms.tag_patterns ?? [],
            environments: actionsPerms.environments ?? [],
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
        .finally(() => setLoadingData(false));
    } else {
      // Create mode: load reference data only (form has initial values)
      Promise.all([listActions(), getTags()])
        .then(([actions, tags]) => {
          setActionsOptions(actions.map((a) => ({ id: a.id, name: a.name })));
          setTagsOptions(tags.map((t) => t.name));
        })
        .catch(() => {
          setActionsOptions([]);
          setTagsOptions([]);
        });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editProfile]);

  // Reset local state when modal closes (Form is recreated by destroyOnHidden on reopen)
  useEffect(() => {
    if (!open) {
      setCurrentStep(0);
      setSubmitError(null);
      setSaving(false);
    }
  }, [open]);

  const handleNext = async () => {
    if (currentStep === 0) {
      try {
        await form.validateFields(['name']);
      } catch {
        return;
      }
    }
    setCurrentStep((s) => Math.min(s + 1, 2));
  };

  const handlePrev = () => setCurrentStep((s) => Math.max(s - 1, 0));

  const handleSave = async () => {
    setSubmitError(null);
    let values: ProfileWizardValues;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }

    setSaving(true);
    try {
      // Build profile payload
      const profilePayload: ProfileCreate | ProfileUpdate = {
        name: values.name.trim(),
        description: values.description?.trim() || null,
        ad_group: values.ad_group?.trim() ?? '',
        is_admin: values.is_admin,
        is_auditor: values.is_auditor,
      };

      // Create or update profile
      let profile: ProfileResponse;
      if (isEditMode && editProfile) {
        profile = await updateProfile(editProfile.id, profilePayload);
      } else {
        profile = await createProfile(profilePayload as ProfileCreate);
      }

      // Build action permissions payload
      const actionsType = values.actions_type ?? 'all';
      const actionsPayload: ProfileActionPermissionsUpdate = {
        actions_type: actionsType,
        action_ids: actionsType === 'list' ? (values.action_ids ?? []) : [],
        tag_patterns: actionsType === 'pattern' ? (values.tag_patterns ?? []) : [],
        environments: values.environments ?? [],
      };

      // Build target permissions payload (validation rules ensure list/pattern have at least one item)
      const targetsType = values.targets_type ?? 'all';
      const targetsPayload: ProfileTargetPermissionsUpdate = {
        targets_type: targetsType,
        target_names: targetsType === 'list' ? (values.target_names ?? []) : [],
        target_patterns: targetsType === 'pattern' ? (values.target_patterns ?? []) : [],
      };

      // Save permissions
      try {
        await putProfileActions(profile.id, actionsPayload);
        await putProfileTargets(profile.id, targetsPayload);
      } catch (permErr) {
        // Profile created/updated but permissions failed - still call onSuccess
        notification.warning({
          title: 'Permissions non enregistrées',
          description: permErr instanceof Error ? permErr.message : 'Les permissions n\'ont pas pu être enregistrées. Éditez le profil pour réessayer.',
        });
        onSuccess?.(profile);
        setSaving(false);
        return;
      }

      onSuccess?.(profile);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Erreur lors de l\'enregistrement');
    } finally {
      setSaving(false);
    }
  };

  const actionsType = Form.useWatch('actions_type', form);
  const targetsType = Form.useWatch('targets_type', form);

  const stepContent = () => {
    return (
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          name: '',
          description: '',
          ad_group: '',
          is_admin: false,
          is_auditor: false,
          actions_type: 'all',
          action_ids: [],
          tag_patterns: [],
          environments: [],
          targets_type: 'all',
          target_names: [],
          target_patterns: [],
        }}
      >
        {/* Step 1: Général — use display:none (not conditional) to preserve input values */}
        <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
          <Form.Item
            name="name"
            label="Nom du profil"
            rules={[
              { required: true, message: 'Le nom est requis' },
              { whitespace: true, message: 'Le nom ne peut pas être vide' },
            ]}
          >
            <Input placeholder="ex. Assurance" aria-label="Nom du profil" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <TextArea rows={2} placeholder="Description du profil" aria-label="Description" />
          </Form.Item>
          <Form.Item name="ad_group" label="Groupe AD">
            <Input placeholder="ex. GRP-IDP-ASSURANCE" aria-label="Groupe AD" />
          </Form.Item>
          <Space size="large">
            <Form.Item name="is_admin" label="Admin" valuePropName="checked">
              <Switch aria-label="Admin" />
            </Form.Item>
            <Form.Item name="is_auditor" label="Auditeur" valuePropName="checked">
              <Switch aria-label="Auditeur" />
            </Form.Item>
          </Space>
        </div>

        {/* Step 2: Permissions Actions */}
        {currentStep === 1 && (
          <Space orientation="vertical" style={{ width: '100%' }} size="middle">
            <Form.Item name="actions_type" label="Type de permission actions">
              <Radio.Group>
                <Radio value="all" aria-label="Toutes les actions">Toutes les actions</Radio>
                <Radio value="list" aria-label="Liste d'actions">Liste d'actions</Radio>
                <Radio value="pattern" aria-label="Pattern de tags">Pattern de tags</Radio>
              </Radio.Group>
            </Form.Item>

            {actionsType === 'list' && (
              <Form.Item name="action_ids" label="Actions autorisées">
                <Select
                  mode="multiple"
                  placeholder="Sélectionner des actions"
                  loading={loadingData}
                  options={actionsOptions.map((a) => ({ value: a.id, label: a.name }))}
                  filterOption={(input, opt) =>
                    (opt?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
                  }
                  aria-label="Actions autorisées"
                />
              </Form.Item>
            )}

            {actionsType === 'pattern' && (
              <Form.Item name="tag_patterns" label="Tags (pattern)">
                <Select
                  mode="multiple"
                  placeholder="ex. oracle, provisioning"
                  loading={loadingData}
                  options={tagsOptions.map((t) => ({ value: t, label: t }))}
                  filterOption={(input, opt) =>
                    (opt?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
                  }
                  aria-label="Tags pattern"
                />
              </Form.Item>
            )}

            <Form.Item name="environments" label="Environnements autorisés">
              <Select
                mode="multiple"
                placeholder="DEV, STAGING, PROD..."
                options={ENVIRONMENT_OPTIONS.map((e) => ({ value: e, label: e }))}
                aria-label="Environnements autorisés"
              />
            </Form.Item>
          </Space>
        )}

        {/* Step 3: Permissions Targets */}
        {currentStep === 2 && (
          <Space orientation="vertical" style={{ width: '100%' }} size="middle">
            <Form.Item name="targets_type" label="Type de permission targets">
              <Radio.Group>
                <Radio value="all" aria-label="Toutes les targets">Toutes les targets</Radio>
                <Radio value="list" aria-label="Liste de targets">Liste de targets</Radio>
                <Radio value="pattern" aria-label="Pattern">Pattern</Radio>
              </Radio.Group>
            </Form.Item>

            {targetsType === 'list' && (
              <Form.Item
                name="target_names"
                label="Targets autorisés"
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
                  aria-label="Targets autorisés"
                />
              </Form.Item>
            )}

            {targetsType === 'pattern' && (
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
                  aria-label="Target patterns"
                />
              </Form.Item>
            )}
          </Space>
        )}
      </Form>
    );
  };

  return (
    <Modal
      title={isEditMode ? 'Modifier le profil' : 'Nouveau profil'}
      open={open}
      onCancel={onCancel}
      footer={null}
      width={640}
      destroyOnHidden
      styles={{ body: { maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' } }}
      aria-label={isEditMode ? 'Modifier le profil' : 'Nouveau profil'}
    >
      {submitError && (
        <Alert title="Erreur" description={submitError} type="error" showIcon style={{ marginBottom: 16 }} />
      )}

      <Steps
        current={currentStep}
        items={STEP_ITEMS.map((item, i) => ({
          title: item.title,
          ...(item.content != null && { content: item.content }),
          status: i === currentStep ? 'process' : i < currentStep ? 'finish' : 'wait',
        }))}
        style={{ marginBottom: 24 }}
        aria-label={`Étape ${currentStep + 1} sur 3 : ${STEP_ITEMS[currentStep].title}`}
      />

      <div style={{ minHeight: 280 }}>{stepContent()}</div>

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
        <Button onClick={onCancel}>Annuler</Button>
        <Space>
          {currentStep > 0 && <Button onClick={handlePrev}>Précédent</Button>}
          {currentStep < 2 && (
            <Button type="primary" onClick={handleNext}>
              Suivant
            </Button>
          )}
          {currentStep === 2 && (
            <Button type="primary" onClick={handleSave} loading={saving}>
              Enregistrer
            </Button>
          )}
        </Space>
      </div>
    </Modal>
  );
}
