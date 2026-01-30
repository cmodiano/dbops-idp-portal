/**
 * ProfileImportModal - Modal d'import YAML avec exemple et template (Story 2.26).
 *
 * Features:
 * - Collapse avec exemple YAML commenté (AC1, AC2, AC3, AC5)
 * - Bouton télécharger template (AC4, AC5)
 * - Input fichier pour import
 */

import { useRef, useCallback } from 'react';
import { Modal, Space, Button, Collapse, notification } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { PROFILE_YAML_TEMPLATE, PROFILE_YAML_TEMPLATE_FILENAME } from '../../utils/profileYamlTemplate';
import { importProfilesYaml } from '../../services/profiles_service';

export interface ProfileImportModalProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: (created: number, updated: number) => void;
}

export function ProfileImportModal({ open, onCancel, onSuccess }: ProfileImportModalProps) {
  const fileRef = useRef<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDownloadTemplate = useCallback(() => {
    const blob = new Blob([PROFILE_YAML_TEMPLATE], { type: 'text/yaml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = PROFILE_YAML_TEMPLATE_FILENAME;
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  const handleSubmit = useCallback(async () => {
    const file = fileRef.current;
    if (!file) {
      notification.warning({ title: 'Fichier requis', description: 'Veuillez selectionner un fichier .yaml ou .yml' });
      return;
    }
    try {
      const { created, updated } = await importProfilesYaml(file);
      fileRef.current = null;
      if (inputRef.current) inputRef.current.value = '';
      onSuccess(created, updated);
    } catch (err) {
      notification.error({
        title: 'Erreur d\'import',
        description: err instanceof Error ? err.message : 'Erreur lors de l\'import YAML',
      });
    }
  }, [onSuccess]);

  const handleCancel = useCallback(() => {
    fileRef.current = null;
    if (inputRef.current) inputRef.current.value = '';
    onCancel();
  }, [onCancel]);

  return (
    <Modal
      title="Importer YAML"
      open={open}
      onCancel={handleCancel}
      onOk={handleSubmit}
      okText="Importer"
      destroyOnHidden
      width={640}
    >
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Button icon={<DownloadOutlined />} onClick={handleDownloadTemplate} data-testid="download-template-btn">
          Telecharger template
        </Button>

        <Collapse
          defaultActiveKey={[]}
          items={[
            {
              key: 'yaml-example',
              label: 'Voir le format YAML',
              children: (
                <pre
                  data-testid="yaml-example-content"
                  style={{
                    backgroundColor: 'var(--ant-color-bg-container)',
                    border: '1px solid var(--ant-color-border)',
                    borderRadius: 6,
                    padding: 12,
                    fontSize: 12,
                    lineHeight: 1.5,
                    overflow: 'auto',
                    maxHeight: 400,
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {PROFILE_YAML_TEMPLATE}
                </pre>
              ),
            },
          ]}
        />

        <div>
          <p style={{ marginBottom: 8 }}>Selectionnez un fichier profiles.yaml ou .yml :</p>
          <input
            ref={inputRef}
            type="file"
            accept=".yaml,.yml"
            data-testid="file-input"
            onChange={(e) => { fileRef.current = e.target.files?.[0] ?? null; }}
          />
        </div>
      </Space>
    </Modal>
  );
}
