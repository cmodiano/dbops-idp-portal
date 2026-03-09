/**
 * Story 17.12: Feature Flags admin panel.
 *
 * Displays all feature flags with inline editing (Switch for enabled, Slider for rollout).
 * Admin-only component.
 */

import { useState, useEffect, useCallback } from 'react';
import { Table, Switch, Slider, App, Tag, Typography } from 'antd';
import type { TableProps } from 'antd';
import {
  fetchFeatureFlags,
  updateFeatureFlag,
  type FeatureFlagDetail,
} from '../../services/feature_flag_service';
import { useFeatureFlagContext } from '../../contexts/FeatureFlagContext';
import logger from '../../services/logger';

const { Text } = Typography;

export function FeatureFlagsPanel() {
  const { notification } = App.useApp();
  const { refresh: refreshGlobalContext } = useFeatureFlagContext();
  const [flags, setFlags] = useState<FeatureFlagDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingKeys, setUpdatingKeys] = useState<Set<string>>(new Set());

  const loadFlags = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetchFeatureFlags();
      setFlags(response.data);
    } catch (err) {
      logger.error('feature_flags_admin_load_error', { error: String(err) });
      notification.error({ title: 'Erreur lors du chargement des feature flags' });
    } finally {
      setLoading(false);
    }
  }, [notification]);

  useEffect(() => {
    loadFlags();
  }, [loadFlags]);

  const handleToggle = async (flagKey: string, enabled: boolean) => {
    setUpdatingKeys(prev => new Set(prev).add(flagKey));
    try {
      await updateFeatureFlag(flagKey, { enabled });
      setFlags(prev =>
        prev.map(f => (f.flag_key === flagKey ? { ...f, enabled } : f)),
      );
      // MEDIUM-2 fix: Refresh global context to propagate change to other components
      await refreshGlobalContext();
      notification.success({ title: `Flag "${flagKey}" ${enabled ? 'activé' : 'désactivé'}` });
    } catch (err) {
      logger.error('feature_flag_toggle_error', { flagKey, error: String(err) });
      notification.error({ title: `Erreur lors de la modification de "${flagKey}"` });
    } finally {
      setUpdatingKeys(prev => {
        const next = new Set(prev);
        next.delete(flagKey);
        return next;
      });
    }
  };

  const handleRolloutChange = async (flagKey: string, rolloutPercent: number) => {
    setUpdatingKeys(prev => new Set(prev).add(flagKey));
    try {
      await updateFeatureFlag(flagKey, { rollout_percent: rolloutPercent });
      setFlags(prev =>
        prev.map(f =>
          f.flag_key === flagKey ? { ...f, rollout_percent: rolloutPercent } : f,
        ),
      );
      // MEDIUM-2 fix: Refresh global context to propagate change to other components
      await refreshGlobalContext();
      notification.success({ title: `Rollout de "${flagKey}" mis à jour : ${rolloutPercent}%` });
    } catch (err) {
      logger.error('feature_flag_rollout_error', { flagKey, error: String(err) });
      notification.error({ title: `Erreur lors de la modification du rollout de "${flagKey}"` });
    } finally {
      setUpdatingKeys(prev => {
        const next = new Set(prev);
        next.delete(flagKey);
        return next;
      });
    }
  };

  const columns: TableProps<FeatureFlagDetail>['columns'] = [
    {
      title: 'Flag Key',
      dataIndex: 'flag_key',
      key: 'flag_key',
      sorter: (a, b) => a.flag_key.localeCompare(b.flag_key),
    },
    {
      title: 'Activé',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 100,
      render: (enabled: boolean, record) => (
        <Switch
          checked={enabled}
          loading={updatingKeys.has(record.flag_key)}
          onChange={(checked) => handleToggle(record.flag_key, checked)}
        />
      ),
    },
    {
      title: 'Rollout %',
      dataIndex: 'rollout_percent',
      key: 'rollout_percent',
      width: 200,
      render: (percent: number, record) => (
        <Slider
          value={percent}
          min={0}
          max={100}
          disabled={updatingKeys.has(record.flag_key)}
          onChangeComplete={(value) => handleRolloutChange(record.flag_key, value)}
          tooltip={{ formatter: (val) => `${val}%` }}
        />
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: 'Modifié',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (val: string | null) =>
        val ? (
          <Text type="secondary">{new Date(val).toLocaleString('fr-FR')}</Text>
        ) : (
          <Tag>—</Tag>
        ),
    },
  ];

  return (
    <Table<FeatureFlagDetail>
      columns={columns}
      dataSource={flags}
      loading={loading}
      rowKey="flag_key"
      size="small"
      pagination={false}
      locale={{ emptyText: 'Aucun feature flag configuré' }}
    />
  );
}
