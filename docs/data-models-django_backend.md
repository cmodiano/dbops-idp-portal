# Modèles de données – Django Backend

**Date :** 2026-02-21

---

## Apps et modèles

### reference
| Modèle | Rôle |
|--------|------|
| RefEngine | Moteurs de référence (type, nom, config, icon_url, etc.) |
| RefPlatform | Plateformes |
| RefCategory | Catégories |

### idp_auth
| Modèle | Rôle |
|--------|------|
| User | Utilisateur (extension ou custom user) |

### executions
| Modèle | Rôle |
|--------|------|
| Execution | Exécution (workflow, statut, cibles, créateur, dates) |
| ExecutionTarget | Cible d’exécution |
| ExecutionStep | Étape d’exécution (logs, statut) |
| ScheduledExecution | Exécution planifiée |
| RecurringPattern | Motif de récurrence (cron, etc.) |

### core
| Modèle | Rôle |
|--------|------|
| AuditLog | Journal d’audit |
| FeatureFlag | Feature flags |

### catalog
| Modèle | Rôle |
|--------|------|
| BusinessRulePolicy | Politique de règles métier |
| Action | Action du catalogue (workflow, config, gates, etc.) |
| Tag | Tag |
| ActionTag | Liaison action–tag |
| UserFavorite | Favoris utilisateur |
| ActionMutex | Exclusion mutuelle entre actions |

### profiles
| Modèle | Rôle |
|--------|------|
| Profile | Profil (nom, config, permissions) |
| ProfileActionPermission | Permission action par profil |
| ProfileTargetPermission | Permission cible par profil |

### integrations
| Modèle | Rôle |
|--------|------|
| Integration | Intégration (type, config, icône) |
| IntegrationTypeCatalogue | Catalogue des types d’intégration |
| IntegrationAction | Liaison intégration–action |

---

## Migrations

- **Django :** `*/migrations/*.py` (apps catalog, executions, integrations, reference, etc.)
- **SQL / schéma externe :** `idp-portal/database/migrations/` (scripts Flyway-style, ex. V079–V082)

---

*Généré par le workflow document-project (étape 4, scan deep).*
