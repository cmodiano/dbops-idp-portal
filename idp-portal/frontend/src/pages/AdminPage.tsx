/**
 * AdminPage - Administration du Catalogue (Story 2.1, AC #1; Story 2.4, AC #2; Story 2.9 Profiles; Story 8.2 Analytics).
 *
 * Features:
 * - Tabs: Actions | Profiles | Integrations | Metriques (Story 8.2)
 * - Actions: list, "Nouvelle action", status badge, notifications
 * - Profiles: list, "Nouveau profil", create/edit/delete (Story 2.9, AC #1–#4)
 * - Metriques: DBOPS analytics dashboard (Story 8.2)
 */

import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import { Typography, Button, Table, Space, Card, Tag, Tabs, App, Spin, Checkbox, Modal } from 'antd';
import type { TableProps } from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  SendOutlined,
  EyeOutlined,
  StopOutlined,
  PlayCircleOutlined,
  ApartmentOutlined,
  DeleteOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons';
import { ActionWizard } from '../components/admin/ActionWizard';
import { ActionStatusBadge } from '../components/admin/ActionStatusBadge';
import { getItemTypeIcon } from '../utils/iconHelpers';
import { ProfileWizard } from '../components/admin/ProfileWizard';
import { ProfilesTable } from '../components/admin/ProfilesTable';
import { ProfileImportModal } from '../components/admin/ProfileImportModal';
import { IntegrationsTable } from '../components/admin/IntegrationsTable';
import { IntegrationForm } from '../components/admin/IntegrationForm';
import { CategoriesAdminTable } from '../components/admin/CategoriesAdminTable';

const AdminAnalyticsDashboard = lazy(() => import('../components/admin/analytics/AdminAnalyticsDashboard'));
const FeatureFlagsPanel = lazy(() => import('../components/admin/FeatureFlagsPanel').then(m => ({ default: m.FeatureFlagsPanel })));
import { createAction, getAction, getAdminActions, updateAction, updateActionStatus, deleteAction, deactivateAction, reactivateAction } from '../services/admin_service';
import type { DeactivateConfirmation } from '../services/admin_service';
import { getProfiles, getProfile, deleteProfile, exportProfilesYaml } from '../services/profiles_service';
import { getIntegrations, getIntegration, createIntegration, updateIntegration, deleteIntegration } from '../services/integrations_service';
import type { ActionCreate, ActionListItem, ActionDetail, ActionResponse, ActionStatus, StatusTransition, AdminActionsFilters, ProfileResponse, ProfileListItem, IntegrationResponse, IntegrationListItem, IntegrationCreate, IntegrationUpdate } from '../types/api';
import { getTagStyle } from '../utils/tagStyles';
import { useTheme } from '../contexts/ThemeContext';

const { Title } = Typography;

const getColumns = (
  onEdit: (record: ActionListItem) => void,
  onStatusChange: (record: ActionListItem, transition: StatusTransition) => void,
  onDelete: (record: ActionListItem) => void,
  onDeactivate: (record: ActionListItem) => void,
  onReactivate: (record: ActionListItem) => void,
  isDark: boolean,
): TableProps<ActionListItem>['columns'] => [
  {
    title: 'Nom',
    dataIndex: 'name',
    key: 'name',
    sorter: (a, b) => a.name.localeCompare(b.name),
    render: (name: string, record: ActionListItem) => {
      const itemType = record.item_type ?? 'action';
      const { icon } = getItemTypeIcon(itemType, record.engine, { withTooltip: true, fontSize: 18 });
      return (
        <Space>
          {icon}
          {name}
        </Space>
      );
    },
  },
  {
    title: 'Type',
    key: 'item_type',
    width: 100,
    render: (_: unknown, record: ActionListItem) => {
      const itemType = record.item_type ?? 'action';
      return (
        <Tag color={itemType === 'workflow' ? 'purple' : 'blue'}>
          {itemType === 'workflow' ? 'Workflow' : 'Action'}
        </Tag>
      );
    },
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
          {tags.map((t) => {
            const tagStyle = getTagStyle(t, isDark);
            return (
              <Tag key={t} style={{ borderRadius: 16, padding: '2px 10px', ...tagStyle }}>
                {t}
              </Tag>
            );
          })}
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
    width: 280,
    render: (_: unknown, record: ActionListItem) => (
      <Space size="small">
        {record.status === 'draft' && (
          <>
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => onEdit(record)}>
              Modifier
            </Button>
            <Button
              type="link"
              size="small"
              icon={<SendOutlined />}
              onClick={() => onStatusChange(record, 'publish')}
            >
              Publier
            </Button>
            {/* AC1/AC6: Delete only for draft with 0 executions */}
            {record.execution_count === 0 && (
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => onDelete(record)}
              >
                Supprimer
              </Button>
            )}
          </>
        )}
        {record.status === 'published' && (
          <>
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => onEdit(record)}>
              Voir
            </Button>
            {/* AC6: Supprimer only when execution_count=0; Désactiver always (for both 0 and >0) */}
            {record.execution_count === 0 && (
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => onDelete(record)}
              >
                Supprimer
              </Button>
            )}
            <Button
              type="link"
              size="small"
              danger
              icon={<PauseCircleOutlined />}
              onClick={() => onDeactivate(record)}
            >
              Desactiver
            </Button>
          </>
        )}
        {record.status === 'disabled' && (
          <>
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => onEdit(record)}>
              Modifier
            </Button>
            {/* AC1/AC6: Delete only when execution_count=0 */}
            {record.execution_count === 0 && (
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={() => onDelete(record)}
              >
                Supprimer
              </Button>
            )}
            {/* AC5: Reactivate for disabled actions */}
            <Button
              type="link"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => onReactivate(record)}
            >
              Reactiver
            </Button>
          </>
        )}
      </Space>
    ),
  },
];

export default function AdminPage() {
  const { notification, modal } = App.useApp();
  const { effectiveMode } = useTheme();
  const [actions, setActions] = useState<ActionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [editAction, setEditAction] = useState<ActionDetail | null>(null);
  const [wizardInitialItemType, setWizardInitialItemType] = useState<'action' | 'workflow' | null>(null);

  // Story 18.1: include disabled actions filter (AC4/AC5)
  const [includeDisabled, setIncludeDisabled] = useState(false);
  // Story 18.1: cascade confirmation modal state (AC3)
  const [cascadeModalOpen, setCascadeModalOpen] = useState(false);
  const [cascadeAction, setCascadeAction] = useState<ActionListItem | null>(null);
  const [cascadeWorkflows, setCascadeWorkflows] = useState<{ id: number; name: string; status: string }[]>([]);
  const [cascadeReason, setCascadeReason] = useState<string>('');

  const [profiles, setProfiles] = useState<ProfileListItem[]>([]);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [editProfile, setEditProfile] = useState<ProfileResponse | null>(null);
  const [importYamlModalOpen, setImportYamlModalOpen] = useState(false);

  const [integrations, setIntegrations] = useState<IntegrationListItem[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(false);
  const [integrationModalOpen, setIntegrationModalOpen] = useState(false);
  const [editIntegration, setEditIntegration] = useState<IntegrationResponse | null>(null);
  const [integrationSubmitError, setIntegrationSubmitError] = useState<string | null>(null);
  const [integrationSubmitting, setIntegrationSubmitting] = useState(false);

  const fetchActions = useCallback(async (filters?: AdminActionsFilters) => {
    setLoading(true);
    try {
      const mergedFilters: AdminActionsFilters = { ...filters };
      if (includeDisabled) mergedFilters.include_disabled = true;
      const response = await getAdminActions(mergedFilters);
      setActions(response.data ?? []);
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur de chargement',
      });
    } finally {
      setLoading(false);
    }
  }, [notification, includeDisabled]);

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
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur de chargement des profils',
      });
    } finally {
      setProfilesLoading(false);
    }
  }, [notification]);

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

  const handleEditSubmit = async (action: ActionCreate) => {
    if (!editAction) throw new Error('editAction manquant');
    const updated = await updateAction(editAction.id, action);
    return updated;
  };

  const handleEdit = async (record: ActionListItem) => {
    setSubmitError(null);
    try {
      const detail = await getAction(record.id);
      setEditAction(detail);
      setModalOpen(true);
    } catch (err) {
      notification.error({
        title: 'Erreur',
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
        title: 'Succes',
        description: `Action "${record.name}" ${statusLabels[transition]}`,
      });
      fetchActions();
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de changer le statut',
      });
    }
  };

  // Story 18.1 AC1: Hard delete (execution_count=0 only)
  const handleDelete = (record: ActionListItem) => {
    modal.confirm({
      title: 'Supprimer l\'action',
      content: `Voulez-vous vraiment supprimer definitivement l'action « ${record.name} » ? Cette operation est irreversible.`,
      okText: 'Supprimer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        try {
          await deleteAction(record.id);
          notification.success({
            message: 'Succes',
            description: `Action « ${record.name} » supprimee`,
          });
          fetchActions();
        } catch (err) {
          notification.error({
            message: 'Erreur',
            description: err instanceof Error ? err.message : 'Impossible de supprimer l\'action',
          });
        }
      },
    });
  };

  // Story 18.1 AC2/AC3: Deactivate (soft-delete) with cascade confirmation
  const handleDeactivate = async (record: ActionListItem) => {
    try {
      const result = await deactivateAction(record.id);
      if ('status' in result && result.status === 'requires_confirmation') {
        // AC3: Show cascade confirmation modal with affected workflows
        const confirmation = result as DeactivateConfirmation;
        setCascadeAction(record);
        setCascadeWorkflows(confirmation.affected_workflows);
        setCascadeReason('');
        setCascadeModalOpen(true);
      } else {
        // No workflows affected — deactivated directly
        notification.success({
          message: 'Succes',
          description: `Action « ${record.name} » desactivee`,
        });
        fetchActions();
      }
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de desactiver l\'action',
      });
    }
  };

  // Story 18.1 AC3: Confirm cascade deactivation
  const handleCascadeConfirm = async () => {
    if (!cascadeAction) return;
    try {
      await deactivateAction(cascadeAction.id, cascadeReason || undefined, true);
      notification.success({
        message: 'Succes',
        description: `Action « ${cascadeAction.name} » et ${cascadeWorkflows.length} workflow(s) desactive(s)`,
      });
      setCascadeModalOpen(false);
      setCascadeAction(null);
      setCascadeWorkflows([]);
      setCascadeReason('');
      fetchActions();
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de desactiver l\'action',
      });
    }
  };

  // Story 18.1 AC5: Reactivate a disabled action
  const handleReactivate = async (record: ActionListItem) => {
    try {
      await reactivateAction(record.id);
      notification.success({
        message: 'Succes',
        description: `Action « ${record.name} » reactivee`,
      });
      fetchActions();
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de reactiver l\'action',
      });
    }
  };

  const handleSuccess = (action: ActionDetail | ActionResponse | ActionListItem) => {
    const wasEdit = !!editAction;
    setSubmitting(false);
    setModalOpen(false);
    setEditAction(null);
    setWizardInitialItemType(null);
    setSubmitError(null);
    const name = 'name' in action ? action.name : '';
    notification.success({
      title: 'Succes',
      description: wasEdit ? `Action "${name}" mise a jour` : `Action "${name}" creee avec succes`,
    });
    fetchActions();
  };

  const handleCancel = () => {
    setModalOpen(false);
    setEditAction(null);
    setWizardInitialItemType(null);
    setSubmitError(null);
  };

  const handleProfileEdit = async (record: ProfileListItem) => {
    try {
      const detail = await getProfile(record.id);
      setEditProfile(detail);
      setProfileModalOpen(true);
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de charger le profil',
      });
    }
  };

  const handleProfileDelete = async (record: ProfileListItem) => {
    try {
      await deleteProfile(record.id);
      notification.success({ title: 'Succes', description: `Profil "${record.name}" supprime` });
      fetchProfiles();
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de supprimer le profil',
      });
    }
  };

  const handleProfileSuccess = (profile: ProfileResponse) => {
    setProfileModalOpen(false);
    setEditProfile(null);
    notification.success({
      title: 'Succes',
      description: editProfile ? `Profil "${profile.name}" mis a jour` : `Profil "${profile.name}" cree`,
    });
    fetchProfiles();
  };

  const handleProfileCancel = () => {
    setProfileModalOpen(false);
    setEditProfile(null);
  };

  const handleExportYaml = useCallback(async () => {
    try {
      await exportProfilesYaml();
      notification.success({ title: 'Export YAML', description: 'Fichier profiles.yaml téléchargé.' });
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur lors de l\'export YAML',
      });
    }
  }, [notification]);

  const handleImportYaml = useCallback(() => {
    setImportYamlModalOpen(true);
  }, []);

  const handleImportYamlSuccess = useCallback((created: number, updated: number) => {
    setImportYamlModalOpen(false);
    notification.success({
      title: 'Import YAML',
      description: `Import reussi : ${created} cree(s), ${updated} mis a jour.`,
    });
    fetchProfiles();
  }, [notification, fetchProfiles]);

  const fetchIntegrations = useCallback(async () => {
    setIntegrationsLoading(true);
    try {
      const list = await getIntegrations();
      setIntegrations(list);
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur de chargement des intégrations',
      });
    } finally {
      setIntegrationsLoading(false);
    }
  }, [notification]);

  const handleIntegrationEdit = async (record: IntegrationListItem) => {
    setIntegrationSubmitError(null);
    try {
      const detail = await getIntegration(record.id);
      setEditIntegration(detail);
      // Ouvrir la modal au prochain tick pour que le formulaire reçoive bien editIntegration (préremplissage)
      setTimeout(() => setIntegrationModalOpen(true), 0);
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de charger l\'intégration',
      });
    }
  };

  const handleIntegrationDelete = async (record: IntegrationListItem) => {
    try {
      await deleteIntegration(record.id);
      notification.success({
        title: 'Succes',
        description: `Intégration « ${record.name} » supprimée`,
      });
      fetchIntegrations();
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de supprimer l\'intégration',
      });
    }
  };

  const handleIntegrationSuccess = (integration: IntegrationResponse) => {
    setIntegrationModalOpen(false);
    setEditIntegration(null);
    setIntegrationSubmitError(null);
    const wasEdit = !!editIntegration;
    notification.success({
      title: 'Succès',
      description: wasEdit
        ? `Intégration « ${integration.name} » mise à jour`
        : `Intégration « ${integration.name} » créée avec succès`,
    });
    fetchIntegrations();
  };

  const handleIntegrationCancel = () => {
    setIntegrationModalOpen(false);
    setEditIntegration(null);
    setIntegrationSubmitError(null);
  };

  const handleIntegrationSubmit = async (payload: IntegrationCreate | IntegrationUpdate) => {
    setIntegrationSubmitting(true);
    setIntegrationSubmitError(null);
    try {
      if (editIntegration) {
        return await updateIntegration(editIntegration.id, payload as IntegrationUpdate);
      }
      return await createIntegration(payload as IntegrationCreate);
    } catch (err) {
      setIntegrationSubmitError(err instanceof Error ? err.message : 'Erreur lors de l\'enregistrement');
      throw err;
    } finally {
      setIntegrationSubmitting(false);
    }
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
        onChange={(key) => {
          if (key === 'profiles') fetchProfiles();
          if (key === 'integrations') fetchIntegrations();
        }}
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
                          setWizardInitialItemType('action');
                          setModalOpen(true);
                        }}
                      >
                        Nouvelle action
                      </Button>
                      <Button
                        icon={<ApartmentOutlined />}
                        onClick={() => {
                          setEditAction(null);
                          setWizardInitialItemType('workflow');
                          setModalOpen(true);
                        }}
                      >
                        Nouveau workflow
                      </Button>
                    </Space>
                  </Space>
                }
                styles={{
                  header: { borderBottom: 'none', paddingBottom: 0 },
                  body: { paddingTop: 16 },
                }}
              >
                {/* Story 18.1 AC4/AC5: Toggle to include disabled actions */}
                <div style={{ marginBottom: 12 }}>
                  <Checkbox
                    checked={includeDisabled}
                    onChange={(e) => setIncludeDisabled(e.target.checked)}
                  >
                    Inclure les actions desactivees
                  </Checkbox>
                </div>
                <Table
                  columns={getColumns(handleEdit, handleStatusChange, handleDelete, handleDeactivate, handleReactivate, effectiveMode === 'dark')}
                  dataSource={actions}
                  rowKey="id"
                  loading={loading}
                  pagination={{ pageSize: 10, showSizeChanger: true }}
                  locale={{ emptyText: 'Aucune action dans le catalogue' }}
                  rowClassName={(record) => record.status === 'disabled' ? 'action-row-disabled' : ''}
                  onRow={(record) => ({
                    style: record.status === 'disabled' ? { opacity: 0.6 } : undefined,
                  })}
                />
              </Card>
            ),
          },
          {
            key: 'profiles',
            label: 'Profils',
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
          {
            key: 'integrations',
            label: 'Intégrations',
            children: (
              <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
                <IntegrationsTable
                  dataSource={integrations}
                  loading={integrationsLoading}
                  onEdit={handleIntegrationEdit}
                  onDelete={handleIntegrationDelete}
                  onNew={() => {
                    setEditIntegration(null);
                    setIntegrationModalOpen(true);
                  }}
                  onRefresh={fetchIntegrations}
                />
              </Card>
            ),
          },
          {
            key: 'categories',
            label: 'Catégories',
            children: (
              <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
                <CategoriesAdminTable />
              </Card>
            ),
          },
          {
            key: 'analytics',
            label: 'Metriques',
            children: (
              <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
                <Suspense fallback={<Spin style={{ display: 'block', margin: '48px auto' }} />}>
                  <AdminAnalyticsDashboard />
                </Suspense>
              </Card>
            ),
          },
          {
            key: 'feature-flags',
            label: 'Feature Flags',
            children: (
              <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
                <Suspense fallback={<Spin style={{ display: 'block', margin: '48px auto' }} />}>
                  <FeatureFlagsPanel />
                </Suspense>
              </Card>
            ),
          },
        ]}
      />

      <ActionWizard
        open={modalOpen}
        onCancel={handleCancel}
        onSubmit={editAction ? handleEditSubmit : handleCreate}
        loading={submitting}
        error={submitError}
        editAction={editAction}
        onSuccess={handleSuccess}
        initialItemType={editAction ? undefined : wizardInitialItemType ?? undefined}
      />

      <ProfileWizard
        open={profileModalOpen}
        onCancel={handleProfileCancel}
        editProfile={editProfile}
        onSuccess={handleProfileSuccess}
      />

      <ProfileImportModal
        open={importYamlModalOpen}
        onCancel={() => setImportYamlModalOpen(false)}
        onSuccess={handleImportYamlSuccess}
      />

      <IntegrationForm
        open={integrationModalOpen}
        onCancel={handleIntegrationCancel}
        onSubmit={handleIntegrationSubmit}
        loading={integrationSubmitting}
        error={integrationSubmitError}
        editIntegration={editIntegration}
        onSuccess={handleIntegrationSuccess}
      />

      {/* Story 18.1 AC3: Cascade confirmation modal for workflow deactivation */}
      <Modal
        title="Confirmation de desactivation en cascade"
        open={cascadeModalOpen}
        onCancel={() => {
          setCascadeModalOpen(false);
          setCascadeAction(null);
          setCascadeWorkflows([]);
          setCascadeReason('');
        }}
        onOk={handleCascadeConfirm}
        okText="Confirmer la desactivation"
        okType="danger"
        cancelText="Annuler"
      >
        <p>
          L'action <strong>{cascadeAction?.name}</strong> est referencee par{' '}
          {cascadeWorkflows.length} workflow(s) qui seront egalement desactive(s) :
        </p>
        <ul style={{ marginBottom: 16 }}>
          {cascadeWorkflows.map((wf) => (
            <li key={wf.id}>
              {wf.name} <Tag>{wf.status}</Tag>
            </li>
          ))}
        </ul>
        <div>
          <Typography.Text type="secondary">Raison (optionnel) :</Typography.Text>
          <input
            type="text"
            value={cascadeReason}
            onChange={(e) => setCascadeReason(e.target.value)}
            placeholder="Raison de la desactivation"
            style={{ width: '100%', marginTop: 4, padding: '4px 8px' }}
          />
        </div>
      </Modal>
    </div>
  );
}
