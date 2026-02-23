# Story 31.7 : Aide contextuelle (tooltip + popover Markdown) alimentée par le backend

Status: done

## Story

En tant que DBOPS,
je veux une **aide contextuelle** dans les fenêtres de configuration : un **tooltip** pour un contexte court au survol, et un **popover** avec doc **Markdown** pour les sections plus complexes au clic, le tout alimenté par des **fichiers MD stockés côté backend** (maintenables dans git),
afin de comprendre rapidement une section (tooltip) ou consulter une doc détaillée (popover) sans quitter l'écran.

## Acceptance Criteria

### Backend — Stockage et API

1. **Given** un répertoire dédié `django_backend/docs/help/` avec des fichiers Markdown par topic (un fichier par `topic_id`, ex. `action-form-integration.md`), avec frontmatter YAML optionnel contenant `short`
   **When** `GET /api/v1/help/<topic_id>/` est appelé avec une authentification valide
   **Then** la réponse 200 retourne `{ "topic_id": "...", "short": "...", "markdown": "..." }` où `short` provient du frontmatter ou du premier paragraphe (fallback), et `markdown` est le corps du fichier

2. **And** si `topic_id` n'est pas dans la liste autorisée (mapping Python), la réponse est **404** `{ "error": { "code": "NOT_FOUND", "message": "Topic inconnu" } }`

3. **And** le mapping `topic_id → fichier` est un dictionnaire Python dans `help/topics.py` (liste blanche — pas de path traversal). Seuls les topic_id figurant dans ce dictionnaire sont acceptés.

4. **And** l'endpoint est protégé par `IsAuthenticated` (même politique que le reste de l'API)

5. **And** les 3 topics pilotes suivants sont créés avec leur fichier MD :
   - `action-form-integration` → `docs/help/action-form-integration.md`
   - `action-form-changement-servicenow` → `docs/help/action-form-changement-servicenow.md`
   - `action-form-gates` → `docs/help/action-form-gates.md`

### Frontend — Composant et affichage

6. **Given** un composant `SectionHelp` avec props `topicId: string` et `mode?: 'tooltip' | 'popover' | 'both'` (défaut : `'both'`)
   **When** l'utilisateur survole l'icône d'aide
   **Then** un **Tooltip** Ant Design affiche le champ `short` (texte brut, pas de Markdown)

7. **And** au **clic** sur l'icône d'aide (mode `'popover'` ou `'both'`), un **Popover** Ant Design s'ouvre avec le champ `markdown` rendu via `<ReactMarkdown>` (avec `remark-gfm` et `rehype-sanitize`). Largeur max 400px, scroll si contenu long.

8. **And** le service `getHelpContent(topicId)` appelle `GET /api/v1/help/<topicId>/` et met en cache la réponse en sessionStorage (clé `help_<topicId>`, durée 10 min) pour éviter les appels répétés.

9. **And** accessibilité : l'icône `QuestionCircleOutlined` a un `aria-label="Aide pour cette section"`, le Popover est fermable via Escape.

### Intégration

10. **And** le composant `<SectionHelp>` est intégré dans **au moins 2 sections pilotes** dans `ActionForm.tsx` et/ou `ActionWizard.tsx` :
    - À côté du label « Intégration » : `<SectionHelp topicId="action-form-integration" />`
    - À côté du label « Changement ServiceNow par environnement » : `<SectionHelp topicId="action-form-changement-servicenow" />`

## Tasks / Subtasks

### Backend — App `help`

- [x] **Tâche 1 : Créer l'app Django `help`** (AC: #1–#4)
  - [x] 1.1 — Créer le dossier `django_backend/help/` avec `__init__.py`, `apps.py`, `views.py`, `urls.py`, `topics.py`, `tests/`
  - [x] 1.2 — Dans `help/apps.py` : `class HelpConfig(AppConfig): name = 'help'`
  - [x] 1.3 — Ajouter `'help'` à `INSTALLED_APPS` dans `idp_backend/settings.py`
  - [x] 1.4 — Enregistrer la route dans `idp_backend/urls.py` : `path('api/v1/', include('help.urls'))`

- [x] **Tâche 2 : Mapping topic_id → fichier** (AC: #2–#3)
  - [x] 2.1 — Créer `help/topics.py` avec le dictionnaire `HELP_TOPICS: dict[str, str]` :
    ```python
    HELP_TOPICS = {
        "action-form-integration": "action-form-integration.md",
        "action-form-changement-servicenow": "action-form-changement-servicenow.md",
        "action-form-gates": "action-form-gates.md",
    }
    ```
  - [x] 2.2 — Constante `HELP_DIR = Path(settings.BASE_DIR) / 'docs' / 'help'`

- [x] **Tâche 3 : Parser frontmatter** (AC: #1)
  - [x] 3.1 — Dans `help/views.py`, implémenter `_parse_help_file(path: Path) -> tuple[str, str]` avec `PyYAML` (déjà installé) :
    - Regex `re.compile(r'^---\n(.*?)\n---\n(.*)', re.DOTALL)` pour détecter le frontmatter
    - `short = yaml.safe_load(frontmatter_str).get('short', '')` si frontmatter présent
    - Fallback (pas de frontmatter) : `short` = première ligne non vide (strippée des `#`), max 200 chars
    - `markdown` = contenu après le frontmatter (ou tout le fichier si pas de frontmatter)

- [x] **Tâche 4 : Vue `GET /api/v1/help/<topic_id>/`** (AC: #1–#4)
  - [x] 4.1 — Dans `help/views.py` :
    ```python
    @api_view(['GET'])
    @permission_classes([IsAuthenticated])
    def get_help_topic(request: Request, topic_id: str) -> Response:
    ```
  - [x] 4.2 — Valider `topic_id` contre `HELP_TOPICS`. Si absent : lever `NotFoundError(message="Topic d'aide inconnu")`
  - [x] 4.3 — Construire le chemin : `HELP_DIR / HELP_TOPICS[topic_id]`
  - [x] 4.4 — Si le fichier n'existe pas : logger warning + retourner 404
  - [x] 4.5 — Lire le fichier, appeler `_parse_help_file()`, retourner `{"topic_id": topic_id, "short": short, "markdown": markdown}`
  - [x] 4.6 — Logging structuré : `logger.info("help_topic_served", topic_id=topic_id, correlation_id=...)`
  - [x] 4.7 — Dans `help/urls.py` : `path('help/<str:topic_id>/', get_help_topic, name='help-topic')`

- [x] **Tâche 5 : Créer les 3 fichiers MD pilotes** (AC: #5)
  - [x] 5.1 — Créer `django_backend/docs/help/action-form-integration.md` avec frontmatter `short` et corps Markdown
  - [x] 5.2 — Créer `django_backend/docs/help/action-form-changement-servicenow.md`
  - [x] 5.3 — Créer `django_backend/docs/help/action-form-gates.md`

- [x] **Tâche 6 : Tests backend** (AC: #1–#5)
  - [x] 6.1 — `test_get_help_topic_ok` : mock fichier MD avec frontmatter → 200 + `{topic_id, short, markdown}`
  - [x] 6.2 — `test_get_help_topic_no_frontmatter` : fichier MD sans frontmatter → `short` = première ligne, `markdown` = contenu complet
  - [x] 6.3 — `test_get_help_topic_unknown` : topic_id inconnu → 404
  - [x] 6.4 — `test_get_help_topic_file_missing` : topic dans mapping mais fichier absent → 404
  - [x] 6.5 — `test_get_help_topic_unauthenticated` : sans JWT → 401
  - [x] 6.6 — `test_get_help_topic_path_traversal` : `topic_id = "../../../etc/passwd"` → 404 (hors mapping)

### Frontend — Service

- [x] **Tâche 7 : Créer `help_service.ts`** (AC: #8)
  - [x] 7.1 — Créer `frontend/src/services/help_service.ts`
  - [x] 7.2 — Interface `HelpContent { topic_id: string; short: string; markdown: string }`
  - [x] 7.3 — `CACHE_KEY = (topicId: string) => \`help_\${topicId}\`` + `CACHE_DURATION_MS = 10 * 60 * 1000`
  - [x] 7.4 — `getHelpContent(topicId: string): Promise<HelpContent>` :
    - Vérifier cache sessionStorage (parse JSON, vérifier timestamp)
    - Si cache valide → retourner `data`
    - Sinon → `apiFetch(\`/api/v1/help/\${topicId}/\`)`, stocker en sessionStorage, retourner
  - [x] 7.5 — Gestion d'erreur : si 404 ou erreur réseau → retourner `{ topic_id: topicId, short: '', markdown: '' }` (pas de crash)

### Frontend — Hook

- [x] **Tâche 8 : Créer `useHelpContent.ts`** (AC: #6–#9)
  - [x] 8.1 — Créer `frontend/src/hooks/useHelpContent.ts`
  - [x] 8.2 — `useHelpContent(topicId: string)` : appelle `getHelpContent()`, retourne `{ content: HelpContent | null, loading: boolean, error: string | null }`
  - [x] 8.3 — Utiliser `useEffect` avec `topicId` en dépendance

### Frontend — Composant `SectionHelp`

- [x] **Tâche 9 : Créer le composant `SectionHelp`** (AC: #6–#9)
  - [x] 9.1 — Créer `frontend/src/components/common/SectionHelp.tsx`
  - [x] 9.2 — Props :
    ```typescript
    interface SectionHelpProps {
      topicId: string;
      mode?: 'tooltip' | 'popover' | 'both';
    }
    ```
  - [x] 9.3 — **Mode `tooltip` / `both`** : icône `<QuestionCircleOutlined>` enveloppée dans `<Tooltip title={content?.short}>` (survol → texte court)
  - [x] 9.4 — **Mode `popover` / `both`** : au clic, ouvrir `<Popover>` avec contenu :
    ```tsx
    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
      {content?.markdown || ''}
    </ReactMarkdown>
    ```
    Style : `maxWidth: 400px`, overflow-y scroll si contenu long
  - [x] 9.5 — Loading state : spinner ou icône grisée pendant le chargement
  - [x] 9.6 — Erreur silencieuse : si `getHelpContent` échoue, le composant s'affiche mais le popover est vide (pas de crash)
  - [x] 9.7 — Accessibilité : `aria-label="Aide pour cette section"` sur l'icône, `tabIndex={0}`, Popover fermable au clic extérieur et via Escape (`keyboard` prop Ant Design)

- [x] **Tâche 10 : Intégration dans ActionForm et ActionWizard** (AC: #10)
  - [x] 10.1 — Dans `ActionForm.tsx`, à côté du label « Intégration » : ajouter `<SectionHelp topicId="action-form-integration" />`
  - [x] 10.2 — Dans `ActionForm.tsx`, à côté du label/section « Changement ServiceNow par environnement » : ajouter `<SectionHelp topicId="action-form-changement-servicenow" />`
  - [x] 10.3 — Même intégration dans `ActionWizard.tsx` pour les étapes correspondantes

### Frontend — Tests

- [x] **Tâche 11 : Tests frontend** (AC: #6–#10)
  - [x] 11.1 — `help_service.test.ts` : getHelpContent OK, cache sessionStorage hit, 404 → objet vide, erreur réseau → objet vide
  - [x] 11.2 — `useHelpContent.test.ts` : chargement, contenu retourné, erreur silencieuse
  - [x] 11.3 — `SectionHelp.test.tsx` : affichage tooltip short, popover Markdown affiché au clic, aria-label présent, loading state, erreur silencieuse

## Dev Notes

### Architecture — app `help` (sans base de données)

Cette story crée une **nouvelle app Django `help`** qui expose un endpoint REST basé sur des fichiers (pas de modèle Django, pas de migration).

```
django_backend/
├── help/
│   ├── __init__.py
│   ├── apps.py          # HelpConfig
│   ├── topics.py        # HELP_TOPICS dict + HELP_DIR
│   ├── views.py         # get_help_topic() + _parse_help_file()
│   ├── urls.py          # path('help/<str:topic_id>/', ...)
│   └── tests/
│       └── test_help_views.py
├── docs/
│   └── help/
│       ├── action-form-integration.md
│       ├── action-form-changement-servicenow.md
│       └── action-form-gates.md
```

**Pas de migration Flyway ni Django** — cette app n'a pas de modèle.

### Parsing frontmatter avec PyYAML (déjà disponible)

`PyYAML>=6.0.0` est déjà dans `pyproject.toml`. Pas de nouvelle dépendance.

```python
import re
import yaml
from pathlib import Path

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)', re.DOTALL)

def _parse_help_file(path: Path) -> tuple[str, str]:
    """
    Parse un fichier MD avec frontmatter YAML optionnel.
    Retourne (short: str, markdown: str).
    """
    content = path.read_text(encoding='utf-8')
    m = _FRONTMATTER_RE.match(content)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        short: str = str(meta.get('short', ''))
        markdown: str = m.group(2).strip()
    else:
        # Fallback : première ligne non vide (strippée de #) comme short
        lines = content.strip().split('\n')
        first = next((l.lstrip('#').strip() for l in lines if l.strip()), '')
        short = first[:200]
        markdown = content.strip()
    return short, markdown
```

### Vue Django — pattern à suivre

Suivre le pattern de `reference/views.py` :

```python
import re
import yaml
import structlog
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.exceptions import NotFoundError
from core.middleware import get_correlation_id
from help.topics import HELP_TOPICS, HELP_DIR

logger = structlog.get_logger(__name__)

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)', re.DOTALL)


def _parse_help_file(path: Path) -> tuple[str, str]:
    content = path.read_text(encoding='utf-8')
    m = _FRONTMATTER_RE.match(content)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        short: str = str(meta.get('short', ''))
        markdown: str = m.group(2).strip()
    else:
        lines = content.strip().split('\n')
        first = next((l.lstrip('#').strip() for l in lines if l.strip()), '')
        short = first[:200]
        markdown = content.strip()
    return short, markdown


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_help_topic(request: Request, topic_id: str) -> Response:
    """
    Story 31.7 - Aide contextuelle backend.
    GET /api/v1/help/<topic_id>/ → { topic_id, short, markdown }
    """
    correlation_id = get_correlation_id()

    if topic_id not in HELP_TOPICS:
        logger.warning(
            "help_topic_not_found",
            topic_id=topic_id,
            correlation_id=correlation_id,
        )
        raise NotFoundError(message="Topic d'aide inconnu")

    file_path = HELP_DIR / HELP_TOPICS[topic_id]
    if not file_path.exists():
        logger.warning(
            "help_file_missing",
            topic_id=topic_id,
            file=str(file_path),
            correlation_id=correlation_id,
        )
        raise NotFoundError(message="Fichier d'aide introuvable")

    short, markdown = _parse_help_file(file_path)

    logger.info(
        "help_topic_served",
        topic_id=topic_id,
        short_len=len(short),
        markdown_len=len(markdown),
        correlation_id=correlation_id,
    )

    return Response(
        {"topic_id": topic_id, "short": short, "markdown": markdown},
        status=status.HTTP_200_OK,
    )
```

### `help/topics.py`

```python
from pathlib import Path
from django.conf import settings

# Répertoire contenant les fichiers d'aide Markdown
HELP_DIR = Path(settings.BASE_DIR) / 'docs' / 'help'

# Liste blanche topic_id → nom de fichier (sécurité path traversal)
HELP_TOPICS: dict[str, str] = {
    "action-form-integration": "action-form-integration.md",
    "action-form-changement-servicenow": "action-form-changement-servicenow.md",
    "action-form-gates": "action-form-gates.md",
}
```

**Note :** `HELP_DIR` utilise `settings.BASE_DIR` défini dans `idp_backend/settings.py` :
`BASE_DIR = Path(__file__).resolve().parent.parent` → pointe vers `django_backend/`.
Le répertoire `django_backend/docs/help/` existe déjà (d'autres docs y sont présents).

### `help/urls.py`

```python
from django.urls import path
from help.views import get_help_topic

urlpatterns = [
    path('help/<str:topic_id>/', get_help_topic, name='help-topic'),
]
```

Enregistrer dans `idp_backend/urls.py` :
```python
path('api/v1/', include('help.urls')),
```

### `idp_backend/settings.py` — ajout `INSTALLED_APPS`

```python
INSTALLED_APPS = [
    ...
    'help',  # Story 31.7 - Aide contextuelle
    ...
]
```

### Format du frontmatter des fichiers MD

```markdown
---
short: "Choisissez l'intégration d'exécution pour cette action. Seules les intégrations configurées dans Admin > Intégrations sont proposées (rôle = plateforme)."
---
# Intégration d'exécution

L'**intégration** correspond à l'instance de plateforme (ex. AAP Production, ServiceNow Prod) qui sera appelée lors de l'exécution de cette action.

## Pourquoi ce champ est important

- Seules les intégrations **configurées et actives** sont proposées.
- Si aucune intégration n'est disponible, créez-en une dans **Admin > Intégrations**.
- La valeur envoyée au backend est l'`integration_id` ; la plateforme est déduite du type de l'intégration.
```

### Frontend — `help_service.ts`

```typescript
// frontend/src/services/help_service.ts
import { apiFetch } from './api_client';

export interface HelpContent {
  topic_id: string;
  short: string;
  markdown: string;
}

const CACHE_DURATION_MS = 10 * 60 * 1000; // 10 minutes

function getCacheKey(topicId: string): string {
  return `help_${topicId}`;
}

export async function getHelpContent(topicId: string): Promise<HelpContent> {
  const cacheKey = getCacheKey(topicId);
  const cached = sessionStorage.getItem(cacheKey);
  if (cached) {
    try {
      const { data, timestamp } = JSON.parse(cached) as { data: HelpContent; timestamp: number };
      if (Date.now() - timestamp < CACHE_DURATION_MS) {
        return data;
      }
    } catch { /* ignore */ }
  }

  try {
    const data = await apiFetch<HelpContent>(`/api/v1/help/${topicId}/`);
    sessionStorage.setItem(cacheKey, JSON.stringify({ data, timestamp: Date.now() }));
    return data;
  } catch {
    // Erreur silencieuse : le composant s'affiche sans aide
    return { topic_id: topicId, short: '', markdown: '' };
  }
}
```

**Note :** Vérifier la signature de `apiFetch` dans `api_client.ts` — utiliser la même convention que `useServiceNowIntegrations.ts` (`res.data || res.results`).

### Frontend — `SectionHelp.tsx` — points d'attention

```tsx
// frontend/src/components/common/SectionHelp.tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { QuestionCircleOutlined } from '@ant-design/icons';
import { Tooltip, Popover } from 'antd';
```

- **`react-markdown` v10** : l'import est `import ReactMarkdown from 'react-markdown'`
- **`remark-gfm` v4** : `import remarkGfm from 'remark-gfm'`
- **`rehype-sanitize` v6** : `import rehypeSanitize from 'rehype-sanitize'`
- Ces trois packages sont déjà dans `package.json` — **pas d'`npm install` nécessaire**

```tsx
const markdownContent = (
  <div style={{ maxWidth: 400, maxHeight: 400, overflowY: 'auto' }}>
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeSanitize]}
    >
      {content?.markdown || ''}
    </ReactMarkdown>
  </div>
);
```

### Frontend — Intégration dans ActionForm/ActionWizard

Pattern d'intégration (à côté d'un label Ant Design Form.Item) :

```tsx
<Form.Item
  label={
    <span>
      Intégration{' '}
      <SectionHelp topicId="action-form-integration" />
    </span>
  }
  name="integration_id"
>
  {/* ... select */}
</Form.Item>
```

Ou plus simplement, après le label existant dans la section.

### Sécurité — Protection path traversal

La protection est **par conception** : seuls les `topic_id` présents dans `HELP_TOPICS` sont acceptés. Le chemin final est `HELP_DIR / HELP_TOPICS[topic_id]` où `HELP_TOPICS[topic_id]` est un **nom de fichier statique** (pas interpolé depuis l'input utilisateur).

Aucune validation de regex supplémentaire n'est nécessaire sur `topic_id` car la liste blanche suffit. Si `topic_id` n'est pas dans `HELP_TOPICS` → 404 immédiat.

### Tests backend — pattern

```python
# help/tests/test_help_views.py
from unittest.mock import patch, mock_open
from pathlib import Path
from rest_framework.test import APITestCase
from django.urls import reverse

class HelpViewsTest(APITestCase):
    def setUp(self):
        self.user = ...  # UserFactory ou create_user()
        self.client.force_authenticate(user=self.user)

    def test_get_help_topic_ok(self):
        """Topic connu + fichier MD avec frontmatter → 200"""
        md_content = "---\nshort: Texte court\n---\n# Titre\n\nCorps."
        with patch('help.views.HELP_DIR', Path('/fake')):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.read_text', return_value=md_content):
                    resp = self.client.get('/api/v1/help/action-form-integration/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['topic_id'], 'action-form-integration')
        self.assertEqual(data['short'], 'Texte court')
        self.assertIn('# Titre', data['markdown'])

    def test_get_help_topic_unknown(self):
        """Topic inconnu → 404"""
        resp = self.client.get('/api/v1/help/topic-inexistant/')
        self.assertEqual(resp.status_code, 404)

    def test_get_help_topic_path_traversal(self):
        """Tentative de path traversal → 404 (hors mapping)"""
        resp = self.client.get('/api/v1/help/../../../etc/passwd/')
        self.assertIn(resp.status_code, [404, 400])

    def test_get_help_topic_unauthenticated(self):
        """Sans auth → 401"""
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/v1/help/action-form-integration/')
        self.assertEqual(resp.status_code, 401)
```

### Project Structure Notes

| Fichier | Rôle |
|---------|------|
| `django_backend/help/__init__.py` | App package |
| `django_backend/help/apps.py` | `HelpConfig` |
| `django_backend/help/topics.py` | `HELP_TOPICS` dict + `HELP_DIR` |
| `django_backend/help/views.py` | Vue `get_help_topic()` + `_parse_help_file()` |
| `django_backend/help/urls.py` | Route `help/<str:topic_id>/` |
| `django_backend/help/tests/test_help_views.py` | 6 tests backend |
| `django_backend/docs/help/action-form-integration.md` | Topic pilote 1 |
| `django_backend/docs/help/action-form-changement-servicenow.md` | Topic pilote 2 |
| `django_backend/docs/help/action-form-gates.md` | Topic pilote 3 |
| `django_backend/idp_backend/settings.py` | Ajout `'help'` dans `INSTALLED_APPS` |
| `django_backend/idp_backend/urls.py` | Ajout `include('help.urls')` |
| `frontend/src/services/help_service.ts` | `getHelpContent()` + cache |
| `frontend/src/services/help_service.test.ts` | Tests service |
| `frontend/src/hooks/useHelpContent.ts` | Hook `useHelpContent()` |
| `frontend/src/hooks/useHelpContent.test.ts` | Tests hook |
| `frontend/src/components/common/SectionHelp.tsx` | Composant tooltip + popover |
| `frontend/src/components/common/SectionHelp.test.tsx` | Tests composant |
| `frontend/src/components/admin/ActionForm.tsx` | Intégration 2 `<SectionHelp>` pilotes |
| `frontend/src/components/admin/ActionWizard.tsx` | Intégration `<SectionHelp>` pilotes |

### Contraintes importantes

1. **Pas de migration** : cette story n'ajoute aucun modèle Django — aucune migration Flyway ni Django n'est requise.
2. **Pas de nouvelle dépendance Python** : `PyYAML` est déjà dans `pyproject.toml` (v6.0.0+).
3. **Pas de nouvelle dépendance NPM** : `react-markdown` (v10.1.0), `remark-gfm` (v4.0.1), `rehype-sanitize` (v6.0.0) sont déjà dans `package.json`.
4. **`BASE_DIR`** dans `settings.py` pointe vers `django_backend/` — `HELP_DIR = BASE_DIR / 'docs' / 'help'` est correct.
5. **Pattern `apiFetch`** : vérifier la signature dans `api_client.ts` vs `useServiceNowIntegrations.ts` qui utilise `res.data || res.results`.
6. **Ant Design 6.2** : `Alert` utilise `title=` (pas `message=`), `Tooltip` et `Popover` sont importés depuis `antd`.
7. **`react-markdown` v10** : la syntaxe d'import est `import ReactMarkdown from 'react-markdown'` (ESM, pas de `{ ReactMarkdown }`).
8. **Tests backend** : utiliser `APITestCase` (pattern établi), pas `TestCase` standard. Pour les tests avec fichiers, utiliser `unittest.mock.patch` sur `pathlib.Path.read_text` et `pathlib.Path.exists`.

### Contexte git récent (Stories 31.1–31.6)

- `feat(31-6)` : gate_config sur Action, ServiceNowService.create_change() implémenté, hook pre-RUNNING
- `feat(31-4)` : ChangeTypeConfig refonte en 2 blocs (Gates + ServiceNow)
- `feat(31-3)` : icon_url sur REF_ENGINES, useEngineIconCache, renderEngineIcon
- `feat(31-2)` : suppression intégration → actions désactivées (signal Django)
- `feat(31-1)` : ActionForm/ActionWizard → liste intégrations role=platform, usePlatformIntegrations()

**Migration Flyway suivante disponible** : V082 (V081 est utilisé par 31-6). Cette story n'utilise pas de migration.
**Migration Django catalog suivante** : 0011 (non utilisée dans cette story).

### References

- [Source: _bmad-output/planning-artifacts/epic-31-admin-catalogue-integrations-et-icones-moteurs.md#Story-31.7]
- [Source: django_backend/docs/help-contextual-design.md] — Spec détaillée de la feature
- [Source: django_backend/reference/views.py] — Pattern vue DRF à suivre (`@api_view`, `@permission_classes`, `structlog`)
- [Source: django_backend/core/exceptions.py] — `NotFoundError` à utiliser pour les 404
- [Source: django_backend/core/middleware.py] — `get_correlation_id()`
- [Source: django_backend/idp_backend/settings.py] — `BASE_DIR` = `django_backend/`
- [Source: django_backend/idp_backend/urls.py] — Pattern d'enregistrement des apps
- [Source: django_backend/pyproject.toml] — `PyYAML>=6.0.0` déjà disponible
- [Source: frontend/package.json] — `react-markdown@^10.1.0`, `remark-gfm@^4.0.1`, `rehype-sanitize@^6.0.0` déjà disponibles
- [Source: frontend/src/hooks/useServiceNowIntegrations.ts] — Pattern hook avec sessionStorage cache
- [Source: _bmad-output/implementation-artifacts/31-6-config-gates-choix-service-creation-changement-servicenow.md] — Story précédente (champs gate_config, patterns établis)

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

### Completion Notes List

- App Django `help` créée sans modèle ni migration — endpoint REST file-based
- Parser frontmatter YAML avec fallback (première ligne si pas de frontmatter)
- Protection path traversal par liste blanche (dictionnaire `HELP_TOPICS`)
- 3 fichiers MD pilotes créés avec frontmatter `short` et contenu Markdown détaillé
- Service frontend `getHelpContent()` avec cache sessionStorage 10 min
- Hook `useHelpContent` avec gestion loading/error/content
- Composant `SectionHelp` : tooltip (hover) + popover Markdown (clic), modes configurable
- Intégration dans ActionForm.tsx (2 instances) et ActionWizard.tsx (2 instances)
- 6 tests backend (pytest) : OK, frontmatter, unknown, missing, unauthenticated, path traversal
- 15 tests frontend (vitest) : 5 service + 4 hook + 6 composant — tous passent
- **Code Review 2026-02-19** : 7 corrections appliquées (4 MEDIUM, 3 LOW) — voir Change Log

### File List

- `django_backend/help/__init__.py` (nouveau)
- `django_backend/help/apps.py` (nouveau)
- `django_backend/help/topics.py` (nouveau)
- `django_backend/help/views.py` (nouveau)
- `django_backend/help/urls.py` (nouveau)
- `django_backend/help/tests/__init__.py` (nouveau)
- `django_backend/help/tests/test_help_views.py` (nouveau)
- `django_backend/docs/help/action-form-integration.md` (nouveau)
- `django_backend/docs/help/action-form-changement-servicenow.md` (nouveau)
- `django_backend/docs/help/action-form-gates.md` (nouveau)
- `django_backend/idp_backend/settings.py` (modifié — ajout `'help'` INSTALLED_APPS)
- `django_backend/idp_backend/urls.py` (modifié — ajout `include('help.urls')`)
- `frontend/src/services/help_service.ts` (nouveau)
- `frontend/src/services/help_service.test.ts` (nouveau)
- `frontend/src/hooks/useHelpContent.ts` (nouveau)
- `frontend/src/hooks/useHelpContent.test.ts` (nouveau)
- `frontend/src/components/common/SectionHelp.tsx` (nouveau)
- `frontend/src/components/common/SectionHelp.test.tsx` (nouveau)
- `frontend/src/components/admin/ActionForm.tsx` (modifié — 2 `<SectionHelp>` ajoutés)
- `frontend/src/components/admin/ActionWizard.tsx` (modifié — 2 `<SectionHelp>` ajoutés)

**Note :** `django_backend/catalog/serializers.py` présente une modification dans le working tree (category `allow_blank=True`, bug fix indépendant) — non attribuée à cette story.

## Change Log

- 2026-02-19 : Création story 31.7 — Aide contextuelle tooltip + popover Markdown alimentée par le backend.
- 2026-02-19 : Implémentation complète — App help Django (endpoint REST file-based, 3 topics MD pilotes), composant SectionHelp React (tooltip + popover Markdown), intégration ActionForm/ActionWizard — 6 BE + 15 FE tests passent.
- 2026-02-19 : Code review adversariale — 7 corrections : M2 test `file_missing` robuste (mock `Path.exists`), M3 test `mode='both'` ajouté (SectionHelp.test.tsx), M4 contrat service/hook documenté, L1 `@pytest.mark.django_db` redondant retiré, L2 `SectionHelpProps` exportée, L3 `role="button"` sur icône. Story → **done**.
