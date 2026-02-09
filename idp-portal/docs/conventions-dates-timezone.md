# Convention Dates & Timezone — IDP Portal

## Principe

Toutes les dates/heures transitant entre le backend et le frontend sont en **UTC** avec un **timezone explicite**.

## Backend (Django)

### Création de datetimes

- Toujours utiliser `django.utils.timezone.now()` (retourne un datetime UTC-aware grâce à `USE_TZ = True`)
- Ne jamais utiliser `datetime.now()` sans timezone (crée un datetime naif)
- `datetime.now(timezone.utc)` est acceptable (stdlib avec UTC explicite)

### Sérialisation

Utiliser `ensure_utc_isoformat()` depuis `core.utils` pour toute sérialisation de datetime vers JSON :

```python
from core.utils import ensure_utc_isoformat

# Dans un serializer ou une vue
"created_at": ensure_utc_isoformat(obj.created_at),
```

Le helper :
1. Retourne `None` si `dt` est `None`
2. Convertit les datetimes naifs en UTC-aware (filet de sécurité)
3. Convertit en UTC si le datetime est dans un autre fuseau
4. Retourne un ISO 8601 avec suffixe `Z` (ex: `"2026-02-09T14:30:00Z"`)

### Ne PAS utiliser

```python
# INCORRECT — peut produire un datetime sans timezone
obj.created_at.isoformat()

# CORRECT
ensure_utc_isoformat(obj.created_at)
```

### Exception: Date-only fields (pas datetime)

Pour les champs `date` (pas `datetime`), `.isoformat()` est acceptable:

```python
# OK — date sans timezone (utilisé pour filenames, week aggregations)
timezone.now().date().isoformat()  # "2026-02-09"

# OK — champs date-only (birthdate, contract start, etc.)
employee.birthdate.isoformat()  # "1990-05-15"
```

**Attention:** Si le champ est sérialisé vers JSON et affiché dans le frontend, considérer si le frontend attend un `date` ou `datetime`.

### Configuration Django

```python
# settings.py
TIME_ZONE = 'UTC'
USE_TZ = True
```

## Frontend (React/TypeScript)

### Parsing des dates

Utiliser `formatUtcToLocal()` depuis `utils/dateFormat.ts` :

```typescript
import { formatUtcToLocal } from '@/utils/dateFormat';

// Affiche en heure locale de l'utilisateur (format fr-FR)
formatUtcToLocal("2026-02-09T14:30:00Z")  // "09/02/2026 15:30" (CET)
formatUtcToLocal("2026-02-09T14:30:00Z", "date")  // "09/02/2026"
```

`new Date()` en JavaScript interprète nativement :
- `"2026-02-09T14:30:00Z"` → UTC
- `"2026-02-09T14:30:00+00:00"` → UTC
- `"2026-02-09T14:30:00"` → **heure locale** (ambigu, à éviter)

### Règle

Toutes les dates de l'API incluent désormais `Z` — le frontend les interprète correctement comme UTC et les affiche en heure locale.

## Tests

- Backend : `executions/tests/test_serializers_timezone.py` (16 tests)
- Frontend : `src/utils/dateFormat.test.ts` (11 tests)
