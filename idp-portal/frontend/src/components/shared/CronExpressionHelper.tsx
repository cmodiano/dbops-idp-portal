/**
 * Cron Expression Helper Modal (Story 11.8, AC9).
 *
 * Displays a modal with cron expression documentation:
 * - Field descriptions and valid values
 * - Annotated examples with explanations
 * - External link to crontab.guru
 */

import { Modal, Table, Typography, Space, Divider, Button, Tag } from 'antd';
import { LinkOutlined } from '@ant-design/icons';
import { CRON_FIELD_DOCS, CRON_EXAMPLES } from '../../utils/cronHelper';

const { Title, Text, Paragraph } = Typography;

interface CronExpressionHelperProps {
  open: boolean;
  onClose: () => void;
}

export default function CronExpressionHelper({ open, onClose }: CronExpressionHelperProps) {
  const fieldColumns = [
    {
      title: 'Champ',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: 'Valeurs possibles',
      dataIndex: 'values',
      key: 'values',
      render: (values: string) => <Text code>{values}</Text>,
    },
    {
      title: 'Exemples',
      dataIndex: 'examples',
      key: 'examples',
      render: (examples: string[]) => (
        <Space>
          {examples.map((ex: string, idx: number) => (
            <Tag key={idx}>{ex}</Tag>
          ))}
        </Space>
      ),
    },
  ];

  const exampleColumns = [
    {
      title: 'Expression',
      dataIndex: 'expression',
      key: 'expression',
      render: (expression: string) => <Text code>{expression}</Text>,
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
    },
  ];

  return (
    <Modal
      title="Aide - Expressions Cron"
      open={open}
      onCancel={onClose}
      footer={[
        <Button
          key="crontab"
          type="link"
          href="https://crontab.guru/"
          target="_blank"
          rel="noopener noreferrer"
          icon={<LinkOutlined />}
        >
          Ouvrir crontab.guru (outil interactif)
        </Button>,
        <Button key="close" type="primary" onClick={onClose}>
          Fermer
        </Button>,
      ]}
      width={800}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <div>
          <Title level={5}>Format des expressions cron</Title>
          <Paragraph>
            Une expression cron est composée de 5 champs séparés par des espaces :
          </Paragraph>
          <Text code style={{ fontSize: '14px' }}>
            minute heure jour mois jour_de_la_semaine
          </Text>
        </div>

        <Divider style={{ margin: '12px 0' }} />

        <div>
          <Title level={5}>Tableau des champs</Title>
          <Table
            dataSource={CRON_FIELD_DOCS}
            columns={fieldColumns}
            pagination={false}
            size="small"
            rowKey="name"
          />
        </div>

        <Divider style={{ margin: '12px 0' }} />

        <div>
          <Title level={5}>Exemples annotés</Title>
          <Table
            dataSource={CRON_EXAMPLES}
            columns={exampleColumns}
            pagination={false}
            size="small"
            rowKey="expression"
          />
        </div>

        <Divider style={{ margin: '12px 0' }} />

        <div>
          <Title level={5}>Caractères spéciaux</Title>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>
              <Text code>*</Text> : Tous les valeurs possibles
            </li>
            <li>
              <Text code>*/N</Text> : Tous les N (ex: <Text code>*/15</Text> = toutes les 15 minutes)
            </li>
            <li>
              <Text code>N-M</Text> : Plage de N à M (ex: <Text code>1-5</Text> = lundi à vendredi)
            </li>
            <li>
              <Text code>N,M</Text> : Liste de valeurs (ex: <Text code>9,17</Text> = 9h et 17h)
            </li>
          </ul>
        </div>
      </Space>
    </Modal>
  );
}
