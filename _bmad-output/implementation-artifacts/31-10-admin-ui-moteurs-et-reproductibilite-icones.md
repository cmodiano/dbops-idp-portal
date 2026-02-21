# Story 31.10 : Admin UI Moteurs (icônes) et reproductibilité de la config icônes entre environnements

Status: done

## Story

En tant que DBOPS,
je veux pouvoir éditer les icônes et libellés des moteurs (REF_ENGINES) depuis l'interface Admin, et disposer d'un moyen de répliquer la config icônes (moteurs et intégrations) entre environnements,
afin de ne pas dépendre de l'API seule pour les moteurs et d'éviter de reconfigurer les icônes à la main à chaque déploiement.

## Acceptance Criteria

1. **Given** un utilisateur avec profil DBOPS sur la page Admin
   **When** il ouvre un onglet **Moteurs** (ou **Technologies**)
   **Then** il voit la liste des moteurs (REF_ENGINES) avec au minimum : code, libellé, ordre d'affichage, actif, icône (aperçu)

2. **And** il peut éditer un moteur (modal) pour modifier : **icon_url** (chemin ou URL de l'icône), **label**, **display_order**, **is_active**. Les changements sont persistés via l'API existante `PATCH /api/v1/admin/engines/{pk}/`

3. **And** après édition d'un moteur, le cache frontend des icônes (`engineIconCache` / `useEngines`) est invalidé ou rafraîchi pour que les changements soient visibles immédiatement dans le catalogue et les exécutions

4. **And** la reproductibilité de la config icônes entre environnements est **documentée** : au choix (ou combinaison) — fixtures Django pour REF_ENGINES, commande de management `seed_reference_engines`, ou section dans la doc déploiement expliquant comment exporter/importer la config entre envs

5. **And** les tests (backend + frontend) couvrent : liste des moteurs en Admin (tous, pas seulement actifs), édition icon_url/label, persistance et rafraîchissement du cache

## Tasks / Subtasks

- [x] Task 1 — Frontend : service admin engines (AC 1, 2)
  - [x] 1.1 Créer `frontend/src/services/engines_service.ts` avec :
    - `fetchEnginesForAdmin(activeOnly?: boolean)` → `GET /reference/engines?active_only=false` (tous les moteurs pour l'admin)
    - `updateEngine(id: number, payload: Partial<EngineUpdatePayload>)` → `PATCH /admin/engines/${id}/`
  - [x] 1.2 Utiliser `apiFetch` (comme `categories_service.ts`) — **pas** `apiFetchRaw`

- [x] Task 2 — Frontend : composant EnginesAdminTable (AC 1, 2, 3)
  - [x] 2.1 Créer `frontend/src/components/admin/EnginesAdminTable.tsx` en suivant le pattern exact de `CategoriesAdminTable.tsx` :
    - Tableau Ant Design : colonnes Code, Label, Ordre, Actif (Tag), Icône (aperçu), Actions
    - Colonne Icône : afficher `<img src={record.icon_url} />` avec fallback si null/invalide (icône générique ou placeholder)
    - Boutons : « Modifier » (ouvre modal), « Désactiver » (si actif, confirmation puis PATCH `is_active: 0`)
    - Bouton Rafraîchir dans le header
    - Chargement initial via `fetchEnginesForAdmin(false)` (tous, actifs + inactifs)
  - [x] 2.2 Créer `frontend/src/components/admin/EngineForm.tsx` (modal d'édition) en suivant le pattern de `CategoryForm.tsx` :
    - Champs : icon_url (Input texte, placeholder « URL de l'icône SVG/PNG »), label, display_order (InputNumber), is_active (Switch)
    - Code en lecture seule (disabled) — pas de création de moteur, édition uniquement
    - Validation : icon_url optionnel, label requis, display_order >= 0
    - Soumission → `updateEngine()` puis callback `onSuccess` pour refetch

- [x] Task 3 — Frontend : onglet Admin « Moteurs » (AC 1)
  - [x] 3.1 Créer `frontend/src/pages/admin/EnginesAdminPanel.tsx` (wrapper Card + EnginesAdminTable, pattern CategoriesAdminPanel)
  - [x] 3.2 Exporter `EnginesAdminPanel` depuis `frontend/src/pages/admin/index.ts`
  - [x] 3.3 Ajouter l'onglet `{ key: 'engines', label: 'Moteurs', children: <EnginesAdminPanel /> }` dans `AdminPage.tsx` — insérer après « Catégories »

- [x] Task 4 — Invalidation du cache après édition (AC 3)
  - [x] 4.1 Dans `engineIconCache.ts` : exporter une fonction `invalidateEngineIconCache()` qui réinitialise le cache interne (mettre `cachedMap = null` et `fetchPromise = null` ou équivalent)
  - [x] 4.2 Dans `useEngines.ts` : exporter une fonction `invalidateEnginesCache()` qui réinitialise le cache partagé du hook
  - [x] 4.3 Dans `EnginesAdminTable.tsx` : après un PATCH réussi, appeler `invalidateEngineIconCache()` + `invalidateEnginesCache()` puis refetch la liste admin

- [x] Task 5 — Reproductibilité config icônes (AC 4)
  - [x] 5.1 Créer `django_backend/docs/reference-data.md` documentant :
    - Les données REF_ENGINES (icon_url, label, etc.) et INTEGRATIONS (icon)
    - Options pour répliquer entre envs : `manage.py dumpdata reference.RefEngine --format=json > fixtures/ref_engines.json`, puis `manage.py loaddata fixtures/ref_engines.json`
    - Ou export API GET /reference/engines → importer via script PATCH en boucle
    - Intégrations : même approche via API /admin/integrations/

- [x] Task 6 — Tests (AC 5)
  - [x] 6.1 Backend : vérifier que `GET /reference/engines?active_only=false` retourne bien les moteurs inactifs (tests existants dans `reference/tests/test_views.py` et `test_engines.py` — 24/24 pass)
  - [x] 6.2 Frontend : tests pour `EnginesAdminTable` (liste, ouverture modal, soumission update, appel API PATCH, invalidation cache) — 8/8 pass
  - [x] 6.3 Frontend : tests pour `EngineForm` (validation, soumission, callback onSuccess) — 10/10 pass

## Dev Notes

### API backend existante — ne rien modifier côté backend

L'API est déjà complète (Story 31.3) :
- `GET /api/v1/reference/engines?active_only=true|false` — liste les moteurs (filtre actifs par défaut)
- `PATCH /api/v1/admin/engines/{pk}/` — édite un moteur (icon_url, label, display_order, is_active)
- Permission : `DBOPSProfilePermission` (IsAuthenticated + profil DBOPS)
- Serializers : `RefEngineSerializer` (lecture), `RefEngineWriteSerializer` (écriture)
- URL routing : `reference/admin_urls.py` ligne 14

**Format réponse PATCH** : objet engine direct (PAS de wrapper `{"data": ...}`) — attention, `updateCategory` utilise un wrapper mais `update_engine` non (inconsistance documentée, code-review Story 31.3). Utiliser `apiFetch` directement.

### Pattern de référence : CategoriesAdminPanel

Suivre exactement le pattern Categories (3 fichiers) :

| Fichier référence | Fichier à créer |
|---|---|
| `pages/admin/CategoriesAdminPanel.tsx` | `pages/admin/EnginesAdminPanel.tsx` |
| `components/admin/CategoriesAdminTable.tsx` | `components/admin/EnginesAdminTable.tsx` |
| `components/admin/CategoryForm.tsx` | `components/admin/EngineForm.tsx` |
| `services/categories_service.ts` | `services/engines_service.ts` |

### Type RefEngine existant

Déjà défini dans `services/reference_service.ts` lignes 14-21 :

```typescript
export interface RefEngine {
  id: number;
  code: string;
  label: string;
  display_order: number;
  is_active: number;  // 0 ou 1 (Oracle INTEGER, pas boolean)
  icon_url: string | null;
}
```

Importer depuis `reference_service.ts` — ne PAS redéfinir le type.

### Cache engines — fichiers à modifier

- `frontend/src/utils/engineIconCache.ts` : ajouter `invalidateEngineIconCache()` exportée
- `frontend/src/hooks/useEngines.ts` : ajouter `invalidateEnginesCache()` exportée
- Les deux caches utilisent des variables de module (`cachedMap`, `fetchPromise`, `cacheData`…) — la fonction d'invalidation doit réinitialiser ces variables à `null`

### AdminPage — structure des onglets

Fichier : `frontend/src/pages/AdminPage.tsx`
7 onglets existants : Actions, Profils, Intégrations, Règles métier, Catégories, Métriques, Feature Flags.
Ajouter « Moteurs » après « Catégories » (key: `'engines'`).

### Différences avec CategoriesAdminTable

1. **Pas de création** : les moteurs sont créés par migration/seed (pas de bouton « Créer »). Seule l'édition est possible.
2. **Pas de suppression** : utiliser « Désactiver » (PATCH is_active: 0) au lieu de DELETE.
3. **Colonne Icône** : afficher un aperçu de l'icône (balise `<img>` ou `<Avatar>` Ant Design avec `src={icon_url}`, taille ~24px). Fallback : icône générique `<DatabaseOutlined />` si icon_url est null.
4. **Champ icon_url dans le formulaire** : Input texte pour l'URL. Pas de file upload — l'icône doit être hébergée ailleurs (chemin relatif type `/static/icons/oracle.svg` ou URL externe).

### Notifications Ant Design

Utiliser `App.useApp()` pour obtenir `notification` et `modal` — ne PAS importer `notification` depuis `antd` directement (pattern Ant Design 6.2, établi Story 26.15).

### Commandes frontend utiles

```bash
cd idp-portal/frontend && npx vitest run src/components/admin/EnginesAdminTable.test.tsx
cd idp-portal/frontend && npx vitest run src/components/admin/EngineForm.test.tsx
```

### Project Structure Notes

- Alignement avec la structure admin existante dans `pages/admin/` et `components/admin/`
- Les services frontend sont dans `services/` (un fichier par domaine)
- Les hooks sont dans `hooks/` (un fichier par domaine)
- Les types API sont dans `types/api/` mais `RefEngine` est dans `services/reference_service.ts` (pas dans `types/api/`) — suivre le même pattern, importer depuis `reference_service.ts`

### Intelligence de la story précédente (31.9)

- Story 31.9 a supprimé RefPlatform et consolidé IntegrationTypeCatalogue comme source unique pour les plateformes
- `_PLATFORM_ALIAS` centralisé dans `catalog/serializers.py` et importé par `business_rule_views.py`
- 158 tests passent — pas de régression
- Pattern migration Flyway V083, migration Django `reference/0005`

### Contexte git récent

Les commits récents (Epic 33 SOLID + Story 31.9) montrent :
- Découpage en sous-composants (SRP) — pattern bien établi
- Registry pattern OCP — cohérent avec le service factory
- Injection de dépendances — utiliser constructeur si nouveau service
- Suppression de doublons — aligné avec l'esprit de cette story (unifier la config)

### References

- [Source: reference/views.py#update_engine] — API PATCH existante (lignes 94-124)
- [Source: reference/serializers.py#RefEngineWriteSerializer] — Serializer écriture (lignes 28-33)
- [Source: reference/admin_urls.py] — URL routing admin engines (ligne 14)
- [Source: reference/models.py#RefEngine] — Modèle RefEngine (lignes 27-48)
- [Source: frontend/src/hooks/useEngines.ts] — Hook cache engines
- [Source: frontend/src/utils/engineIconCache.ts] — Cache icônes engines
- [Source: frontend/src/services/reference_service.ts] — Type RefEngine + fetchEngines()
- [Source: frontend/src/components/admin/CategoriesAdminTable.tsx] — Pattern de référence
- [Source: frontend/src/components/admin/CategoryForm.tsx] — Pattern formulaire modal
- [Source: frontend/src/services/categories_service.ts] — Pattern service admin
- [Source: frontend/src/pages/AdminPage.tsx] — Structure onglets admin
- [Source: frontend/src/pages/admin/index.ts] — Exports des panels admin
- [Source: _bmad-output/planning-artifacts/epic-31-admin-catalogue-integrations-et-icones-moteurs.md#Story-31.10]
- [Source: _bmad-output/implementation-artifacts/31-9-suppression-doublon-ref-platforms.md] — Story précédente

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

- ✅ Task 1 : Service `engines_service.ts` créé avec `fetchEnginesForAdmin` et `updateEngine`, utilisant `apiFetch`
- ✅ Task 2 : `EnginesAdminTable.tsx` créé (pattern CategoriesAdminTable) avec colonnes Code/Label/Icône/Ordre/Actif/Actions, aperçu icône Avatar, boutons Modifier/Désactiver. `EngineForm.tsx` créé (modal édition, code disabled, validation label requis)
- ✅ Task 3 : `EnginesAdminPanel.tsx` créé, exporté dans `index.ts`, onglet « Moteurs » ajouté après « Catégories » dans `AdminPage.tsx`
- ✅ Task 4 : `invalidateEngineIconCache()` ajoutée dans `engineIconCache.ts`, `invalidateEnginesCache()` ajoutée dans `useEngines.ts`, appelées après PATCH réussi dans EnginesAdminTable
- ✅ Task 5 : `docs/reference-data.md` créé documentant 3 options de reproductibilité (fixtures Django, export/import API REST, commande seed)
- ✅ Task 6 : 24 backend tests pass (existants), 8 EnginesAdminTable tests + 10 EngineForm tests = 18 frontend tests pass, 3 AdminPage tests pass (0 régression)

### File List

- `idp-portal/frontend/src/services/engines_service.ts` (NEW)
- `idp-portal/frontend/src/components/admin/EnginesAdminTable.tsx` (NEW)
- `idp-portal/frontend/src/components/admin/EngineForm.tsx` (NEW)
- `idp-portal/frontend/src/pages/admin/EnginesAdminPanel.tsx` (NEW)
- `idp-portal/frontend/src/pages/admin/index.ts` (MODIFIED — ajout export EnginesAdminPanel)
- `idp-portal/frontend/src/pages/AdminPage.tsx` (MODIFIED — ajout import + onglet Moteurs)
- `idp-portal/frontend/src/utils/engineIconCache.ts` (MODIFIED — ajout invalidateEngineIconCache)
- `idp-portal/frontend/src/hooks/useEngines.ts` (MODIFIED — ajout invalidateEnginesCache)
- `idp-portal/django_backend/docs/reference-data.md` (NEW — documentation reproductibilité)
- `idp-portal/frontend/src/components/admin/EnginesAdminTable.test.tsx` (NEW — 9 tests)
- `idp-portal/frontend/src/components/admin/EngineForm.test.tsx` (NEW — 10 tests)

## Change Log

- 2026-02-21 : Story 31.10 implémentée — Onglet Admin Moteurs (liste, édition icon_url/label/display_order/is_active), invalidation cache engines après édition, documentation reproductibilité config icônes, 18 frontend + 24 backend tests pass
- 2026-02-21 : Code review adversariale — 7 issues trouvés (1 HIGH, 5 MEDIUM, 1 LOW). 6 corrigés automatiquement :
  - [H1] reference-data.md : commande seed_reference_data inexistante → reformulée en « à créer si besoin »
  - [M1] Avatar fallback cassé pour icon_url invalide → simplifié en Avatar unique avec `icon` fallback
  - [M2] Champ icon_url sans validation URL → ajout règle pattern `/^(\/|https?:\/\/)/`
  - [M3] Test manquant invalidation cache après édition formulaire → ajouté (EnginesAdminTable.test.tsx)
  - [M4] Test déactivation ne vérifie pas `updateEngine({ is_active: 0 })` → assertion ajoutée
  - [M5] reference-data.md Option 2 : fausse revendication « pas de dépendance aux PKs » → limitations documentées
  - [L1] Non corrigé (low) : signature onSuccess divergente du pattern CategoryForm — justifié par l'absence de création
  - 19 frontend tests passent (9 EnginesAdminTable + 10 EngineForm), 3 AdminPage tests passent
