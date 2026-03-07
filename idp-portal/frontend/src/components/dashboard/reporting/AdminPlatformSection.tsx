/**
 * AdminPlatformSection — Section "Utilisation de la plateforme" (Story 60.3).
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

import { useState, useEffect } from 'react';
import { Row, Col, Alert, Typography, Divider } from 'antd';
import { StatCard } from '../StatCard';
import { ApiError } from '../../../services/api_client';
import {
  fetchStatsCatalogue,
  fetchStatsAdoption,
} from '../../../services/dashboard_service';
import type { DashboardFilters, StatsCatalogueData, StatsAdoptionData } from '../../../types/api';

const { Title } = Typography;

export interface AdminPlatformSectionProps {
  filters: DashboardFilters;
}

export function AdminPlatformSection({ filters }: AdminPlatformSectionProps) {
  const [catalogueData, setCatalogueData] = useState<StatsCatalogueData | null>(null);
  const [adoptionData, setAdoptionData] = useState<StatsAdoptionData | null>(null);
  const [sectionLoading, setSectionLoading] = useState(true);
  const [sectionError, setSectionError] = useState<string | null>(null);
  const [catalogueForbidden, setCatalogueForbidden] = useState(false);

  // Use JSON.stringify as dependency to avoid infinite re-renders (filters object re-created on each render)
  const filtersKey = JSON.stringify(filters);

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setSectionLoading(true);
      setSectionError(null);
      setCatalogueForbidden(false);

      const [catalogueResult, adoptionResult] = await Promise.allSettled([
        fetchStatsCatalogue(filters),
        fetchStatsAdoption(filters),
      ]);

      if (cancelled) return;

      if (catalogueResult.status === 'fulfilled') {
        setCatalogueData(catalogueResult.value);
      } else {
        const err = catalogueResult.reason;
        if (err instanceof ApiError && err.status === 403) {
          setCatalogueForbidden(true); // Masquer silencieusement
        } else {
          setSectionError(err instanceof Error ? err.message : 'Erreur de chargement');
        }
      }

      if (adoptionResult.status === 'fulfilled') {
        setAdoptionData(adoptionResult.value);
      } else {
        const err = adoptionResult.reason;
        // Only set section error if not already set by catalogue error
        setSectionError((prev) =>
          prev ? prev : err instanceof Error ? err.message : 'Erreur de chargement'
        );
      }

      setSectionLoading(false);
    }

    loadData();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey]);

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

      {/* TODO Story 60.4 : graphiques admin (répartition actions/workflows, évolution catalogue, adoption par profil) */}
    </>
  );
}

export default AdminPlatformSection;
