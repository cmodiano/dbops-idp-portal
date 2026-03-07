# Architecture API Client — `api_client.ts`

## Vue d'ensemble

Le module `api_client.ts` centralise toute la communication HTTP frontend avec le backend Django REST.

**Flow :** Service → `apiFetch*()` → helpers (`buildHeaders`, `handleAuthenticatedFetch`, `parseErrorResponse`) → `fetch()` → Response

---

## Helpers internes

### `buildHeaders(token, contentType?, customHeaders?)`

Construit les headers HTTP avec authentification et Content-Type.

| Paramètre | Type | Description |
|-----------|------|-------------|
| `token` | `string \| null` | Token JWT (de `_getAccessToken()`) |
| `contentType` | `string?` | Content-Type (default: omis) |
| `customHeaders` | `Record<string, string>?` | Headers additionnels à merger |

**Exemple d'utilisation standalone:**
```typescript
import { buildHeaders } from './api_client';

const token = getAccessToken();
const headers = buildHeaders(token, 'application/json', { 'X-Request-Id': '123' });
// Résultat: { 'Content-Type': 'application/json', 'X-Request-Id': '123', 'Authorization': 'Bearer <token>' }
```

---

### `handleAuthenticatedFetch(path, init, headers)`

Exécute un fetch avec retry automatique sur 401 (token refresh).

1. Fetch initial vers `${API_BASE}${path}`
2. Si 401 et token présent → appel `_onRefreshNeeded()`
3. Si refresh succès → retry avec nouveau token
4. Retourne la Response finale

**Exemple d'utilisation standalone:**
```typescript
import { handleAuthenticatedFetch, buildHeaders } from './api_client';

const token = getAccessToken();
const headers = buildHeaders(token, 'application/json');
const response = await handleAuthenticatedFetch('/catalog', { method: 'GET' }, headers);
// Response inclut retry 401 automatique si token expiré
```

---

### `parseErrorResponse(response, captureBody?)`

Parse une Response en erreur en message structuré.

- **JSON** : Extrait `body.error.message`, fallback `Erreur HTTP {status}`
- **Text** : Utilise le body texte, fallback `Erreur HTTP {status}: {statusText}`
- **captureBody** : Si `true`, capture le body complet (utile pour les détails de validation 400)

**Exemple - Parsing erreur JSON:**
```typescript
import { parseErrorResponse } from './api_client';

const response = await fetch('/api/v1/action/create', { ... });
if (!response.ok) {
  const { message, body } = await parseErrorResponse(response, true);
  // message = "Validation failed"
  // body = { error: { message: "Validation failed", details: { name: "required" } } }
  console.error(message, body?.error?.details);
}
```

**Exemple - Parsing erreur texte:**
```typescript
const response = await fetch('/api/v1/health');
if (!response.ok) {
  const { message } = await parseErrorResponse(response, false);
  // message = "Service Unavailable" (body texte) ou "Erreur HTTP 503: Service Unavailable"
}
```

---

## Fonctions publiques

| Fonction | Content-Type | Réponse | Usage |
|----------|:------------:|---------|-------|
| `apiFetch<T>` | `application/json` | `body.data as T` | Appels standard (catalogue, admin, etc.) |
| `apiFetchRaw<T>` | `application/json` | `body as T` | Réponses avec champs extra (can_execute, etc.) |
| `apiFetchBlob` | aucun | `Blob` | Téléchargement fichiers (export audit) |
| `apiPostFormData<T>` | aucun (FormData auto) | `body as { data: T }` | Upload fichiers (photos profil) |

### Exemples d'utilisation

**`apiFetch<T>` - Standard (unwrap `.data`):**
```typescript
import { apiFetch } from '@/services/api_client';

// GET avec data unwrapping
const actions = await apiFetch<Action[]>('/catalog');
// Backend: { data: [{ id: 1, name: "Action 1" }] }
// Retour: [{ id: 1, name: "Action 1" }]

// POST
const newAction = await apiFetch<Action>('/admin/actions', {
  method: 'POST',
  body: JSON.stringify({ name: 'New Action' }),
});
```

**`apiFetchRaw<T>` - Full body (avec champs extra):**
```typescript
import { apiFetchRaw } from '@/services/api_client';

const response = await apiFetchRaw<{
  data: Action;
  can_execute: boolean;
  allowed_environments: string[];
}>('/action/123');

// Backend: { data: { id: 123, name: "DB Backup" }, can_execute: true, allowed_environments: ["dev", "staging"] }
// Retour complet sans unwrap
console.log(response.data.name);           // "DB Backup"
console.log(response.can_execute);         // true
console.log(response.allowed_environments); // ["dev", "staging"]
```

**`apiFetchBlob` - Téléchargement fichier:**
```typescript
import { apiFetchBlob } from '@/services/api_client';

const blob = await apiFetchBlob('/audit/export/pdf');
const url = URL.createObjectURL(blob);
const link = document.createElement('a');
link.href = url;
link.download = 'audit-report.pdf';
link.click();
```

**`apiPostFormData<T>` - Upload fichier:**
```typescript
import { apiPostFormData } from '@/services/api_client';

const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('name', 'Profile Picture');

const result = await apiPostFormData<{ file_id: string }>('/profiles/upload', formData);
console.log(result.data.file_id); // "abc-123"
```

---

## Exception : `auth_service.ts`

`auth_service.ts` utilise **partiellement** les helpers au lieu de fonctions complètes:

- **`refreshAccessToken()`** : Utilise `fetch()` brut + `parseErrorResponse()` helper
  - **Raison:** C'est le handler de refresh appelé par `handleAuthenticatedFetch` → circularité
  - **Alignment partiel:** Utilise `parseErrorResponse()` pour consistency

- **`fetchCurrentUser()`** : Utilise `buildHeaders()` + `parseErrorResponse()` helpers
  - **Raison:** Pas besoin de retry 401 (appelé après login avec token frais)
  - **Alignment partiel:** Utilise helpers pour consistency

- **`logoutApi()`** : Utilise `fetch()` brut (best effort, pas de throw)

**Exemple auth_service:**
```typescript
import { buildHeaders, parseErrorResponse } from './api_client';

export async function fetchCurrentUser(token: string): Promise<User | null> {
  const headers = buildHeaders(token); // ← Helper usage
  const res = await fetch(`${API_BASE}/auth/me`, { headers });
  if (!res.ok) {
    const { message } = await parseErrorResponse(res); // ← Helper usage
    console.warn(`fetchCurrentUser failed: ${message}`);
    return null;
  }
  const body = await res.json();
  return body.data ?? null;
}
```

---

## Error handling dans composants React

Toutes les erreurs HTTP sont lancées via `ApiError(message, status, responseBody?)`.

**Pattern recommandé:**
```typescript
import { apiFetch, ApiError } from '@/services/api_client';

try {
  const data = await apiFetch<Action>('/action/123');
  setAction(data);
} catch (err) {
  if (err instanceof ApiError) {
    if (err.status === 403) {
      message.error('Accès refusé');
    } else if (err.status === 400) {
      // Validation error avec détails
      const details = err.responseBody?.error?.details;
      message.error(`Validation: ${JSON.stringify(details)}`);
    } else if (err.status === 404) {
      message.warning('Action introuvable');
    } else {
      message.error(err.message);
    }
  } else {
    // Network error ou autre
    message.error('Erreur réseau');
  }
}
```

**Erreur 401:** Gérée automatiquement par `handleAuthenticatedFetch` (retry + refresh), ne remonte pas au composant sauf si refresh échoue.

---

## Avant/Après Refactoring

### Avant (duplication)

Chaque fonction (`apiFetch`, `apiFetchRaw`, `apiFetchBlob`, `apiPostFormData`) dupliquait:
- ~6 lignes: Token injection + headers setup
- ~8 lignes: 401 retry logic
- ~22-24 lignes: Error parsing (try-catch imbriqués)

**Total:** ~60 lignes dupliquées x4 fonctions = ~240 lignes dupliquées

### Après (centralisé)

3 helpers centralisés (29 lignes au total) utilisés par les 4 fonctions:
- `buildHeaders()`: 15 lignes
- `handleAuthenticatedFetch()`: 17 lignes
- `parseErrorResponse()`: 24 lignes

4 fonctions publiques refactorées: ~13-15 lignes chacune (total ~52 lignes)

**Total api_client.ts:** 208 → 157 lignes (-24.5%, 51 lignes économisées)

**Bénéfice maintenabilité:**
- Modifier error parsing: **1 helper** au lieu de 4 fonctions
- Ajouter nouvelle méthode HTTP: **~15 lignes** avec helpers au lieu de copier-coller ~60 lignes
