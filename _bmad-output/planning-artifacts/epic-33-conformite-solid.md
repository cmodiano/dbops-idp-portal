# Epic 33 : Conformité SOLID — Corrections des écarts

**En tant que** mainteneur du code,  
**je veux** que la codebase respecte les principes SOLID (SRP, OCP, LSP, ISP, DIP),  
**afin de** faciliter l'évolution, les tests et l'ajout de nouvelles plateformes/intégrations sans modifier le code existant.

---

## Contexte

Un audit SOLID a été réalisé (voir `planning-artifacts/solid-audit-report.md`). Les écarts principaux :

- **OCP** : Factories `adapters/__init__.py` et `services/__init__.py` utilisent des chaînes if/elif — ajouter une plateforme impose de modifier le fichier.
- **DIP** : Services instanciés directement dans les vues et runtimes (`ProfileService()`, `ExecutionService()`, etc.) — pas d'injection, tests difficiles.
- **SRP** : `executions/tasks.py` (~1 580 LOC) et `catalog/views.py` (~1 100 LOC) mélangent plusieurs responsabilités ; `ActionForm`/`ActionWizard` sont volumineux.

---

## Stories

### Story 33.1 : OCP — Registry pattern pour adapters et services

**En tant que** développeur,  
**je veux** que les adapters et services s'enregistrent via un registry,  
**afin de** pouvoir ajouter une nouvelle plateforme ou un nouveau service sans modifier `adapters/__init__.py` ni `services/__init__.py`.

**Acceptance Criteria:**

- **Given** une nouvelle plateforme (ex. GitLab CI) ou un nouveau service
- **When** on crée un adapter/service et on l'enregistre dans le registry
- **Then** `get_platform_adapter()` et `get_service_client()` le découvrent automatiquement
- **And** aucun if/elif n'est ajouté dans les factories — le registry est la seule source de vérité
- **And** la rétrocompatibilité est assurée : les adapters/services existants continuent de fonctionner
- **And** des tests valident l'enregistrement et la résolution

**Fichiers :** `adapters/__init__.py`, `services/__init__.py`, création de `adapters/registry.py` et `services/registry.py` (ou module partagé).

---

### Story 33.2 : SRP — Découper executions/tasks.py

**En tant que** mainteneur,  
**je veux** que `executions/tasks.py` soit découpé en modules cohérents,  
**afin de** réduire la taille du fichier et isoler les responsabilités (retry, polling par plateforme, gate evaluation).

**Acceptance Criteria:**

- **Given** le fichier `executions/tasks.py` actuel (~1 580 LOC)
- **Then** il est découpé en au moins 3 modules (ex. `tasks/retry.py`, `tasks/polling.py`, `tasks/gates.py`) ou par domaine (retry + gates dans un module, polling dans un autre)
- **And** les tâches Celery restent importables depuis `executions.tasks` (ré-exports) pour ne pas casser les références
- **And** chaque module a une responsabilité claire documentée
- **And** les tests existants passent sans modification des imports (ou avec des imports mis à jour de façon minimale)

**Fichiers :** `executions/tasks.py` → `executions/tasks/` (package avec `__init__.py` ré-exportant les tâches).

---

### Story 33.3 : SRP — Découper catalog/views.py

**En tant que** mainteneur,  
**je veux** que les ViewSets du catalogue soient dans des fichiers séparés,  
**afin de** réduire la taille de `catalog/views.py` et clarifier les responsabilités.

**Acceptance Criteria:**

- **Given** `catalog/views.py` (~1 100 LOC) contenant ActionViewSet, CatalogViewSet, tags, remediation, business rules
- **Then** les ViewSets sont extraits dans des modules dédiés (ex. `catalog/views/action_views.py`, `catalog/views/catalog_views.py`, `catalog/views/tags_views.py`)
- **And** les routes (urls) restent inchangées ou sont mises à jour de façon minimale
- **And** chaque fichier de vues a une responsabilité claire
- **And** les tests passent

**Fichiers :** `catalog/views.py` → `catalog/views/` (package).

---

### Story 33.4 : DIP — Injection de dépendances pour les services principaux

**En tant que** développeur,  
**je veux** que les services (ProfileService, ExecutionService, CatalogService, InventoryService) soient injectables,  
**afin de** pouvoir les mocker facilement dans les tests et les remplacer sans modifier les consommateurs.

**Acceptance Criteria:**

- **Given** les vues et runtimes qui instancient directement `ProfileService()`, `ExecutionService()`, etc.
- **Then** un mécanisme d'injection est introduit (option A : paramètre optionnel dans les constructeurs avec fallback sur l'instanciation par défaut ; option B : factory/callable injecté ; option C : framework DI léger si pertinent)
- **And** au minimum les vues principales (`profiles/views.py`, `executions/views/`, `catalog/views.py`, `inventory/views.py`) et `ContainerWorkflowRuntime` acceptent des services injectés (ou utilisent une factory configurable)
- **And** les tests peuvent injecter des mocks sans monkey-patching
- **And** la rétrocompatibilité est assurée : si aucun service n'est injecté, l'instanciation par défaut est utilisée
- **And** la documentation (ADR ou README) décrit le pattern d'injection adopté

**Fichiers :** vues, `ContainerWorkflowRuntime`, éventuellement `core/di.py` ou module dédié.

---

### Story 33.5 : SRP — Réduire ActionForm et ActionWizard (extraction de sous-composants)

**En tant que** mainteneur frontend,  
**je veux** que `ActionForm.tsx` et `ActionWizard.tsx` soient découpés en sous-composants réutilisables,  
**afin de** réduire la complexité et améliorer la maintenabilité.

**Acceptance Criteria:**

- **Given** `ActionForm.tsx` (765 LOC) et `ActionWizard.tsx` (943 LOC)
- **Then** au moins 3 blocs logiques sont extraits en composants dédiés (ex. `ImpactRulesEditor`, `ChangeTypeConfigPanel`, `RemediationRulesSection`, `StepsEditor` si pas déjà extrait)
- **And** chaque sous-composant a une responsabilité claire et des props bien définies
- **And** les tests existants passent ; de nouveaux tests unitaires couvrent les sous-composants extraits si pertinent
- **And** la taille des fichiers parents est réduite d'au moins 30 %

**Fichiers :** `components/admin/ActionForm.tsx`, `components/admin/ActionWizard.tsx`, nouveaux composants dans `components/admin/`.

---

### Story 33.6 : Documentation et checklist SOLID

**En tant que** nouvel arrivant ou relecteur,  
**je veux** une documentation et une checklist pour maintenir la conformité SOLID,  
**afin de** éviter la réintroduction d'écarts lors des évolutions.

**Acceptance Criteria:**

- **Given** le rapport d'audit `solid-audit-report.md` et les corrections des stories 33.1 à 33.5
- **Then** un document `docs/solid-guidelines.md` (ou section dans CONTRIBUTING.md) décrit :
  - Les principes SOLID appliqués au projet
  - Les patterns à utiliser (registry, injection, découpage)
  - Les anti-patterns à éviter (if/elif pour dispatch, instanciation directe dans les vues)
- **And** une checklist (ou section dans le template de PR) rappelle les points à vérifier avant merge
- **And** le rapport d'audit est mis à jour pour refléter l'état après corrections

**Fichiers :** `docs/solid-guidelines.md`, `CONTRIBUTING.md`, `solid-audit-report.md`.

---

## Références

- Rapport d'audit : `planning-artifacts/solid-audit-report.md`
- Principes SOLID : Robert C. Martin (Clean Architecture, Agile Software Development)
