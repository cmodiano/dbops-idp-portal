# Production Secrets Checklist (Story 17.5)

## Pre-Deployment Validation

### Step 1: Generate Secrets

```bash
# Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# JWT SECRET_KEY (minimum 32 caracteres aleatoires)
openssl rand -base64 32
```

### Step 2: Configure Environment File

```bash
# Copier template
cp django_backend/.env.production.template /etc/idp/django.env

# Remplacer placeholders
vi /etc/idp/django.env
```

### Step 3: Validate Configuration

```bash
# Verifier aucun placeholder restant
grep -E "CHANGE_|<[A-Z_]+>|TODO:" /etc/idp/django.env
# Doit retourner vide

# Verifier variables critiques presentes
grep -E "^SECRET_KEY=|^JWT_SECRET_KEY=|^ORACLE_PASSWORD=" /etc/idp/django.env
# Doit afficher 3 lignes avec valeurs non-vides
```

### Step 4: Test Startup

```bash
# Charger environnement
export $(cat /etc/idp/django.env | grep -v '^#' | xargs)

# Verifier configuration Django
python manage.py check --deploy

# Demarrer application
python manage.py runserver
# Doit demarrer sans erreur et logger: "Configuration des secrets validee"
```

## Post-Deployment Validation

### Health Check

```bash
curl http://localhost:8000/api/v1/health
# Expected: {"status": "healthy", "oracle": "connected", ...}
```

### Security Test

```bash
# Verifier AUTH_DEV_BYPASS desactive
grep "AUTH_DEV_BYPASS=true" /etc/idp/django.env
# Doit retourner vide

# Verifier APP_ENV production
grep "APP_ENV=production" /etc/idp/django.env
# Doit retourner la ligne
```

## Troubleshooting

### Error: "SECRET_KEY is not set"
- Cause: Variable SECRET_KEY absente ou vide
- Fix: `export SECRET_KEY=$(python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")`

### Error: "SECRET_KEY contains insecure default value"
- Cause: SECRET_KEY commence par `django-insecure-`
- Fix: Generer une nouvelle cle (voir Step 1)

### Error: "JWT_SECRET_KEY contains unreplaced placeholder"
- Cause: Placeholder `CHANGE_JWT_SECRET` non remplace
- Fix: Remplacer par valeur generee avec `openssl rand -base64 32`

### Error: "SAML_SP_CERT_PATH required"
- Cause: Certificat SAML manquant en production avec AUTH_DEV_BYPASS=false
- Fix: Configurer chemins vers certificats ou activer AUTH_DEV_BYPASS=true (non recommande en prod)
