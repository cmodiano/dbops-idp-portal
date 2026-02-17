# Story 25.4 : Overrides par environnement (change_type_config enrichi)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want configurer par environnement (prod, staging, dev) des exigences différentes : ticket ServiceNow requis, plage de maintenance requise, opération autorisée ou interdite,
So que la gouvernance soit adaptée à chaque environnement sans dupliquer les actions.

## Acceptance Criteria

**AC1: Lecture des flags par environnement à la validation / exécution**

**Given** une action avec un champ change_type_config (ou équivalent) par environnement
**When** le backend valide ou exécute une exécution pour un environnement donné
**Then** les flags suivants sont lus depuis la config de cet environnement : requires_maintenance_window, requires_approval, allowed (booléen)
**And** si allowed est false pour l'environnement cible, la soumission est refusée avec un message explicite
**And** les règles d'ouverture de changement ServiceNow et de vérification de plage de maintenance s'appuient sur requires_maintenance_window et requires_approval

**AC2: Interface admin et validation backend du JSON enrichi**

**Given** l'éditeur admin des actions (ou des règles d'impact)
**When** on configure les overrides par environnement
**Then** l'interface permet de définir pour chaque environnement : change_type, template_id (si applicable), requires_maintenance_window, requires_approval, allowed
**And** la validation côté backend rejette les valeurs invalides et persiste le JSON enrichi

**AC3: Pas de nouveau schéma de table**

**And** aucun nouveau schéma de table n'est requis : le champ Oracle/JSON existant (change_type_config ou équivalent) est étendu
**And** la logique de validation dans executions/utils.py (ou équivalent) utilise ces flags pour accepter ou refuser la soumission

## Tasks / Subtasks

- [x] Task 1: Étendre le schéma et la validation du change_type_config (AC: 1, 2, 3)
  - [x] 1.1: Documenter la structure JSON enrichie par environnement (change_type, template_id, required, change_model_code, requires_maintenance_window, requires_approval, allowed)
  - [x] 1.2: Ajouter validation backend (catalog/serializers ou validators) : allowed booléen, requires_maintenance_window/requires_approval booléens optionnels
  - [x] 1.3: Conserver rétrocompatibilité : clés existantes (required, change_model_code) inchangées ; absence de allowed = traité comme true
  - [x] 1.4: Si required=true pour un environnement, exiger change_model_code non vide et alphanumerique (comportement existant à confirmer/renforcer)

- [x] Task 2: Utiliser les flags dans la validation à la soumission (AC: 1, 3)
  - [x] 2.1: Dans executions/views.py (création d'exécution), après _get_env_config_case_insensitive(change_type_config, env) : lire allowed, requires_maintenance_window, requires_approval
  - [x] 2.2: Si allowed === false pour l'environnement demandé : refuser la soumission avec BadRequestError (code explicite, message en français)
  - [x] 2.3: Stocker requires_maintenance_window et requires_approval dans parameters['_env_config'] pour usage downstream (ServiceNow, gate maintenance_window)
  - [x] 2.4: Ne pas créer de nouvelle table : tout repose sur Action.change_type_config (OracleJSONField)

- [x] Task 3: Adapter executions/utils.py si besoin (AC: 3)
  - [x] 3.1: Exposer une helper (ex: get_env_change_config) qui retourne le bloc config pour un env (déjà couvert par _get_env_config_case_insensitive) avec les nouveaux champs
  - [x] 3.2: S'assurer que la logique existante (required, change_model_code) reste inchangée et que les nouveaux flags sont simplement lus et propagés

- [x] Task 4: Interface admin — overrides par environnement (AC: 2)
  - [x] 4.1: Identifier le composant admin qui édite les règles d'impact / change type (éditeur visuel des règles d'impact ou formulaire action)
  - [x] 4.2: Ajouter pour chaque environnement les champs : requires_maintenance_window (bool), requires_approval (bool), allowed (bool) ; optionnellement change_type, template_id si pas déjà présents
  - [x] 4.3: Validation côté frontend : allowed booléen ; valeurs par défaut raisonnables (ex: allowed=true, requires_approval=false pour dev)
  - [x] 4.4: Soumission vers l'API catalog : envoyer change_type_config enrichi ; le backend valide et persiste (Task 1.2)

- [x] Task 5: Migration de données et compatibilité (AC: 3)
  - [x] 5.1: Pas de migration SQL des données obligatoire : le JSON existant reste valide (clés additionnelles optionnelles)
  - [x] 5.2: Si change_model_code existait au niveau action (legacy), documenter ou appliquer la migration de données déjà prévue en epics (reporter sur les environnements qui avaient pre_approved) — uniquement si pertinent pour ce projet
  - [x] 5.3: Documenter la structure dans docs/backend (ex: change-type-config.md ou section dans condition-gates / convergence)

- [x] Task 6: Tests (AC: tous)
  - [x] 6.1: Tests unitaires : _get_env_config_case_insensitive retourne requires_maintenance_window, requires_approval, allowed ; allowed=false → rejet soumission
  - [x] 6.2: Tests API : POST execution avec env dont allowed=false → 400 et message explicite
  - [x] 6.3: Tests API : POST execution avec env dont allowed=true et requires_approval=true → _env_config contient les flags
  - [x] 6.4: Tests validation catalog : change_type_config avec allowed booléen invalide (ex: chaîne) → erreur de validation
  - [x] 6.5: Tests rétrocompatibilité : change_type_config sans allowed → comportement comme allowed=true

## Dev Notes

### Contexte Epic 25 — Convergence DBOps → IDP Portal

Cette story implémente les **overrides par environnement** décrits dans `_bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md` (section 2).

**Dépendances :**
- Story 25.1 ✅ DONE : ExecutionTarget (utilisé pour cibles et env dérivé)
- Story 25.2 ✅ DONE : Condition Gates + statut WAITING
- Story 25.3 ✅ DONE : Tâche Celery Beat evaluate_waiting_gates
- **CETTE STORY** : Enrichir change_type_config et utiliser les flags à la soumission

**Ce qui existe déjà :**
- `Action.change_type_config` : OracleJSONField (catalog/models.py), structure par environnement avec `required`, `change_model_code`
- `executions/views.py` : lecture via `_get_env_config_case_insensitive(change_type_config, env_str)` ; stockage de `change_required`, `change_model_code`, `impact_level` dans `parameters['_env_config']`
- `executions/utils.py` : `_get_env_config_case_insensitive(config, env)` — lookup case-insensitive, retourne le dict de l’environnement
- Pas de table supplémentaire : tout est dans le JSON

**Ce que cette story ajoute :**
- Nouveaux champs par environnement dans le même JSON : `requires_maintenance_window`, `requires_approval`, `allowed`
- Règle métier : si `allowed === false` pour l’env de l’exécution → refus de soumission avec message clair
- Propagation de `requires_maintenance_window` et `requires_approval` dans `_env_config` pour les moteurs (ServiceNow, condition gates) sans implémenter ici la logique métier de “vérification plage maintenance” ou “attente approbation” (déjà ou partiellement ailleurs)
- Admin UI : pouvoir éditer ces trois flags (et optionnellement change_type, template_id) par environnement

### Structure JSON cible (change_type_config)

Exemple (convergence-dbops-idp-portal.md) :

```json
{
  "prod": {
    "change_type": "normal",
    "template_id": "CHG_TPL_001",
    "required": true,
    "change_model_code": "1516B",
    "requires_maintenance_window": true,
    "requires_approval": true,
    "allowed": true
  },
  "staging": {
    "change_type": "standard",
    "requires_maintenance_window": false,
    "requires_approval": false,
    "allowed": true
  },
  "dev": {
    "allowed": true,
    "requires_maintenance_window": false,
    "requires_approval": false
  }
}
```

- **allowed** : si `false` → refus de soumission pour cet environnement (message explicite).
- **requires_maintenance_window** / **requires_approval** : lus et stockés dans `_env_config` ; l’utilisation concrète (ex: gate maintenance_window, flux ServiceNow) peut être dans cette story ou déjà partiellement en place — à aligner avec le code existant.

### Fichiers à modifier / créer

| Fichier | Action |
|--------|--------|
| `executions/views.py` | Lire allowed, requires_maintenance_window, requires_approval depuis env_change_config ; si allowed false → BadRequestError ; enrichir parameters['_env_config'] |
| `executions/utils.py` | Optionnel : helper ou doc pour accès aux nouveaux champs ; _get_env_config_case_insensitive déjà suffisant |
| `catalog/serializers.py` | Validation du JSON change_type_config : allowed bool, requires_* bool optionnels |
| `catalog/services.py` | Pas de changement structurel si le champ est déjà assigné depuis le serializer ; vérifier persistance du JSON enrichi |
| Admin frontend (éditeur règles d’impact / action) | Ajouter champs par environnement : requires_maintenance_window, requires_approval, allowed |
| `docs/backend/` | Documenter structure change_type_config (nouveau fichier ou section existante) |
| Tests | executions/tests, catalog/tests : rejet si allowed=false ; lecture des nouveaux flags ; rétrocompatibilité |

### Project Structure Notes

- Backend : `idp-portal/django_backend/` — catalog (modèles, serializers, services, vues admin), executions (views, utils).
- Frontend admin : à identifier dans le repo (ex: formulaire d’édition d’action ou éditeur de règles d’impact).
- Pas de nouvelle migration Django/Flyway pour les colonnes : seul le contenu JSON du champ existant est étendu.

### References

- [Source: _bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md#2-overrides-par-environnement]
- [Source: _bmad-output/planning-artifacts/epics.md#story-254--overrides-par-environnement-change_type_config-enrichi]
- [Source: idp-portal/django_backend/executions/views.py — lecture change_type_config et _env_config]
- [Source: idp-portal/django_backend/executions/utils.py — _get_env_config_case_insensitive]
- [Source: idp-portal/django_backend/catalog/models.py — Action.change_type_config]

## Change Log

- 2026-02-10: Implémentation complète Story 25.4 — overrides par environnement (change_type_config enrichi)

## Senior Developer Review (AI)

Date: 2026-02-10

### Correctifs appliqués (suite au code review adversarial)

- **Backend**
  - `validate_change_type_config()` rejette désormais un `change_type_config` top-level non objet (prévention corruption + crash runtime).
  - Validation renforcée: `required` doit être booléen si présent; `change_type`/`template_id` acceptés comme chaînes optionnelles (avec limites).
  - Protection défensive dans `executions/views.py` si `Action.change_type_config` est corrompu (log + fallback `{}`).
  - `GateEvaluator` exploite maintenant `_env_config.requires_maintenance_window/requires_approval` pour auto-satisfaire les gates non requis (évite des WAITING inutiles).

- **Frontend**
  - `ChangeTypeConfigEntry` supporte `change_type` et `template_id`.
  - `ChangeTypeConfig` permet d’éditer `change_type` et `template_id` par environnement.
  - `ActionForm` et `ActionWizard` propagent ces champs vers l’API.
  - `ActionWizard` aligne la validation: si `required=true`, `change_model_code` est obligatoire et alphanumérique.

- **Tests**
  - Tests 25.4 durcis: assertions structurées sur `error.code`, vérification qu’aucune exécution n’est créée si `allowed=false`, régression “change_type_config corrompu ne crash pas”.
  - Couverture validation: `required` non-bool, `change_type`/`template_id` non-string, top-level non-dict.

### Résultat

- **Status recommandé**: done (AC1–AC3 couverts, avec protections + tests).

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Story 25.4 implémentée : overrides par environnement (change_type_config enrichi)
- Backend : validate_change_type_config (allowed, requires_maintenance_window, requires_approval) ; rejet si allowed=false à la soumission ; _env_config enrichi
- Frontend : ChangeTypeConfig avec 5 colonnes (Autorisé, Changement requis, Plage maintenance, Approbation, Code modèle)
- 17 tests backend + 10 tests frontend passent

### File List

- idp-portal/django_backend/catalog/validators.py
- idp-portal/django_backend/catalog/services.py
- idp-portal/django_backend/executions/views.py
- idp-portal/django_backend/executions/utils.py
- idp-portal/frontend/src/types/api/catalog.ts
- idp-portal/frontend/src/components/admin/ChangeTypeConfig.tsx
- idp-portal/frontend/src/components/admin/ActionForm.tsx
- idp-portal/frontend/src/components/admin/ActionWizard.tsx
- idp-portal/docs/backend/change-type-config.md
- idp-portal/django_backend/executions/tests/test_story_25_4.py
- idp-portal/django_backend/catalog/tests/test_story_25_4_validators.py
- _bmad-output/implementation-artifacts/sprint-status.yaml
