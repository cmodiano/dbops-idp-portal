# Contrats API – Django Backend

**Date :** 2026-02-21  
**Base URL :** `/api/v1/` (préfixe racine projet : `/api/v1/`)

---

## Vue d'ensemble

- **Documentation OpenAPI :** `/api/schema/`, `/api/schema/swagger-ui/`, `/api/schema/redoc/`
- **Auth :** JWT Bearer (header `Authorization`), SAML SSO (login/callback)
- **Convention :** trailing slash requis (Django `APPEND_SLASH`)

---

## Endpoints par module

### Core
| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `health/` | Health check |
| GET | `feature-flags/` | Liste feature flags |
| GET | `feature-flags/status/` | Statut flags |
| GET/PUT | `feature-flags/<flag_key>/` | Détail / mise à jour flag |

### Catalog (admin + catalogue)
| Méthode | Chemin | Description |
|---------|--------|-------------|
| CRUD | `admin/actions/` | Admin – actions (ViewSet) |
| CRUD | `admin/business-rule-policies/` | Admin – politiques de règles métier |
| CRUD | `catalog/actions/` | Catalogue – actions (ViewSet) |
| GET | `catalog/tags/` | Tags du catalogue |
| CRUD | `tags/` | Tags (ViewSet) |

### Executions
| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET/POST | `executions/` | Liste / création exécutions |
| GET | `executions/stats/` | Statistiques |
| GET | `executions/timeseries/` | Série temporelle |
| GET | `executions/tags/` | Tags exécutions |
| GET | `executions/pending-approvals/` | Approbations en attente |
| GET/PUT/DELETE | `executions/<id>/` | Détail exécution |
| POST | `executions/<id>/approve/` | Approuver |
| POST | `executions/<id>/reject/` | Rejeter |
| POST | `executions/<id>/cancel/` | Annuler |
| GET | `executions/<id>/steps/` | Étapes |
| GET | `executions/<id>/steps/<step_id>/logs/` | Logs d’une étape |
| GET | `executions/<id>/logs/` | Logs exécution |
| GET | `executions/<id>/remediation` | Suggestions de remédiation |
| GET | `executions/<id>/remediation-context` | Contexte remédiation |
| GET/POST | `scheduled-executions/` | Exécutions planifiées |
| GET/PUT/DELETE | `scheduled-executions/<id>/` | Détail planifié |
| GET/PUT | `scheduled-executions/<id>/recurring-pattern/` | Motif récurrent |
| POST | `scheduled-executions/validate-cron/` | Validation cron |
| GET | `scheduled-executions/cron-next-executions/` | Prochaines exécutions cron |

### Dashboard
| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `dashboard/stats/` | Stats dashboard |
| GET | `dashboard/recent/` | Exécutions récentes |
| GET | `dashboard/timeseries/` | Série temporelle |
| GET | `dashboard/stats-by-technology/` | Stats par technologie |
| GET | `dashboard/stats-by-environment/` | Stats par environnement |
| GET | `dashboard/compare/` | Comparaison |
| GET | `dashboard/filter-options/` | Options de filtre |
| GET | `dashboard/export/csv` | Export CSV |
| GET | `dashboard/export/pdf` | Export PDF |

### Audit
| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `audit/executions/` | Audit exécutions |
| GET | `audit/export/` | Export audit |

### Auth (idp_auth)
| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `auth/saml/login/` | Initiation login SAML |
| POST | `auth/saml/callback/` | Callback SAML |
| GET | `auth/me/` | Profil utilisateur courant |
| POST | `auth/refresh/` | Rafraîchir JWT |
| POST | `auth/logout/` | Déconnexion |
| GET/POST/DELETE | `users/me/favorites/` | Favoris utilisateur |
| GET/PUT/DELETE | `users/me/favorites/<action_id>/` | Un favori |

### Integrations
| Méthode | Chemin | Description |
|---------|--------|-------------|
| POST | `admin/integrations/upload-icon/` | Upload icône intégration |
| CRUD | `admin/integrations/` | CRUD intégrations (ViewSet) |
| GET | `integrations/types/` | Catalogue des types d’intégration |

### Admin analytics
| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `admin/analytics/` | Analytics admin |

### Profiles
| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET/POST | `admin/profiles/export/` | Export profils (YAML) |
| POST | `admin/profiles/import/` | Import profils |
| CRUD | `admin/profiles/profiles/` | CRUD profils (ViewSet) |

### Inventory
| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `inventory/targets/` | Cibles (filtrées) |
| GET | `inventory/targets/all/` | Toutes les cibles |
| GET | `inventory/environments/` | Environnements |
| GET | `inventory/servers/` | Serveurs |
| GET | `inventory/instances/` | Instances |
| GET | `inventory/databases/` | Bases de données |

### Reference
| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `reference/engines/` | Moteurs |
| GET | `reference/platforms/` | Plateformes |
| GET | `reference/categories/` | Catégories (liste) |
| POST | `admin/categories/` | Admin – créer catégorie |
| PUT | `admin/categories/<id>/` | Admin – modifier catégorie |
| DELETE | `admin/categories/<id>/delete/` | Admin – supprimer catégorie |
| PUT | `admin/engines/<id>/` | Admin – modifier moteur |

### Help (aide contextuelle)
| Méthode | Chemin | Description |
|---------|--------|-------------|
| GET | `help/<topic_id>/` | Contenu d’aide par topic |

### Webhooks (HMAC, sans auth DRF)
| Méthode | Chemin | Description |
|---------|--------|-------------|
| POST | `webhooks/github/workflow_run` | GitHub Actions workflow run |
| POST | `webhooks/terraform/run` | Terraform Cloud run |

---

*Généré par le workflow document-project (étape 4, scan deep).*
