import { useState, useEffect, useCallback } from 'react';
import { Card } from 'antd';
import type { NotificationInstance } from 'antd';
import { ProfileWizard } from '../../components/admin/ProfileWizard';
import { ProfilesTable } from '../../components/admin/ProfilesTable';
import { ProfileImportModal } from '../../components/admin/ProfileImportModal';
import { getProfiles, getProfile, deleteProfile, exportProfilesYaml } from '../../services/profiles_service';
import type { ProfileResponse, ProfileListItem } from '../../types/api';

export interface ProfilesAdminPanelProps {
  notification: NotificationInstance;
}

export function ProfilesAdminPanel({ notification }: ProfilesAdminPanelProps) {
  const [profiles, setProfiles] = useState<ProfileListItem[]>([]);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [editProfile, setEditProfile] = useState<ProfileResponse | null>(null);
  const [importYamlModalOpen, setImportYamlModalOpen] = useState(false);

  const fetchProfiles = useCallback(async () => {
    setProfilesLoading(true);
    try {
      const list = await getProfiles();
      setProfiles(list);
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur de chargement des profils',
      });
    } finally {
      setProfilesLoading(false);
    }
  }, [notification]);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  const handleProfileEdit = async (record: ProfileListItem) => {
    try {
      const detail = await getProfile(record.id);
      setEditProfile(detail);
      setProfileModalOpen(true);
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de charger le profil',
      });
    }
  };

  const handleProfileDelete = async (record: ProfileListItem) => {
    try {
      await deleteProfile(record.id);
      notification.success({ message: 'Succes', description: `Profil "${record.name}" supprime` });
      fetchProfiles();
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de supprimer le profil',
      });
    }
  };

  const handleProfileSuccess = (profile: ProfileResponse) => {
    setProfileModalOpen(false);
    setEditProfile(null);
    notification.success({
      message: 'Succes',
      description: editProfile ? `Profil "${profile.name}" mis a jour` : `Profil "${profile.name}" cree`,
    });
    fetchProfiles();
  };

  const handleProfileCancel = () => {
    setProfileModalOpen(false);
    setEditProfile(null);
  };

  const handleExportYaml = useCallback(async () => {
    try {
      await exportProfilesYaml();
      notification.success({ message: 'Export YAML', description: 'Fichier profiles.yaml téléchargé.' });
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur lors de l\'export YAML',
      });
    }
  }, [notification]);

  const handleImportYaml = useCallback(() => {
    setImportYamlModalOpen(true);
  }, []);

  const handleImportYamlSuccess = useCallback((created: number, updated: number) => {
    setImportYamlModalOpen(false);
    notification.success({
      message: 'Import YAML',
      description: `Import reussi : ${created} cree(s), ${updated} mis a jour.`,
    });
    fetchProfiles();
  }, [notification, fetchProfiles]);

  return (
    <>
      <Card styles={{ header: { borderBottom: 'none', paddingBottom: 0 }, body: { paddingTop: 16 } }}>
        <ProfilesTable
          dataSource={profiles}
          loading={profilesLoading}
          onEdit={handleProfileEdit}
          onDelete={handleProfileDelete}
          onNew={() => {
            setEditProfile(null);
            setProfileModalOpen(true);
          }}
          onExportYaml={handleExportYaml}
          onImportYaml={handleImportYaml}
        />
      </Card>

      <ProfileWizard
        open={profileModalOpen}
        onCancel={handleProfileCancel}
        editProfile={editProfile}
        onSuccess={handleProfileSuccess}
      />

      <ProfileImportModal
        open={importYamlModalOpen}
        onCancel={() => setImportYamlModalOpen(false)}
        onSuccess={handleImportYamlSuccess}
      />
    </>
  );
}
