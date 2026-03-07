# Système de Feature Flags

## Vue d'ensemble

Le système de feature flags permet de contrôler l'activation de fonctionnalités sans redéploiement. Il supporte :
- **Dark launch** : déployer du code désactivé en production
- **Rollout progressif** : activer pour un pourcentage d'utilisateurs (hashing cohérent)
- **Kill switch** : désactiver rapidement une fonctionnalité problématique
- **A/B testing** : afficher différentes variantes selon le flag

## Backend (Django)

### Configuration

Variables d'environnement (`.env` ou système) :

| Variable | Description | Valeurs | Défaut |
|---|---|---|---|
| `FEATURE_FLAGS_ENABLED` | Active/désactive le système globalement | `true`/`false` | `true` |
| `FEATURE_FLAGS_SOURCE` | Source des flags | `env`/`database` | `env` |
| `FEATURE_FLAGS_CACHE_TTL` | Durée du cache (secondes) | entier positif | `300` |
| `FEATURE_FLAGS` | Config JSON (quand source=env) | JSON object | `{}` |

Exemple de `FEATURE_FLAGS` :
```json
{
  "new_workflow_builder": {"enabled": true, "rollout_percent": 100},
  "dark_mode_v2": {"enabled": true, "rollout_percent": 50},
  "experimental_api": {"enabled": false, "rollout_percent": 0}
}
```

### Service (`core/feature_flags.py`)

```python
from core import feature_flags

# Vérifier si un flag est activé
if feature_flags.is_enabled('new_workflow_builder'):
    # Nouveau code
    pass

# Avec contexte utilisateur (pour rollout progressif)
if feature_flags.is_enabled('gradual_rollout', {'user_id': request.user.id}):
    # Activé pour cet utilisateur
    pass

# Obtenir tous les flags
all_status = feature_flags.get_all_flags_status(context={'user_id': user.id})

# Invalider le cache après modification
feature_flags.invalidate_cache('flag_key')  # Un flag spécifique
feature_flags.invalidate_cache()             # Tous les flags
```

### API REST

| Endpoint | Méthode | Permissions | Description |
|---|---|---|---|
| `/api/v1/feature-flags/` | GET | Admin (DBOPS) | Liste tous les flags |
| `/api/v1/feature-flags/status/` | GET | Authentifié | État des flags pour l'utilisateur courant |
| `/api/v1/feature-flags/{flag_key}/` | PATCH | Admin (DBOPS) | Modifier un flag |

PATCH body :
```json
{"enabled": true, "rollout_percent": 75}
```

### Modèle de données

Table `CORE_FEATURE_FLAGS` (quand `FEATURE_FLAGS_SOURCE=database`) :

| Colonne | Type | Description |
|---|---|---|
| `ID` | BIGINT PK | Identifiant auto-incrémenté |
| `FLAG_KEY` | VARCHAR(100) UNIQUE | Clé du flag (format: `[a-z0-9][a-z0-9_-]*`) |
| `ENABLED` | BOOLEAN | Flag activé/désactivé |
| `ROLLOUT_PERCENT` | INT (0-100) | Pourcentage de rollout |
| `DESCRIPTION` | VARCHAR(500) | Description optionnelle |
| `UPDATED_AT` | TIMESTAMP | Dernière modification |
| `UPDATED_BY` | VARCHAR(100) | Utilisateur ayant modifié |

### Validation au démarrage

La configuration est validée au startup via `core/startup_checks.py` :
- `FEATURE_FLAGS_SOURCE` doit être `env` ou `database`
- `FEATURE_FLAGS_ENABLED` doit être un booléen valide
- `FEATURE_FLAGS_CACHE_TTL` doit être un entier positif
- Le JSON de `FEATURE_FLAGS` doit être valide (fail-fast en production, warning en dev)

## Frontend (React)

### FeatureFlagProvider

Ajouté dans `App.tsx` au niveau des providers (entre `AuthProvider` et `DashboardProvider`). Auto-refresh toutes les 5 minutes.

### Hooks

```tsx
import { useFeatureFlag, useFeatureFlags } from '../contexts/FeatureFlagContext';

// Vérifier un flag unique
function MyComponent() {
  const isNewUI = useFeatureFlag('new_ui');
  return isNewUI ? <NewUI /> : <OldUI />;
}

// Accéder à tous les flags
function DebugPanel() {
  const flags = useFeatureFlags();
  return <pre>{JSON.stringify(flags, null, 2)}</pre>;
}
```

### Composants

**FeatureGuard** - Rendu conditionnel :
```tsx
import { FeatureGuard } from '../components/FeatureGuard';

<FeatureGuard flag="new_workflow_builder" fallback={<OldWorkflow />}>
  <NewWorkflow />
</FeatureGuard>
```

**FeatureToggle** - A/B testing :
```tsx
import { FeatureToggle } from '../components/FeatureToggle';

<FeatureToggle flag="dark_mode_v2" on={<DarkTheme />} off={<LightTheme />} />
```

### Admin UI

Onglet "Feature Flags" dans la page Admin (`/admin`). Permet de :
- Voir tous les flags configurés
- Toggle on/off via Switch
- Modifier le rollout % via Slider
- Voir la date de dernière modification

## Déploiement

### Activation/Désactivation d'urgence (Kill Switch)

Pour désactiver **tout le système** de feature flags :
```bash
FEATURE_FLAGS_ENABLED=false
```

Pour désactiver **un flag spécifique** :
- Via API : `PATCH /api/v1/feature-flags/{flag_key}/ {"enabled": false}`
- Via env : Mettre `"enabled": false` dans le JSON `FEATURE_FLAGS`

### Impact CI/CD

- **Aucun changement requis** dans le pipeline CI/CD
- Les flags sont désactivés par défaut (opt-in)
- La migration ajoute la table `CORE_FEATURE_FLAGS` automatiquement
- Les variables d'environnement sont optionnelles (valeurs par défaut sûres)

### Stratégie de rollout

1. Créer le flag avec `"enabled": true, "rollout_percent": 0`
2. Augmenter progressivement : 10% → 25% → 50% → 100%
3. Surveiller les métriques à chaque palier
4. Si problème : réduire le rollout ou désactiver le flag
5. Une fois stable à 100% : retirer le flag et le code conditionnel
