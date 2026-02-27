/**
 * WizardStep1General — Étape 1 du wizard (Général) extraite de ActionWizard::stepContent (Story 33.5, Task 5).
 * Contient : type, nom, description, catégorie, moteur, intégration, tags.
 *
 * Story 48.8 (SOLID-FE-4, AC3): checkActionNameAvailable encapsulé dans useActionNameAvailability hook (DIP).
 */
import { Form, Input, Select, Alert, Radio } from 'antd';
import type { FormInstance } from 'antd';
import type { ActionDetail } from '../../types/api';
import SectionHelp from '../common/SectionHelp';
import { useActionNameAvailability } from '../../hooks/useActionNameAvailability';

const { TextArea } = Input;

type IntegrationLike = { id: number; type: string; name: string };

export interface WizardStep1GeneralProps {
  form: FormInstance;
  isWorkflow: boolean;
  showTypeSelector: boolean;
  isReadOnly: boolean;
  engineOptions: { value: string; label: string }[];
  enginesLoading: boolean;
  integrationOptions: { value: number; label: string }[];
  integrationsLoading: boolean;
  isEditMode: boolean;
  editAction?: ActionDetail | null;
  selectedTags: string[];
  setSelectedTags: (tags: string[]) => void;
  tagsOptions: { value: string; label: string }[];
  categoryOptions: { value: string; label: string }[];
  categoriesLoading: boolean;
  getIntegrationById: (id: number) => IntegrationLike | undefined;
}

export function WizardStep1General({
  isWorkflow,
  showTypeSelector,
  isReadOnly,
  engineOptions,
  enginesLoading,
  integrationOptions,
  integrationsLoading,
  isEditMode,
  editAction,
  selectedTags,
  setSelectedTags,
  tagsOptions,
  categoryOptions,
  categoriesLoading,
}: WizardStep1GeneralProps) {
  const { checkName } = useActionNameAvailability();

  return (
    <>
      {/* Story 9.5 / 2.29: Type selector — hidden when initialItemType is set or in edit mode */}
      <Form.Item
        name="item_type"
        label="Type"
        rules={showTypeSelector ? [{ required: true, message: 'Le type est requis' }] : undefined}
        hidden={!showTypeSelector}
      >
        <Radio.Group aria-label="Type d'élément" disabled={isReadOnly}>
          <Radio value="action">Action</Radio>
          <Radio value="workflow">Workflow</Radio>
        </Radio.Group>
      </Form.Item>

      <Form.Item
        name="name"
        label={isWorkflow ? 'Nom du workflow' : "Nom de l'action"}
        validateTrigger={['onBlur', 'onFinish']}
        rules={[
          { required: true, message: 'Le nom est requis' },
          { min: 1, max: 255, message: 'Le nom doit faire entre 1 et 255 caractères' },
          {
            validator: async (_, value) => {
              const name = value ? String(value).trim() : '';
              if (!name) return;
              const available = await checkName(name, editAction?.id);
              if (!available) {
                return Promise.reject(new Error('Une action ou un workflow avec ce nom existe déjà.'));
              }
            },
          },
        ]}
      >
        <Input
          placeholder={isWorkflow ? 'Ex: Provisionner environnement' : 'Ex: Créer PDB Oracle'}
          aria-label={isWorkflow ? 'Nom du workflow' : "Nom de l'action"}
          disabled={isReadOnly}
        />
      </Form.Item>

      <Form.Item
        name="description"
        label="Description"
        rules={[
          { required: true, message: 'La description est requise' },
          { max: 4000, message: 'La description ne peut pas dépasser 4000 caractères' },
        ]}
      >
        <TextArea
          rows={3}
          placeholder="Description..."
          aria-label="Description"
          showCount
          maxLength={4000}
          disabled={isReadOnly}
        />
      </Form.Item>

      {/* Story 2.30: Category field — actions and workflows (workflows: optional, default 'autres' backend) */}
      <Form.Item
        name="category"
        label="Catégorie"
        rules={[{ required: false }]}
        tooltip={isWorkflow ? "Catégorie du workflow (optionnel, défaut: Autres)" : "La catégorie permet d'organiser les actions dans le catalogue"}
      >
        <Select
          options={categoryOptions}
          placeholder={categoriesLoading ? 'Chargement...' : (isWorkflow ? 'Autres (défaut)' : 'Sélectionnez une catégorie')}
          loading={categoriesLoading}
          disabled={isReadOnly}
          allowClear
          aria-label="Catégorie"
        />
      </Form.Item>

      {/* Only show engine/platform for actions, not workflows */}
      {!isWorkflow && (
        <>
          <Form.Item
            name="engine"
            label="Moteur de base de données"
            rules={[{ required: true, message: 'Le moteur est requis' }]}
          >
            <Select
              options={engineOptions}
              placeholder={enginesLoading ? 'Chargement...' : 'Sélectionnez un moteur'}
              aria-label="Moteur"
              loading={enginesLoading}
              disabled={isReadOnly}
            />
          </Form.Item>

          <Form.Item
            name="integration_id"
            label={<span>Intégration <SectionHelp topicId="action-form-integration" /></span>}
            rules={[{ required: true, message: "L'intégration est requise" }]}
          >
            <Select
              options={integrationOptions}
              placeholder={integrationsLoading ? 'Chargement...' : 'Sélectionnez une intégration'}
              aria-label="Intégration"
              loading={integrationsLoading}
              disabled={isReadOnly}
            />
          </Form.Item>

          {/* Story 31.1 AC4: Alert when no platform integrations available */}
          {!integrationsLoading && integrationOptions.length === 0 && (
            <Alert
              type="warning"
              showIcon
              title="Aucune intégration de type plateforme n'est disponible. Créez-en une dans Admin > Intégrations."
              style={{ marginBottom: 16 }}
            />
          )}

          {/* Story 31.1 AC6: Degraded mode for legacy actions without integration_id */}
          {isEditMode && !editAction?.integration_id && editAction?.platform && (
            <Alert
              type="info"
              showIcon
              title={`Cette action utilise l'ancienne plateforme « ${editAction.platform} ». Sélectionnez une intégration pour la mettre à jour.`}
              style={{ marginBottom: 16 }}
            />
          )}
        </>
      )}

      <Form.Item label="Tags" tooltip="Tags existants ou saisie libre + Entrée pour en créer un nouveau.">
        <Select
          mode="tags"
          value={selectedTags}
          onChange={(v) => setSelectedTags((Array.isArray(v) ? v : [v]).filter(Boolean) as string[])}
          options={tagsOptions}
          placeholder="Ex: RAC, dataguard, provisioning"
          aria-label="Tags"
          style={{ width: '100%' }}
          tokenSeparators={[',']}
          disabled={isReadOnly}
        />
      </Form.Item>
    </>
  );
}
