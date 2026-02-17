# Story 2.7 : Refactorisation des connecteurs génériques

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a développeur,
I want refactoriser les étapes d'exécution pour utiliser un `connector_type` générique au lieu du flag `is_servicenow_change`,
So that tous les systèmes externes (AAP, ServiceNow, Azure DevOps, Jira, GitHub Actions) sont traités de manière uniforme.

## Acceptance Criteria

1. **AC1 — Modèle ExecutionStep** : Given une action existante avec des étapes, When le modèle ExecutionStep est mis à jour, Then le champ `is_servicenow_change` est remplacé par `connector_type` (enum: aap, servicenow, azuredevops, jira, github_actions, terraform, none) et le champ `connector_config` (JSON) stocke la configuration spécifique au connecteur.

2. **AC2 — Configuration ServiceNow conditionnelle** : Given une action a une étape ServiceNow conditionnelle en production, When le DBOPS consulte la configuration, Then l'étape affiche `connector_type: "servicenow"` avec `conditional_environments: ["PROD"]`.

3. **AC3 — Migration de données** : Given une migration de données est exécutée, When les anciennes données sont converties, Then `is_servicenow_change: true` devient `connector_type: "servicenow"` et `is_servicenow_change: false` devient `connector_type: "none"` (ou type d'origine si déjà prévu).

4. **AC4 — Schéma et API** : La migration SQL (prochaine version après V007, ex. V008) n'ajoute pas de colonnes physiques si EXECUTION_STEPS reste un CLOB JSON : le format du JSON est étendu (connector_type, connector_config). Le frontend StepsEditor est mis à jour pour afficher un dropdown de connecteurs. Les modèles Pydantic backend sont mis à jour. La rétro-compatibilité avec les données existantes est assurée (lecture ancien format → conversion en mémoire ou par migration de données). FR2 (PRD mis à jour) est satisfaite.

## Tasks / Subtasks

- [x] Task 1: Backend — Modèles et enum connecteur (AC: 1, 4)
  - [x] 1.1: Ajouter enum `ConnectorType` dans `backend/app/models/catalog.py` : aap, servicenow, azuredevops, jira, github_actions, terraform, none.
  - [x] 1.2: Remplacer dans `ExecutionStep` : `is_servicenow_change: bool` par `connector_type: ConnectorType = ConnectorType.none` et ajouter `connector_config: dict | None = None`. Adapter le validateur : si `connector_type == servicenow` alors `conditional_environments` requis.
  - [x] 1.3: Conserver `conditional_environments` pour les connecteurs conditionnels (ex. ServiceNow uniquement en PROD). Documenter dans le modèle que connector_config contient les paramètres spécifiques (ex. template changement ServiceNow).
  - [x] 1.4: Écrire tests unitaires modèles : ExecutionStep avec connector_type, validation conditional_environments pour servicenow.

- [x] Task 2: Backend — Repository et migration de données (AC: 3, 4)
  - [x] 2.1: Dans `_parse_execution_steps` : accepter l'ancien format (is_servicenow_change) et le convertir en connector_type (true → servicenow, false → none). Écrire en JSON avec le nouveau format (connector_type, connector_config).
  - [x] 2.2: Dans `_execution_steps_to_json` : sérialiser connector_type et connector_config ; ne plus écrire is_servicenow_change.
  - [x] 2.3: Créer migration SQL V008 (optionnelle si pas de changement de schéma) : soit commentaire sur EXECUTION_STEPS mis à jour pour documenter le nouveau format JSON ; soit script de migration de données (UPDATE ACTIONS_CATALOG SET EXECUTION_STEPS = ...) pour remplacer is_servicenow_change par connector_type dans le CLOB existant.
  - [x] 2.4: Tests repository : parse ancien format → steps avec connector_type ; to_json nouveau format ; round-trip.

- [x] Task 3: Backend — API (AC: 4)
  - [x] 3.1: Vérifier que PUT /api/v1/admin/actions/{id}/steps accepte le nouveau body (steps avec connector_type, connector_config). Adapter les tests admin API pour envoyer connector_type au lieu de is_servicenow_change.
  - [x] 3.2: Réponses GET admin/actions et catalog : inclure steps avec connector_type et connector_config (rétro-compatibilité lecture déjà gérée en 2.1).

- [x] Task 4: Frontend — Types et StepsEditor (AC: 2, 4)
  - [x] 4.1: Dans `frontend/src/types/api.ts` : remplacer `is_servicenow_change: boolean` par `connector_type: ConnectorType` et `connector_config?: Record<string, unknown>`. Définir type/enum ConnectorType (valeurs alignées backend).
  - [x] 4.2: Dans `StepsEditor.tsx` : remplacer le Switch "Changement ServiceNow" par un Select "Connecteur" (options: Aucun, ServiceNow, AAP, Azure DevOps, Jira, GitHub Actions, Terraform). Si connector_type === 'servicenow', afficher le bloc conditional_environments (existant).
  - [x] 4.3: Valeur par défaut nouvelle étape : connector_type: 'none', connector_config: null. Lors du chargement d'une action avec ancien format (is_servicenow_change), le backend renvoie déjà le nouveau format (conversion parse), donc le frontend reçoit toujours connector_type/connector_config.
  - [x] 4.4: Tests StepsEditor (et ActionForm si besoin) : rendu dropdown connecteur, sélection ServiceNow affiche environnements conditionnels, sauvegarde envoie connector_type.

- [x] Task 5: Rétro-compatibilité et régression (AC: 3, 4)
  - [x] 5.1: Données existantes : au premier read, _parse_execution_steps convertit is_servicenow_change → connector_type ; au prochain save, le JSON est écrit en nouveau format. Optionnel : script V008 pour réécrire tous les CLOB en nouveau format (évite double logique à long terme).
  - [x] 5.2: Tous les tests existants (test_catalog_models, test_catalog_repository, test_admin_api, ActionForm.test) passent après adaptation (remplacer is_servicenow_change par connector_type dans fixtures et assertions).
  - [x] 5.3: Linter et suite complète. File List et Dev Agent Record à jour.

## Dev Notes

### Contexte métier

- **FR2** : DBOPS peut définir les étapes d'exécution d'une action, chaque étape pouvant appeler un connecteur générique (AAP, ServiceNow, Azure DevOps, Jira, etc.) avec des conditions selon l'environnement cible.
- La story 2.2 a introduit `is_servicenow_change` et `conditional_environments`. Cette story généralise en un seul concept : **connecteur** (type + config), permettant d'ajouter d'autres connecteurs sans nouveau flag.
- La story 2.8 (suppression du rail CAB) retire "cab" du ChangeType ; elle peut être faite après ou en parallèle. Ne pas supprimer ChangeType.CAB dans cette story si 2.8 n'est pas faite (éviter régression).

### Ce qui existe déjà (NE PAS RÉIMPLÉMENTER)

| Élément | Fichier | Rôle |
|--------|---------|------|
| ExecutionStep (Pydantic) | `backend/app/models/catalog.py` | Remplacer is_servicenow_change par connector_type + connector_config |
| _parse_execution_steps / _execution_steps_to_json | `backend/app/repositories/catalog_repository.py` | Étendre pour ancien/nouveau format |
| StepsEditor | `frontend/src/components/admin/StepsEditor.tsx` | Remplacer Switch ServiceNow par Select connecteur |
| ExecutionStep (TS) | `frontend/src/types/api.ts` | Ajouter connector_type, connector_config ; retirer is_servicenow_change |
| PUT /admin/actions/{id}/steps | `backend/app/api/v1/admin.py` | Accepte déjà steps ; vérifier body et tests |
| ChangeTypeConfig | Backend + frontend | Conservé pour l'instant (story 2.8 le simplifiera) |

### Ce qu'il faut CRÉER / MODIFIER

| Élément | Fichier | Description |
|--------|---------|-------------|
| ConnectorType (enum) | `backend/app/models/catalog.py` | aap, servicenow, azuredevops, jira, github_actions, terraform, none |
| ExecutionStep (backend) | idem | connector_type, connector_config ; suppression is_servicenow_change |
| _parse_execution_steps | catalog_repository.py | Lire is_servicenow_change si présent → remplir connector_type |
| _execution_steps_to_json | idem | Écrire connector_type, connector_config uniquement |
| Migration V008 (optionnelle) | `database/migrations/V008_connector_type_in_execution_steps.sql` | Commentaire COLUMN ou script UPDATE CLOB pour migrer JSON existant |
| ConnectorType (TS) | `frontend/src/types/api.ts` | Aligné backend |
| StepsEditor | `frontend/src/components/admin/StepsEditor.tsx` | Dropdown connecteur, conditional_environments si servicenow |
| Fixtures / tests | Backend + frontend | Remplacer is_servicenow_change par connector_type |

### Architecture (extrait architecture.md)

- **Repository Pattern** : SQL brut, pas d'ORM. EXECUTION_STEPS reste un CLOB JSON ; pas de nouvelle colonne si le format étendu tient dans le même CLOB.
- **API** : snake_case JSON, wrapper { "data": ... } / { "error": ... }. Les réponses admin et catalog doivent exposer les steps avec connector_type et connector_config.
- **FR2** : Étapes d'exécution avec connecteurs génériques ; cette story pose la base pour les adapters (AAP, ServiceNow, etc.) utilisés au moment de l'exécution (Epic 4).

### Format JSON EXECUTION_STEPS (après refacto)

Exemple :

```json
[
  {"order": 1, "name": "Vérification", "type": "prerequisite", "connector_type": "none", "connector_config": null, "conditional_environments": null},
  {"order": 2, "name": "Ouverture changement", "type": "execution", "connector_type": "servicenow", "connector_config": {}, "conditional_environments": ["PROD"]}
]
```

Ancien format encore accepté en lecture :

```json
{"order": 2, "name": "Ouverture changement", "type": "execution", "is_servicenow_change": true, "conditional_environments": ["PROD"]}
```

→ converti en `connector_type: "servicenow"`, `connector_config: null` (ou {}).

### Project Structure Notes

- Migrations : `idp-portal/database/migrations/` — prochaine version **V008** (V007 = tags). V003 a ajouté EXECUTION_STEPS et CHANGE_TYPE_CONFIG ; V008 documente ou migre le format JSON des steps.
- Backend : `backend/app/models/catalog.py`, `backend/app/repositories/catalog_repository.py`, `backend/app/api/v1/admin.py`.
- Frontend : `frontend/src/types/api.ts`, `frontend/src/components/admin/StepsEditor.tsx`, `frontend/src/components/admin/ActionForm.tsx` (validation step si besoin).

### References

- [Source: epics.md — Story 2.7, FR2]
- [Source: architecture.md — Repository Pattern, API format]
- [Source: 2-6-systeme-de-tags-flexibles-pour-les-actions.md — Patterns ActionForm, API admin, tests]

---

## Developer Context (Guardrails)

### Technical requirements

- **Backend** : Pydantic v2, Python 3.12+. Enum `ConnectorType` doit être sérialisable en JSON (value string). Validation : si `connector_type == "servicenow"` et `conditional_environments` absent ou vide → ValueError.
- **Frontend** : TypeScript strict. Enum ou union type `ConnectorType` aligné sur le backend. StepsEditor : Ant Design Select pour le connecteur, pas de nouveau composant custom lourd.
- **Rétro-compatibilité** : Toute donnée existante avec `is_servicenow_change` doit être lue sans erreur et exposée en `connector_type` / `connector_config`. À la prochaine sauvegarde des steps, le JSON doit être écrit en nouveau format uniquement.

### Architecture compliance

- Repository : pas d'ORM ; lecture/écriture du CLOB EXECUTION_STEPS via _parse_execution_steps et _execution_steps_to_json.
- API : PUT /api/v1/admin/actions/{id}/steps garde le même contrat de haut niveau (steps + change_type_config) ; le corps `steps` contient désormais `connector_type` et `connector_config` au lieu de `is_servicenow_change`.
- Pas de changement de route ou d’URL ; pas de nouvelle table. Optionnel : V008 pour mise à jour en masse des CLOB (recommandé pour nettoyer l’ancien format).

### Library / framework requirements

- Backend : FastAPI, Pydantic v2, python-oracledb. Aucune nouvelle dépendance.
- Frontend : React, Ant Design 6 (Select, Option). Aucune nouvelle dépendance.
- Tests : pytest + httpx (backend), Vitest + RTL (frontend). Adapter les mocks et fixtures existants.

### File structure requirements

- Modèles : `backend/app/models/catalog.py` (ConnectorType, ExecutionStep).
- Repository : `backend/app/repositories/catalog_repository.py` (parse/to_json).
- Migration : `idp-portal/database/migrations/V008_*.sql` (nom explicite, ex. V008_connector_type_in_execution_steps.sql).
- Types : `frontend/src/types/api.ts` (ExecutionStep, ConnectorType).
- UI : `frontend/src/components/admin/StepsEditor.tsx` (dropdown connecteur).

### Testing requirements

- Backend : tests unitaires pour ExecutionStep (connector_type, validation conditional_environments), _parse_execution_steps (ancien format → nouveau), _execution_steps_to_json (nouveau format uniquement), update_execution_steps (round-trip). Tests API PUT steps avec body connector_type.
- Frontend : tests StepsEditor (dropdown visible, sélection servicenow affiche conditional_environments, onChange appelle avec connector_type). ActionForm : pas de régression sur la sauvegarde des steps.
- Régression : tous les tests existants passent après remplacement des champs dans fixtures (is_servicenow_change → connector_type).

---

## Previous Story Intelligence (2.6)

- **Tags** : Migration V007, table TAGS et ACTION_TAGS, GET /api/v1/tags, PUT /admin/actions/{id}/tags. ActionForm : section Tags avec Select mode tags, persistance à la sauvegarde. Ne pas toucher aux tags dans cette story.
- **Repository** : pattern get_* / set_* / create_*_if_not_exists ; gestion race condition (IntegrityError → retry SELECT). Même style pour _parse_* / _*_to_json : idempotent et tolérant à l’ancien format.
- **Tests** : mock COUNT pour list_all_admin ; tests API avec AsyncMock sur catalog_repository. Adapter les payloads admin (steps) pour utiliser connector_type au lieu de is_servicenow_change.
- **Fichiers modifiés en 2.6** : catalog_repository.py, catalog.py (models), admin.py, tags.py, ActionForm.tsx, AdminPage.tsx, api.ts. Pour 2.7 : catalog.py, catalog_repository.py, admin.py (tests), StepsEditor.tsx, api.ts.

---

## Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md — Repository Pattern, API format, FR2]
- [Source: _bmad-output/planning-artifacts/epics.md — Story 2.7, 2.8 (CAB à supprimer ensuite)]
- [Source: idp-portal/database/migrations/V003_add_execution_steps.sql — Format actuel EXECUTION_STEPS]

---

## Story Completion Status

- **Status** : done
- **Sprint status** : development_status["2-7-refactorisation-des-connecteurs-generiques"] = "done" (code-review 2026-01-28).

## Dev Agent Record

### Agent Model Used

(Dev agent — Story 2.7 implementation)

### Debug Log References

(N/A)

### Completion Notes List

- AC1/AC4: Enum `ConnectorType` ajouté dans `backend/app/models/catalog.py` (aap, servicenow, azuredevops, jira, github_actions, terraform, none). `ExecutionStep` utilise `connector_type` et `connector_config`; validateur `conditional_environments` requis si `connector_type == servicenow`.
- AC3: `_parse_execution_steps` accepte l’ancien format `is_servicenow_change` et le convertit en `connector_type`. `_execution_steps_to_json` n’écrit que le nouveau format (connector_type, connector_config).
- AC4: Migration V008 documente le nouveau format JSON (COMMENT ON COLUMN). Pas de nouvelle colonne.
- Frontend: `api.ts` — type `ConnectorType` et `ExecutionStep` avec connector_type/connector_config. `StepsEditor.tsx` — Select connecteur (Aucun, ServiceNow, AAP, etc.), bloc conditional_environments si servicenow. `ActionForm.tsx` — validation sur connector_type === 'servicenow'.
- Tests: test_catalog_models (ConnectorType, ExecutionStep connector_type, conditional_environments), test_catalog_repository (parse legacy, to_json nouveau format, row_to_action_detail), test_admin_api (PUT steps avec connector_type), StepsEditor.test.tsx (dropdown, servicenow, onChange connector_type). Correction de 2 tests admin (update_status appel en kwargs) pour faire passer la suite.
- Code-review 2026-01-28: File List complété avec admin.py; docstring PUT steps mise à jour (Story 2.7); tests API PUT steps avec connector_type servicenow (200 avec conditional_environments, 422 sans conditional_environments).

### Change Log

- 2026-01-28: Story 2.7 implémentée — connecteur générique (connector_type/connector_config), rétro-compat lecture is_servicenow_change, migration V008, frontend StepsEditor dropdown, tests backend et frontend.
- 2026-01-28: Code-review — File List (admin.py), docstring PUT steps, tests API ServiceNow (AC2/AC4).

### File List

- idp-portal/backend/app/models/catalog.py
- idp-portal/backend/app/repositories/catalog_repository.py
- idp-portal/backend/app/api/v1/admin.py
- idp-portal/database/migrations/V008_connector_type_in_execution_steps.sql
- idp-portal/backend/tests/unit/test_catalog_models.py
- idp-portal/backend/tests/unit/test_catalog_repository.py
- idp-portal/backend/tests/unit/test_admin_api.py
- idp-portal/frontend/src/types/api.ts
- idp-portal/frontend/src/components/admin/StepsEditor.tsx
- idp-portal/frontend/src/components/admin/ActionForm.tsx
- idp-portal/frontend/src/components/admin/StepsEditor.test.tsx
