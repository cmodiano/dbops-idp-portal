/**
 * ExportButton - Dropdown button to export dashboard data as CSV or PDF.
 * Story 8.5, AC1, Task 8.
 *
 * Displays a dropdown menu with export options:
 * - "Exporter en CSV" (FileExcelOutlined icon)
 * - "Exporter en PDF" (FilePdfOutlined icon)
 *
 * Shows loading spinner during export and error message on failure.
 */

import { useState } from 'react';
import { App, Button, Dropdown } from 'antd';
import {
  DownloadOutlined,
  FileExcelOutlined,
  FilePdfOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import type { DashboardFilters } from '../../../types/api';
import {
  exportDashboardCSV,
  exportDashboardPDF,
} from '../../../services/dashboard_service';

export interface ExportButtonProps {
  /** Current filters to apply to export. */
  filters: DashboardFilters;
  /** Disable button when parent is loading. */
  loading?: boolean;
  /** Disable button explicitly. */
  disabled?: boolean;
}

/**
 * ExportButton component (Story 8.5, AC1).
 *
 * Renders a dropdown button with CSV and PDF export options.
 * Passes current filters to export functions and triggers browser download.
 */
export function ExportButton({
  filters,
  loading = false,
  disabled = false,
}: ExportButtonProps) {
  const { message } = App.useApp();
  const [exporting, setExporting] = useState(false);

  const handleExport = async (format: 'csv' | 'pdf') => {
    setExporting(true);
    try {
      if (format === 'csv') {
        await exportDashboardCSV(filters);
      } else {
        await exportDashboardPDF(filters);
      }
      message.success(`Export ${format.toUpperCase()} téléchargé`);
    } catch (error) {
      message.error(`Erreur lors de l'export ${format.toUpperCase()}`);
    } finally {
      setExporting(false);
    }
  };

  const items: MenuProps['items'] = [
    {
      key: 'csv',
      icon: <FileExcelOutlined />,
      label: 'Exporter en CSV',
      onClick: () => handleExport('csv'),
    },
    {
      key: 'pdf',
      icon: <FilePdfOutlined />,
      label: 'Exporter en PDF',
      onClick: () => handleExport('pdf'),
    },
  ];

  return (
    <Dropdown menu={{ items }} trigger={['click']} disabled={disabled || loading}>
      <Button icon={<DownloadOutlined />} loading={exporting}>
        Exporter
      </Button>
    </Dropdown>
  );
}

export default ExportButton;
