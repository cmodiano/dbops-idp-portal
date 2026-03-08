import { useMemo, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';

import { useApiKeys } from '../hooks/useApiKeys';
import type { ApiKeyScope } from '../services/api_keys_service';

const { Title, Text } = Typography;

const scopeOptions: { label: string; value: ApiKeyScope }[] = [
  { label: 'Executions', value: 'executions' },
  { label: 'Catalog', value: 'catalog' },
  { label: 'Full', value: 'full' },
];

export default function ApiKeysPage() {
  const { message: apiMessage } = App.useApp();
  const [form] = Form.useForm<{ name: string; scope?: ApiKeyScope }>();
  const [open, setOpen] = useState(false);
  const { keys, loading, saving, error, lastCreatedRawKey, create, revoke, clearRawKey } = useApiKeys();

  const dataSource = useMemo(
    () => keys.map((key) => ({ ...key, key: key.id })),
    [keys],
  );

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await create(values.name, values.scope);
      setOpen(false);
      form.resetFields();
      apiMessage.success('Clé API créée');
    } catch (err) {
      apiMessage.error(err instanceof Error ? err.message : 'Erreur lors de la création');
    }
  };

  const handleRevoke = async (id: number) => {
    try {
      await revoke(id);
      apiMessage.success('Clé API révoquée');
    } catch (err) {
      apiMessage.error(err instanceof Error ? err.message : 'Erreur lors de la révocation');
    }
  };

  const handleCopyRawKey = async () => {
    if (!lastCreatedRawKey) {
      return;
    }
    await navigator.clipboard.writeText(lastCreatedRawKey);
    apiMessage.success('Clé copiée dans le presse-papiers');
  };

  return (
    <div style={{ padding: 24 }}>
      <Space orientation="vertical" size={16} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={2} style={{ margin: 0 }}>
            Mes clés API
          </Title>
          <Button type="primary" onClick={() => setOpen(true)}>
            Créer une clé
          </Button>
        </div>

        <Text type="secondary">
          Créez et gérez vos clés API personnelles pour scripts et CI/CD.
        </Text>

        {error ? <Alert type="error" showIcon title={error} /> : null}

        {lastCreatedRawKey && (
          <Alert
            type="warning"
            showIcon
            title="Copiez maintenant, elle ne sera plus affichée"
            description={
              <Space orientation="vertical">
                <Text code>{lastCreatedRawKey}</Text>
                <Space>
                  <Button size="small" onClick={() => void handleCopyRawKey()}>
                    Copier
                  </Button>
                  <Button size="small" onClick={clearRawKey}>
                    Fermer
                  </Button>
                </Space>
              </Space>
            }
          />
        )}

        <Table
          loading={loading}
          dataSource={dataSource}
          pagination={false}
          columns={[
            { title: 'Nom', dataIndex: 'name', key: 'name' },
            { title: 'Scope', dataIndex: 'scope', key: 'scope', render: (value: string | null) => value ?? '-' },
            { title: 'Créée le', dataIndex: 'created_at', key: 'created_at' },
            {
              title: 'Statut',
              dataIndex: 'status',
              key: 'status',
              render: (status: string) => (
                <Tag color={status === 'expired' ? 'orange' : 'green'}>
                  {status === 'expired' ? 'Expirée' : 'Active'}
                </Tag>
              ),
            },
            {
              title: 'Action',
              key: 'action',
              render: (_, record: { id: number }) => (
                <Popconfirm
                  title="Révoquer cette clé ?"
                  okText="Révoquer"
                  cancelText="Annuler"
                  onConfirm={() => void handleRevoke(record.id)}
                >
                  <Button danger size="small" loading={saving}>
                    Révoquer
                  </Button>
                </Popconfirm>
              ),
            },
          ]}
        />
      </Space>

      <Modal
        title="Créer une clé API"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => void handleCreate()}
        okText="Créer"
        cancelText="Annuler"
        confirmLoading={saving}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="Nom"
            name="name"
            rules={[{ required: true, message: 'Le nom est requis' }]}
          >
            <Input placeholder="Ex: CI Pipeline" maxLength={255} />
          </Form.Item>
          <Form.Item label="Scope" name="scope">
            <Select
              allowClear
              options={scopeOptions}
              placeholder="Sélectionnez un scope"
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
