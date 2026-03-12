# ADR-010 : Configuration as Code — Paradigme API-Only pour l'Import

**Date :** 2025-06-01
**Statut :** Accepté
**Décideurs :** Équipe IDP Portal

## Contexte

Le portail IDP gère une configuration métier complexe : feature flags, tags, types
d'intégration, intégrations, politiques (business rule policies), et actions avec leurs
dépendances FK/M2M. Cette configuration évolue fréquemment et doit être versionnée,
auditée, et déployée de manière reproductible via CI/CD (Epic 64).

**Besoin fondamental :** versionner la configuration dans un repo Git et la déployer
de façon traçable, sans intervention manuelle en base de données.

Lors de l'Epic 70, la commande de synchronisation autonome (`sync_config`) a été
supprimée suite à un problème de **source de vérité ambiguë** : la plateforme pouvait
écraser des modifications manuelles en base en lisant son propre filesystem.

## Décision

**Paradigme API-only pour l'import** : la plateforme ne synchronise jamais elle-même
sa configuration depuis son propre filesystem. Toute importation de configuration
transite obligatoirement par l'API REST.

### Flux GitOps cible

```
Config Repo (Git)
    │
    │ commit + push
    ▼
CI/CD Pipeline
    │  scripts/apply_idp_config.py
    │  POST .../sync/ (API REST)
    ▼
IDP Portal API
    │  Validation + hashing
    │  Import en base de données
    ▼
Oracle DB
```

1. **Création/édition** : l'équipe utilise l'UI du portail ou édite directement le YAML
2. **Export** : UI → export YAML → commit manuel dans le repo de config
3. **Déploiement** : CI/CD exécute `scripts/apply_idp_config.py` → `POST .../sync/`
4. **Aucune synchronisation autonome** : la plateforme ne déclenche jamais de sync au démarrage

### Format YAML envelope (`core/services_cac_utils.py`)

Chaque fichier CaC respecte une enveloppe structurée :
```yaml
kind: FeatureFlag  # ou Tag, IntegrationType, Integration, Policy, Action
version: "1.0"
metadata:
  name: mon-feature-flag
spec:
  # ... données spécifiques à l'entité
```

Les utilitaires `parse_yaml()`, `validate_envelope()`, `compute_yaml_hash()` et
`serialize_to_yaml()` centralisent le traitement du format.

### Entités CaC supportées

| Entité | Endpoints |
|--------|-----------|
| Feature flags | `core/cac_views.py` |
| Tags | `core/cac_views.py` |
| Integration types | `catalog/cac_views.py` |
| Integrations | `integrations/cac_views.py` |
| Business rule policies | `catalog/cac_views.py` |
| Actions (avec dépendances FK/M2M) | `catalog/cac_views.py` |

### Drift tracking (Story 64.13)

Chaque entité CaC possède deux champs de suivi :
- `last_synced_at` : horodatage du dernier import réussi
- `last_synced_hash` : SHA-256 du contenu YAML importé

Ces champs permettent de détecter les **drifts** (modifications manuelles en base depuis
le dernier import). La fonction `update_sync_tracking()` met à jour ces champs après
chaque import réussi.

## Conséquences

### Positives
- Source de vérité unique et non ambiguë : le repo Git
- Traçabilité complète via l'historique Git (qui a changé quoi, quand)
- Déploiements reproductibles et réversibles (git revert)
- Détection de drift (modifications manuelles en base visibles)
- La plateforme n'a pas accès au filesystem en production (sécurité)

### Négatives
- Flux en deux temps pour les modifications : UI → export YAML → commit → CI/CD
- Pas de "apply immédiat" depuis l'UI (l'UI sert à la création, pas au déploiement direct)
- Nécessite une pipeline CI/CD opérationnelle pour chaque déploiement de config

### Neutres
- Le script `apply_idp_config.py` peut être exécuté manuellement par les admins en cas
  de besoin urgent (hors CI/CD)

## Alternatives Considérées

### Alternative 1 : Import via l'UI uniquement

- **Description :** Upload de fichiers YAML directement dans l'interface web du portail
- **Raison du rejet :** Pas de traçabilité Git, opérations manuelles non auditables dans
  la pipeline de déploiement, risque d'incohérences entre environnements.

### Alternative 2 : Synchronisation automatique au démarrage

- **Description :** La plateforme lit ses fichiers de config au démarrage et les importe
  automatiquement en base (pattern `sync_config` supprimé en Epic 70)
- **Raison du rejet :** Source de vérité ambiguë — la plateforme écrase potentiellement
  des modifications manuelles légitimes en base. Comportement non déterministe selon
  l'environnement de déploiement.

### Alternative 3 : Synchronisation bidirectionnelle (plateforme ↔ Git)

- **Description :** La plateforme pousse automatiquement les changements UI vers Git
- **Raison du rejet :** Complexité élevée (gestion des conflits, tokens Git dans la
  plateforme, permissions). Hors périmètre de l'Epic 64.

## Références

- `core/services_cac_utils.py` — Utilitaires CaC (parsing, validation, hashing)
- `core/cac_views.py` — Endpoints export/sync entités core
- `catalog/cac_views.py` — Endpoints CaC catalog
- `integrations/cac_views.py` — Endpoints CaC intégrations
- `scripts/apply_idp_config.py` — Script CI/CD d'application
- Epic 64 — Infrastructure-as-Code : fondation du paradigme CaC
- Epic 70 — Simplification CaC : suppression `sync_config`, API-only
- Story 64.1 — Utilitaires CaC de base
- Story 64.13 — Drift tracking (`last_synced_hash`)
