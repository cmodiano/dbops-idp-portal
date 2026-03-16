# Architecture

Documentation d'architecture du projet IDP Portal.

## Documents

| Document | Description |
|----------|-------------|
| [Architecture des workflows](workflow-architecture.md) | Vue d'ensemble complète : composants, schéma BD, cycle de vie, machine à états, gates, retry, auth, observabilité |
| [Guide développeur](developer-guide.md) | Référence technique : stack, structure projet, modules Django, runtime, step handlers, Celery, React, debugging |
| [Stratégie de cache](caching-strategy.md) | Cache in-memory TTLCache, invalidation, patterns |
| [Configuration as Code](configuration-as-code-strategy.md) | Paradigme Git-as-source-of-truth, import/export YAML |
| [Architecture conteneurs](container-architecture.md) | Docker, orchestration locale |
