# Vérification du rapport de review adversarial — Story 20.1

**Date:** 2026-02-08  
**Source:** Terminal output (code review adversarial), vérification par analyse du code et des fichiers.

---

## Résumé

| Catégorie | Revue affirme | Vérification |
|-----------|----------------|--------------|
| HIGH-3 (UserFactory non utilisé) | ✅ **CONFIRMÉ** | Voir détail ci-dessous |
| HIGH-5 (KNOWN_ISSUES 180) | ⚠️ **Partiel** | Formulation correcte ; interprétation "false impression" subjective |
| HIGH-6 (AC pour mauvaises raisons) | ✅ **CONFIRMÉ** | Story décrit UserFactory, les vrais correctifs sont autres |
| HIGH-7 (OracleJSONField non testé en catalog) | ✅ **CONFIRMÉ** | Aucun test catalog ne vérifie le rejet de `execution_steps` string |
| MEDIUM-1 (RefEngine/RefPlatform manquants) | ✅ **CONFIRMÉ** | Uniquement test_admin_views a le setup |
| MEDIUM-2 (Constantes UserProfile) | ❌ **NON APPLICABLE** | Pas de classe `UserProfile` dans idp_auth |
| MEDIUM-3 (Pas de test régression double transition) | ✅ **CONFIRMÉ** | Aucun test dédié "double transition" |
| LOW-1 (Mix pytest + TestCase) | ✅ **CONFIRMÉ** | Plusieurs tests catalog |
| LOW-3 (README vs code) | ✅ **CONFIRMÉ** | README recommande UserFactory, les tests utilisent User.objects.create() |

---

## Détail des vérifications

### HIGH-3 : UserFactory non utilisé dans catalog (et workflow_runtime)

**Vérification :**
- `catalog/tests/` : **aucune occurrence de `UserFactory`**. Toutes les créations d’utilisateur passent par `User.objects.create(...)` dans :
  - test_admin_views.py (2)
  - test_catalog_views.py (1)
  - test_tags_views.py (1)
  - test_services.py (1)
  - test_edge_cases.py (7)
  - test_managers.py (2)
  - test_models.py (2)
  - test_story_18_1.py, test_story_18_3.py, test_performance.py, test_validation.py, test_workflow_steps_integration.py
- `executions/tests/test_workflow_runtime.py` : **4 occurrences de `User.objects.create(...)`**, aucune de `UserFactory`.

**Conclusion :** La story 20.1 indique "UserFactory replacement" dans la section File Structure Requirements, et les AC parlent de "fixtures User correctes" / "UserFactory", mais le code n’utilise pas UserFactory. **HIGH-3 confirmé.**

---

### HIGH-5 : KNOWN_ISSUES et les 180 échecs "pre-existing"

**Vérification :**
- `tests/KNOWN_ISSUES.md` contient bien :  
  *"Story 20.1 Progress: +96 tests fixed... Remaining 180 failures are pre-existing issues in other areas (auth, security, inventory, execution, reference)."*
- Les 180 échecs sont bien catégorisés (ISSUE-001 à 018, etc.) dans auth, security, reference, health, inventory, execution, etc.

**Conclusion :** La formulation est factuellement correcte. L’affirmation de la revue selon laquelle cela crée une "false impression" est une **interprétation** (on peut comprendre que la story 20.1 a "résolu catalog/workflow et laissé 180 autres"). Pour éviter toute ambiguïté, on pourrait préciser dans KNOWN_ISSUES que ces 180 échecs **existaient déjà avant** la story 20.1.

---

### HIGH-6 : AC1/AC2 atteints pour d’autres raisons que UserFactory

**Vérification :**
- Story 20.1 (Dev Agent Record) :  
  *"Les problèmes réels n'étaient PAS des `is_staff` TypeError"* ; correctifs réels : double transition de statut, signature API `list_all()`, `delete_action()` User, pagination dict, contrainte CHECK, RefEngine/RefPlatform, `referenced_action_id` dans workflow.
- Titre / AC de la story parlent de "fixtures User" et "UserFactory".
- Les tests passent (37 catalog, 3 workflow_runtime) mais pas grâce au remplacement User → UserFactory.

**Conclusion :** La description de la story et les AC ne reflètent pas les vrais correctifs. **HIGH-6 confirmé.** Une mise à jour de la story (titre / AC / completion notes) pour refléter les vrais correctifs serait pertinente.

---

### HIGH-7 : OracleJSONField non testé dans les tests catalog

**Vérification :**
- Les tests catalog utilisent surtout `CatalogService.create_action()` ou `Action.objects.create()` avec des champs non-JSON / engine/platform.
- `test_models.py` utilise `action.execution_steps = complex_execution_steps` (liste), donc conforme à OracleJSONField.
- Aucun test catalog ne vérifie explicitement qu’un `Action.objects.create(..., execution_steps='[...]')` (string) échoue ou est rejeté.

**Conclusion :** Il n’y a pas de test de non-régression pour le piège "string vs list/dict" sur `execution_steps` dans catalog. **HIGH-7 confirmé.**

---

### MEDIUM-1 : RefEngine/RefPlatform manquants dans 3 fichiers

**Vérification :**
- `test_admin_views.py` :  
  `RefEngine.objects.get_or_create(code='Oracle', ...)` et `RefPlatform.objects.get_or_create(code='AAP', ...)` dans `setUp`.
- `test_catalog_views.py` : importe `RefEngine, RefPlatform` mais **aucun** `get_or_create` (ou `create`) dans `setUp` ; utilise `CatalogService.create_action()` avec engine/platform.
- `test_tags_views.py` : **n’importe pas** RefEngine/RefPlatform ; pas de setup.
- `test_services.py` : pas d’import RefEngine/RefPlatform ; pas de setup.

**Conclusion :** Seul test_admin_views assure la présence des références. Les autres fichiers s’appuient sur le service ou une DB déjà peuplée. **MEDIUM-1 confirmé** (setup incohérent / fragile si la validation exige ces refs).

---

### MEDIUM-2 : Constantes UserProfile au lieu de chaînes

**Vérification :**
- `idp_auth/models.py` : modèle `User` avec `profile = models.CharField(max_length=50, ...)`. **Aucune classe `UserProfile`** avec constantes (DBA, DBOPS, etc.).

**Conclusion :** La revue suggère `UserProfile.DBA` ; cette constante **n’existe pas** dans le projet. **MEDIUM-2 non applicable** en l’état. La remarque sur les chaînes en dur ('dba', 'dbops', 'DBA') reste valide pour cohérence / maintenabilité.

---

### MEDIUM-3 : Pas de test de régression "double transition"

**Vérification :**
- test_catalog_views et test_tags_views utilisent le pattern "créer en DRAFT puis `update_status(..., 'publish')`" (commentaires "Create action as DRAFT then publish").
- test_services a `test_update_status_publish` qui vérifie la transition publish.
- Aucun test ne s’intitule ou ne vise explicitement la régression : "création en DRAFT + publish ne doit pas provoquer de double transition (ex. PUBLISHED→DRAFT avant publish)".

**Conclusion :** Le correctif "double transition" est en place, mais il n’y a pas de test dédié pour cette régression. **MEDIUM-3 confirmé.**

---

### LOW-1 : Mix pytest + TestCase

**Vérification :**
- Exemple dans `test_catalog_views.py` : `@pytest.mark.django_db` sur la classe et `class TestCatalogActionViewSet(TestCase):`.
- Même pattern dans test_tags_views, test_services, etc.

**Conclusion :** Mix confirmé. **LOW-1 confirmé.**

---

### LOW-3 : README "Common Pitfalls" vs code

**Vérification :**
- `tests/README.md` : "TOUJOURS utiliser UserFactory", "JAMAIS User.objects.create(is_staff=True)", exemples avec `UserFactory`, checklist "J'utilise UserFactory (pas User.objects.create())".
- Les tests catalog utilisent massivement `User.objects.create(...)` (sans is_staff, avec profile='DBA' ou 'dba').

**Conclusion :** La doc recommande UserFactory ; le code ne l’applique pas. **LOW-3 confirmé.**

---

## Non vérifié (dépend de l’état Git au moment du review)

- **HIGH-4 / MEDIUM-4 / MEDIUM-5** : Fichiers modifiés hors scope (frontend, node_modules, V056, core/fields.py). Le git status en début de conversation montrait bien `M core/fields.py` et `D .../V056__....DISABLED`. Une vérification git diff / log au moment du review permettrait de confirmer si ces changements sont liés à la story 20.1 ou à d’autres branches.

---

## Recommandations

1. **Story 20.1** : Mettre à jour la description / AC / completion notes pour refléter les vrais correctifs (transitions, API, RefEngine/RefPlatform, referenced_action_id), et ne pas laisser croire que le correctif principal était le remplacement par UserFactory.
2. **Tests catalog** : À terme, aligner sur les guidelines (UserFactory, RefEngine/RefPlatform en setUp où nécessaire, style pytest cohérent) et ajouter si pertinent :
   - un test de régression pour la double transition,
   - un test sur OracleJSONField (rejet ou comportement attendu pour `execution_steps` string).
3. **KNOWN_ISSUES.md** : Optionnel : préciser une phrase du type "Ces 180 échecs existaient déjà avant la story 20.1 (hors périmètre catalog/workflow)."
4. **MEDIUM-2** : Si on souhaite éviter les chaînes en dur pour les profils, introduire des constantes (p.ex. dans `idp_auth` ou `core`) puis les utiliser dans les tests ; la suggestion "UserProfile.DBA" n’est pas applicable tant que ce type n’existe pas.
