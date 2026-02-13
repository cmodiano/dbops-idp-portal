# Epic 21 : Inventaire — source unique des environnements

**En tant que** équipe produit et utilisateurs du portail,  
**je veux** que l'inventaire soit la seule source de vérité pour les environnements, sans normalisation ni liste hardcodée,  
**afin de** accepter toute valeur présente dans l'inventaire (ex. `lab`, `dev`, `staging`, `prod`), éviter les cascades de requêtes Oracle et les warnings, et permettre l'ajout de nouveaux environnements sans migration.

---

## Contexte

Actuellement, `_normalize_environment` dans `inventory/services.py` impose une liste fixe (`dev`, `staging`, `prod`), appelle récursivement `list_environments()` pour valider des valeurs inconnues, et force les valeurs non reconnues (ex. `lab`) vers `dev`. Cela provoque :

1. **Récursion / cascade** : pour chaque cible avec environnement inconnu, une lecture Oracle complète
2. **Incohérence** : l'inventaire est censé être la source de vérité (Story 13.7), mais on réécrit ses valeurs
3. **Problèmes de perf** : explosion de logs et de requêtes Oracle au clic sur une action du catalogue

Cet epic supprime la normalisation et fait que tout le portail consomme directement les valeurs renvoyées par l'inventaire.

---

## Portée (scope)

### Backend

- `inventory/services.py` : lecture brute des environnements depuis Oracle, suppression de `_normalize_environment` ou limitation aux alias legacy (certif→staging) sans appel à `list_environments`
- `list_targets_for_user`, `get_allowed_environments_for_user` : comparaison case-insensitive avec les valeurs inventaire, pas de normalisation
- Profils : `ENVIRONMENTS_JSON` contient des valeurs venant de l'inventaire (UI admin utilise `useEnvironments`)
- Exécutions : `_validate_environment_against_inventory`, `change_type_config`, `impact_rules` — lookup case-insensitive, fallback `default_impact_level` si pas de règle pour l'env

### Frontend

- **Editeurs admin** : `ImpactRulesEditor`, `StepsEditor`, `ChangeTypeConfig`, `RemediationRulesEditor` — remplacer les listes hardcodées par `useEnvironments()`
- **TargetSelectionStep** : supprimer le fallback `['dev','staging','prod']`, utiliser uniquement l'inventaire
- **Labels** : `ENVIRONMENT_LABELS` dynamique — env inconnu affiché tel quel ou avec capitalisation
- **Type** : `ExecutionEnvironment` étendu à `string` pour accepter `lab`, etc.

### Fichiers impactés

| Zone | Fichiers |
|------|----------|
| Backend inventory | `inventory/services.py`, `inventory/tests/test_services.py` |
| Backend catalog | `catalog/views.py` (aucun changement si permissions utilisent déjà list_environments) |
| Backend executions | `executions/views.py` (impact/change_type lookup minimal) |
| Frontend admin | `ImpactRulesEditor.tsx`, `impactRulesSchema.ts`, `StepsEditor.tsx`, `ChangeTypeConfig.tsx`, `RemediationRulesEditor.tsx` |
| Frontend catalog | `TargetSelectionStep.tsx`, `ConfirmationStep.tsx`, `TargetSelector.tsx` |
| Frontend hooks | `useEnvironments.ts` |
| Frontend types | `api.ts` |

---

## Definition of Done

- [ ] Les valeurs ENVIRONMENT de l'inventaire sont utilisées telles quelles (trim + lowercase pour cohérence)
- [ ] Aucun appel récursif à `list_environments()` depuis `_normalize_environment`
- [ ] Les profils peuvent référencer tous les environnements présents dans l'inventaire
- [ ] Les editeurs admin (impact, steps, change type, remediation) utilisent la liste dynamique de l'inventaire
- [ ] TargetSelectionStep n'a plus de fallback hardcodé
- [ ] Les environnements inconnus (ex. `lab`) s'affichent correctement dans l'UI
- [ ] Les tests backend et frontend passent avec les nouvelles valeurs

---

## Stories proposées

### Story 21.1 : Backend — Supprimer normalisation inventaire et utiliser valeurs brutes

**En tant que** développeur backend,  
**je veux** que la lecture de l'inventaire Oracle retourne les valeurs ENVIRONMENT telles quelles (avec trim/lowercase uniquement),  
**afin de** éliminer la récursion et les warnings `unknown_environment_value_defaulted`, et faire de l'inventaire la source unique.

**Acceptance Criteria:**

**Given** `_read_oracle_inventory` dans `inventory/services.py`  
**When** une ligne Oracle contient `ENVIRONMENT = 'lab'`  
**Then** la valeur retournée est `'lab'` (ou `'lab'.lower()` pour cohérence), sans appel à `_normalize_environment`  
**And** aucun warning `unknown_environment_value_defaulted` n'est loggé

**Given** la méthode `_normalize_environment`  
**When** on la supprime ou la simplifie  
**Then** elle ne contient plus d'appel à `list_environments()`  
**And** optionnel : on conserve uniquement un mapping d'alias pour legacy (ex. `certif`→`staging`) sans appel récursif

**Given** `list_environments()`  
**When** elle extrait les environnements distincts des targets  
**Then** elle utilise les valeurs brutes des targets (sans normalisation dans la boucle)  
**And** le cache `_environments_cache` continue de fonctionner

**Fichiers :** `inventory/services.py`

---

### Story 21.2 : Backend — Ajuster profile/env matching et exécutions

**En tant que** développeur backend,  
**je veux** que les profils et les exécutions comparent les environnements de manière case-insensitive sans normalisation forcée,  
**afin de** accepter les valeurs de l'inventaire et des profils de façon cohérente.

**Acceptance Criteria:**

**Given** `list_targets_for_user` et `get_allowed_environments_for_user`  
**When** un profil a `ENVIRONMENTS_JSON = ["lab", "dev"]` et l'inventaire contient `lab`, `dev`  
**Then** la comparaison est case-insensitive  
**And** les targets avec `environment: 'lab'` sont autorisés  
**And** on n'appelle plus `_normalize_environment` sur les valeurs de profil (ou uniquement pour alias legacy)

**Given** `_validate_environment_against_inventory` dans `executions/views.py`  
**When** l'environnement soumis est `lab` et l'inventaire le contient  
**Then** la validation réussit  
**And** aucun fallback vers `dev` n'est appliqué

**Given** `change_type_config` et `impact_rules` lookup  
**When** l'environnement d'exécution est `lab`  
**Then** le lookup utilise `env_upper` ou comparaison case-insensitive  
**And** si aucune règle n'existe pour `lab`, `default_impact_level` est utilisé pour impact  
**And** si aucune config change_type n'existe pour `lab`, pas de changement requis (comportement par défaut)

**Fichiers :** `inventory/services.py`, `executions/views.py`

---

### Story 21.3 : Tests backend — inventaire, exécutions, profils

**En tant que** développeur,  
**je veux** que les tests couvrent les nouveaux comportements (valeurs brutes, profils avec `lab`, exécutions avec env inconnu),  
**afin de** éviter les régressions et documenter le comportement attendu.

**Acceptance Criteria:**

**Given** les tests `inventory/tests/test_services.py`  
**When** on exécute la suite  
**Then** les tests de `_normalize_environment` sont mis à jour ou supprimés selon le choix (suppression vs alias uniquement)  
**And** des tests vérifient que `list_targets` retourne des environnements bruts (ex. `lab`)  
**And** des tests vérifient que `list_environments()` retourne les valeurs distinctes sans normalisation

**Given** les tests d'exécution et de profils  
**When** un profil a `environments: ['lab']` et l'inventaire contient `lab`  
**Then** les tests vérifient l'accès autorisé  
**And** les tests de `_validate_environment_against_inventory` avec `lab` passent

**Fichiers :** `inventory/tests/test_services.py`, `executions/tests/`, `profiles/tests/` si applicable

---

### Story 21.4 : Frontend — Editeurs admin avec environnements dynamiques

**En tant que** DBOPS,  
**je veux** que les editeurs d'actions (règles d'impact, étapes, changement ServiceNow, règles de remédiation) proposent la liste des environnements issue de l'inventaire,  
**afin de** configurer des règles pour tous les environnements existants (ex. `lab`, `dev`, `staging`, `prod`) sans liste fixe.

**Acceptance Criteria:**

**Given** `ImpactRulesEditor`  
**When** j'ajoute une règle d'impact  
**Then** le dropdown Environnement affiche les options de `useEnvironments()` (ou équivalent)  
**And** `IMPACT_ENVIRONMENTS` hardcodé est remplacé par la liste dynamique

**Given** `StepsEditor`  
**When** je configure `conditional_environments` pour une étape ServiceNow  
**Then** le multi-select utilise les environnements de l'inventaire  
**And** `ENVIRONMENT_OPTIONS = ['DEV','STAGING','PROD']` est remplacé

**Given** `ChangeTypeConfig`  
**When** je configure le changement requis par environnement  
**Then** la grille affiche une ligne par environnement de l'inventaire  
**And** `ENVIRONMENTS = ['DEV','STAGING','PROD']` est remplacé  
**And** si l'inventaire retourne `['dev','staging','prod','lab']`, les 4 environnements sont affichés

**Given** `RemediationRulesEditor`  
**When** j'ajoute une règle de remédiation  
**Then** le champ `environments` utilise les options de l'inventaire  
**And** la valeur par défaut d'une nouvelle règle peut être vide ou les envs courants (pas hardcodé)

**Fichiers :** `ImpactRulesEditor.tsx`, `impactRulesSchema.ts`, `StepsEditor.tsx`, `ChangeTypeConfig.tsx`, `RemediationRulesEditor.tsx`

---

### Story 21.5 : Frontend — TargetSelectionStep, labels et type ExecutionEnvironment

**En tant que** DBA ou utilisateur,  
**je veux** que la sélection d'environnement et l'affichage des labels utilisent les valeurs de l'inventaire sans fallback hardcodé,  
**afin de** pouvoir exécuter des actions sur des environnements comme `lab` et les afficher correctement.

**Acceptance Criteria:**

**Given** `TargetSelectionStep`  
**When** le cache d'environnements (`environmentsCache`) est chargé  
**Then** le Select Environnement utilise uniquement ces valeurs  
**And** le fallback `['dev','staging','prod']` est supprimé  
**And** si le cache est vide, un état de chargement ou d'erreur approprié est affiché

**Given** `ENVIRONMENT_LABELS` dans `TargetSelectionStep`, `ConfirmationStep`, `TargetSelector`  
**When** un environnement n'est pas dans la map (ex. `lab`)  
**Then** on affiche `labels[env.toLowerCase()] || env.charAt(0).toUpperCase() + env.slice(1)` ou équivalent  
**And** l'utilisateur voit "Lab" ou "lab" selon le format choisi, jamais une valeur vide

**Given** le type `ExecutionEnvironment` dans `api.ts`  
**When** on étend le type  
**Then** `ExecutionEnvironment` devient `string` (ou union étendue incluant `'lab'` et autres)  
**And** les usages sont mis à jour si nécessaire (typage strict)

**Fichiers :** `TargetSelectionStep.tsx`, `ConfirmationStep.tsx`, `TargetSelector.tsx`, `useEnvironments.ts`, `api.ts`

---

### Story 21.6 (optionnel) : Validation des environnements de profil à la sauvegarde

**En tant que** DBOPS,  
**je veux** que la sauvegarde d'un profil valide que les environnements sélectionnés existent dans l'inventaire,  
**afin de** éviter les typo et les références à des environnements obsolètes.

**Acceptance Criteria:**

**Given** le formulaire de profil (ProfileForm / ProfileWizard)  
**When** je sauvegarde un profil avec `environments: ['lab', 'invalid_env']`  
**Then** le backend vérifie que chaque valeur existe dans `list_environments()`  
**And** si `invalid_env` n'existe pas, une erreur de validation est retournée  
**And** un message explicite indique les environnements invalides

**Ou** : validation côté frontend uniquement (warning si env pas dans la liste) — à définir selon priorité.

**Fichiers :** `profiles/` (backend et/ou frontend)

---

## Priorisation recommandée

| Story | Priorité | Impact |
|-------|----------|--------|
| 21.1 | Haute | Élimine récursion et cascade Oracle |
| 21.2 | Haute | Cohérence profils et exécutions |
| 21.3 | Haute | Confiance dans les changements |
| 21.4 | Moyenne | Admin peut configurer tous les envs |
| 21.5 | Moyenne | UX exécution et affichage |
| 21.6 | Basse | Qualité des données profils |

---

## Référence

- Plan : `.cursor/plans/inventory_as_environment_source_026f79bf.plan.md`
- Story 13.7 : Ref environnements et technologies via tables
- `docs/frontend/catalog-filtering.md` : Modèle target-first
