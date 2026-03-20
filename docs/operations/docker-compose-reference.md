# Référence docker-compose — IDP Portal

> Document généré le 2026-03-16
> Audience : développeurs, ops, nouveaux contributeurs

Ce document est un guide de référence rapide pour travailler avec l'environnement Docker Compose du projet IDP Portal. Pour une description approfondie de l'architecture des conteneurs, consulter [docs/architecture/container-architecture.md](../architecture/container-architecture.md).

---

## 1. Services et configuration

### Vue d'ensemble des services

| Service | Image / Build | Port(s) exposé(s) | Dépendances |
|---------|-------------|-------------------|-------------|
| `redis` | `redis:7.4-alpine` | `127.0.0.1:6379` | — |
| `oracle-db` | `oracle.com/database/free:latest` | `127.0.0.1:1521`, `127.0.0.1:5500` | — |
| `backend` | Build `./django_backend` | `0.0.0.0:8000` | `oracle-db` (healthy), `redis` (healthy) |
| `celery-worker` | Build `./django_backend` | — | `oracle-db` (healthy), `redis` (healthy) |
| `celery-beat` | Build `./django_backend` | — | `oracle-db` (healthy), `redis` (healthy) |
| `frontend` | Build `./frontend` | `0.0.0.0:8080` | `backend` |

### `redis`

```yaml
image: redis:7.4-alpine
container_name: idp-redis
ports:
  - "127.0.0.1:6379:6379"
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 10s
restart: unless-stopped
networks:
  - idp-network
```

**Bases Redis utilisées :**

| DB | URL | Usage |
|----|-----|-------|
| 0 | `redis://redis:6379/0` | Broker Celery + Result backend |
| 1 | `redis://redis:6379/1` | Cache applicatif Django |
| 2 | `redis://redis:6379/2` | Django Channels (WebSocket) |

---

### `oracle-db`

```yaml
image: container-registry.oracle.com/database/free:${ORACLE_IMAGE_TAG:-latest}
container_name: dbops-oracle
hostname: oracle-db
environment:
  ORACLE_PWD: ${ORACLE_PASSWORD:-Oracle123!}
  ORACLE_CHARACTERSET: AL32UTF8
  ENABLE_APEX: "true"
ports:
  - "127.0.0.1:1521:1521"   # SQL*Net
  - "127.0.0.1:5500:5500"   # EM Express (admin web)
volumes:
  - oracle-data:/opt/oracle/oradata
  - ./database/migrations:/opt/oracle/scripts/startup  # bind mount dev
healthcheck:
  test: ["CMD", "bash", "-c", "echo 'ALTER SESSION SET CONTAINER = FREEPDB1; SELECT 1 FROM DUAL;' | sqlplus -s / as sysdba | grep -q '1'"]
  interval: 30s
  timeout: 10s
  retries: 20
  start_period: 300s  # Oracle 23ai peut prendre jusqu'à 5 min au 1er démarrage
restart: unless-stopped
networks:
  - idp-network
```

**Points clés :**
- `start_period: 300s` — ne pas réduire, sinon les conteneurs dépendants démarrent avant qu'Oracle soit prêt.
- PDB : `FREEPDB1`, utilisateur applicatif : `IDP_APP`
- **Dev/staging uniquement** — remplacé par Oracle DataGuard en production.

---

### `backend`

```yaml
build:
  context: ./django_backend
  dockerfile: Dockerfile
container_name: idp-backend
hostname: backend
ports:
  - "8000:8000"
depends_on:
  oracle-db:
    condition: service_healthy
  redis:
    condition: service_healthy
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health/"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
restart: unless-stopped
networks:
  - idp-network
env_file: .env
```

**Commande de démarrage (définie dans le Dockerfile) :**
```bash
gunicorn idp_backend.asgi:application \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 6 \
  --timeout 60 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --bind 0.0.0.0:8000
```

---

### `celery-worker`

```yaml
build:
  context: ./django_backend
  dockerfile: Dockerfile
container_name: idp-celery-worker
command: >
  celery -A idp_backend worker
  -Q aap,azure,github,terraform,default
  --concurrency=8
  -n worker@%h
depends_on:
  oracle-db:
    condition: service_healthy
  redis:
    condition: service_healthy
healthcheck:
  test: ["CMD-SHELL", "celery -A idp_backend inspect ping -d worker@%h --timeout=5"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
restart: unless-stopped
networks:
  - idp-network
env_file: .env
```

---

### `celery-beat`

```yaml
build:
  context: ./django_backend
  dockerfile: Dockerfile
container_name: idp-celery-beat
command: >
  celery -A idp_backend beat
  --loglevel=info
  --schedule=/tmp/celerybeat-schedule
depends_on:
  oracle-db:
    condition: service_healthy
  redis:
    condition: service_healthy
healthcheck:
  test: ["CMD-SHELL", "pgrep -f 'celery.*beat'"]
  interval: 30s
  timeout: 5s
  retries: 3
restart: unless-stopped
networks:
  - idp-network
env_file: .env
```

> **⚠️ SINGLETON** — Ne jamais démarrer plus d'une instance de `celery-beat`.

---

### `frontend`

```yaml
build:
  context: ./frontend
  dockerfile: Dockerfile
  args:
    VITE_MODE: docker
container_name: idp-frontend
hostname: frontend
ports:
  - "8080:8080"
depends_on:
  - backend
healthcheck:
  test: ["CMD-SHELL", "wget -q --spider http://localhost:8080/ || exit 1"]
  interval: 30s
  timeout: 5s
  retries: 3
restart: unless-stopped
networks:
  - idp-network
```

---

## 2. Volumes et réseau

```yaml
volumes:
  oracle-data:
    name: dbops-oracle-data

networks:
  idp-network:
    driver: bridge
```

| Volume | Nom Docker | Contenu | Persisté |
|--------|-----------|---------|---------|
| `oracle-data` | `dbops-oracle-data` | Fichiers Oracle (`/opt/oracle/oradata`) | ✅ Oui |

**Note :** Il n'existe **pas** de volume nommé pour Celery Beat. Le fichier `/tmp/celerybeat-schedule` est dans le tmpfs du conteneur et est recréé au démarrage.

---

## 3. Démarrage rapide

### Premier démarrage (initialisation Oracle)

```bash
# Depuis le répertoire idp-portal/
docker compose up -d

# Suivre l'initialisation Oracle (peut prendre 3-5 min)
docker compose logs -f oracle-db

# Vérifier que tous les services sont sains
docker compose ps
```

### Démarrage normal

```bash
docker compose up -d
docker compose ps  # vérifier le statut health
```

### Démarrage partiel (dev sans Oracle)

```bash
# Si Oracle DataGuard externe configuré dans .env :
docker compose up -d redis backend celery-worker celery-beat frontend
```

### Arrêt

```bash
docker compose down          # arrêt sans suppression des volumes
docker compose down -v       # arrêt + suppression des volumes (DESTRUCTIF — perd les données Oracle)
```

### Redémarrage d'un service

```bash
docker compose restart backend
docker compose restart celery-worker celery-beat
```

### Rebuild après modification du code

```bash
docker compose build backend celery-worker celery-beat
docker compose up -d --no-deps backend celery-worker celery-beat
```

### Consulter les logs

```bash
# Tous les services
docker compose logs -f

# Service spécifique
docker compose logs -f backend
docker compose logs -f celery-worker
docker compose logs -f celery-beat

# Dernières N lignes
docker compose logs --tail=100 backend
```

---

## 4. Variables d'environnement requises

Le fichier `.env` (copié depuis `.env.example`) doit être présent à la racine du projet. Variables **obligatoires** :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `SECRET_KEY` | Clé de sécurité Django (50+ chars) | `django-insecure-...` (dev uniquement) |
| `JWT_SECRET_KEY` | Clé de signature JWT | Chaîne aléatoire longue |
| `ORACLE_PASSWORD` | Mot de passe Oracle sys/system | `Oracle123!` (dev) |

Variables **importantes** pour le comportement dev vs prod :

| Variable | Dev | Prod |
|----------|-----|------|
| `DEBUG` | `true` | `false` |
| `AUTH_DEV_BYPASS` | `true` | `false` |
| `RATELIMIT_ENABLED` | `false` | `true` |
| `SIMULATE_EXECUTION_DEV` | `true` | `false` |

> 🔗 Référence exhaustive : `docs/operations/environment-variables-reference.md` (story 87-6).

---

## 5. Troubleshooting

### Oracle ne démarre pas ou est lent

**Symptôme :** Les conteneurs `backend`, `celery-worker`, `celery-beat` restent en état `health: starting` ou `Exit 1`.

```bash
# Vérifier les logs Oracle
docker compose logs oracle-db

# Vérifier le status health
docker inspect dbops-oracle --format '{{.State.Health.Status}}'

# Attendre et réessayer (Oracle peut prendre 3-5 min au 1er démarrage)
docker compose logs -f oracle-db | grep -i "database open"
```

**Solutions :**
- Attendre : `start_period: 300s` est normal pour le 1er démarrage.
- Si le volume est corrompu : `docker compose down -v && docker compose up -d` (⚠️ efface les données Oracle).

---

### Celery Worker inactif ou ne consomme pas les tâches

**Symptôme :** Les tâches restent en file, les exécutions ne progressent pas.

```bash
# Vérifier l'état du worker
docker compose logs celery-worker

# Tester le ping Celery
docker compose exec celery-worker celery -A idp_backend inspect ping

# Vérifier les files Redis
docker compose exec redis redis-cli -n 0 llen celery
docker compose exec redis redis-cli -n 0 keys "*"

# Redémarrer le worker
docker compose restart celery-worker
```

---

### Celery Beat ne planifie pas les tâches

**Symptôme :** Les gates ne sont pas évaluées, les exécutions planifiées ne démarrent pas.

```bash
# Vérifier les logs
docker compose logs celery-beat

# Vérifier qu'une seule instance tourne
docker compose ps celery-beat
pgrep -c -f 'celery.*beat'  # doit retourner 1

# Redémarrer (recrée le schedule)
docker compose restart celery-beat
```

---

### Redis — Connexion refusée

**Symptôme :** `ConnectionRefusedError` ou `redis.exceptions.ConnectionError` dans les logs backend/celery.

```bash
# Vérifier que Redis est opérationnel
docker compose exec redis redis-cli ping  # doit retourner PONG

# Vérifier les 3 bases
docker compose exec redis redis-cli -n 0 ping  # Celery broker
docker compose exec redis redis-cli -n 1 ping  # Cache Django
docker compose exec redis redis-cli -n 2 ping  # Channels

# Redémarrer Redis (attention : vide les files Celery)
docker compose restart redis
```

> ⚠️ Redémarrer Redis vide les files Celery. Les tâches en attente sont perdues. Le backend les re-soumetttra lors de la prochaine action utilisateur ou du prochain cycle de Beat.

---

### Frontend ne se charge pas (page blanche ou 502)

```bash
# Vérifier les logs Nginx
docker compose logs frontend

# Vérifier que le backend répond
curl -f http://localhost:8000/api/v1/health/

# Reconstruire le frontend si le code a changé
docker compose build frontend
docker compose up -d --no-deps frontend
```

---

## 6. Commandes utiles

```bash
# Exécuter une commande Django dans le conteneur backend
docker compose exec backend python manage.py shell
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser

# Inspecter les files Celery
docker compose exec redis redis-cli -n 0 llen celery

# Accéder à SQLPlus Oracle
docker compose exec oracle-db sqlplus IDP_APP@FREEPDB1

# Stats Celery en temps réel
docker compose exec celery-worker celery -A idp_backend inspect active
docker compose exec celery-worker celery -A idp_backend inspect reserved
docker compose exec celery-worker celery -A idp_backend inspect stats

# Voir les tâches planifiées de Beat
docker compose exec celery-beat celery -A idp_backend inspect scheduled
```
