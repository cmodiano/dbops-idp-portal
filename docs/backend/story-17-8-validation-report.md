# Rapport de Validation - Story 17.8

**Date:** 2026-02-06
**Story:** 17-8-pyproject-toml-lockfile-django-backend

## Dépendances migrées

### Runtime (production) — 13 dépendances directes → 33 packages verrouillés

| Dépendance | Contrainte | Version verrouillée |
|------------|-----------|-------------------|
| cachetools | >=5.3.0 | 7.0.0 |
| croniter | >=6.0.0 | 6.0.0 |
| Django | >=5.1.0,<6.0 | 5.2.11 |
| django-cors-headers | >=4.3.0 | 4.9.0 |
| djangorestframework | >=3.15.0 | 3.16.1 |
| gunicorn | >=22.0.0 | 25.0.2 |
| oracledb | >=3.4.1 | 3.4.2 |
| python-dotenv | >=1.0.0 | 1.2.1 |
| python-jose[cryptography] | >=3.3.0 | 3.5.0 |
| python3-saml | >=1.16.0 | 1.16.0 |
| PyYAML | >=6.0.0 | 6.0.3 |
| requests | >=2.32.5 | 2.32.5 |
| structlog | >=24.1.0 | 25.5.0 |

### Dev (runtime + outils) — 15 dépendances dev supplémentaires → 79 packages verrouillés

Outils de développement inclus : pytest, ruff, mypy, bandit, pip-audit, detect-secrets, coverage, factory-boy, Faker, httpx, pytest-benchmark, pytest-cov, pytest-django, pytest-mock, pytest-asyncio.

## Lockfiles générés

- `requirements.lock` : 33 packages (runtime uniquement)
- `requirements-dev.lock` : 79 packages (runtime + dev)

## Tests de reproductibilité

Deux générations successives de `requirements.lock` produisent des versions strictement identiques (seule différence : le nom du fichier dans le commentaire d'en-tête uv).

## Scan de vulnérabilités (pip-audit)

| Package | Version | CVE | Sévérité | Statut |
|---------|---------|-----|----------|--------|
| ecdsa | 0.19.1 | CVE-2024-23342 | Medium (timing attack) | Pré-existant, pas de fix disponible. ECDSA signature verification non affectée. |

**Résultat :** 0 vulnérabilités HIGH/CRITICAL. 1 MEDIUM pré-existante sans correctif.

## Tests Django

- **512 tests passent** avec les lockfiles
- **127 échecs pré-existants** (non liés aux changements 17.8 — problèmes User model, reference tests)
- **Aucune régression introduite** par la migration pyproject.toml/lockfiles

## Conclusion

La migration vers `pyproject.toml` + lockfiles est validée. Les builds sont désormais reproductibles et les dépendances traçables pour audit de sécurité.
