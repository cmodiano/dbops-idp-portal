import { Typography, Button, Space, Tag } from 'antd';
import type { TableProps } from 'antd';
import {
  EditOutlined,
  SendOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  DeleteOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons';
import { ActionStatusBadge } from '../../components/admin/ActionStatusBadge';
import { DriftBadge } from '../../components/admin/DriftBadge';
import { getItemTypeIcon } from '../../utils/iconHelpers';
import type { ActionListItem, ActionStatus, StatusTransition } from '../../types/api';
import { getTagStyle } from '../../utils/tagStyles';

export const getActionsColumns = (
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
    title: 'Sync Git',
    dataIndex: 'last_synced_at',
    key: 'drift',
    width: 120,
    render: (_: unknown, record: ActionListItem) => (
      <DriftBadge last_synced_at={record.last_synced_at} updated_at={record.updated_at} />
    ),
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
