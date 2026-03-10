# Analyse de décorrélation DBOPS/DBA — IDP Portal

**Objectif :** Rendre la solution agnostique du domaine DBOPS/DBA pour permettre son adoption par d'autres équipes d'automatisation utilisant les mêmes plateformes et intégrations.

**Date :** 2026-03-02

---

## 1. Synthèse des couplages identifiés

| Catégorie | Occurrences | Impact | Effort |
|-----------|-------------|--------|--------|
| Permissions RBAC | ~40 fichiers | Élevé | Moyen |
| Inventaire | ~15 fichiers | Moyen | Faible |
| Notifications | ~10 fichiers | Faible | Faible |
| Frontend | ~5 fichiers | Moyen | Faible |
| Tests | ~20 fichiers | Faible | Moyen |
| Documentation | ~15 fichiers | Faible | Faible |

---

## 2. Couplages détaillés et recommandations

### 2.1 Permissions RBAC (priorité haute)

**Problème :** Les profils `DBA` et `DBOPS` sont codés en dur dans le code et les noms de classes.

| Fichier | Couplage | Recommandation |
|---------|----------|----------------|
| `core/permissions.py` | `_ADMIN_PROFILES = {'dbops', 'dba', ...}` | Remplacer par `Profile.is_admin` ou config `settings.ADMIN_PROFILE_NAMES` |
| `core/permissions.py` | `DBOPSProfilePermission` vérifie `profile == 'dbops'` | Renommer en `AdminProfilePermission` et vérifier `profile.is_admin` |
| `core/permissions.py` | `IsDBAOrDBOPS` | Renommer en `IsAdminUser` ou `IsOperatorUser` |
| `profile.models.Profile` | `is_admin` existe déjà | Utiliser ce flag plutôt que de comparer les noms |

**Stratégie (complétée) :**
- Le modèle `Profile` a déjà `is_admin` (INTEGER). Utiliser ce flag pour les permissions.
- `DBOPSProfilePermission` → `AdminProfilePermission` : vérifier si l'utilisateur a un profil avec `is_admin=1`.
- `IsDBAOrDBOPS` → `IsAdminUser` : logique basée sur `is_admin`.
- **Aliases supprimés** — utiliser `AdminProfilePermission` et `IsAdminUser` exclusivement.

**Fichiers concernés :**
- `core/permissions.py`
- Tous les imports : `dashboard/views.py`, `executions/views/*.py`, `catalog/views/*.py`, `integrations/views.py`, `profiles/views.py`, `reference/views.py`, `admin_analytics/views.py`, `executions/views/approval_views.py`, etc.

---

### 2.2 Inventaire (priorité moyenne)

**Problème :** Le schéma `DBOPS_INVENTORY` est codé en dur comme fallback.

| Fichier | Couplage | Recommandation |
|---------|----------|----------------|
| `inventory/services.py` | `fallback="DBOPS_INVENTORY"` | `settings.INVENTORY_FALLBACK_SCHEMA` (défaut: `DBOPS_INVENTORY`) |
| `inventory/services.py` | `schema_name = ... or 'DBOPS_INVENTORY'` | Idem |
| `inventory/query_executor.py` | `read_oracle_inventory('DBOPS_INVENTORY', ...)` | Passer la config |
| `inventory/tests/*.py` | Tests avec `DBOPS_INVENTORY` | Garder pour compatibilité |

**Stratégie :**
- Ajouter `INVENTORY_FALLBACK_SCHEMA` dans `settings.py` (défaut: `DBOPS_INVENTORY`).
- Les autres équipes pourront configurer leur propre schéma sans toucher au code.

---

### 2.3 Notifications (priorité basse)

**Problème :** Le canal `page_dba` et la méthode `send_page_dba` sont spécifiques au domaine.

| Fichier | Couplage | Recommandation |
|---------|----------|----------------|
| `services/notification_service.py` | `send_page_dba`, `page_dba` | Renommer en `send_page_oncall` / `page_oncall` |
| `idp_backend/settings.py` | `PAGE_DBA_API_URL` | `PAGE_ONCALL_API_URL` (PAGE_DBA supprimé) |
| `catalog/models.py` | Commentaire `page_dba` | `page_oncall` |

**Stratégie (complétée) :**
- `page_dba` → `page_oncall` : migration effectuée.
- L'alias `page_dba` a été supprimé du dispatch. Utiliser `page_oncall` uniquement.

---

### 2.4 Frontend (priorité moyenne)

**Problème :** Le frontend vérifie `profile === 'dbops'` en dur.

| Fichier | Couplage | Recommandation |
|---------|----------|----------------|
| `App.tsx` | `isDbops = user?.profile?.toLowerCase() === 'dbops'` | Utiliser `hasTab('analytics')` ou `user?.is_admin` |
| `App.tsx` | Commentaires "DBOPS only", "DBA/DBOPS" | Retirer ou généraliser |

**Stratégie :**
- Le backend expose déjà `navigation_tabs` et `hasTab` via AuthContext.
- Si `analytics` est dans `navigation_tabs` pour les utilisateurs admin, on peut remplacer `isDbops` par `hasTab('analytics')`.
- Vérifier que `AuthContext` / `hasTab` reflète bien les permissions côté backend.

---

### 2.5 Noms de tables/schémas externes (DBOPS_SERVERS, etc.)

**Constat :** Les tables `DBOPS_SERVERS`, `DBOPS_INSTANCES`, `DBOPS_DATABASES` sont documentées dans `inventory-mapping-guide.md` et `dbops_inventory_schema.sql`. Ce sont des **noms de tables externes** (dans la plateforme DBOPS). Pour les autres équipes :

- Soit elles utilisent leur propre schéma avec des noms différents → config via `IntegrationType.INVENTORY_DB` et mapping.
- Soit elles utilisent le même schéma → pas de changement.

**Recommandation :** Rendre le schéma fallback configurable (voir 2.2). Les noms de tables dans les configs d'intégration sont déjà config-driven.

---

## 3. Plan de migration (phases)

### Phase 1 — Faible risque (1–2 jours)

1. **Inventaire** : Ajouter `INVENTORY_FALLBACK_SCHEMA` dans settings.
2. **Notifications** : Ajouter `page_oncall` comme alias de `page_dba` ; documenter la dépréciation.
3. **Frontend** : Remplacer `isDbops` par `hasTab('analytics')` si le backend expose déjà cette info.

### Phase 2 — Permissions (3–5 jours)

1. **Refactoriser** `core/permissions.py` :
   - Utiliser `Profile.is_admin` pour `AdminProfilePermission`.
   - Créer `AdminProfilePermission` et `IsAdminUser` (noms canoniques).
   - ~~Garder DBOPSProfilePermission et IsDBAOrDBOPS comme alias~~ — **aliases supprimés**.
2. **Mettre à jour** les imports — migration complète effectuée.
3. **Tests** : Adapter les tests pour utiliser les nouveaux noms — complété.

### Phase 3 — Nettoyage ✅ Complète

1. ~~Renommer tous les usages~~ — **complété** : AdminProfilePermission et IsAdminUser utilisés partout.
2. ~~Renommer page_dba → page_oncall~~ — **complété** : alias supprimé.
3. Mettre à jour la documentation — **complété**.

---

## 4. Ce qui reste inchangé (volontairement)

- **Noms de profils en base** : `DBA`, `DBOPS` peuvent rester dans la table `PROFILES` — ce sont des données métier. Les autres équipes pourront créer leurs propres profils (`AUTOMATION`, `OPERATOR`, etc.) avec `is_admin=1`.
- **Tests** : Les fixtures `profile='DBA'` ou `profile='DBOPS'` sont des données de test ; pas besoin de les changer pour la décorrélation.
- **Groupes AD** : `CN=GRP-IDP-DBOPS`, etc. sont des conventions d'entreprise ; le mapping `ad_group` → `Profile` reste dans la config.

---

## 5. Fichiers clés à modifier

```
idp-portal/
├── django_backend/
│   ├── core/permissions.py          # Refactor principal
│   ├── idp_backend/settings.py      # INVENTORY_FALLBACK_SCHEMA
│   ├── inventory/services.py       # Utiliser config fallback
│   ├── services/notification_service.py  # page_oncall
│   └── [~15 views avec permission_classes]
├── frontend/
│   └── src/App.tsx                  # hasTab('analytics')
└── docs/                            # Mise à jour
```

---

## 6. Conclusion

**Oui, la décorrélation est possible** sans réécriture majeure. Les points principaux :

1. **Permissions** : Basculer sur `Profile.is_admin` et renommer les classes (avec alias).
2. **Inventaire** : Configurer le schéma fallback via settings.
3. **Notifications** : Renommer `page_dba` → `page_oncall` (avec alias).
4. **Frontend** : Utiliser `hasTab()` au lieu de vérifier le nom du profil.

L'effort estimé est de **5–8 jours** pour les phases 1 et 2. La phase 3 (nettoyage complet) peut être faite progressivement.

---

## 7. État d'implémentation (2026-03-03)

### Phase 1 — Fondations techniques ✅ Complète

| Story | Titre | Statut |
|-------|-------|--------|
| 56.1 | Inventaire Oracle : schéma fallback configurable | ✅ done |
| 56.2 | Notifications : canal `page_oncall` agnostique | ✅ done |
| 56.3 | Frontend : `hasTab('analytics')` dans AnalyticsGuard | ✅ done |

### Phase 2 — Renommage canonique ✅ Complète

| Story | Titre | Statut |
|-------|-------|--------|
| 56.4 | Permissions : `AdminProfilePermission` / `IsAdminUser` (avec aliases) | ✅ done |
| 56.5 | Tests : migration vers les noms canoniques | ✅ done |

### Phase 3 — Nettoyage documentation et code ✅ Complète avec reliquats

| Story | Titre | Statut |
|-------|-------|--------|
| 56.6 | Nettoyage documentation et renommage complet | ✅ done |

**Résumé :** L'ensemble de l'epic 56 est terminé. Les profils `DBA` et `DBOPS` restent valides en base de données. Les aliases Python (`DBOPSProfilePermission`, `IsDBAOrDBOPS`) ont été supprimés — utiliser `AdminProfilePermission` et `IsAdminUser` exclusivement.
