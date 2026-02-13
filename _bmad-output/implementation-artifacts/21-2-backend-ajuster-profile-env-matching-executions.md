# Story 21.2 : Backend — Ajuster profile/env matching et exécutions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur backend,
je veux que les profils et les exécutions comparent les environnements de manière case-insensitive sans normalisation forcée,
afin d'accepter les valeurs de l'inventaire et des profils de façon cohérente.

## Acceptance Criteria

1. **Given** `list_targets_for_user` et `get_allowed_environments_for_user`  
   **When** un profil a `ENVIRONMENTS_JSON = ["lab", "dev"]` et l'inventaire contient `lab`, `dev`  
   **Then** la comparaison est case-insensitive  
   **And** les targets avec `environment: 'lab'` sont autorisés  
   **And** on n'appelle plus `_normalize_environment` sur les valeurs de profil (ou uniquement pour alias legacy)

2. **Given** `_validate_environment_against_inventory` dans `executions/views.py`  
   **When** l'environnement soumis est `lab` et l'inventaire le contient  
   **Then** la validation réussit  
   **And** aucun fallback vers `dev` n'est appliqué

3. **Given** `change_type_config` et `impact_rules` lookup  
   **When** l'environnement d'exécution est `lab`  
   **Then** le lookup utilise `env_upper` ou comparaison case-insensitive  
   **And** si aucune règle n'existe pour `lab`, `default_impact_level` est utilisé pour impact  
   **And** si aucune config change_type n'existe pour `lab`, pas de changement requis (comportement par défaut)

## Tasks / Subtasks

- [x] Task 1 : Ajuster `list_targets_for_user` — comparaison case-insensitive (AC #1)
  - [x] 1.1 Construire `allowed_environments` avec valeurs raw + alias (quand profil a certif, inclure staging ET certif pour matcher targets Oracle raw)
  - [x] 1.2 Filtrer les targets : comparaison case-insensitive entre `t['environment']` et `allowed_environments`
  - [x] 1.3 Pour le filtre query param `environment`, utiliser comparaison case-insensitive
- [x] Task 2 : Ajuster `get_allowed_environments_for_user` (AC #1)
  - [x] 2.1 Retourner un set incluant raw + alias pour chaque env de profil (cohérent avec Task 1.1)
- [x] Task 3 : Vérifier `_validate_environment_against_inventory` (AC #2)
  - [x] 3.1 Confirmer que la validation utilise déjà `environment.lower()` vs `[e.lower() for e in valid_environments]` — pas de fallback vers dev
  - [x] 3.2 Si besoin, supprimer tout fallback résiduel
- [x] Task 4 : Lookup case-insensitive pour `change_type_config` et `impact_rules` (AC #3)
  - [x] 4.1 Créer helper `_get_env_config_case_insensitive(config: dict, env: str) -> dict` dans executions/views.py
  - [x] 4.2 Remplacer `change_type_config.get(env_upper, {})` par lookup case-insensitive
  - [x] 4.3 Remplacer `impact_rules.get(env_upper, {})` par lookup case-insensitive
  - [x] 4.4 Fallback : si aucune règle pour l'env → `default_impact_level` pour impact ; pas de changement requis pour change_type
- [x] Task 5 : Tests
  - [x] 5.1 Réactiver les 2 tests RBAC skippés dans Story 21.1 (`test_list_targets_certif_normalized_to_staging`, `test_list_targets_profile_env_certif_normalized_to_staging`) et les adapter au nouveau comportement
  - [x] 5.2 Ajouter tests : profil `['lab','dev']` + targets raw `lab` → autorisés
  - [x] 5.3 Tests executions : `_validate_environment_against_inventory` avec `lab` ; change_type/impact lookup avec env `lab`

## Dev Notes

⚠️ **DEPLOYMENT WARNING:** Story 21.1 et 21.2 forment un **changement atomique**. Déployer ensemble uniquement. 21.1 seule casse le RBAC (targets raw vs profils normalisés).

- **Contexte Story 21.1 :** L'inventaire retourne désormais les valeurs brutes (ex. `lab`, `dev`, `certif`). `_normalize_environment` ne fait plus que les alias (certif→staging, etc.) sans récursion. Les targets ont des environnements raw.
- **Problème actuel :** `list_targets_for_user` construit `allowed_environments` via `_normalize_environment` sur les envs de profil. Si profil a `certif`, on obtient `staging`. Mais les targets ont `certif` (raw Oracle). Donc `t['environment'] in allowed_environments` échoue (certif ≠ staging).
- **Solution :** allowed_environments doit contenir à la fois la forme normalisée ET la forme raw pour les alias. Ex. profil certif → `{staging, certif}`. Comparaison case-insensitive partout.

### Project Structure Notes

- Backend Django : `idp-portal/django_backend/`
- Fichiers impactés : `inventory/services.py`, `inventory/tests/test_services.py`, `executions/views.py`, `executions/tests/`
- Référence Epic 21 : `_bmad-output/planning-artifacts/epic-21-inventaire-source-unique-environnements.md`

### References

- [Source: _bmad-output/planning-artifacts/epic-21-inventaire-source-unique-environnements.md] — AC 21.2, portée
- [Source: idp-portal/django_backend/inventory/services.py] — `list_targets_for_user` (l.352–398), `get_allowed_environments_for_user` (l.428–449), `_normalize_environment` (l.424–455)
- [Source: idp-portal/django_backend/executions/views.py] — `_validate_environment_against_inventory` (l.51–81), change_type/impact lookup (l.766–777)
- [Source: _bmad-output/implementation-artifacts/21-1-backend-supprimer-normalisation-inventaire-valeurs-brutes.md] — Contexte 21.1, deployment warning

---

## Developer Context & Guardrails

- **Objectif métier :** Accepter les valeurs d'environnement de l'inventaire (lab, dev, staging, prod, certif, etc.) sans normalisation forcée. La comparaison RBAC et les lookups exécution doivent être case-insensitive et gérer les alias legacy.
- **Piège à éviter :** Ne pas casser le matching RBAC. Actuellement, profil certif → allowed = {staging}, target = certif → pas de match. Il faut inclure les deux formes dans allowed.
- **Périmètre strict :** Backend uniquement. Pas de frontend (Story 21.4, 21.5).
- **Cohérence avec 21.1 :** Story 21.1 a supprimé la récursion et les warnings. 21.2 complète en ajustant la couche RBAC et exécutions pour consommer correctement les valeurs brutes.

## Technical Requirements

- **`list_targets_for_user` :** Pour chaque env de profil `e`, ajouter à `allowed_environments` : `_normalize_environment(e)` et `(e or '').strip().lower()`. Ainsi certif → {staging, certif}, lab → {lab}. Filtre targets : `t['environment'].lower() in {a.lower() for a in allowed_environments}`.
- **`get_allowed_environments_for_user` :** Même logique pour construire le set retourné.
- **`_validate_environment_against_inventory` :** Déjà case-insensitive (l.62). Vérifier absence de fallback vers dev.
- **executions/views.py change_type / impact :** Créer helper `_get_env_config_case_insensitive(config, env)` qui parcourt les clés du config et retourne la valeur si `k.lower() == (env or '').lower()`, sinon `{}`. Pour impact : fallback sur `action.default_impact_level` si pas de règle.

## Architecture Compliance

- Repository / service pattern : pas de changement de structure. Logique dans InventoryService et executions/views.
- RBAC : Story 13.3, 13.7 — le filtrage RBAC par environnement reste inchangé en principe, seules les valeurs comparées changent.
- Sécurité : pas de nouvelle surface d'attaque. Validation des environnements inchangée.

## Library & Framework Requirements

- Django ORM, structlog, cachetools : inchangés.
- Pas de nouvelle dépendance.

## File Structure Requirements

- Fichiers à modifier : `idp-portal/django_backend/inventory/services.py`, `idp-portal/django_backend/inventory/tests/test_services.py`, `idp-portal/django_backend/executions/views.py`, `idp-portal/django_backend/executions/tests/` (ajouter ou adapter tests).
- Pas de nouveau fichier dédié.

## Testing Requirements

- **Réactiver tests 21.1 :** `test_list_targets_certif_normalized_to_staging`, `test_list_targets_profile_env_certif_normalized_to_staging` — les adapter pour le nouveau comportement (profil certif → targets certif autorisés).
- **Nouveaux tests :** (1) Profil `['lab','dev']`, inventory targets raw `lab` → list_targets_for_user retourne les targets lab. (2) get_allowed_environments_for_user avec profil lab → retourne set contenant lab. (3) _validate_environment_against_inventory('lab') avec inventaire contenant lab → pas d'exception. (4) change_type_config / impact_rules avec clé 'lab' ou 'LAB' → lookup réussi ; avec env lab et pas de règle → default_impact_level.
- Exécuter : `inventory/tests/test_services.py`, `executions/tests/test_environment_validation.py`, `executions/tests/test_story_13_4.py`, tests d'exécution pertinents.

## Previous Story Intelligence

**Story 21.1 — learnings :**
- `_read_oracle_inventory` retourne raw env (trim + lowercase). Ne pas appeler `_normalize_environment` ici.
- `_normalize_environment` : alias uniquement (certif→staging, etc.), valeurs inconnues retournées telles quelles.
- Tests RBAC avec certif ont été skippés car 21.1 ne touchait pas list_targets_for_user. 21.2 doit les réactiver.
- **Critical :** 21.1 et 21.2 doivent être déployées ensemble. Documenter dans Dev Notes.

## Project Context Reference

- Portail DBOPS, backend Django, inventaire Oracle. Epic 21 = inventaire comme source unique des environnements.
- Pas de `project-context.md` trouvé.

## Story Completion Status

- **Status :** ready-for-dev
- **Analyse :** Epic 21 + code actuel analysé ; inventory/services.py (list_targets_for_user, get_allowed_environments_for_user) et executions/views.py (change_type_config, impact_rules, _validate_environment_against_inventory) identifiés ; tâches et AC alignés.
- **Note :** Ultimate context engine analysis completed — comprehensive developer guide created.

---

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

✅ **Task 1-4 Completed (2026-02-08):**
- Implémenté comparaison case-insensitive pour RBAC environnement dans `list_targets_for_user`
- `allowed_environments` inclut maintenant raw + normalized (ex: certif → {staging, certif})
- Filtre query param `environment` utilise comparaison case-insensitive
- `get_allowed_environments_for_user` aligné avec même logique
- `_validate_environment_against_inventory` vérifié conforme (déjà case-insensitive, pas de fallback)
- Créé helper `_get_env_config_case_insensitive` pour lookup config environnement
- Remplacé `env_upper` par lookup case-insensitive dans change_type_config et impact_rules

✅ **Task 5 Completed (2026-02-08):**
- Réactivé et adapté 2 tests RBAC skippés : targets retournent valeurs raw (certif, certification)
- Ajouté 2 nouveaux tests RBAC : profil lab/dev, filtre case-insensitive
- Ajouté test `get_allowed_environments_includes_raw_and_normalized`
- Ajouté 6 tests dans `test_environment_validation.py` : validation lab, lookup case-insensitive
- Tous les tests suivent le nouveau comportement : inventaire = source vérité, valeurs raw préservées

**Approche technique :**
- Lors construction `allowed_environments`, pour chaque env du profil :
  1. Ajouter valeur normalisée (alias appliqué)
  2. Si différente, ajouter aussi valeur raw
- Résultat : profil certif → allowed = {staging, certif}, match targets certif ✅
- Comparaison : `t['environment'].lower() in {e.lower() for e in allowed_environments}`

---

✅ **Code Review Adversarial (2026-02-09) - 10 issues fixed:**

**5 HIGH issues fixed:**
- HIGH-1: Test `test_list_targets_certif_normalized_to_staging` corrigé - expectations fausses (total=0, pas 2)
- HIGH-2: Validation environnement bloque maintenant si inventaire indisponible (sécurité SOC1)
- HIGH-3: Performance optimisée - set comprehension au lieu de list comprehension (O(1) vs O(n))
- HIGH-4: Audit trail ajouté pour tentatives environnement invalide (SOC1 compliance)
- HIGH-5: Validation type ajoutée dans `_get_env_config_case_insensitive` avec log warning

**3 MEDIUM issues fixed:**
- MEDIUM-1: Commentaire "Oracle recursion" supprimé (trompeur, pas de recursion)
- MEDIUM-2: Documentation enrichie pour `get_allowed_environments_for_user` avec exemple
- MEDIUM-3: Commentaire sprint-status précisé (8 tests ajoutés + 2 réactivés)

**2 LOW issues fixed:**
- LOW-1: Double transformation acceptée (performance mineure)
- LOW-2: Docstring test corrigée (Task 2.1 au lieu de AC1)

**Signature fonctionnelle modifiée:**
- `_validate_environment_against_inventory(environment, *, user_id=None)` - ajout user_id pour audit trail
- Tous les appels mis à jour avec `user_id=request.user.id`

**Impact fixes:**
- Sécurité renforcée: pas d'exécution si env invalide ou inventaire down
- SOC1 compliance: audit trail complet des tentatives invalides
- Tests corrigés: validation logique correcte
- Documentation améliorée: clarté sur comportement raw+normalized

### File List

- `idp-portal/django_backend/inventory/services.py` (modified - MEDIUM-1 fix)
- `idp-portal/django_backend/inventory/tests/test_services.py` (modified - HIGH-1, LOW-2 fixes)
- `idp-portal/django_backend/executions/views.py` (modified - HIGH-2, HIGH-3, HIGH-4, HIGH-5 fixes)
- `idp-portal/django_backend/executions/tests/test_environment_validation.py` (modified)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified - MEDIUM-3 fix)
