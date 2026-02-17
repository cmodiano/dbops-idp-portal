# Feature Flags — Upgrade Redis Pub/Sub Multi-Instance

## Limitation actuelle

Le système de feature flags (Story 17.12) utilise `LocMemCache` comme backend de cache.

**Conséquence :** Chaque instance Django a son propre cache en mémoire. En multi-instance
(derrière un load balancer), une mise à jour de flag via l'API n'invalide que le cache de
l'instance ayant reçu la requête. Les autres instances conservent l'ancienne valeur
jusqu'à expiration du TTL (5 minutes par défaut).

**Impact :** Un utilisateur peut voir un flag activé ou désactivé selon l'instance
qui sert sa requête, pendant une fenêtre de 0-5 minutes après modification.

## Architecture cible : Redis Pub/Sub

### Principe

```
┌──────────────┐     PATCH /feature-flags/X/     ┌──────────────┐
│  Instance 1  │ ──────────────────────────────►  │    Redis      │
│  (Django)    │                                  │   Pub/Sub     │
└──────────────┘ ◄──── subscribe ─────────────── └──────────────┘
                                                        │
┌──────────────┐ ◄──── subscribe ───────────────────────┘
│  Instance 2  │
│  (Django)    │
└──────────────┘
```

1. Instance 1 reçoit PATCH → met à jour DB → publie message sur channel Redis
2. Toutes les instances (y compris Instance 1) reçoivent le message
3. Chaque instance invalide son cache local pour le flag concerné

### Channel Redis

```
REDIS_FEATURE_FLAGS_CHANNEL = 'feature_flags:invalidate'
```

### Message format

```json
{
  "flag_key": "new_ui",
  "action": "invalidate",
  "timestamp": "2026-02-08T10:30:00Z"
}
```

## Variables d'environnement

Ajouter dans `.env.production.template` :

```bash
# Feature Flags Redis Pub/Sub (multi-instance)
REDIS_URL=redis://localhost:6379/0
FEATURE_FLAGS_PUBSUB_ENABLED=false
FEATURE_FLAGS_REDIS_CHANNEL=feature_flags:invalidate
```

## Implémentation

### 1. Publisher (dans `feature_flag_views.py`)

Après invalidation cache locale, publier sur Redis :

```python
# core/feature_flags.py
import json
from django.conf import settings

def _publish_invalidation(flag_key):
    """Publish cache invalidation to Redis pub/sub."""
    if not getattr(settings, 'FEATURE_FLAGS_PUBSUB_ENABLED', False):
        return

    redis_url = getattr(settings, 'REDIS_URL', None)
    if not redis_url:
        return

    import redis
    channel = getattr(settings, 'FEATURE_FLAGS_REDIS_CHANNEL', 'feature_flags:invalidate')
    try:
        client = redis.from_url(redis_url)
        client.publish(channel, json.dumps({
            'flag_key': flag_key,
            'action': 'invalidate',
        }))
    except Exception as e:
        logger.warning("feature_flag_pubsub_publish_error", error=str(e))
```

### 2. Subscriber (dans `core/apps.py ready()`)

```python
# core/apps.py
import threading

class CoreConfig(AppConfig):
    def ready(self):
        if getattr(settings, 'FEATURE_FLAGS_PUBSUB_ENABLED', False):
            thread = threading.Thread(target=self._start_flag_subscriber, daemon=True)
            thread.start()

    def _start_flag_subscriber(self):
        import json
        import redis
        import structlog
        from django.core.cache import cache

        logger = structlog.get_logger(__name__)
        redis_url = getattr(settings, 'REDIS_URL', '')
        channel = getattr(settings, 'FEATURE_FLAGS_REDIS_CHANNEL', 'feature_flags:invalidate')

        try:
            client = redis.from_url(redis_url)
            pubsub = client.pubsub()
            pubsub.subscribe(channel)
            logger.info("feature_flags_pubsub_started", channel=channel)

            for message in pubsub.listen():
                if message['type'] != 'message':
                    continue
                try:
                    data = json.loads(message['data'].decode())
                    flag_key = data.get('flag_key')
                    if flag_key:
                        cache.delete(f'feature_flag:{flag_key}')
                    cache.delete('feature_flags:all')
                    logger.debug("feature_flags_pubsub_invalidated", flag_key=flag_key)
                except json.JSONDecodeError as e:
                    logger.warning("feature_flags_pubsub_invalid_message", error=str(e))
                except Exception as e:
                    logger.error("feature_flags_pubsub_error", error=str(e), error_type=type(e).__name__)
        except Exception as e:
            logger.error("feature_flags_pubsub_startup_failed", error=str(e))
            # Don't crash the app — pub/sub is enhancement, not critical
```

### 3. Modifier `invalidate_cache()` pour publier

```python
def invalidate_cache(flag_key=None):
    if flag_key:
        cache.delete(f'feature_flag:{flag_key}')
    cache.delete('feature_flags:all')
    logger.info("feature_flag_cache_invalidated", flag_key=flag_key or "all")
    _publish_invalidation(flag_key or '__all__')
```

## Migration LocMemCache → Redis Cache Backend

Pour de meilleures performances, le cache backend peut aussi migrer vers Redis :

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    }
}
```

**Note :** Ceci remplace LocMemCache pour *tout* le cache Django (pas seulement feature flags).
Le pub/sub reste nécessaire pour l'invalidation proactive (sinon il faut attendre expiration TTL).

## Tests de validation multi-instance

### Prérequis

- 2 instances Django (ports 8000 et 8001)
- 1 Redis (port 6379)
- 1 load balancer (nginx round-robin)

### Scénario de test

```bash
# 1. Vérifier état initial (flag disabled sur les 2 instances)
curl http://localhost:8000/api/v1/feature-flags/status/ -H "Authorization: Bearer $TOKEN"
curl http://localhost:8001/api/v1/feature-flags/status/ -H "Authorization: Bearer $TOKEN"

# 2. Activer le flag via instance 1
curl -X PATCH http://localhost:8000/api/v1/feature-flags/new_ui/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# 3. Vérifier que instance 2 reflète le changement (< 1s)
sleep 1
curl http://localhost:8001/api/v1/feature-flags/status/ -H "Authorization: Bearer $TOKEN"
# new_ui devrait être true
```

### Résultat attendu

- Sans pub/sub : Instance 2 garde l'ancienne valeur pendant max 5 min (TTL)
- Avec pub/sub : Instance 2 invalide son cache en < 1 seconde
