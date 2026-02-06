# Assessment Qualité du Code — IDP Portal

**Date :** 6 février 2026  
**Portée :** Analyse complète du dépôt `idp-portal`

---

## 1. Vue d'ensemble du projet

| Composant | Technologie | Lignes de code (hors tests) | Fichiers |
|---|---|---|---|
| Django Backend | Python 3.12 / Django 5.x / DRF | ~17 000 | ~90 .py |
| FastAPI Backend (legacy) | Python 3.11 / FastAPI / Pydantic | ~30 000 | ~65 .py |
| Frontend | React 19 / TypeScript 5.9 / Ant Design 6 / Vite 7 | ~25 000 | ~200 .ts/.tsx |
| Base de données | Oracle 23ai / Flyway migrations | ~1 500 | 51 .sql |
| **Total** | | **~75 000** | **~400+** |

Le projet est un **portail interne (IDP)** de gestion d'opérations de bases de données (DBA/DBOPS) avec catalogue d'actions, exécution de workflows, RBAC par profils, audit trail, et intégrations externes (AAP, ServiceNow, Vault).

---

## 2. Score global

| Catégorie | Note | Commentaire |
|---|:---:|---|
| **Architecture** | B+ | Séparation claire des couches, mais deux backends coexistent |
| **Qualité du code backend** | B+ | Bien structuré, conventions Django/DRF respectées |
| **Qualité du code frontend** | B | Composants bien organisés mais certains trop volumineux |
| **Tests** | A- | Excellent ratio de couverture, tests frontend et backend |
| **Sécurité** | B | Bonnes pratiques en place, quelques points d'attention |
| **DevOps / CI** | B | Pipeline CI présent, déploiement documenté |
| **Documentation** | B+ | Bonne documentation inline et doc séparée |
| **Maintenabilité** | B | Code lisible mais dette technique identifiée |

**Score global : B+ (Bon)**

---

## 3. Points forts

### 3.1 Architecture bien pensée

- **Séparation des couches** claire : Models → Services → Views/Serializers dans le Django backend. Le pattern Service Layer est correctement utilisé pour encapsuler la logique métier.
- **Custom QuerySet / Manager** sur les modèles Django (`ActionQuerySet`, `ActionManager`) pour encapsuler les requêtes récurrentes, évitant les N+1 queries (`with_tags()`, `with_creator()`).
- **Transactions atomiques** (`@transaction.atomic`) systématiquement utilisées dans les services pour les opérations d'écriture.
- **Audit trail** intégré à toutes les opérations critiques via `AuditService`.

### 3.2 Gestion des erreurs exemplaire

- **Exception handler personnalisé** (`custom_exception_handler`) qui normalise toutes les erreurs au format FastAPI `{error: {code, message, details}}`, assurant une API cohérente.
- **Hiérarchie d'exceptions métier** bien définie : `NotFoundError`, `BadRequestError`, `InvalidStateError`, `ForbiddenError`, `UnauthorizedError`.
- **Masquage des erreurs internes** pour le client (500 → message générique) tout en loggant les détails complets côté serveur.

### 3.3 Observabilité de qualité

- **Structured logging** avec `structlog` sur tout le backend Django.
- **Correlation ID** propagé via middleware (`CorrelationIdMiddleware`) et inclus dans tous les logs et réponses HTTP.
- **Request/Response logging** avec durée, IP, user agent, et log level adapté au status code (INFO pour 2xx, WARNING pour 4xx, ERROR pour 5xx).

### 3.4 Excellente couverture de tests

- **44 fichiers de tests backend** couvrant unit, intégration, edge cases, validation, RBAC, performance.
- **82+ fichiers de tests frontend** (Vitest + Testing Library) couvrant composants, services, hooks, contextes, utilitaires.
- **Fixtures factory-based** (`factory-boy`) dans le backend pour des tests maintenables.
- **CI/CD** avec seuil de couverture à 80% (`--cov-fail-under=80`).
- Faible nombre de `TODO`/`FIXME` dans le code (6 backend, 3 frontend).

### 3.5 Frontend bien architecturé

- **Lazy loading** des pages avec `React.lazy()` et `Suspense`.
- **Contextes React** bien isolés (`AuthContext`, `ThemeContext`, `DashboardContext`).
- **Custom hooks** réutilisables (`useDebounce`, `useUrlFilters`, `useExecutionFilters`, etc.).
- **TypeScript strict** avec types bien définis dans `types/api.ts` et `types/common.ts`.
- **Accessibilité** : `aria-labels`, `aria-live`, navigation clavier, focus management.

### 3.6 Sécurité

- **Security headers middleware** (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Cache-Control).
- **RBAC multi-niveaux** : profils utilisateur, permissions par action/tag, filtrage par environnement.
- **JWT avec refresh token** httpOnly, et intercepteur 401 avec retry automatique.
- **SAML SSO** intégré avec bypass dev conditionnel.
- **Outils de sécurité** dans les dépendances : `bandit`, `pip-audit`, `detect-secrets`.

---

## 4. Points d'amélioration

### 4.1 CRITIQUE — Double backend FastAPI + Django (dette technique majeure)

Le dépôt contient **deux backends complets** :
- `backend/` : FastAPI (47 823 LOC) — l'ancien
- `django_backend/` : Django/DRF (27 066 LOC) — le nouveau

Le fichier `MIGRATION_STRATEGY.md` confirme une migration en cours. Cette coexistence représente :
- **~48 000 lignes de code legacy** à maintenir ou supprimer
- Risque de divergence de comportement entre les deux APIs
- Confusion pour les nouveaux développeurs
- Duplication de logique métier (services, RBAC, validation)

**Recommandation :** Accélérer le décommissionnement du backend FastAPI et supprimer le code une fois la migration validée.

### 4.2 HAUTE — Composants frontend trop volumineux

Plusieurs fichiers dépassent les bonnes pratiques de taille :

| Fichier | Lignes | Recommandation |
|---|---|---|
| `ExecutionWizard.tsx` | **1 661** | Extraire chaque step en composant, hook pour la logique |
| `executions/views.py` | **1 140** | Séparer en ViewSets dédiés par ressource |
| `ScheduledExecutionsPage.tsx` | 692 | Extraire composants tableau et filtres |
| `ExecutionTimeline.tsx` | 664 | Extraire les sous-composants (step card, status badge) |
| `ExecutionsPage.tsx` | 650 | Extraire la logique dans un hook dédié |
| `catalog/views.py` | 749 | Les fonctions helper pourraient être dans un module séparé |

**Recommandation :** Refactoriser les fichiers > 500 lignes. Adopter une règle de max ~300-400 lignes par fichier composant.

### 4.3 HAUTE — API client avec duplication significative

Le fichier `api_client.ts` contient **4 fonctions** (`apiFetch`, `apiFetchRaw`, `apiFetchBlob`, `apiPostFormData`) qui dupliquent toutes :
- La logique d'authentification
- L'intercepteur 401 avec retry
- Le parsing d'erreurs

**Recommandation :** Extraire un wrapper HTTP commun qui gère auth, retry et error parsing, puis exposer des méthodes spécifiques par-dessus.

### 4.4 MOYENNE — JSON dans des champs CLOB (modèle Action)

Le modèle `Action` stocke du JSON dans des `TextField` (CLOB Oracle) avec des getter/setter manuels (`get_parameters_schema()`, `set_parameters_schema()`, etc.). Cela représente :
- **7 paires getter/setter identiques** dans `models.py` (duplication de pattern)
- Pas de validation JSON au niveau du modèle
- Pas de JSONField (incompatible Oracle, mais un custom field serait bienvenu)

**Recommandation :** Créer un `OracleJSONField` custom ou un descripteur Python pour éliminer la duplication des getter/setter.

### 4.5 MOYENNE — Broad exception catches

14 occurrences de `except Exception` ou `except:` dans le Django backend. Certains sont justifiés (fallback graceful), mais d'autres masquent potentiellement des bugs :

```python
# catalog/views.py - trop large, masque les erreurs ProfileService
except Exception:
    return None
```

**Recommandation :** Restreindre les `except` aux exceptions spécifiques attendues. Logger les exceptions inattendues.

### 4.6 MOYENNE — `console.log/error/warn` dans le frontend

21 occurrences de `console.log/error/warn` dans le code frontend de production. Ces sorties ne sont pas structurées et ne peuvent pas être facilement filtrées ou monitorées.

**Recommandation :** Créer un service de logging frontend avec niveaux (debug/info/warn/error) et possibilité de les envoyer au backend en production. Utiliser un linter rule pour interdire `console.log` direct.

### 4.7 BASSE — Secrets hardcodés dans la configuration

- `settings.py` : `SECRET_KEY` par défaut en dur (`django-insecure-bvc0qsxvq0...`)
- `settings.py` : `JWT_SECRET_KEY = 'change-me-in-production'`
- `docker-compose.yml` : `ORACLE_PWD=Oracle123!`

Bien que commentés comme "development only", ces valeurs pourraient fuiter en production si les variables d'environnement ne sont pas configurées.

**Recommandation :** Faire échouer le démarrage si `SECRET_KEY` ou `JWT_SECRET_KEY` ne sont pas définis en environnement non-dev. Utiliser `detect-secrets` dans le CI.

### 4.8 BASSE — Manque de pyproject.toml pour le Django backend

Le Django backend utilise `requirements.txt` avec des ranges de versions (`>=X,<Y`), tandis que le FastAPI backend a un `pyproject.toml` structuré. Le manque de fichier de lock signifie que les builds ne sont pas reproductibles.

**Recommandation :** Migrer vers `pyproject.toml` + `pip-tools` ou `poetry` pour le lock des dépendances.

### 4.9 BASSE — Type checking advisory only

Le CI exécute `mypy` avec `continue-on-error: true`, ce qui signifie que les erreurs de typage ne bloquent pas le merge. Le fichier `pyproject.toml` du FastAPI backend a `strict = false`.

**Recommandation :** Progressivement renforcer le type checking jusqu'à le rendre bloquant.

### 4.10 BASSE — Pas de Dockerfile dans le repo

Malgré un `docker-compose.yml` (pour la BDD Oracle uniquement), il n'y a pas de `Dockerfile` pour le backend ou le frontend. Le déploiement semble reposer sur des scripts systemd et Nginx manuels (`deployment/idp-django.service`, `nginx/`).

**Recommandation :** Conteneuriser les applications (backend + frontend) pour des déploiements plus reproductibles et portables.

---

## 5. Métriques de complexité

### Backend Django — Fichiers par module

| Module | Fichiers (hors tests) | LOC | Tests | LOC Tests |
|---|:---:|:---:|:---:|:---:|
| catalog | 8 | ~2 500 | 8 | ~2 800 |
| executions | 7 | ~3 000 | 5 | ~2 500 |
| profiles | 7 | ~1 500 | 5 | ~1 200 |
| idp_auth | 8 | ~1 400 | 7 | ~1 500 |
| core | 9 | ~1 000 | 4 | ~800 |
| integrations | 7 | ~900 | 4 | ~600 |
| inventory | 5 | ~800 | 3 | ~1 200 |
| **Total** | **~55** | **~11 100** | **~36** | **~10 600** |

**Ratio tests/code : ~0.95** (excellent)

### Frontend — Répartition

| Catégorie | Fichiers | LOC |
|---|:---:|:---:|
| Composants | 75 (dont 57 tests) | ~20 000 |
| Pages | 14 (dont 7 tests) | ~6 100 |
| Services | 16 (dont 6 tests) | ~3 000 |
| Hooks | 18 (dont 6 tests) | ~2 500 |
| Types | 2 | ~1 000 |
| Utils | 18 (dont 5 tests) | ~1 500 |
| **Total** | **~143** | **~34 100** |

---

## 6. Conformité aux bonnes pratiques

| Pratique | Status | Notes |
|---|:---:|---|
| Linter Python (ruff) | ✅ | Configuré dans CI |
| Linter TypeScript (ESLint) | ✅ | Configuré avec typescript-eslint |
| Type checking Python (mypy) | ⚠️ | Advisory only (continue-on-error) |
| Type checking TypeScript | ✅ | Build inclut `tsc -b` |
| Tests unitaires | ✅ | pytest + vitest |
| Tests d'intégration | ✅ | pytest avec marqueurs dédiés |
| CI/CD | ✅ | GitHub Actions (tests, lint, type-check) |
| Structured logging | ✅ | structlog sur tout le backend |
| Error handling cohérent | ✅ | Format unifié FastAPI-compatible |
| RBAC | ✅ | Multi-niveau (profils, actions, tags, envs) |
| Audit trail | ✅ | Toutes opérations critiques loggées |
| DB migrations versionnées | ✅ | Flyway V001-V048 |
| Security headers | ✅ | Middleware dédié |
| CORS configuré | ✅ | Paramétrable par env |
| Input validation | ✅ | DRF serializers + validation custom |
| Pagination | ✅ | Backend et frontend |
| Caching | ✅ | TTLCache en mémoire (5 min) |
| Code documentation | ✅ | Docstrings Python, JSDoc TS, docs/ |
| Dependency security scan | ✅ | bandit, pip-audit, detect-secrets |
| Lock file dépendances | ❌ | Pas de pip.lock / poetry.lock |
| Containerisation | ❌ | Pas de Dockerfile applicatif |
| Feature flags | ❌ | Pas de système de feature flags |
| Rate limiting API | ❌ | Non implémenté |
| API versioning | ⚠️ | `/api/v1/` en dur, pas de stratégie v2 |

---

## 7. Recommandations prioritaires

### Court terme (1-2 sprints)

1. **Refactoriser `ExecutionWizard.tsx`** (1 661 lignes) en composants et hooks distincts
2. **Extraire un HTTP wrapper** dans `api_client.ts` pour éliminer la duplication
3. **Créer un `OracleJSONField`** custom pour le modèle Action
4. **Restreindre les `except Exception`** aux exceptions spécifiques

### Moyen terme (1-2 mois)

5. **Finaliser le décommissionnement FastAPI** et supprimer le dossier `backend/`
6. **Ajouter un Dockerfile** pour backend et frontend
7. **Migrer vers `pyproject.toml` + lockfile** pour le Django backend
8. **Remplacer `console.log`** par un service de logging frontend
9. **Rendre mypy bloquant** dans le CI (progressivement)

### Long terme (3+ mois)

10. **Implémenter du rate limiting** sur les endpoints publics
11. **Ajouter un système de feature flags** pour les déploiements progressifs
12. **Mettre en place du monitoring applicatif** (APM, alertes)
13. **Préparer une stratégie de versioning API** pour v2

---

## 8. Conclusion

Le codebase de l'IDP Portal est de **bonne qualité générale** (B+). L'architecture est solide, les tests sont nombreux et bien structurés, l'observabilité et la sécurité sont bien pensées. Les principales axes d'amélioration concernent la **dette technique du double backend** (la plus urgente), la **taille de certains composants**, et quelques **patterns de code dupliqué** facilement refactorisables. Le projet est dans un bon état pour une application en développement actif avec de nombreuses stories livrées.
