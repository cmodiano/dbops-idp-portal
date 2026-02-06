# Story M.11: Nettoyage code FastAPI — suppression des références et mise à jour documentation

Status: backlog

## Story

As a développeur,
I want supprimer toutes les références à FastAPI dans le code et mettre à jour la documentation pour refléter que Django est le backend unique,
So que le codebase soit cohérent, sans dette documentaire, et que les nouveaux contributeurs ne soient plus induits en erreur par des mentions de FastAPI.

## Contexte

**Contexte Epic M — Migration FastAPI vers Django REST :**

L'Epic M a migré le backend vers Django/DRF. La story M.10 a défini la stratégie de bascule et archivé le code FastAPI (branche `legacy/fastapi-final`). Le backend Django est désormais le backend de production.

Il reste cependant :
- Des commentaires et docstrings dans le code Django faisant référence à FastAPI (« matches FastAPI », « FastAPI format », etc.)
- Des documents (README, docs/) mentionnant encore FastAPI comme option ou référence
- Possiblement le répertoire `idp-portal/backend/` (code FastAPI) toujours présent dans la branche principale

Cette story finalise le ménage : documentation alignée sur la cible, code sans référence à FastAPI.

## Acceptance Criteria

### AC1 — Documentation mise à jour

**Given** la documentation technique du portail (README, docs/, planning-artifacts),
**When** on la consulte,
**Then** elle décrit uniquement Django/DRF comme backend
**And** les mentions de FastAPI sont supprimées ou reformulées en contexte historique (ex. « anciennement FastAPI » uniquement si pertinent)
**And** les guides de démarrage, d’architecture et de contribution ne font plus référence à FastAPI comme option active

### AC2 — Code Django sans référence à FastAPI

**Given** le code source du backend Django (`idp-portal/django_backend/`),
**When** on recherche « FastAPI » ou « fastapi » dans les fichiers,
**Then** aucune occurrence ne subsiste dans les commentaires, docstrings, ou chaînes de caractères
**And** les formulations sont adaptées (ex. « format d’erreur DRF » au lieu de « format FastAPI »)

### AC3 — Répertoire FastAPI traité

**Given** le répertoire `idp-portal/backend/` (code FastAPI legacy),
**When** la story est terminée,
**Then** soit le répertoire est supprimé de la branche principale (le code restant dans `legacy/fastapi-final`),
**Or** une note claire dans le README indique que ce répertoire est archivé et non utilisé en production
**And** les scripts CI/CD, Makefile, ou scripts de démarrage ne pointent plus vers le backend FastAPI

### AC4 — Cohérence des artefacts BMAD

**Given** les artefacts d’implémentation (_bmad-output) et de planification,
**When** ils mentionnent le backend,
**Then** la terminologie est alignée (Django, DRF) sauf dans les stories historiques Epic M où le contexte « migration depuis FastAPI » reste explicite

## Tasks / Subtasks

### Task 1: Recenser et mettre à jour la documentation (AC1)

- [ ] Subtask 1.1: Identifier tous les fichiers de documentation mentionnant FastAPI
  - README.md, docs/*.md, docs/backend/*.md, docs/frontend/*.md
  - Fichiers dans _bmad-output/implementation-artifacts et planning-artifacts (sélectivement)
- [ ] Subtask 1.2: Mettre à jour les guides de démarrage
  - Supprimer ou remplacer les instructions `fastapi dev`, `uvicorn`, etc.
  - Documenter uniquement `python manage.py runserver` (Django)
- [ ] Subtask 1.3: Mettre à jour les diagrammes et descriptions d’architecture
  - Backend = Django + DRF uniquement
  - Conserver une section « Historique migration » si utile
- [ ] Subtask 1.4: Mettre à jour requirements.txt, pyproject.toml, .env templates
  - Vérifier qu’aucune dépendance FastAPI n’est requise pour le backend actif

### Task 2: Supprimer les références FastAPI du code Django (AC2)

- [ ] Subtask 2.1: Parcourir `django_backend/` et lister les occurrences
  - grep -r "FastAPI\|fastapi" idp-portal/django_backend/
- [ ] Subtask 2.2: Remplacer les commentaires « matches FastAPI » par « DRF » ou formulation neutre
  - Exemples : catalog/views.py, catalog/serializers.py, core/exceptions.py, core/rbac.py
  - executions/views.py, dashboard/views.py, idp_auth/views.py, integrations/models.py
- [ ] Subtask 2.3: Mettre à jour les docstrings et commentaires
  - « format d’erreur DRF » au lieu de « format FastAPI »
  - « Routes DRF » au lieu de « routes FastAPI »
- [ ] Subtask 2.4: Vérifier requirements.txt et settings.py
  - Supprimer les mentions « same as FastAPI », « mirrors FastAPI », etc.

### Task 3: Traiter le répertoire backend FastAPI (AC3)

- [ ] Subtask 3.1: Décider de la stratégie (suppression vs archivage in-repo)
  - Option A: Supprimer `idp-portal/backend/` de la branche principale (recommandé si legacy/fastapi-final existe)
  - Option B: Garder avec README explicite « ARCHIVED - not used »
- [ ] Subtask 3.2: Mettre à jour CI/CD et scripts
  - Vérifier .github/workflows/* — aucun job ne lance FastAPI
  - Vérifier scripts/deploy.sh, docker-compose, Makefile
- [ ] Subtask 3.3: Mettre à jour README principal
  - Structure du projet : `django_backend/` comme backend unique
  - Si backend/ supprimé : mentionner que le code legacy est dans `legacy/fastapi-final`

### Task 4: Vérifier la cohérence des artefacts BMAD (AC4)

- [ ] Subtask 4.1: Mettre à jour sprint-status.yaml et docs de synthèse
  - Formulations « backend Django » systématiques
- [ ] Subtask 4.2: Conserver le contexte historique Epic M dans les stories M.1–M.10
  - Ne pas réécrire l’historique des stories de migration
  - S’assurer que les nouveaux documents ne réintroduisent pas FastAPI comme option active

## Critères de validation

- [ ] `grep -ri "fastapi" idp-portal/django_backend/` retourne 0 résultat
- [ ] Documentation lue par un nouveau développeur ne mentionne pas FastAPI comme backend actif
- [ ] Tests backend Django passent (aucune régression)

## Références

- [Source: _bmad-output/planning-artifacts/epics.md#Epic M] — Contexte Epic M Migration FastAPI → Django
- [Source: _bmad-output/implementation-artifacts/m-10-strategie-bascule-et-decommissionnement-fastapi.md] — Story M.10 (archivage FastAPI)
- [Source: docs/fastapi-to-django-migration.md] — Récapitulatif migration (contexte historique)
