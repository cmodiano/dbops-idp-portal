# Story 31.3 : Définir les icônes des technologies / moteurs de base de données

Status: done

## Story

En tant que DBOPS,
je veux pouvoir définir l'icône associée à chaque moteur de base de données (technologie) dans l'admin,
afin de personnaliser l'affichage dans le catalogue, les exécutions et les rapports sans modifier le code (ex. logo Oracle, SQL Server, DB2).

## Acceptance Criteria

1. **Given** le référentiel des moteurs (table `REF_ENGINES`) est administrable
   **When** un DBOPS édite un moteur via l'API admin
   **Then** il peut renseigner une **icône** pour ce moteur : URL d'image (SVG/PNG) ou identifiant d'icône prédéfini via le champ `icon_url`

2. **And** l'API `GET /api/v1/reference/engines/` expose le champ `icon_url` (null si non défini) pour chaque moteur

3. **And** le frontend utilise `icon_url` (depuis l'API) pour afficher l'icône du moteur **partout où le moteur est affiché**, avec un fallback en cascade :
   1. `icon_url` depuis l'API (si non null et non vide)
   2. `ENGINE_SVG_SOURCES` hardcodé (compatibilité existante)
   3. Composant Ant Design `ENGINE_ICONS` (fallback final)

4. **And** la rétrocompatibilité est assurée : moteurs sans `icon_url` défini conservent l'affichage actuel (fallback vers `ENGINE_SVG_SOURCES` puis `ENGINE_ICONS`)

5. **And** des tests backend valident : persistance du champ, exposition via API, endpoint admin PATCH

6. **And** un endpoint admin `PATCH /api/v1/admin/engines/{pk}/` permet à un DBOPS de mettre à jour `icon_url` (et `label`, `display_order`, `is_active`) d'un moteur

## Tasks / Subtasks

- [x] Task 1 — Migration DB : ajouter colonne `ICON_URL` à `REF_ENGINES` (AC: #1, #4)
  - [x] 1.1 Créer `reference/migrations/0003_refengine_icon_url.py` : ajouter `icon_url = models.CharField(max_length=500, null=True, blank=True, db_column='ICON_URL')`
  - [x] 1.2 Vérifier que la migration Oracle est compatible (VARCHAR2(500) NULL)

- [x] Task 2 — Modèle `RefEngine` : ajouter le champ `icon_url` (AC: #1, #4)
  - [x] 2.1 Dans `reference/models.py`, classe `RefEngine` : ajouter `icon_url = models.CharField(max_length=500, null=True, blank=True, db_column='ICON_URL')`

- [x] Task 3 — Serializer : exposer `icon_url` dans l'API publique (AC: #2)
  - [x] 3.1 Dans `reference/serializers.py`, classe `RefEngineSerializer` : ajouter `'icon_url'` à la liste `fields`

- [x] Task 4 — Vue admin : endpoint `PATCH /api/v1/admin/engines/{pk}/` (AC: #6)
  - [x] 4.1 Dans `reference/serializers.py`, créer `RefEngineWriteSerializer` avec champs éditables : `icon_url`, `label`, `display_order`, `is_active`
  - [x] 4.2 Dans `reference/views.py`, créer la fonction `update_engine(request, pk)` : `@api_view(['PATCH'])`, permission `DBOPSProfilePermission`, validation via `RefEngineWriteSerializer`, `partial=True`
  - [x] 4.3 Dans `reference/admin_urls.py`, enregistrer `path('engines/<int:pk>/', update_engine, name='admin-engine-update')`
  - [x] 4.4 Import de `update_engine` dans `admin_urls.py`

- [x] Task 5 — Frontend : hook `useEngines` + cache d'icônes (AC: #3, #4)
  - [x] 5.1 `useEngines.ts` existe déjà — ajout de `icon_url` à l'interface `RefEngine` dans `reference_service.ts`
  - [x] 5.2 Créé `engineIconCache.ts` — singleton cache code → icon_url avec `prefetchEngineIcons()` au démarrage App

- [x] Task 6 — Frontend : adapter `renderEngineIcon` avec fallback cascade (AC: #3, #4)
  - [x] 6.1 Dans `executionRenderers.tsx`, `renderEngineIcon` accepte paramètre optionnel `iconUrl?: string | null` + lookup automatique via `getEngineIconUrl(engine)`
  - [x] 6.2 Fallback cascade : 1) iconUrl param, 2) engineIconCache, 3) ENGINE_SVG_SOURCES, 4) ENGINE_ICONS
  - [x] 6.3 Appelants `ActionCard.tsx` et `RecentExecutions.tsx` mis à jour pour utiliser `getEngineIconUrl()` du cache
  - [x] 6.4 `executionsColumns.tsx` inchangé (rétrocompatible via lookup automatique dans renderEngineIcon)

- [x] Task 7 — Tests backend (AC: #5)
  - [x] 7.1 `test_engines.py` : PATCH icon_url → persistée, retournée par GET
  - [x] 7.2 Test : moteur sans icon_url → null dans la réponse API
  - [x] 7.3 Test : accès PATCH par utilisateur non-DBOPS → 403
  - [x] 7.4 Test : icon_url > 500 chars → 400

## Dev Notes

### État actuel du code (analyse exhaustive)

#### Backend — Modèle `RefEngine`

```python
# reference/models.py (état ACTUEL — pas d'icon_url)
class RefEngine(models.Model):
    id            = models.BigAutoField(primary_key=True, db_column='ID')
    code          = models.CharField(max_length=50, unique=True, db_column='CODE')
    label         = models.CharField(max_length=100, db_column='LABEL')
    display_order = models.IntegerField(default=0, db_column='DISPLAY_ORDER')
    is_active     = models.IntegerField(default=1, db_column='IS_ACTIVE')
    objects       = RefEngineManager()

    class Meta:
        db_table = 'REF_ENGINES'
        ordering = ['display_order', 'code']
```

**Ajouter :**
```python
icon_url = models.CharField(max_length=500, null=True, blank=True, db_column='ICON_URL')
```

#### Backend — Serializer existant

```python
# reference/serializers.py (état ACTUEL)
class RefEngineSerializer(serializers.ModelSerializer):
    normalized_code = serializers.SerializerMethodField()

    class Meta:
        model = RefEngine
        fields = ['id', 'code', 'label', 'display_order', 'is_active', 'normalized_code']

    def get_normalized_code(self, obj):
        return obj.code.lower().replace(' ', '_')
```

**Modifier `fields` pour inclure `'icon_url'` :**
```python
fields = ['id', 'code', 'label', 'display_order', 'is_active', 'normalized_code', 'icon_url']
```

`normalized_code` est calculé côté backend mais **non utilisé** actuellement dans le frontend (grep confirmé — 0 occurrence dans `src/`).

#### Backend — Vue `list_engines` (ne pas modifier)

```python
# reference/views.py — conserver tel quel
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_engines(request: Request) -> Response:
    """GET /api/v1/reference/engines/"""
    active_only = request.query_params.get('active_only', 'true').lower() == 'true'
    queryset = RefEngine.objects.all()
    if active_only:
        queryset = queryset.active()
    queryset = queryset.ordered()
    serializer = RefEngineSerializer(queryset, many=True)
    return Response({"data": serializer.data})
```

#### Backend — Vue admin à créer

Pattern identique à `update_category` (Story 2.30) dans `reference/views.py` :

```python
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, DBOPSProfilePermission])
def update_engine(request: Request, pk: int) -> Response:
    """
    PATCH /api/v1/admin/engines/{pk}/
    Update engine fields (icon_url, label, display_order, is_active).
    DBOPS only.
    """
    correlation_id = get_correlation_id()
    logger.info("updating_engine", engine_id=pk, correlation_id=correlation_id)

    try:
        engine = RefEngine.objects.get(pk=pk)
    except RefEngine.DoesNotExist:
        return Response({"detail": "Moteur introuvable."}, status=status.HTTP_404_NOT_FOUND)

    serializer = RefEngineWriteSerializer(engine, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    logger.info("engine_updated", engine_id=pk, correlation_id=correlation_id)
    return Response(RefEngineSerializer(engine).data)
```

**Write serializer à créer :**
```python
class RefEngineWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefEngine
        fields = ['label', 'display_order', 'is_active', 'icon_url']
```

#### Backend — admin_urls.py (état actuel)

```python
# reference/admin_urls.py (état ACTUEL)
from reference.views import create_category, update_category, delete_category

urlpatterns = [
    path('categories/', create_category, name='admin-category-create'),
    path('categories/<int:pk>/', update_category, name='admin-category-update'),
    path('categories/<int:pk>/delete/', delete_category, name='admin-category-delete'),
]
```

**Ajouter :**
```python
from reference.views import create_category, update_category, delete_category, update_engine

urlpatterns = [
    path('categories/', create_category, name='admin-category-create'),
    path('categories/<int:pk>/', update_category, name='admin-category-update'),
    path('categories/<int:pk>/delete/', delete_category, name='admin-category-delete'),
    path('engines/<int:pk>/', update_engine, name='admin-engine-update'),  # Story 31.3
]
```

#### Backend — Migration Oracle

```python
# reference/migrations/0003_refengine_icon_url.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('reference', '0002_refcategory'),
    ]
    operations = [
        migrations.AddField(
            model_name='refengine',
            name='icon_url',
            field=models.CharField(blank=True, db_column='ICON_URL', max_length=500, null=True),
        ),
    ]
```

Oracle : `VARCHAR2(500 CHAR) NULL` — compatible sans problème.

### Frontend — Architecture actuelle des icônes moteurs

#### `ENGINE_SVG_SOURCES` (hardcodé, à conserver en fallback)

```typescript
// frontend/src/utils/executionRenderers.tsx (état ACTUEL)
const ENGINE_SVG_SOURCES: Partial<Record<ActionEngine, string>> = {
  Oracle: 'https://www.svgrepo.com/show/354152/oracle.svg',      // CDN externe
  'SQL Server': 'https://www.svgrepo.com/show/303229/microsoft-sql-server-logo.svg',  // CDN externe
  DB2: '/icons/engines/db2.svg',                                  // fichier local
};
```

⚠️ Ces URLs CDN externes (svgrepo.com) peuvent être bloquées en réseau entreprise — la fonctionnalité `icon_url` stockée en DB permettra de les remplacer par des URLs internes.

#### `renderEngineIcon` — signature actuelle et appelants

```typescript
// Signature actuelle
export function renderEngineIcon(
  engine: ActionEngine | null | undefined,
  itemType?: ItemType | null,
): React.ReactNode

// Appelants (3 fichiers)
// executionsColumns.tsx:115
renderEngineIcon(record.engine, record.item_type)

// ActionCard.tsx:52
renderEngineIcon(action.engine, action.item_type)

// RecentExecutions.tsx:68
renderEngineIcon(exec.engine, exec.item_type)
```

Les objets `record`, `action`, `exec` viennent de l'API — ils ont un champ `engine: string` (code comme "Oracle") mais **pas** `engine_icon_url`. Il faut donc un mapping code → icon_url accessible sans passer par les objets exécution/action.

#### Stratégie recommandée : module cache singleton

```typescript
// frontend/src/utils/engineIconCache.ts (NOUVEAU FICHIER)
import { apiClient } from '../services/api';

type EngineIconMap = Record<string, string | null>;

let cache: EngineIconMap | null = null;
let loadingPromise: Promise<EngineIconMap> | null = null;

export async function getEngineIconMap(): Promise<EngineIconMap> {
  if (cache) return cache;
  if (!loadingPromise) {
    loadingPromise = apiClient
      .get('/reference/engines/')
      .then((res) => {
        const map: EngineIconMap = {};
        for (const engine of res.data.data) {
          map[engine.code] = engine.icon_url ?? null;
        }
        cache = map;
        return cache;
      });
  }
  return loadingPromise;
}

export function getEngineIconUrl(engineCode: string): string | null {
  return cache?.[engineCode] ?? null;
}

export function prefetchEngineIcons(): void {
  getEngineIconMap().catch(() => {}); // prefetch silencieux
}
```

**Alternative simplifiée (sans async) :** Modifier `renderEngineIcon` pour accepter `iconUrl?: string | null` en paramètre, et passer la valeur depuis le composant parent qui a accès au store React Query des engines.

**Recommandation :** Commencer par la solution `iconUrl` en paramètre optionnel (plus simple), et n'implémenter le cache singleton que si les 3 appelants ont accès aux données engines via React Query / store.

#### Adaptation `renderEngineIcon`

```typescript
// Nouvelle signature (rétrocompatible — paramètre optionnel)
export function renderEngineIcon(
  engine: ActionEngine | null | undefined,
  itemType?: ItemType | null,
  iconUrl?: string | null,  // NOUVEAU : icon_url depuis l'API, prioritaire sur ENGINE_SVG_SOURCES
): React.ReactNode {
  // Workflow prend la priorité (comportement actuel inchangé)
  // ...

  // Résolution de l'icône SVG avec fallback cascade
  const svgSrc = (iconUrl && iconUrl.trim())
    ? iconUrl.trim()                              // 1. icon_url API (prioritaire)
    : ENGINE_SVG_SOURCES[engine as ActionEngine]; // 2. hardcodé (fallback)

  // Suite de la logique actuelle inchangée...
}
```

### Tests backend — structure recommandée

```
reference/tests/
├── __init__.py
└── test_engines.py   (NOUVEAU)
```

Si `reference/tests/` n'existe pas, créer le répertoire avec `__init__.py`.

Pattern de test à suivre (inspiré de `integrations/tests/test_integration_views.py`) :

```python
# reference/tests/test_engines.py
class RefEngineAdminViewTests(APITestCase):
    def setUp(self):
        self.dbops_user = ...  # User avec profil DBOPS
        self.regular_user = ...
        self.engine = RefEngine.objects.create(code='TEST', label='Test Engine', display_order=99)

    def test_patch_engine_icon_url_success(self):
        """DBOPS peut mettre à jour icon_url."""
        self.client.force_authenticate(self.dbops_user)
        response = self.client.patch(
            f'/api/v1/admin/engines/{self.engine.pk}/',
            {'icon_url': 'https://example.com/icon.svg'},
        )
        self.assertEqual(response.status_code, 200)
        self.engine.refresh_from_db()
        self.assertEqual(self.engine.icon_url, 'https://example.com/icon.svg')

    def test_patch_engine_icon_url_exposed_in_list(self):
        """icon_url mis à jour est retourné par GET /reference/engines/."""
        self.engine.icon_url = 'https://example.com/oracle.svg'
        self.engine.save()
        self.client.force_authenticate(self.regular_user)
        response = self.client.get('/api/v1/reference/engines/?active_only=false')
        data = {e['code']: e for e in response.data['data']}
        self.assertEqual(data['TEST']['icon_url'], 'https://example.com/oracle.svg')

    def test_patch_engine_forbidden_for_non_dbops(self):
        """Non-DBOPS → 403."""
        self.client.force_authenticate(self.regular_user)
        response = self.client.patch(
            f'/api/v1/admin/engines/{self.engine.pk}/',
            {'icon_url': 'https://example.com/icon.svg'},
        )
        self.assertEqual(response.status_code, 403)

    def test_patch_engine_icon_url_null_on_create(self):
        """Nouveau moteur sans icon_url → null dans l'API."""
        self.client.force_authenticate(self.regular_user)
        response = self.client.get('/api/v1/reference/engines/?active_only=false')
        data = {e['code']: e for e in response.data['data']}
        self.assertIsNone(data['TEST']['icon_url'])
```

### Fichiers à créer / modifier

**Backend (Django) :**
- `reference/migrations/0003_refengine_icon_url.py` — NOUVEAU
- `reference/models.py` — ajouter champ `icon_url`
- `reference/serializers.py` — ajouter `icon_url` + créer `RefEngineWriteSerializer`
- `reference/views.py` — ajouter vue `update_engine()`
- `reference/admin_urls.py` — enregistrer route engines
- `reference/tests/test_engines.py` — NOUVEAU (+ `reference/tests/__init__.py` si besoin)

**Frontend (React) :**
- `frontend/src/utils/executionRenderers.tsx` — adapter `renderEngineIcon` (paramètre `iconUrl?`)
- `frontend/src/utils/engineIconCache.ts` — NOUVEAU (optionnel, si cache singleton nécessaire)
- `frontend/src/pages/executions/executionsColumns.tsx` — passer `iconUrl`
- `frontend/src/components/catalog/ActionCard.tsx` — passer `iconUrl`
- `frontend/src/components/dashboard/RecentExecutions.tsx` — passer `iconUrl`

### Project Structure Notes

```
django_backend/
├── reference/
│   ├── migrations/
│   │   ├── 0001_initial.py         — RefEngine + RefPlatform (id, code, label, display_order, is_active)
│   │   ├── 0002_refcategory.py     — RefCategory
│   │   └── 0003_refengine_icon_url.py  — NOUVEAU (icon_url)
│   ├── models.py                   — RefEngine, RefPlatform, RefCategory
│   ├── serializers.py              — RefEngineSerializer (+ RefEngineWriteSerializer à créer)
│   ├── views.py                    — list_engines, list_platforms, categories CRUD (+ update_engine)
│   ├── admin_urls.py               — admin categories CRUD (+ engines/{pk}/ à ajouter)
│   ├── urls.py                     — GET /engines/, GET /platforms/, categories
│   └── tests/
│       └── test_engines.py         — NOUVEAU

frontend/src/
├── utils/
│   ├── executionRenderers.tsx      — renderEngineIcon (adapter iconUrl?)
│   └── engineIconCache.ts          — NOUVEAU (optionnel)
├── pages/executions/
│   └── executionsColumns.tsx       — appelant renderEngineIcon
└── components/
    ├── catalog/ActionCard.tsx      — appelant renderEngineIcon
    └── dashboard/RecentExecutions.tsx — appelant renderEngineIcon
```

### Conventions et patterns du projet

- **Oracle DB** : utiliser `db_column='NOM_MAJ'` (convention Oracle colonnes en majuscules)
- **Permissions admin** : `@permission_classes([IsAuthenticated, DBOPSProfilePermission])` — pattern identique à `create_category`, `update_category`
- **Logger** : `structlog.get_logger(__name__)` avec `correlation_id = get_correlation_id()`
- **Format réponse** : `{"data": [...]}` pour les listes, objet direct pour les PATCH
- **Tests** : `APITestCase` de DRF, `force_authenticate()`
- **Frontend** : Ant Design + TypeScript strict, `Partial<Record<K, V>>` pour les maps avec types enum

### Rétrocompatibilité garantie

1. `icon_url = null` pour tous les moteurs existants après migration → `ENGINE_SVG_SOURCES` continue de fonctionner
2. `renderEngineIcon(engine, itemType)` sans 3ème argument → comportement 100% identique à l'actuel
3. Les URLs CDN svgrepo.com dans `ENGINE_SVG_SOURCES` ne sont **pas supprimées** — elles restent en fallback
4. Aucune donnée de configuration existante n'est impactée

### References

- [Source: reference/models.py] — modèle `RefEngine` actuel (sans icon_url)
- [Source: reference/serializers.py] — `RefEngineSerializer` (fields à compléter)
- [Source: reference/views.py] — `list_engines` + pattern `update_category` à reproduire
- [Source: reference/admin_urls.py] — admin URLs existantes
- [Source: reference/migrations/0001_initial.py] — schéma initial REF_ENGINES
- [Source: frontend/src/utils/executionRenderers.tsx#L46-57] — `ENGINE_SVG_SOURCES`, `ENGINE_ICONS`
- [Source: frontend/src/utils/executionRenderers.tsx#L196-248] — `renderEngineIcon()`
- [Source: frontend/src/pages/executions/executionsColumns.tsx#L115] — appelant `renderEngineIcon`
- [Source: frontend/src/components/catalog/ActionCard.tsx#L32,52] — appelant `renderEngineIcon`
- [Source: frontend/src/components/dashboard/RecentExecutions.tsx#L24,68] — appelant `renderEngineIcon`
- [Source: _bmad-output/implementation-artifacts/31-2-suppression-integration-desactiver-actions.md] — story précédente (patterns admin API, permissions, audit)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 31.3]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

### Completion Notes List

- ✅ Migration 0003_refengine_icon_url.py créée — VARCHAR2(500 CHAR) NULL Oracle compatible
- ✅ Modèle RefEngine enrichi avec champ icon_url
- ✅ RefEngineSerializer expose icon_url (null par défaut)
- ✅ RefEngineWriteSerializer créé pour édition admin (label, display_order, is_active, icon_url)
- ✅ Endpoint PATCH /api/v1/admin/engines/{pk}/ — DBOPS only, pattern identique à update_category
- ✅ Interface TypeScript RefEngine enrichie avec icon_url: string | null
- ✅ engineIconCache.ts créé — singleton cache code→icon_url, prefetch au démarrage App
- ✅ renderEngineIcon enrichi — fallback cascade : API icon_url → ENGINE_SVG_SOURCES → ENGINE_ICONS
- ✅ ActionCard.tsx et RecentExecutions.tsx utilisent getEngineIconUrl() du cache
- ✅ Rétrocompatibilité totale — appelants existants sans 3e paramètre fonctionnent identiquement
- ✅ 12 tests backend (9 PATCH admin + 3 GET API) — tous passent (ajout test null par code-review)
- ✅ 67/67 reference tests passent — 0 régression
- ✅ 32/32 executionRenderers frontend tests passent — 0 régression
- ✅ TypeScript compile sans erreur
- ✅ [code-review] Fix H1 : prefetchEngineIcons déplacé dans useEffect de ThemedApp (évite race condition SAML)
- ✅ [code-review] Fix M1 : EngineIconCell dans RecentExecutions — icon_url API affiché pour moteurs inconnus
- ✅ [code-review] Fix M2 : commentaire documentant incohérence format réponse PATCH
- ✅ [code-review] Fix L1 : TestCase → APITestCase dans test_engines.py
- ✅ [code-review] Fix L2 : test ajouté pour effacement icon_url via null
- ✅ [code-review] Fix L4 : reference/tests/__init__.py ajouté au File List

### Change Log

- 2026-02-19: Story 31.3 implémentée — icônes moteurs administrables via icon_url (backend PATCH admin + frontend fallback cascade)
- 2026-02-19: Code review — 7 issues (1H, 2M, 4L) corrigées : race condition SAML prefetch, EngineIconCell moteurs inconnus, APITestCase, test null, documentation

### File List

**Backend (Django) — créés/modifiés :**
- idp-portal/django_backend/reference/migrations/0003_refengine_icon_url.py (NOUVEAU)
- idp-portal/django_backend/reference/models.py (MODIFIÉ — ajout icon_url)
- idp-portal/django_backend/reference/serializers.py (MODIFIÉ — icon_url + RefEngineWriteSerializer)
- idp-portal/django_backend/reference/views.py (MODIFIÉ — ajout update_engine + commentaire M2)
- idp-portal/django_backend/reference/admin_urls.py (MODIFIÉ — route engines/{pk}/)
- idp-portal/django_backend/reference/tests/test_engines.py (NOUVEAU — 12 tests, code-review: APITestCase + test null)
- idp-portal/django_backend/reference/tests/__init__.py (pré-existant, ajouté au File List)

**Frontend (React) — créés/modifiés :**
- idp-portal/frontend/src/services/reference_service.ts (MODIFIÉ — icon_url dans RefEngine)
- idp-portal/frontend/src/utils/engineIconCache.ts (NOUVEAU)
- idp-portal/frontend/src/utils/executionRenderers.tsx (MODIFIÉ — renderEngineIcon fallback cascade)
- idp-portal/frontend/src/components/catalog/ActionCard.tsx (MODIFIÉ — getEngineIconUrl)
- idp-portal/frontend/src/components/dashboard/RecentExecutions.tsx (MODIFIÉ — getEngineIconUrl + fix M1 moteurs inconnus)
- idp-portal/frontend/src/App.tsx (MODIFIÉ — prefetchEngineIcons via useEffect, fix H1)
