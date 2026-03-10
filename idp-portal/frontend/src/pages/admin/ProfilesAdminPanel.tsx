import { useState, useEffect, useCallback } from 'react';
import { Card, App } from 'antd';
import { ProfileWizard } from '../../components/admin/ProfileWizard';
import { ProfilesTable } from '../../components/admin/ProfilesTable';
import { getProfiles, getProfile, deleteProfile, exportProfilesYaml } from '../../services/profiles_service';
import type { ProfileResponse, ProfileListItem } from '../../types/api';

type NotificationInstance = ReturnType<typeof App.useApp>['notification'];

export interface ProfilesAdminPanelProps {
  notification: NotificationInstance;
}

export function ProfilesAdminPanel({ notification }: ProfilesAdminPanelProps) {
  const [profiles, setProfiles] = useState<ProfileListItem[]>([]);
  const [profilesLoading, setProfilesLoading] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [editProfile, setEditProfile] = useState<ProfileResponse | null>(null);

  const fetchProfiles = useCallback(async () => {
    setProfilesLoading(true);
    try {
      const list = await getProfiles();
      setProfiles(list);
    } catch (err) {
      notification.error({
        title: 'Erreur',
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
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de charger le profil',
      });
    }
  };

  const handleProfileDelete = async (record: ProfileListItem) => {
    try {
      await deleteProfile(record.id);
      notification.success({ title: 'Succès', description: `Profil "${record.name}" supprimé` });
      fetchProfiles();
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de supprimer le profil',
      });
    }
  };

  const handleProfileSuccess = (profile: ProfileResponse) => {
    setProfileModalOpen(false);
    setEditProfile(null);
    notification.success({
      title: 'Succès',
      description: editProfile ? `Profil "${profile.name}" mis à jour` : `Profil "${profile.name}" créé`,
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
      notification.success({ title: 'Export YAML', description: 'Fichier profiles.yaml téléchargé.' });
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur lors de l\'export YAML',
      });
    }
  }, [notification]);

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
        />
      </Card>

      <ProfileWizard
        open={profileModalOpen}
        onCancel={handleProfileCancel}
        editProfile={editProfile}
        onSuccess={handleProfileSuccess}
      />
    </>
  );
}
