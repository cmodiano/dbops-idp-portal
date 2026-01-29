# Story 2.13: Import/Export profiles as code (YAML)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DBOPS**,
I want **importer et exporter la configuration des profils en YAML**,
so that **je puisse gérer les profils en GitOps et versionner les changements**.

## Acceptance Criteria

1. **AC1 — Export YAML** : Given un DBOPS consulte la liste des profils, When il clique sur « Exporter YAML », Then un fichier profiles.yaml est téléchargé avec tous les profils et leurs permissions (actions, targets, environnements).

2. **AC2 — Import YAML (création/mise à jour)** : Given un DBOPS a un fichier profiles.yaml, When il clique sur « Importer YAML » et uploade le fichier, Then les profils sont créés ou mis à jour selon le contenu du fichier.

3. **AC3 — Upsert par nom** : Given le fichier YAML contient un profil existant (même nom) avec des modifications, When l'import est exécuté, Then le profil est mis à jour (upsert par nom), pas dupliqué.

4. **AC4 — Erreur de syntaxe** : Given le fichier YAML contient une erreur de syntaxe ou un schéma invalide, When l'import est exécuté, Then une erreur claire est affichée et aucun changement n'est appliqué.

5. **AC5 — Format YAML** : Le format d'export/import respecte le schéma documenté (profiles[], name, description, ad_group, is_admin, is_auditor, actions { type, patterns | list }, targets { type, patterns | list }, environments[]).

6. **AC6 — FR25d** : FR25d est satisfaite (DBOPS peut importer/exporter la configuration des profils en YAML as code).

**Format YAML (référence epics.md) :**

```yaml
profiles:
  - name: Assurance
    description: Equipe assurance
    ad_group: GRP-IDP-ASSURANCE
    is_admin: false
    is_auditor: false
    actions:
      type: pattern   # ou "list"
      patterns: ["tag:oracle", "tag:provisioning"]
      # ou: list: [5, 12, 23]
    targets:
      type: pattern    # ou "list"
      patterns: ["assurance-*"]
      # ou: list: ["assurance-srv-01", "assurance-srv-02"]
    environments: [DEV, STAGING]
```

## Tasks / Subtasks

- [x] Task 1 : Backend — Modèles et schéma d'import (AC: 5)
  - [x] 1.1 : Définir un modèle Pydantic (ex. `ProfileYamlItem`) pour un profil dans le YAML : name, description, ad_group, is_admin, is_auditor, actions (type + patterns ou list), targets (type + patterns ou list), environments.
  - [x] 1.2 : Définir un modèle racine (ex. `ProfilesYamlImport`) avec `profiles: list[ProfileYamlItem]` pour valider le fichier uploadé.
  - [x] 1.3 : Valider que pour actions/targets : type "pattern" → patterns requis ; type "list" → list (action_ids ou target_names) requis ; pas de type "all" dans le YAML ou le gérer comme absence de restrictions selon la convention choisie.

- [x] Task 2 : Backend — Export YAML (AC: 1, 5)
  - [x] 2.1 : Implémenter la logique d'export : récupérer tous les profils (profile_repository.get_all()), pour chaque profil charger les permissions actions (profile_action_permission_repository) et targets (profile_target_permission_repository).
  - [x] 2.2 : Construire une structure dict/list conforme au format YAML ci-dessus (snake_case, actions.type/patterns|list, targets.type/patterns|list, environments).
  - [x] 2.3 : Sérialiser en YAML (PyYAML ou ruamel.yaml) et retourner en tant que fichier téléchargeable (Content-Disposition: attachment; filename=profiles.yaml) ou retourner le YAML en body avec content-type application/x-yaml / text/yaml.

- [x] Task 3 : Backend — Import YAML (AC: 2, 3, 4)
  - [x] 3.1 : Endpoint POST /api/v1/admin/profiles/import acceptant un body multipart (fichier .yaml) ou raw YAML (content-type application/x-yaml / application/json pour alternative).
  - [x] 3.2 : Parser le YAML, valider avec les modèles Pydantic (ProfileYamlItem / ProfilesYamlImport). En cas d'erreur de validation → 400 avec message clair (ex. « Ligne X : champ 'actions.type' invalide »).
  - [x] 3.3 : Pour chaque profil dans le YAML : si un profil avec le même nom existe (requête par nom), faire update (profile_repository + set_actions + set_targets) ; sinon create puis set_actions + set_targets. Ordre : créer/mettre à jour les profils un par un ; en cas d'erreur métier (ex. ad_group vide), retourner 400 avec détail.
  - [x] 3.4 : Réponse succès : 200 avec résumé (created: n, updated: n) ou 201 si tout créé.

- [x] Task 4 : Backend — Routes et intégration (AC: 1–6)
  - [x] 4.1 : GET /api/v1/admin/profiles/export : retourne le fichier YAML (StreamingResponse ou Response avec content_type et headers Content-Disposition). Protégé par require_profile("dbops").
  - [x] 4.2 : POST /api/v1/admin/profiles/import : reçoit le fichier, parse, valide, applique upsert. Protégé par require_profile("dbops"). Invalider le cache RBAC après import réussi (si présent, voir story 2.12).

- [x] Task 5 : Frontend — Boutons Export / Import (AC: 1, 2, 4)
  - [x] 5.1 : Sur la page Admin → Profils (liste des profils), ajouter un bouton « Exporter YAML » : appel GET /admin/profiles/export, téléchargement du fichier (blob + lien de téléchargement ou window.open / fetch + download).
  - [x] 5.2 : Ajouter un bouton « Importer YAML » : ouverture d’un modal ou drawer avec input file (accept .yaml, .yml), puis POST /admin/profiles/import avec le fichier en multipart. Afficher le résumé (created/updated) ou l’erreur (message clair) dans un message/toast.
  - [x] 5.3 : En cas d’erreur 400 (syntaxe ou validation), afficher le message d’erreur retourné par l’API (pas de message générique).

- [x] Task 6 : Tests et non-régression (AC: 1–6)
  - [x] 6.1 : Tests unitaires backend : export (0 profil, 1 profil, N profils avec actions/targets variés) ; import (fichier valide upsert, fichier invalide syntaxe, fichier schéma invalide).
  - [x] 6.2 : Tests API : GET export retourne 200 et YAML valide ; POST import avec fichier valide → 200 et profils créés/mis à jour ; POST import avec YAML invalide → 400 et message explicite.
  - [x] 6.3 : Pas de régression sur stories 2.9, 2.10, 2.11 (CRUD profils, permissions actions, permissions targets).

## Dev Notes

- **Contexte métier** : FR25d — DBOPS peut importer/exporter la configuration des profils en YAML (as code). Les stories 2.9 (profils), 2.10 (permissions actions), 2.11 (permissions targets) ont livré les données ; cette story ajoute la couche export (lecture DB → YAML) et import (YAML → validation → upsert DB).
- **Upsert** : Clé d’identification = nom du profil (name). Si name existe déjà → update ; sinon create. Pas d’ID dans le YAML pour l’import.
- **Validation stricte** : Pydantic suffit pour valider la structure après parsing YAML. Pas obligatoire d’utiliser JSON Schema côté fichier ; un modèle Pydantic qui reflète le format YAML (avec aliases si besoin) est conforme à l’architecture.

### Ce qui existe déjà (NE PAS RÉIMPLÉMENTER)

| Élément | Fichier | Rôle |
|--------|---------|------|
| PROFILES | V010_create_profiles.sql | Table profils |
| PROFILE_ACTION_PERMISSIONS | V011 | Permissions actions par profil |
| PROFILE_TARGET_PERMISSIONS | V012 | Permissions targets par profil |
| profile_repository | backend/app/repositories/profile_repository.py | CRUD profils, get_all, get_by_id, create, update. Ajouter get_by_name si absent. |
| profile_action_permission_repository | backend/app/repositories/profile_action_permission_repository.py | set_actions_permissions(profile_id, payload) |
| profile_target_permission_repository | backend/app/repositories/profile_target_permission_repository.py | set_target_permissions(profile_id, payload) |
| Routes profiles | backend/app/api/v1/profiles.py | GET/POST /profiles, GET/PUT/DELETE /profiles/{id}, PUT .../actions, PUT .../targets |
| Modèles ProfileCreate, ProfileUpdate, ProfileActionPermissionsUpdate, ProfileTargetPermissionsUpdate | backend/app/models/profile.py | Réutiliser la logique métier (types list/pattern/all) pour construire les payloads depuis le YAML |

### Architecture (extrait)

- **API** : Nouveaux endpoints GET /admin/profiles/export et POST /admin/profiles/import (sous le router profiles, donc préfixe /admin/profiles). Réponses : export = fichier binaire YAML ; import = 200/201 avec body { "data": { "created": n, "updated": n } } ou 400 avec { "error": { "code": "INVALID_YAML", "message": "...", "details": {...} } }.
- **Pas de nouvelle table** : Lecture/écriture via repositories existants.
- **Cache RBAC** : Après import réussi, appeler l’invalidation du cache RBAC (même point que pour PUT profiles/actions/targets, story 2.12).

### Project Structure Notes

- Backend : `app/api/v1/profiles.py` — ajouter les routes export/import. `app/models/profile.py` — ajouter ProfileYamlItem, ProfilesYamlImport (ou dans un fichier dédié app/models/profile_import.py si préféré). Logique d’export/import peut être dans un service `app/services/profile_export_import_service.py` ou directement dans les routes si simple.
- Frontend : Page ou section Admin → Profils (liste) : ajouter boutons Export YAML et Importer YAML, appel vers profiles_service (getExportUrl + download, postImport avec FormData).
- Dépendance Python : PyYAML (pyyaml) ou ruamel.yaml pour sérialisation/désérialisation YAML. Vérifier pyproject.toml ; ajouter si absent.

### References

- [Source: epics.md — Story 2.13, FR25d, format YAML]
- [Source: architecture.md — API wrapper { data } / { error }, snake_case, Repository Pattern]
- [Source: 2-12-cumul-des-permissions-multi-profiles.md — Invalidation cache RBAC après modification profils]
- [Source: idp-portal/backend/app/api/v1/profiles.py — Routes existantes /profiles]
- [Source: idp-portal/backend/app/models/profile.py — ProfileCreate, ProfileActionPermissionsUpdate, ProfileTargetPermissionsUpdate]

---

## Developer Context (Guardrails)

### Technical requirements

- **Backend** : Python 3.12+, FastAPI. Export : récupérer tous les profils + permissions actions/targets pour chacun, construire une structure dict conforme au format YAML, sérialiser avec PyYAML (ou ruamel.yaml). Import : parser YAML, valider avec Pydantic, pour chaque profil get_by_name (à ajouter si manquant) → update ou create, puis set_actions_permissions et set_target_permissions avec payloads dérivés du YAML (list/pattern/all). Gérer type "all" dans le YAML : soit champ optionnel, soit absence de actions/targets = all.
- **Frontend** : Bouton Export → GET /api/v1/admin/profiles/export avec réponse blob, déclencher téléchargement (filename=profiles.yaml). Bouton Import → input file, POST multipart/form-data vers /api/v1/admin/profiles/import, afficher succès (created/updated) ou erreur (message API).
- **Validation** : Erreur de syntaxe YAML (parser) → 400 "Syntaxe YAML invalide". Erreur de schéma (Pydantic) → 400 avec détails des champs invalides. Aucun changement en base si validation échoue.

### Architecture compliance

- Réponses API : `{ "data": ... }` / `{ "error": ... }`. Codes HTTP : 200 (export, import succès), 201 (optionnel import tout créé), 400 (validation), 401/403 (non authentifié / non DBOPS). Logging structuré avec correlation_id sur import/export. Pas de Redis ; invalidation cache RBAC in-memory après import.

### Library / framework requirements

- PyYAML (pyyaml) ou ruamel.yaml pour YAML. Préférer ruamel.yaml si conservation des commentaires/ordre est requise ; sinon PyYAML suffit. Vérifier compatibilité Python 3.12.

### File structure requirements

- Backend : Routes dans `api/v1/profiles.py` (GET export, POST import). Modèles Pydantic d’import dans `models/profile.py` ou `models/profile_import.py`. Service optionnel `services/profile_export_import_service.py`. Repositories existants inchangés sauf ajout éventuel `get_by_name` dans profile_repository.
- Frontend : Appels dans `services/profiles_service.ts` (exportProfilesYaml, importProfilesYaml). Boutons sur la page/section Admin des profils (composant existant à étendre).

### Testing requirements

- Tests unitaires : export avec 0, 1, N profils ; import avec YAML valide (création, mise à jour par nom) ; import avec YAML invalide (syntaxe, schéma) → erreur et pas de changement en base.
- Tests API : GET /admin/profiles/export retourne 200 et body YAML parsable ; POST /admin/profiles/import avec fichier valide → 200/201, profils créés/mis à jour ; POST avec fichier invalide → 400 et message clair.
- Non-régression : CRUD profils et PUT actions/targets inchangés.

---

## Previous Story Intelligence (2.12)

- **Cumul des permissions** : Story 2.12 a livré la résolution des profils par groupes AD, l’agrégation des permissions (union) et le cache RBAC avec invalidation lors des modifications admin (PUT profiles, PUT actions, PUT targets). Pour l’import YAML, après chaque création/mise à jour de profil, il faut invalider le cache RBAC (même mécanisme que pour les routes PUT existantes).
- **Fichiers utiles** : profile_repository (get_all, get_by_id, create, update), profile_action_permission_repository (set_actions_permissions), profile_target_permission_repository (set_target_permissions). Si get_by_name n’existe pas, l’ajouter pour l’upsert par nom.

---

## Git Intelligence Summary

- Contexte récent : stories 2.9–2.12 (profils, permissions actions, permissions targets, cumul multi-profils). Migrations V010–V012, repositories et routes admin en place. Même conventions : snake_case, wrapper { data } / { error }, require_profile("dbops") sur les routes admin.

---

## Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md — API format, Repository Pattern, cache RBAC]
- [Source: _bmad-output/planning-artifacts/epics.md — Story 2.13, FR25d, format YAML]
- [Source: idp-portal/backend/app/api/v1/profiles.py — Router /profiles, list, get, create, update, delete, put actions, put targets]
- [Source: idp-portal/backend/app/models/profile.py — ProfileCreate, ProfileActionPermissionsUpdate, ProfileTargetPermissionsUpdate]
- [Source: idp-portal/backend/app/repositories/profile_repository.py — CRUD profils]
- [Source: idp-portal/backend/app/repositories/profile_action_permission_repository.py, profile_target_permission_repository.py — Permissions]

---

## Story Completion Status

- **Status** : review
- **Sprint status** : development_status["2-13-import-export-profiles-as-code-yaml"] = "review"

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Task 1: Modèles Pydantic ProfileYamlItem, ProfilesYamlImport, ProfileYamlActions, ProfileYamlTargets dans app/models/profile_import.py ; validation type pattern/list/all ; get_by_name ajouté au profile_repository.
- Task 2: Service export_profiles_yaml() (get_all + get_by_id + permissions par profil, build dict, yaml.dump) ; route GET /admin/profiles/export (Response blob, Content-Disposition).
- Task 3–4: import_profiles_yaml(content) (parse YAML, ProfilesYamlImport.model_validate, upsert par nom, set_actions_permissions/set_target_permissions) ; route POST /admin/profiles/import (UploadFile, invalidate cache RBAC) ; conversion list: [] → type "all" pour l'API.
- Task 5: Boutons Exporter YAML / Importer YAML sur ProfilesTable ; modal Import avec input file ; profiles_service.exportProfilesYaml (apiFetchBlob + download), importProfilesYaml (FormData).
- Task 6: Tests unitaires modèles import, service export/import, API export/import ; test frontend ProfilesTable Export/Import ; 491 backend + 147 frontend passent.
- Code Review: AC4 two-phase validation (validate all profiles before applying changes), duplicate profile name detection in YAML file, apiPostFormData return type consistency, extension validation test, File List accuracy corrected.

### Change Log

- 2026-01-28: Implémentation complète 2.13 (export/import YAML profils). Backend: modèles, service, routes GET /export, POST /import. Frontend: boutons + modal import. Tests backend et frontend ajoutés.
- 2026-01-28: Code Review fixes — AC4 two-phase validation (validate all before apply), duplicate name detection in YAML, apiPostFormData type consistency, new tests for extension validation and duplicate names, File List corrected.

### File List

- idp-portal/backend/app/models/profile_import.py (new)
- idp-portal/backend/app/models/profile.py (contains Story 2.10/2.11 models: ProfileActionPermissionsUpdate, ProfileActionPermissionsResponse, ProfileTargetPermissionsUpdate, ProfileTargetPermissionsResponse)
- idp-portal/backend/app/repositories/profile_repository.py (get_by_name)
- idp-portal/backend/app/services/profile_export_import_service.py (new, AC4 two-phase validation)
- idp-portal/backend/app/api/v1/profiles.py (GET /export, POST /import)
- idp-portal/backend/pyproject.toml (pyyaml)
- idp-portal/backend/tests/unit/test_profile_import_models.py (new)
- idp-portal/backend/tests/unit/test_profile_export_import_service.py (new, includes duplicate name test)
- idp-portal/backend/tests/unit/test_profile_repository.py (TestGetByName)
- idp-portal/backend/tests/unit/test_profiles_api.py (TestExportImportProfiles)
- idp-portal/frontend/src/services/api_client.ts (apiFetchBlob, apiPostFormData)
- idp-portal/frontend/src/services/profiles_service.ts (exportProfilesYaml, importProfilesYaml)
- idp-portal/frontend/src/types/api.ts (Story 2.10/2.11 types: ProfileActionPermissionsUpdate, ProfileActionPermissionsResponse, ProfileTargetPermissionsUpdate, ProfileTargetPermissionsResponse)
- idp-portal/frontend/src/components/admin/ProfilesTable.tsx (onExportYaml, onImportYaml)
- idp-portal/frontend/src/pages/AdminPage.tsx (handleExportYaml, handleImportYaml, modal Import)
- idp-portal/frontend/src/components/admin/ProfilesTable.test.tsx (test Export/Import buttons)
- _bmad-output/implementation-artifacts/sprint-status.yaml (2-13 in-progress → review)
- _bmad-output/implementation-artifacts/2-13-import-export-profiles-as-code-yaml.md (tasks, status, Dev Agent Record)
