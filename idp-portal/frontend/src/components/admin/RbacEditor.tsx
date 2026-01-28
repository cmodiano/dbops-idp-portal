/**
 * RbacEditor component for managing RBAC policies per environment (Story 2.3, AC #1, #2).
 *
 * Features:
 * - Table layout with environments as rows (DEV, STAGING, PROD)
 * - Multi-select for authorized profiles
 * - Switch for approval requirement
 * - Multi-select for approver profiles (visible when approval required)
 * - Inline validation
 * - Accessibility support
 */

import React from 'react';
import { Select, Switch, Form, Typography, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { RbacPolicies, EnvironmentPermission, UserProfileType } from '../../types/api';

const { Text } = Typography;

const ENVIRONMENTS = ['DEV', 'STAGING', 'PROD'];

const PROFILE_OPTIONS: { value: UserProfileType; label: string }[] = [
  { value: 'dba_applicatif', label: 'DBA Applicatif' },
  { value: 'dba_infrastructure', label: 'DBA Infrastructure' },
  { value: 'client_business', label: 'Client Business' },
];

const APPROVER_PROFILE_OPTIONS: { value: UserProfileType; label: string }[] = [
  { value: 'dba_applicatif', label: 'DBA Applicatif' },
  { value: 'dba_infrastructure', label: 'DBA Infrastructure' },
];

interface RbacEditorProps {
  value?: RbacPolicies;
  onChange?: (value: RbacPolicies) => void;
}

interface EnvironmentRow {
  key: string;
  environment: string;
  permission: EnvironmentPermission;
}

const DEFAULT_PERMISSION: EnvironmentPermission = {
  profiles: [],
  requires_approval: false,
  approver_profiles: null,
};

export const RbacEditor: React.FC<RbacEditorProps> = ({ value, onChange }) => {
  // Initialize with default structure if no value provided
  const policies: RbacPolicies = value || {
    environments: {
      DEV: { ...DEFAULT_PERMISSION },
      STAGING: { ...DEFAULT_PERMISSION },
      PROD: { ...DEFAULT_PERMISSION },
    },
  };

  const handlePermissionChange = (
    env: string,
    field: keyof EnvironmentPermission,
    fieldValue: unknown
  ) => {
    const newPolicies: RbacPolicies = {
      environments: {
        ...policies.environments,
        [env]: {
          ...policies.environments[env],
          [field]: fieldValue,
        },
      },
    };

    // If approval is unchecked, clear approver_profiles
    if (field === 'requires_approval' && !fieldValue) {
      newPolicies.environments[env].approver_profiles = null;
    }

    onChange?.(newPolicies);
  };

  // Build table data
  const tableData: EnvironmentRow[] = ENVIRONMENTS.map((env) => ({
    key: env,
    environment: env,
    permission: policies.environments[env] || { ...DEFAULT_PERMISSION },
  }));

  const columns: ColumnsType<EnvironmentRow> = [
    {
      title: 'Environnement',
      dataIndex: 'environment',
      key: 'environment',
      width: 120,
      render: (env: string) => <Text strong>{env}</Text>,
    },
    {
      title: 'Profils autorises',
      key: 'profiles',
      width: 250,
      render: (_, record) => {
        const hasError = record.permission.profiles.length === 0;
        return (
          <Form.Item
            validateStatus={hasError ? 'error' : ''}
            help={hasError ? 'Au moins un profil requis' : ''}
            style={{ marginBottom: 0 }}
          >
            <Select
              mode="multiple"
              value={record.permission.profiles}
              onChange={(val) => handlePermissionChange(record.environment, 'profiles', val)}
              options={PROFILE_OPTIONS}
              placeholder="Selectionnez les profils"
              style={{ width: '100%' }}
              aria-label={`Profils autorises ${record.environment}`}
            />
          </Form.Item>
        );
      },
    },
    {
      title: 'Approbation requise',
      key: 'requires_approval',
      width: 140,
      render: (_, record) => (
        <Switch
          checked={record.permission.requires_approval}
          onChange={(checked) =>
            handlePermissionChange(record.environment, 'requires_approval', checked)
          }
          aria-label={`Approbation requise ${record.environment}`}
        />
      ),
    },
    {
      title: 'Profils approbateurs',
      key: 'approver_profiles',
      render: (_, record) => {
        if (!record.permission.requires_approval) {
          return <Text type="secondary">-</Text>;
        }

        const hasError =
          record.permission.requires_approval &&
          (!record.permission.approver_profiles || record.permission.approver_profiles.length === 0);

        return (
          <Form.Item
            validateStatus={hasError ? 'error' : ''}
            help={hasError ? 'Profils approbateurs requis' : ''}
            style={{ marginBottom: 0 }}
          >
            <Select
              mode="multiple"
              value={record.permission.approver_profiles || []}
              onChange={(val) =>
                handlePermissionChange(record.environment, 'approver_profiles', val)
              }
              options={APPROVER_PROFILE_OPTIONS}
              placeholder="Selectionnez les approbateurs"
              style={{ width: '100%' }}
              aria-label={`Profils approbateurs ${record.environment}`}
            />
          </Form.Item>
        );
      },
    },
  ];

  return (
    <Table
      dataSource={tableData}
      columns={columns}
      pagination={false}
      size="small"
      bordered
      aria-label="Configuration RBAC par environnement"
    />
  );
};
