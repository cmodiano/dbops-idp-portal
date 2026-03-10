/**
 * Story 28.4, AC#1, AC#2: Panel Admin pour la gestion des règles métier prédéfinies.
 * Story 71.1, AC3: Migration DIP — utilise useBusinessRulePoliciesAdmin au lieu d'importer directement le service.
 */

import { useState } from 'react';
import { Table, Button, Tag, Space, App, Select, Switch, Typography } from 'antd';
import type { TableProps } from 'antd';
import { PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import type {
  BusinessRulePolicyListItem,
  BusinessRulePolicyDetail,
  BusinessRulePolicyPayload,
} from '../../types/api';
import { useBusinessRulePoliciesAdmin } from '../../hooks/useBusinessRulePoliciesAdmin';
import { BusinessRulePolicyModal } from './BusinessRulePolicyModal';
import logger from '../../services/logger';

const { Text } = Typography;

const STEP_TYPE_OPTIONS = [
  { value: '', label: 'Tous' },
  { value: 'terraform_cloud', label: 'Terraform Cloud' },
  { value: 'aap', label: 'AAP' },
  { value: 'azure_devops', label: 'Azure DevOps' },
  { value: 'github_actions', label: 'GitHub Actions' },
];

export function BusinessRulesPolicyPanel() {
  const { notification, modal } = App.useApp();
  const [modalOpen, setModalOpen] = useState(false);
  const [editPolicy, setEditPolicy] = useState<BusinessRulePolicyDetail | null>(null);
  const [saving, setSaving] = useState(false);
  const [filterStepType, setFilterStepType] = useState('');
  const [filterActiveOnly, setFilterActiveOnly] = useState(false);

  const { policies, loading, fetchPolicies, getOne, create, update, remove } = useBusinessRulePoliciesAdmin({
    step_type: filterStepType || undefined,
    is_active: filterActiveOnly ? true : undefined,
  });

  const handleCreate = () => {
    setEditPolicy(null);
    setModalOpen(true);
  };

  const handleEdit = async (record: BusinessRulePolicyListItem) => {
    try {
      const detail = await getOne(record.id);
      setEditPolicy(detail);
      setModalOpen(true);
    } catch (err) {
      notification.error({ message: 'Erreur lors du chargement de la règle' });
      logger.error('business_rule_policy_load_error', { error: String(err) });
    }
  };

  const handleDelete = (record: BusinessRulePolicyListItem) => {
    modal.confirm({
      title: 'Supprimer la règle métier',
      content: `Êtes-vous sûr de vouloir supprimer la règle « ${record.name} » ? Les actions associées n'auront plus de règle.`,
      okText: 'Supprimer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        try {
          await remove(record.id);
          notification.success({ message: `Règle « ${record.name} » supprimée` });
        } catch (err) {
          notification.error({ message: 'Erreur lors de la suppression' });
          logger.error('business_rule_policy_delete_error', { error: String(err) });
        }
      },
    });
  };

  const handleSave = async (payload: BusinessRulePolicyPayload) => {
    setSaving(true);
    try {
      if (editPolicy) {
        await update(editPolicy.id, payload);
        notification.success({ message: `Règle « ${payload.name} » mise à jour` });
      } else {
        await create(payload);
        notification.success({ message: `Règle « ${payload.name} » créée` });
      }
      setModalOpen(false);
      setEditPolicy(null);
    } finally {
      setSaving(false);
    }
  };

  const columns: TableProps<BusinessRulePolicyListItem>['columns'] = [
    {
      title: 'Nom',
      dataIndex: 'name',
      key: 'name',
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (val: string | null) => val || <Text type="secondary">—</Text>,
    },
    {
      title: 'Type',
      dataIndex: 'step_type',
      key: 'step_type',
      width: 150,
      render: (val: string | null) =>
        val ? <Tag>{val}</Tag> : <Text type="secondary">—</Text>,
    },
    {
      title: 'Actif',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (val: boolean) =>
        val ? <Tag color="green">Oui</Tag> : <Tag color="red">Non</Tag>,
    },
    {
      title: 'Modifié',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 160,
      render: (val: string) => (
        <Text type="secondary">{new Date(val).toLocaleString('fr-FR')}</Text>
      ),
    },
    {
      title: '',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
            aria-label={`Modifier ${record.name}`}
          />
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record)}
            aria-label={`Supprimer ${record.name}`}
          />
        </Space>
      ),
    },
  ];

  return (
    <>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} align="center">
        <Space>
          <Select
            value={filterStepType}
            onChange={setFilterStepType}
            options={STEP_TYPE_OPTIONS}
            style={{ width: 180 }}
            placeholder="Type d'étape"
            aria-label="Filtre par type"
          />
          <Space size="small">
            <Switch
              checked={filterActiveOnly}
              onChange={setFilterActiveOnly}
              size="small"
            />
            <Text type="secondary">Actifs seulement</Text>
          </Space>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => fetchPolicies()} loading={loading}>
            Actualiser
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            Créer règle métier
          </Button>
        </Space>
      </Space>

      <Table<BusinessRulePolicyListItem>
        columns={columns}
        dataSource={policies}
        loading={loading}
        rowKey="id"
        size="small"
        pagination={{ pageSize: 20 }}
        locale={{ emptyText: 'Aucune règle métier configurée' }}
      />

      <BusinessRulePolicyModal
        open={modalOpen}
        onCancel={() => { setModalOpen(false); setEditPolicy(null); }}
        onSave={handleSave}
        editPolicy={editPolicy}
        saving={saving}
      />
    </>
  );
}
