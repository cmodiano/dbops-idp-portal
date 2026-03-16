# Configuration sécurisée des secrets (Story 30.1)

## Fail-fast : comportement au démarrage

Le backend Django **refuse de démarrer** si les secrets critiques sont absents ou vides.
L'erreur `ImproperlyConfigured` est levée au chargement de `settings.py` (pas au runtime).

### Secrets requis

| Variable | Description | Génération |
|----------|-------------|------------|
| `SECRET_KEY` | Clé secrète Django (sessions, CSRF, signatures) | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `JWT_SECRET_KEY` | Clé de signature JWT (authentification API) | `openssl rand -hex 32` |

**Important :** `SECRET_KEY` et `JWT_SECRET_KEY` doivent être **différentes** (défense en profondeur).

### Mode DEBUG

`DEBUG` est **`False` par défaut** (opt-in explicite requis).

- Production : ne pas définir `DEBUG` ou définir `DEBUG=False`
- Développement : définir `DEBUG=True` dans `.env`

## Configuration par environnement

### Développement local

```bash
cp .env.example .env
# Modifier les valeurs générées dans .env
```

Le fichier `.env.example` contient des valeurs d'exemple (non sécurisées) pour le développement local.

### Production

```bash
cp .env.production.template /etc/idp/django.env
# Remplacer TOUS les placeholders CHANGE_* par des valeurs réelles
# Vérifier : grep -n "CHANGE_" /etc/idp/django.env (doit être vide)
```

### Tests (CI/CD)

Les tests utilisent `test_settings.py` qui fournit des secrets via `os.environ.setdefault()` **avant** l'import de `settings.py`. Aucune configuration manuelle requise.

## Validation supplémentaire

`startup_checks.py` (Story 17.5) effectue des vérifications supplémentaires au démarrage :
- Vérifie que `SECRET_KEY` n'est pas une valeur par défaut connue
- Vérifie que `JWT_SECRET_KEY` n'est pas vide
- Émet des warnings pour les configurations non sécurisées en mode dev

Ces vérifications sont conservées comme garde-fou supplémentaire au-delà du fail-fast.
