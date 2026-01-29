/**
 * AdminPage - Administration du Catalogue (Story 2.1, AC #1; Story 2.4, AC #2; Story 2.9 Profiles).
 *
 * Features:
 * - Tabs: Actions | Profiles
 * - Actions: list, "Nouvelle action", status badge, notifications
 * - Profiles: list, "Nouveau profil", create/edit/delete (Story 2.9, AC #1–#4)
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Typography, Button, Table, Space, notification, Card, Tag, Tabs, Modal } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { ActionForm } from '../components/admin/ActionForm';
import { ActionStatusBadge } from '../components/admin/ActionStatusBadge';
import { ProfileForm } from '../components/admin/ProfileForm';
import { ProfilesTable } from '../components/admin/ProfilesTable';
import { createAction, getAction, getAdminActions, updateActionStatus } from '../services/admin_service';
import { getProfiles, getProfile, createProfile, updateProfile, deleteProfile, exportProfilesYaml, importProfilesYaml } from '../services/profiles_service';
import type { ActionCreate, ActionListItem, ActionDetail, ActionResponse, ActionStatus, StatusTransition, AdminActionsFilters, ProfileCreate, ProfileUpdate, ProfileResponse, ProfileListItem } from '../types/api';

const { Title } = Typography;

const getColumns = (
  onEdit: (record: ActionListItem) => void,
  onStatusChange: (record: ActionListItem, transition: StatusTransition) => void,
): ColumnsType<ActionListItem> => [
  {
    title: 'Nom',
    dataIndex: 'name',
    key: 'name',
    sorter: (a, b) => a.name.localeCompare(b.name),
  },
  {
    title: 'Categorie',
    dataIndex: 'category',
    key: 'category',
    filters: [
      { text: 'Provisioning', value: 'Provisioning' },
      { text: 'Patching', value: 'Patching' },
      { text: 'Administration', value: 'Administration' },
      { text: 'Monitoring', value: 'Monitoring' },
    ],
    onFilter: (value, record) => record.category === value,
  },
  {
    title: 'Moteur',
    dataIndex: 'engine',
    key: 'engine',
  },
  {
    title: 'Statut',
    dataIndex: 'status',
    key: 'status',
    render: (status: ActionStatus) => <ActionStatusBadge status={status} />,
    filters: [
      { text: 'Brouillon', value: 'draft' },
      { text: 'Publiee', value: 'published' },
      { text: 'Desactivee', value: 'disabled' },
    ],
    onFilter: (value, record) => record.status === value,
  },
  {
    title: 'Executions',
    dataIndex: 'execution_count',
    key: 'execution_count',
    sorter: (a, b) => a.execution_count - b.execution_count,
    width: 100,
  },
  {
    title: 'Tags',
    dataIndex: 'tags',
    key: 'tags',
    render: (tags: string[] | undefined) =>
      (tags?.length ? (
        <Space size={4} wrap>
          {tags.map((t) => (
            <Tag key={t}>{t}</Tag>
          ))}
        </Space>
      ) : (
        <Typography.Text type="secondary">—</Typography.Text>
      )),
  },
  {
    title: 'Date de creation',
    dataIndex: 'created_at',
    key: 'created_at',
    render: (date: string) => new Date(date).toLocaleDateString('fr-CA'),
    sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    defaultSortOrder: 'descend',
  },
  {
    title: '',
    key: 'actions',
    width: 200,
    render: (_: unknown, record: ActionListItem) => (
      <Space size="small">
        {record.status === 'draft' && (
          <>
            <Button type="link" size="small" onClick={() => onEdit(record)}>
              Modifier
            </Button>
            <Button type="link" size="small" onClick={() => onStatusChange(record, 'publish')}>
              Publier
            </Button>
          </>
        )}
        {record.status === 'published' && (
          <>
            <Button type="link" size="small" onClick={() => onEdit(record)}>
              Voir
            </Button>
            <Button type="link" size="small" danger onClick={() => onStatusChange(record, 'disable')}>
              Desactiver
            </Button>
          </>
        )}
        {record.status === 'disabled' && (
          <>
            <Button type="link" size="small" onClick={() => onEdit(record)}>
              Voir
            </Button>
            <Button type="link" size="small" onClick={() => onStatusChange(record, 'enable')}>
              Reactiver
            </Button>
          </>
        )}
      </Space>
    ),
  },
];

export default function AdminPage() {
  const [actions, setActions] = useState<ActionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [editAction, setEditAction] = useState<ActionDetail | null>(null);

  const [profiles, setProfiles] = useState<ProfileListItem[]>([]);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [profileSubmitting, setProfileSubmitting] = useState(false);
  const [profileSubmitError, setProfileSubmitError] = useState<string | null>(null);
  const [editProfile, setEditProfile] = useState<ProfileResponse | null>(null);
  const [importYamlModalOpen, setImportYamlModalOpen] = useState(false);
  const [importYamlLoading, setImportYamlLoading] = useState(false);
  const importYamlFileRef = useRef<File | null>(null);

  const fetchActions = useCallback(async (filters?: AdminActionsFilters) => {
    setLoading(true);
    try {
      const response = await getAdminActions(filters);
      setActions(response.data);
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur de chargement',
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchActions();
  }, [fetchActions]);

  const fetchProfiles = useCallback(async () => {
    setProfilesLoading(true);
    try {
      const list = await getProfiles();
      setProfiles(list);
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur de chargement des profils',
      });
    } finally {
      setProfilesLoading(false);
    }
  }, []);

  const handleCreate = async (action: ActionCreate) => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await createAction(action);
      return created;
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Erreur de creation');
      setSubmitting(false);
      throw err;
    }
  };

  const handleEditSubmit = async (_action: ActionCreate) => {
    if (!editAction) throw new Error('editAction manquant');
    return editAction;
  };

  const handleEdit = async (record: ActionListItem) => {
    setSubmitError(null);
    try {
      const detail = await getAction(record.id);
      setEditAction(detail);
      setModalOpen(true);
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de charger l\'action',
      });
    }
  };

  const handleStatusChange = async (record: ActionListItem, transition: StatusTransition) => {
    try {
      await updateActionStatus(record.id, transition);
      const statusLabels: Record<StatusTransition, string> = {
        publish: 'publiee',
        disable: 'desactivee',
        enable: 'reactivee',
      };
      notification.success({
        message: 'Succes',
        description: `Action "${record.name}" ${statusLabels[transition]}`,
      });
      fetchActions();
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de changer le statut',
      });
    }
  };

  const handleSuccess = (action: ActionDetail | ActionResponse | ActionListItem) => {
    const wasEdit = !!editAction;
    setSubmitting(false);
    setModalOpen(false);
    setEditAction(null);
    setSubmitError(null);
    const name = 'name' in action ? action.name : '';
    notification.success({
      message: 'Succes',
      description: wasEdit ? `Action "${name}" mise a jour` : `Action "${name}" creee avec succes`,
    });
    fetchActions();
  };

  const handleCancel = () => {
    setModalOpen(false);
    setEditAction(null);
    setSubmitError(null);
  };

  const handleProfileCreate = async (payload: ProfileCreate) => {
    setProfileSubmitting(true);
    setProfileSubmitError(null);
    try {
      const created = await createProfile(payload);
      return created;
    } catch (err) {
      setProfileSubmitError(err instanceof Error ? err.message : 'Erreur de creation');
      setProfileSubmitting(false);
      throw err;
    }
  };

  const handleProfileUpdate = async (payload: ProfileUpdate) => {
    if (!editProfile) throw new Error('editProfile manquant');
    setProfileSubmitting(true);
    setProfileSubmitError(null);
    try {
      const updated = await updateProfile(editProfile.id, payload);
      return updated;
    } catch (err) {
      setProfileSubmitError(err instanceof Error ? err.message : 'Erreur de mise a jour');
      setProfileSubmitting(false);
      throw err;
    }
  };

  const handleProfileEdit = async (record: ProfileListItem) => {
    setProfileSubmitError(null);
    try {
      const detail = await getProfile(record.id);
      setEditProfile(detail);
      setProfileModalOpen(true);
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de charger le profil',
      });
    }
  };

  const handleProfileDelete = async (record: ProfileListItem) => {
    try {
      await deleteProfile(record.id);
      notification.success({ message: 'Succes', description: `Profil "${record.name}" supprime` });
      fetchProfiles();
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de supprimer le profil',
      });
    }
  };

  const handleProfileSuccess = (profile: ProfileResponse) => {
    setProfileSubmitting(false);
    setProfileModalOpen(false);
    setEditProfile(null);
    setProfileSubmitError(null);
    notification.success({
      message: 'Succes',
      description: editProfile ? `Profil "${profile.name}" mis a jour` : `Profil "${profile.name}" cree`,
    });
    fetchProfiles();
  };

  const handleProfileCancel = () => {
    setProfileModalOpen(false);
    setEditProfile(null);
    setProfileSubmitError(null);
  };

  const handleExportYaml = useCallback(async () => {
    try {
      await exportProfilesYaml();
      notification.success({ message: 'Export YAML', description: 'Fichier profiles.yaml téléchargé.' });
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur lors de l\'export YAML',
      });
    }
  }, []);

  const handleImportYaml = useCallback(() => {
    importYamlFileRef.current = null;
    setImportYamlModalOpen(true);
  }, []);

  const handleImportYamlSubmit = useCallback(async () => {
    const file = importYamlFileRef.current;
    if (!file) {
      notification.warning({ message: 'Fichier requis', description: 'Veuillez sélectionner un fichier .yaml ou .yml' });
      return;
    }
    setImportYamlLoading(true);
    try {
      const { created, updated } = await importProfilesYaml(file);
      setImportYamlModalOpen(false);
      importYamlFileRef.current = null;
      notification.success({
        message: 'Import YAML',
        description: `Import réussi : ${created} créé(s), ${updated} mis à jour.`,
      });
      fetchProfiles();
    } catch (err) {
      notification.error({
        message: 'Erreur d\'import',
        description: err instanceof Error ? err.message : 'Erreur lors de l\'import YAML',
      });
    } finally {
      setImportYamlLoading(false);
    }
  }, []);

  const handleProfileSubmit = async (values: ProfileCreate | ProfileUpdate) => {
    if (editProfile) return handleProfileUpdate(values as ProfileUpdate);
    return handleProfileCreate(values as ProfileCreate);
  };

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* Page Header */}
      <div style={{ marginBottom: 32 }}>
        <Title level={2} style={{ margin: 0, marginBottom: 8 }}>
          Administration du Catalogue
        </Title>
        <Typography.Text type="secondary">
          Gerez vos actions et profils
        </Typography.Text>
      </div>

      <Tabs
        defaultActiveKey="actions"
        onChange={(key) => { if (key === 'profiles') fetchProfiles(); }}
        items={[
          {
            key: 'actions',
            label: 'Actions',
            children: (
              <Card
                title={
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <span>Actions ({actions.length})</span>
                    <Space>
                      <Button icon={<ReloadOutlined />} onClick={() => fetchActions()} loading={loading}>
                        Actualiser
                      </Button>
                      <Button
                        type="primary"
                        icon={<PlusOutlined />}
                        onClick={() => {
                          setEditAction(null);
                          setModalOpen(true);
                        }}
                      >
                        Nouvelle action
                      </Button>
                    </Space>
                  </Space>
                }
                styles={{
                  header: { borderBottom: 'none', paddingBottom: 0 },
                  body: { paddingTop: 16 },
                }}
              >
                <Table
                  columns={getColumns(handleEdit, handleStatusChange)}
                  dataSource={actions}
                  rowKey="id"
                  loading={loading}
                  pagination={{ pageSize: 10, showSizeChanger: true }}
                  locale={{ emptyText: 'Aucune action dans le catalogue' }}
                />
              </Card>
            ),
          },
          {
            key: 'profiles',
            label: 'Profiles',
            children: (
              <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
                <ProfilesTable
                  dataSource={profiles}
                  loading={profilesLoading}
                  onEdit={handleProfileEdit}
                  onDelete={handleProfileDelete}
                  onNew={() => {
                    setEditProfile(null);
                    setProfileModalOpen(true);
                  }}
                  onExportYaml={handleExportYaml}
                  onImportYaml={handleImportYaml}
                />
              </Card>
            ),
          },
        ]}
      />

      <ActionForm
        open={modalOpen}
        onCancel={handleCancel}
        onSubmit={editAction ? handleEditSubmit : handleCreate}
        loading={submitting}
        error={submitError}
        editAction={editAction}
        onSuccess={handleSuccess}
      />

      <ProfileForm
        open={profileModalOpen}
        onCancel={handleProfileCancel}
        onSubmit={handleProfileSubmit}
        loading={profileSubmitting}
        error={profileSubmitError}
        editProfile={editProfile}
        onSuccess={handleProfileSuccess}
      />

      <Modal
        title="Importer YAML"
        open={importYamlModalOpen}
        onCancel={() => { setImportYamlModalOpen(false); importYamlFileRef.current = null; }}
        onOk={handleImportYamlSubmit}
        okText="Importer"
        confirmLoading={importYamlLoading}
        destroyOnClose
      >
        <p style={{ marginBottom: 8 }}>Sélectionnez un fichier profiles.yaml ou .yml :</p>
        <input
          type="file"
          accept=".yaml,.yml"
          onChange={(e) => { importYamlFileRef.current = e.target.files?.[0] ?? null; }}
        />
      </Modal>
    </div>
  );
}
