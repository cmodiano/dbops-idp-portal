/**
 * AdminPlatformSection — Section "Utilisation de la plateforme" (Story 60.3).
 * Story 71.1, AC7: Migration DIP — utilise useAdminPlatformStats au lieu d'importer directement dashboard_service.
 *
 * Displays catalogue and adoption StatCards:
 * - "Actions publiées" : count of published actions (stats-catalogue, DBOPS only)
 * - "Workflows" : count of workflow items (stats-catalogue, DBOPS only)
 * - "Utilisateurs actifs" : sum of active users by profile (stats-adoption, all authenticated)
 *
 * RBAC: if stats-catalogue returns 403, catalogue cards are silently hidden.
 * Errors other than 403 display an Alert.
 * Loading state shows Skeleton inside each StatCard.
 */

import { Row, Col, Alert, Typography, Divider } from 'antd';
import { StatCard } from '../StatCard';
import { useAdminPlatformStats } from '../../../hooks/useDashboardStats';
import type { DashboardFilters } from '../../../types/api';
import { CatalogueItemTypeChart } from './CatalogueItemTypeChart';
import { CatalogueEvolutionChart } from './CatalogueEvolutionChart';
import { AdoptionByProfileChart } from './AdoptionByProfileChart';

const { Title } = Typography;

export interface AdminPlatformSectionProps {
  filters: DashboardFilters;
}

export function AdminPlatformSection({ filters }: AdminPlatformSectionProps) {
  const {
    catalogueData,
    adoptionData,
    loading: sectionLoading,
    error: sectionError,
    setError: setSectionError,
    catalogueForbidden,
  } = useAdminPlatformStats(filters);

  const publishedCount =
    catalogueData?.by_status.find((s) => s.status === 'published')?.count ?? 0;
  const workflowCount =
    catalogueData?.by_item_type.find((t) => t.item_type === 'workflow')?.count ?? 0;
  const activeUsersCount =
    adoptionData?.active_users_by_profile.reduce((sum, p) => sum + p.user_count, 0) ?? 0;

  return (
    <>
      <Divider />
      <Title level={5}>Utilisation de la plateforme</Title>

      {sectionError && (
        <Alert
          type="error"
          title={sectionError}
          showIcon
          closable
          onClose={() => setSectionError(null)}
        />
      )}

      <Row gutter={[16, 16]}>
        {!catalogueForbidden && (
          <>
            <Col xs={24} sm={8}>
              <StatCard
                label="Actions publiées"
                value={publishedCount}
                variant="success"
                tooltip="Actions publiées dans le catalogue"
                loading={sectionLoading}
              />
            </Col>
            <Col xs={24} sm={8}>
              <StatCard
                label="Workflows"
                value={workflowCount}
                variant="inProgress"
                tooltip="Workflows définis dans le catalogue"
                loading={sectionLoading}
              />
            </Col>
          </>
        )}
        <Col xs={24} sm={8}>
          <StatCard
            label="Utilisateurs actifs"
            value={activeUsersCount}
            variant="default"
            tooltip="Utilisateurs ayant exécuté au moins une action sur la période"
            loading={sectionLoading}
          />
        </Col>
      </Row>

      {!catalogueForbidden && (
        <>
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} md={12}>
              <CatalogueItemTypeChart
                data={catalogueData?.by_item_type ?? []}
                loading={sectionLoading}
              />
            </Col>
            <Col xs={24} md={12}>
              <CatalogueEvolutionChart
                data={catalogueData?.evolution ?? []}
                loading={sectionLoading}
              />
            </Col>
          </Row>
        </>
      )}

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <AdoptionByProfileChart
            data={adoptionData?.executions_by_profile ?? []}
            loading={sectionLoading}
          />
        </Col>
      </Row>
    </>
  );
}

export default AdminPlatformSection;
