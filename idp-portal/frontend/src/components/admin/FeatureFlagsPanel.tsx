/**
 * Story 17.12: Feature Flags admin panel.
 * Story 71.1, AC2: Migration DIP — utilise useFeatureFlagsAdmin au lieu d'importer directement le service.
 *
 * Displays all feature flags with inline editing (Switch for enabled, Slider for rollout).
 * Admin-only component.
 */

import { useState, useCallback } from 'react';
import { Table, Switch, Slider, App, Tag, Typography } from 'antd';
import type { TableProps } from 'antd';
import { useFeatureFlagsAdmin, type FeatureFlagDetail } from '../../hooks/useFeatureFlagsAdmin';
import { useFeatureFlagContext } from '../../contexts/FeatureFlagContext';
import logger from '../../services/logger';

const { Text } = Typography;

export function FeatureFlagsPanel() {
  const { notification } = App.useApp();
  const { refresh: refreshGlobalContext } = useFeatureFlagContext();
  const { flags, loading, handleToggle, handleRolloutChange } = useFeatureFlagsAdmin();
  const [updatingKeys, setUpdatingKeys] = useState<Set<string>>(new Set());

  const onToggle = useCallback(async (flagKey: string, enabled: boolean) => {
    setUpdatingKeys(prev => new Set(prev).add(flagKey));
    try {
      await handleToggle(flagKey, enabled);
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
  }, [handleToggle, refreshGlobalContext, notification]);

  const onRolloutChange = useCallback(async (flagKey: string, rolloutPercent: number) => {
    setUpdatingKeys(prev => new Set(prev).add(flagKey));
    try {
      await handleRolloutChange(flagKey, rolloutPercent);
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
  }, [handleRolloutChange, refreshGlobalContext, notification]);

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
          onChange={(checked) => onToggle(record.flag_key, checked)}
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
          onChangeComplete={(value) => onRolloutChange(record.flag_key, value)}
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
