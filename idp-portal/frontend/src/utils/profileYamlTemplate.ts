/**
 * Profile YAML template for import (Story 2.26).
 * Aligned with backend ProfilesYamlImport model (Story 2.13).
 */

export const PROFILE_YAML_TEMPLATE = `# Format d'import de profils DBOPS Portal
# Le fichier doit contenir une liste de profils sous la clé "profiles"
# Tous les champs sont optionnels sauf 'name' et 'ad_group'

profiles:
  - name: "dba_oracle"                    # Obligatoire - Nom unique du profil
    description: "DBAs Oracle production"  # Description du profil
    ad_group: "GRP-DBA-ORACLE"             # Obligatoire - Groupe Active Directory
    is_admin: false                        # Acces admin (defaut: false)
    is_auditor: false                      # Acces audit (defaut: false)

    actions:
      type: "pattern"                      # "all" | "list" | "pattern"
      patterns: ["oracle*", "backup*"]     # Requis si type=pattern
      # list: [1, 2, 3]                    # Requis si type=list (IDs d'actions)

    targets:
      type: "list"                         # "all" | "list" | "pattern"
      list: ["srv-ora-01", "srv-ora-02"]   # Requis si type=list (noms de serveurs)
      # patterns: ["srv-ora-*"]            # Requis si type=pattern

    environments: ["DEV", "STAGING", "PROD"]  # Environnements autorises

  # Exemple avec type "all" (acces complet)
  - name: "admin_full"
    description: "Administrateurs avec acces complet"
    ad_group: "GRP-ADMIN-FULL"
    is_admin: true
    is_auditor: false

    actions:
      type: "all"                          # Acces a toutes les actions

    targets:
      type: "all"                          # Acces a tous les serveurs

    environments: ["DEV", "STAGING", "PROD"]
`;

export const PROFILE_YAML_TEMPLATE_FILENAME = 'profile-template.yaml';
