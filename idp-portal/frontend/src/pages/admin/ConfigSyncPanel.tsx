import { useEffect, useRef, useState } from 'react';
import { Card, Table, Statistic, Row, Col, Button, Spin, App, Tag } from 'antd';
import { SyncOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router';
import { getConfigSyncStatus } from '../../services/config_sync_service';
import type { ConfigSyncEntityStatus, ConfigSyncGlobal } from '../../types/api/config_sync';

const ENTITY_LABELS: Record<string, string> = {
  actions: 'Actions',
  integrations: 'Intégrations',
  profiles: 'Profils',
  policies: 'Politiques',
  engines: 'Moteurs',
  categories: 'Catégories',
  'integration-types': "Types d'intégration",
  'feature-flags': 'Feature Flags',
};

export function ConfigSyncPanel() {
  const [loading, setLoading] = useState(true);
  const [globalData, setGlobalData] = useState<ConfigSyncGlobal | null>(null);
  const [entityTypes, setEntityTypes] = useState<ConfigSyncEntityStatus[]>([]);
  const { message } = App.useApp();
  const messageRef = useRef(message);
  messageRef.current = message;
  const navigate = useNavigate();

  useEffect(() => {
    getConfigSyncStatus()
      .then((resp) => {
        setGlobalData(resp.data.global);
        setEntityTypes(resp.data.entity_types);
      })
      .catch(() => messageRef.current.error('Erreur lors du chargement du statut de sync'))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const columns = [
    {
      title: 'Type',
      dataIndex: 'entity_type',
      key: 'entity_type',
      render: (v: string) => ENTITY_LABELS[v] ?? v,
    },
    { title: 'Total', dataIndex: 'total', key: 'total' },
    {
      title: 'Synchronisé',
      dataIndex: 'synced',
      key: 'synced',
      render: (v: number) => <Tag color="success">{v}</Tag>,
    },
    {
      title: 'Divergé',
      dataIndex: 'diverged',
      key: 'diverged',
      render: (v: number) =>
        v > 0 ? <Tag color="warning">{v}</Tag> : <Tag color="success">{v}</Tag>,
    },
    {
      title: 'Jamais synchro',
      dataIndex: 'never_synced',
      key: 'never_synced',
      render: (v: number) =>
        v > 0 ? <Tag color="processing">{v}</Tag> : <Tag color="success">{v}</Tag>,
    },
    {
      title: 'Dernière sync',
      dataIndex: 'last_sync_date',
      key: 'last_sync_date',
      render: (v: string | null) =>
        v ? new Date(v).toLocaleString('fr-FR') : '—',
    },
    {
      title: 'Statut',
      key: 'status',
      render: (_: unknown, record: ConfigSyncEntityStatus) => {
        if (record.diverged > 0) return <Tag color="warning">Divergé</Tag>;
        if (record.never_synced > 0) return <Tag color="processing">Jamais synchro</Tag>;
        if (record.synced > 0 && record.synced === record.total) return <Tag color="success">Synchronisé</Tag>;
        if (record.total === 0) return <Tag>Vide</Tag>;
        return <Tag color="default">Partiel</Tag>;
      },
    },
  ];

  return (
    <Spin spinning={loading}>
      {globalData && (
        <Card style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={4}>
              <Statistic title="Total entités" value={globalData.total} />
            </Col>
            <Col span={4}>
              <Statistic
                title="Synchronisées"
                value={globalData.synced}
                valueStyle={{ color: 'green' }}
              />
            </Col>
            <Col span={4}>
              <Statistic
                title="Divergées"
                value={globalData.diverged}
                valueStyle={{ color: globalData.diverged > 0 ? 'orange' : 'green' }}
              />
            </Col>
            <Col span={4}>
              <Statistic title="Jamais synchro" value={globalData.never_synced} />
            </Col>
            <Col
              span={8}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}
            >
              <Button
                icon={<SyncOutlined />}
                onClick={() => navigate('/audit?action_type=CONFIG_SYNC_ACTION_IMPORT')}
              >
                Voir l'audit des syncs
              </Button>
            </Col>
          </Row>
          {globalData.last_sync_date && (
            <div style={{ marginTop: 8, color: '#888' }}>
              Dernière synchronisation globale :{' '}
              {new Date(globalData.last_sync_date).toLocaleString('fr-FR')}
            </div>
          )}
        </Card>
      )}
      <Table
        dataSource={entityTypes}
        columns={columns}
        rowKey="entity_type"
        pagination={false}
      />
    </Spin>
  );
}
