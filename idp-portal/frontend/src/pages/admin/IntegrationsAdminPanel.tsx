import { useState, useEffect, useCallback } from 'react';
import { Card } from 'antd';
import type { NotificationInstance } from 'antd';
import { IntegrationsTable } from '../../components/admin/IntegrationsTable';
import { IntegrationForm } from '../../components/admin/IntegrationForm';
import { getIntegrations, getIntegration, createIntegration, updateIntegration, deleteIntegration } from '../../services/integrations_service';
import type { IntegrationResponse, IntegrationListItem, IntegrationCreate, IntegrationUpdate } from '../../types/api';

export interface IntegrationsAdminPanelProps {
  notification: NotificationInstance;
}

export function IntegrationsAdminPanel({ notification }: IntegrationsAdminPanelProps) {
  const [integrations, setIntegrations] = useState<IntegrationListItem[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(false);
  const [integrationModalOpen, setIntegrationModalOpen] = useState(false);
  const [editIntegration, setEditIntegration] = useState<IntegrationResponse | null>(null);
  const [integrationSubmitError, setIntegrationSubmitError] = useState<string | null>(null);
  const [integrationSubmitting, setIntegrationSubmitting] = useState(false);

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

  useEffect(() => {
    fetchIntegrations();
  }, [fetchIntegrations]);

  const handleIntegrationEdit = async (record: IntegrationListItem) => {
    setIntegrationSubmitError(null);
    try {
      const detail = await getIntegration(record.id);
      setEditIntegration(detail);
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
      const result = await deleteIntegration(record.id);
      const count = result?.disabled_actions_count ?? 0;
      if (count > 0) {
        notification.warning({
          title: 'Intégration supprimée',
          description: `${count} action(s) associée(s) ont été désactivées.`,
        });
      } else {
        notification.success({
          title: 'Succès',
          description: `Intégration « ${record.name} » supprimée`,
        });
      }
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
    <>
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

      <IntegrationForm
        open={integrationModalOpen}
        onCancel={handleIntegrationCancel}
        onSubmit={handleIntegrationSubmit}
        loading={integrationSubmitting}
        error={integrationSubmitError}
        editIntegration={editIntegration}
        onSuccess={handleIntegrationSuccess}
      />
    </>
  );
}
