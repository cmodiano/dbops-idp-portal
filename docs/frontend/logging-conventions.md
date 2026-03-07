# Conventions de Logging - Frontend

Story 17.7 - Service de logging structuré et règle ESLint

## Pourquoi un service de logging ?

- Logging cohérent et structuré à travers tout le frontend
- Configuration par environnement (dev vs prod)
- Préparation pour envoi backend futur (observabilité)
- Respect des bonnes pratiques via linter (`no-console: error`)

## Import et Usage

```typescript
import logger from '../services/logger';

// Debug (développement uniquement)
logger.debug('Cache hit', { key: 'environments', size: 10 });

// Info (développement uniquement)
logger.info('User action completed', { actionId: 123, userId: 456 });

// Warning (dev + prod)
logger.warn('API call failed, retrying', { attempt: 2, error: err.message });

// Error (dev + prod)
logger.error('Failed to load data', {
  error: err.message,
  stack: err.stack,
  correlation_id: response.correlation_id
});
```

## Environnements

**Développement (`MODE=development`):**
- Tous les niveaux actifs (debug, info, warn, error)
- Affichage console formaté : `[LEVEL] message` + objet structuré

**Production (`MODE=production`):**
- Seuls `warn` et `error` actifs
- Logs structurés JSON (préparation backend futur)

## Règle ESLint no-console

**Interdiction stricte de `console.*` dans le code source.**

```typescript
// INTERDIT - Erreur ESLint
console.log('debug info');
console.error('error message');

// CORRECT - Utiliser le logger
logger.debug('debug info');
logger.error('error message', { error: err });
```

**Exception:** Les fichiers de test (`*.test.ts`, `*.test.tsx`) peuvent utiliser `console.*`.

Le fichier `logger.ts` utilise `eslint-disable-next-line no-console` pour les appels internes à `console.*` dans la fonction `_output()`.

## Pattern de données structurées

Toujours inclure le contexte pertinent dans le deuxième paramètre :

```typescript
// Mauvais - message seul
logger.error('Failed to fetch actions');

// Bon - message + contexte
logger.error('Failed to fetch actions', {
  userId: user.id,
  error: err.message,
  correlation_id: response?.correlation_id
});
```

## Niveaux de log

| Niveau | Env Dev | Env Prod | Usage |
|--------|---------|----------|-------|
| `debug` | Actif | Inactif | Cache, infos techniques internes |
| `info` | Actif | Inactif | Actions utilisateur, événements métier |
| `warn` | Actif | Actif | Erreurs récupérables, dégradations |
| `error` | Actif | Actif | Erreurs critiques, échecs API |

## Performance et bonnes pratiques

**Attention en production:** Les logs `warn` et `error` utilisent `JSON.stringify()` pour sérialiser les données structurées. Évitez de logger des objets volumineux (> 1 KB) qui peuvent bloquer le thread.

**Bonne pratique:**
```typescript
// ❌ Mauvais - objet énorme loggé
logger.error('Failed to load', { fullDataset: data }); // data = 10 000 rows

// ✅ Bon - résumé compact
logger.error('Failed to load', { count: data.length, error: err.message });
```

**Protection:** Le logger utilise try/catch autour de `JSON.stringify()` pour éviter les crashes en cas de références circulaires.
