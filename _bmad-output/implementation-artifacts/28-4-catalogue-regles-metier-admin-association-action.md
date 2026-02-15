# Story 28.4 : Catalogue de règles métier et association par action

Status: done

## Story

En tant que **DBOPS**,
Je veux **définir des règles métier réutilisables dans un onglet Admin dédié, puis associer une règle prédéfinie à une action** (au lieu de saisir le JSON à chaque fois),
Afin que **les mêmes règles (ex. « revue Terraform si sku_name modifié ») soient réutilisables sur plusieurs actions, et que la maintenance soit centralisée**.

## Contexte Epic 28

**Objectif Epic :** Clarifier et étendre le modèle des règles métier applicables à une action : schéma JSON (business_rule_policies) stocké en base, éditable via un menu dédié ; **moteur de règles métier intelligent** s'adaptant aux différentes plateformes (Terraform, AAP, Azure DevOps, etc.) via des interpréteurs de sortie d'étape ; évaluation des politiques pour déclencher revue DBA ou auto-approbation.

**Stories Epic 28 :**
- **Story 28.1** (done) : Modèle et schéma business_rule_policies — backend + validation + UI admin
- **Story 28.2** (done) : PolicyEvaluator et politique Terraform plan (require_review_if_modified)
- **Story 28.3** (done) : Moteur de règles métier intelligent multi-plateforme (RuleEngine + OutputInterpreter)
- **Story 28.4** (cette story) : Catalogue de règles métier et association par action

**Dépendances :**
- ✅ Story 28.1 complétée : champ business_rule_policies, schéma JSON défini, éditeur admin inline
- ✅ Story 28.2 complétée : PolicyEvaluator + parsing Terraform plan + intégration workflow
- ✅ Story 28.3 complétée : RuleEngine + OutputInterpreter (TerraformPlanInterpreter, AAPOutputInterpreter)

**Référence :** [Source: _bmad-output/planning-artifacts/epics.md — Epic 28, Story 28-4]

## Acceptance Criteria

### AC1 — Nouvel onglet Admin « Règles métier »

**Given** un utilisateur DBOPS accède au portail,
**When** il navigue vers la page Admin,
**Then** un nouvel onglet « Règles métier » est visible dans le menu Admin,
**And** l'onglet est positionné après « Intégrations » et avant « Catégories »,
**And** la clé de navigation est `business-rules` (URL : /admin#business-rules).

### AC2 — CRUD règles métier prédéfinies

**Given** un DBOPS accède à l'onglet Admin « Règles métier »,
**When** l'onglet est affiché,
**Then** une liste des règles métier prédéfinies est visible avec colonnes :
- **Nom** (name) : nom lisible de la règle
- **Description** (description) : description courte de la règle
- **Type** (step_type) : terraform_cloud, aap, azure_devops, etc.
- **Actif** (is_active) : badge Oui/Non
- **Actions** : boutons Modifier, Supprimer

**And** un bouton « Créer règle métier » est affiché en haut de la liste,
**And** la liste est paginée (20 règles par page),
**And** un filtre par `step_type` (dropdown) permet de filtrer les règles,
**And** un filtre par `is_active` (checkbox « Actifs seulement ») permet de filtrer les règles actives.

**Given** un DBOPS clique sur « Créer règle métier »,
**When** le modal de création s'ouvre,
**Then** un formulaire structuré est affiché avec champs :
- **Nom** (requis, max 200 caractères)
- **Description** (optionnel, textarea, max 500 caractères)
- **Règle JSON** (requis, éditeur JSON avec validation temps réel)
- **Actif** (checkbox, par défaut coché)

**And** un bouton « Insérer exemple Terraform » insère un exemple de règle review_if_modified,
**And** un bouton « Insérer exemple AAP » insère un exemple de règle AAP,
**And** un Help popover explique la structure du JSON (réutilise documentation BusinessRulePoliciesEditor),
**And** la validation backend est appelée lors de la sauvegarde (POST /api/v1/admin/business-rule-policies/),
**And** une notification de succès s'affiche après création,
**And** la liste est rafraîchie automatiquement.

**Given** un DBOPS clique sur « Modifier » une règle,
**When** le modal d'édition s'ouvre,
**Then** le formulaire est pré-rempli avec les données de la règle,
**And** la sauvegarde appelle PATCH /api/v1/admin/business-rule-policies/{id}/,
**And** une notification de succès s'affiche après modification,
**And** la liste est rafraîchie automatiquement.

**Given** un DBOPS clique sur « Supprimer » une règle,
**When** une confirmation est demandée,
**Then** un message avertit « Cette règle est utilisée par X action(s). Supprimer cette règle rendra les actions associées sans règle. Continuer ? »,
**And** si confirmé, la suppression appelle DELETE /api/v1/admin/business-rule-policies/{id}/,
**And** une notification de succès s'affiche après suppression,
**And** la liste est rafraîchie automatiquement.

### AC3 — Backend : modèle BusinessRulePolicy

**Given** le backend Django,
**When** on définit le modèle de données pour les règles métier,
**Then** un nouveau modèle `BusinessRulePolicy` est créé dans `catalog/models.py` :
- **id** : PK auto-incrémenté
- **name** : VARCHAR(200), NOT NULL, UNIQUE
- **description** : VARCHAR(500), NULL
- **policy_json** : CLOB (OracleJSONField), NOT NULL
- **is_active** : BOOLEAN, DEFAULT TRUE
- **created_at** : TIMESTAMP, auto_now_add
- **updated_at** : TIMESTAMP, auto_now
- **created_by_id** : FK vers User, NOT NULL

**And** le modèle a une méthode `clean()` qui valide policy_json avec validate_business_rule_policies(),
**And** le modèle a une méthode `__str__()` qui retourne name,
**And** Meta.db_table = 'BUSINESS_RULE_POLICIES',
**And** Meta.ordering = ['name'],
**And** une migration V074 est créée pour ajouter la table BUSINESS_RULE_POLICIES.

### AC4 — Backend : API CRUD BusinessRulePolicy

**Given** le backend DRF,
**When** on expose l'API CRUD pour les règles métier,
**Then** un ViewSet `BusinessRulePolicyViewSet` est créé dans `catalog/views.py` :
- **GET /api/v1/admin/business-rule-policies/** : liste paginée avec filtres `?step_type=terraform_cloud` et `?is_active=true`
- **POST /api/v1/admin/business-rule-policies/** : création avec validation policy_json
- **GET /api/v1/admin/business-rule-policies/{id}/** : détail d'une règle
- **PATCH /api/v1/admin/business-rule-policies/{id}/** : modification avec validation policy_json
- **DELETE /api/v1/admin/business-rule-policies/{id}/** : suppression (soft-delete si is_active=False ou hard-delete)

**And** les permissions requises sont : IsAuthenticated + IsDBAOrDBOPS,
**And** la création enregistre created_by = request.user,
**And** la validation policy_json utilise validate_business_rule_policies() existant,
**And** l'audit trail est créé pour chaque opération (POLICY_CREATED, POLICY_UPDATED, POLICY_DELETED),
**And** les serializers `BusinessRulePolicySerializer` et `BusinessRulePolicyListSerializer` sont créés.

**And** le filtre `step_type` extrait le `when.step_type` du policy_json pour filtrer,
**And** le filtre `is_active` filtre les règles actives/inactives.

### AC5 — Extension modèle Action : FK business_rule_policy_id

**Given** le modèle Action existant,
**When** on étend le modèle pour supporter l'association à une règle prédéfinie,
**Then** un nouveau champ `business_rule_policy_id` (FK vers BusinessRulePolicy, NULL, SET_NULL on delete) est ajouté,
**And** le champ business_rule_policies (JSON inline) reste présent pour rétrocompatibilité,
**And** une migration V074 (même migration que AC3) ajoute la colonne BUSINESS_RULE_POLICY_ID,
**And** une contrainte CHECK garantit que seulement l'un des deux champs est renseigné (business_rule_policy_id XOR business_rule_policies non NULL).

**And** le modèle Action a une propriété computed `effective_business_rule_policies` qui :
- Retourne business_rule_policy.policy_json si business_rule_policy_id est renseigné
- Retourne business_rule_policies si business_rule_policies est renseigné
- Retourne None si aucun des deux n'est renseigné

**And** le serializer ActionDetailSerializer expose :
- `business_rule_policy_id` (FK, nullable)
- `business_rule_policy_name` (computed, nom de la règle si FK renseigné)
- `business_rule_policies` (JSON inline legacy)

### AC6 — ActionWizard : sélecteur règle prédéfinie

**Given** le formulaire ActionWizard (Step 3 : Impact & Change),
**When** la section « Règles métier » est affichée,
**Then** un sélecteur Radio.Group avec 2 options est affiché :
- **Option 1 : « Règle prédéfinie »** (par défaut) :
  - Un Select component affiche la liste des règles actives (GET /api/v1/admin/business-rule-policies/?is_active=true)
  - Chaque option affiche : `{name} — {description}` (avec step_type en badge)
  - Un bouton « Voir JSON » ouvre un modal read-only avec le policy_json de la règle sélectionnée
  - Filtre par step_type (dropdown) pour filtrer les règles affichées
  - Option « Aucune » pour ne pas associer de règle
- **Option 2 : « Règle personnalisée (inline) »** (legacy) :
  - Affiche l'éditeur BusinessRulePoliciesEditor existant (Story 28.1)
  - Permet de saisir un JSON custom pour des cas avancés

**And** la sauvegarde appelle PATCH /api/v1/admin/actions/{id}/ avec :
- Si option 1 sélectionnée : `business_rule_policy_id` = ID sélectionné, `business_rule_policies` = null
- Si option 2 sélectionnée : `business_rule_policy_id` = null, `business_rule_policies` = JSON saisi

**And** lors de l'édition d'une action existante :
- Si business_rule_policy_id est renseigné → option 1 sélectionnée avec règle chargée
- Si business_rule_policies est renseigné → option 2 sélectionnée avec JSON affiché

### AC7 — RuleEngine : chargement règle prédéfinie

**Given** le RuleEngine (Story 28.3),
**When** il charge les politiques d'une action,
**Then** la méthode `_load_policies()` est modifiée pour :
- Si action.business_rule_policy_id est renseigné :
  - Charger business_rule_policy = BusinessRulePolicy.objects.get(id=action.business_rule_policy_id)
  - Vérifier business_rule_policy.is_active == True (sinon log warning + retourner None)
  - Retourner business_rule_policy.policy_json
- Si action.business_rule_policies est renseigné :
  - Retourner action.business_rule_policies (fallback legacy)
- Sinon :
  - Retourner None (pas de règles définies)

**And** un log structuré est ajouté pour tracer la source de la règle (policy_source="predefined" ou "inline"),
**And** le correlation_id est propagé dans tous les logs,
**And** les tests Story 28.3 continuent de passer (0 régression).

### AC8 — Migration données : conversion inline → prédéfinie (optionnel)

**Given** des actions existantes avec business_rule_policies inline,
**When** un DBOPS souhaite migrer vers des règles prédéfinies,
**Then** un script Django management command `migrate_inline_policies` est fourni :
- Analyse toutes les actions avec business_rule_policies non NULL
- Détecte les règles identiques (comparaison JSON normalisée)
- Propose de créer des règles prédéfinies pour les doublons
- Met à jour les actions avec business_rule_policy_id vers la règle créée
- Nullifie business_rule_policies après migration

**And** le script est documenté dans README backend avec exemple d'utilisation,
**And** le script est DRY-RUN par défaut (--apply pour exécuter réellement),
**And** un rapport de migration est généré (nombre d'actions migrées, règles créées).

### AC9 — Tests backend

**And** des tests unitaires (`catalog/tests/test_business_rule_policy_api.py`) valident :
- **test_create_business_rule_policy** : POST crée règle avec audit trail
- **test_create_invalid_policy_json** : POST avec JSON invalide → 400
- **test_list_business_rule_policies** : GET retourne liste paginée
- **test_filter_by_step_type** : GET ?step_type=terraform_cloud filtre correctement
- **test_filter_by_is_active** : GET ?is_active=true filtre actifs seulement
- **test_update_business_rule_policy** : PATCH met à jour règle
- **test_delete_business_rule_policy** : DELETE supprime règle
- **test_action_with_predefined_policy** : Action.effective_business_rule_policies retourne policy_json de la FK
- **test_action_with_inline_policy** : Action.effective_business_rule_policies retourne business_rule_policies inline
- **test_action_with_both_policies_fails** : Contrainte CHECK échoue si les deux sont renseignés

**And** des tests d'intégration (`executions/tests/test_policy_integration.py`) valident :
- **test_rule_engine_with_predefined_policy** : RuleEngine charge policy_json depuis FK
- **test_rule_engine_with_inactive_policy** : RuleEngine ignore règle si is_active=False

### AC10 — Tests frontend

**And** des tests frontend (`pages/admin/BusinessRulesPolicyPanel.test.tsx`) valident :
- **test_render_business_rules_list** : Liste des règles affichée
- **test_create_business_rule** : Modal création + sauvegarde réussie
- **test_edit_business_rule** : Modal édition + sauvegarde réussie
- **test_delete_business_rule** : Confirmation + suppression réussie
- **test_filter_by_step_type** : Filtre par step_type fonctionne
- **test_filter_by_is_active** : Filtre actifs seulement fonctionne

**And** des tests frontend (`components/admin/ActionWizard.test.tsx`) valident :
- **test_select_predefined_rule** : Sélection règle prédéfinie + sauvegarde business_rule_policy_id
- **test_select_custom_rule** : Sélection règle custom + sauvegarde business_rule_policies inline
- **test_view_predefined_rule_json** : Modal read-only affiche JSON de la règle
- **test_edit_action_with_predefined_rule** : Chargement action avec FK → option 1 sélectionnée
- **test_edit_action_with_inline_rule** : Chargement action avec JSON inline → option 2 sélectionnée

## Tasks / Subtasks

### Phase 1: Backend — Modèle et Migration

- [x]Task 1: Créer modèle BusinessRulePolicy (AC: #3)
  - [x]1.1: Ouvrir `catalog/models.py`
  - [x]1.2: Créer classe `BusinessRulePolicy(models.Model)` avec champs :
    - id (PK auto)
    - name (CharField 200, unique, not null)
    - description (TextField 500, null)
    - policy_json (OracleJSONField, not null)
    - is_active (BooleanField, default=True)
    - created_at (DateTimeField, auto_now_add)
    - updated_at (DateTimeField, auto_now)
    - created_by (ForeignKey User, on_delete=PROTECT)
  - [x]1.3: Ajouter Meta : db_table='BUSINESS_RULE_POLICIES', ordering=['name']
  - [x]1.4: Implémenter méthode clean() : validate_business_rule_policies(self.policy_json)
  - [x]1.5: Implémenter méthode __str__() : return self.name

- [x]Task 2: Étendre modèle Action avec FK business_rule_policy_id (AC: #5)
  - [x]2.1: Ouvrir `catalog/models.py` classe Action
  - [x]2.2: Ajouter champ business_rule_policy = ForeignKey(BusinessRulePolicy, null=True, on_delete=SET_NULL, related_name='actions')
  - [x]2.3: Ajouter propriété computed `effective_business_rule_policies` :
    - Si business_rule_policy_id : return self.business_rule_policy.policy_json
    - Sinon si business_rule_policies : return self.business_rule_policies
    - Sinon : return None
  - [x]2.4: Ajouter validation clean() : vérifier seulement 1 des 2 champs renseigné (XOR)

- [x]Task 3: Créer migration V074 (AC: #3, #5)
  - [x]3.1: Générer migration : `python manage.py makemigrations catalog`
  - [x]3.2: Créer fichier `database/migrations/V074__add_business_rule_policies_to_actions_catalog.sql`
  - [x]3.3: Script SQL :
    - CREATE TABLE BUSINESS_RULE_POLICIES (id, name, description, policy_json CLOB, is_active, created_at, updated_at, created_by_id FK)
    - ALTER TABLE ACTIONS_CATALOG ADD COLUMN BUSINESS_RULE_POLICY_ID NUMBER NULL
    - ADD CONSTRAINT FK_ACTION_BUSINESS_RULE_POLICY FOREIGN KEY (BUSINESS_RULE_POLICY_ID) REFERENCES BUSINESS_RULE_POLICIES(ID) ON DELETE SET NULL
    - ADD CONSTRAINT CHK_ACTION_POLICY_XOR CHECK ((BUSINESS_RULE_POLICY_ID IS NOT NULL AND BUSINESS_RULE_POLICIES IS NULL) OR (BUSINESS_RULE_POLICY_ID IS NULL AND BUSINESS_RULE_POLICIES IS NOT NULL) OR (BUSINESS_RULE_POLICY_ID IS NULL AND BUSINESS_RULE_POLICIES IS NULL))
  - [x]3.4: Tester migration : `python manage.py migrate --database=default --fake-initial`
  - [x]3.5: Vérifier contrainte XOR fonctionne (INSERT avec les deux → erreur)

### Phase 2: Backend — Serializers et API

- [x]Task 4: Créer serializers BusinessRulePolicy (AC: #4)
  - [x]4.1: Ouvrir `catalog/serializers.py`
  - [x]4.2: Créer `BusinessRulePolicyListSerializer` avec champs : id, name, description, is_active, created_at, step_type (computed depuis policy_json)
  - [x]4.3: Créer `BusinessRulePolicySerializer` (détail + création/édition) avec tous champs + validation policy_json
  - [x]4.4: Méthode validate_policy_json() : appeler validate_business_rule_policies()
  - [x]4.5: Méthode create() : enregistrer created_by = request.user

- [x]Task 5: Étendre ActionDetailSerializer avec FK (AC: #5)
  - [x]5.1: Ouvrir `catalog/serializers.py` classe ActionDetailSerializer
  - [x]5.2: Ajouter champs :
    - business_rule_policy_id (PrimaryKeyRelatedField, nullable)
    - business_rule_policy_name (SerializerMethodField, computed)
  - [x]5.3: Méthode get_business_rule_policy_name() : return obj.business_rule_policy.name if obj.business_rule_policy_id else None
  - [x]5.4: Validation : méthode validate() vérifie XOR business_rule_policy_id / business_rule_policies

- [x]Task 6: Créer ViewSet BusinessRulePolicyViewSet (AC: #4)
  - [x]6.1: Ouvrir `catalog/views.py`
  - [x]6.2: Créer classe BusinessRulePolicyViewSet(ModelViewSet) :
    - queryset = BusinessRulePolicy.objects.all()
    - serializer_class = BusinessRulePolicySerializer (list_serializer_class = BusinessRulePolicyListSerializer)
    - permission_classes = [IsAuthenticated, IsDBAOrDBOPS]
    - filterset_fields = ['is_active']
    - Méthode get_queryset() : filtrer par step_type si ?step_type= fourni (extraire depuis policy_json)
  - [x]6.3: Implémenter méthodes CRUD :
    - list() : GET avec pagination + filtres
    - create() : POST avec audit POLICY_CREATED
    - retrieve() : GET détail
    - update() : PATCH avec audit POLICY_UPDATED
    - destroy() : DELETE avec audit POLICY_DELETED
  - [x]6.4: Ajouter URLs : router.register('admin/business-rule-policies', BusinessRulePolicyViewSet, basename='business-rule-policies')

- [x]Task 7: Ajouter audit trail AuditActionType (AC: #4)
  - [x]7.1: Ouvrir `core/models.py` (ou audit/models.py)
  - [x]7.2: Ajouter enums AuditActionType :
    - POLICY_CREATED = "policy_created"
    - POLICY_UPDATED = "policy_updated"
    - POLICY_DELETED = "policy_deleted"
  - [x]7.3: Intégrer AuditService dans BusinessRulePolicyViewSet (create, update, destroy)

### Phase 3: Backend — RuleEngine Extension

- [x]Task 8: Modifier RuleEngine._load_policies() (AC: #7)
  - [x]8.1: Ouvrir `executions/rule_engine.py` méthode _load_policies()
  - [x]8.2: Ajouter logique :
    - Si action.business_rule_policy_id : charger FK, vérifier is_active, retourner policy_json
    - Sinon si action.business_rule_policies : retourner inline (legacy)
    - Sinon : retourner None
  - [x]8.3: Ajouter log structlog : policy_source="predefined" ou "inline"
  - [x]8.4: Ajouter log warning si FK renseignée mais is_active=False
  - [x]8.5: Vérifier tests Story 28.3 passent (0 régression)

### Phase 4: Backend — Tests Unitaires

- [x]Task 9: Créer tests API BusinessRulePolicy (AC: #9)
  - [x]9.1: Créer `catalog/tests/test_business_rule_policy_api.py`
  - [x]9.2: test_create_business_rule_policy : POST /api/v1/admin/business-rule-policies/ → 201 + audit trail
  - [x]9.3: test_create_invalid_policy_json : POST avec JSON invalide → 400 avec erreurs validation
  - [x]9.4: test_list_business_rule_policies : GET → 200 avec liste paginée
  - [x]9.5: test_filter_by_step_type : GET ?step_type=terraform_cloud → filtré
  - [x]9.6: test_filter_by_is_active : GET ?is_active=true → actifs seulement
  - [x]9.7: test_update_business_rule_policy : PATCH → 200 + audit trail
  - [x]9.8: test_delete_business_rule_policy : DELETE → 204 + audit trail
  - [x]9.9: test_permissions_dbops_only : Non-DBOPS → 403 Forbidden

- [x]Task 10: Créer tests modèle Action avec FK (AC: #9)
  - [x]10.1: Ouvrir `catalog/tests/test_action_model.py`
  - [x]10.2: test_action_with_predefined_policy : Action avec FK → effective_business_rule_policies retourne policy_json
  - [x]10.3: test_action_with_inline_policy : Action avec inline → effective_business_rule_policies retourne JSON inline
  - [x]10.4: test_action_with_no_policy : Action sans règle → effective_business_rule_policies retourne None
  - [x]10.5: test_action_with_both_policies_fails : Créer action avec FK + inline → IntegrityError (contrainte CHECK)

- [x]Task 11: Créer tests intégration RuleEngine (AC: #9)
  - [x]11.1: Ouvrir `executions/tests/test_policy_integration.py`
  - [x]11.2: test_rule_engine_with_predefined_policy : Action avec FK → RuleEngine charge policy_json depuis FK
  - [x]11.3: test_rule_engine_with_inactive_policy : Action avec FK is_active=False → RuleEngine log warning + ignore règle
  - [x]11.4: test_rule_engine_with_inline_policy : Action avec inline → RuleEngine charge inline (fallback)

### Phase 5: Frontend — Onglet Admin « Règles métier »

- [x]Task 12: Créer composant BusinessRulesPolicyPanel (AC: #1, #2)
  - [x]12.1: Créer `frontend/src/pages/admin/BusinessRulesPolicyPanel.tsx`
  - [x]12.2: Structure composant :
    - State : policies, loading, policyModalOpen, editPolicy, filters (step_type, is_active)
    - Fetch : useCallback fetchPolicies() → GET /api/v1/admin/business-rule-policies/
    - Table : colonnes (name, description, step_type badge, is_active badge, actions)
    - Filtres : Select step_type, Checkbox is_active
    - Bouton : « Créer règle métier » → ouvre modal
  - [x]12.3: Méthodes :
    - handleCreate() : POST avec notification succès
    - handleEdit() : PATCH avec notification succès
    - handleDelete() : DELETE avec confirmation (modal.confirm)
  - [x]12.4: Pagination : pageSize=20, pagination={{ current, pageSize, total }}

- [x]Task 13: Créer modal BusinessRulePolicyModal (AC: #2)
  - [x]13.1: Créer `frontend/src/components/admin/BusinessRulePolicyModal.tsx`
  - [x]13.2: Props : open, policy (nullable), onSuccess, onCancel
  - [x]13.3: Champs formulaire :
    - Input name (requis, max 200)
    - TextArea description (optionnel, max 500)
    - BusinessRulePoliciesEditor policy_json (réutiliser existant)
    - Checkbox is_active (par défaut coché)
  - [x]13.4: Boutons : « Annuler », « Enregistrer »
  - [x]13.5: Validation temps réel : validatePoliciesJson() (réutiliser)
  - [x]13.6: Sauvegarde : POST ou PATCH selon mode création/édition

- [x]Task 14: Ajouter onglet « Règles métier » dans AdminPage (AC: #1)
  - [x]14.1: Ouvrir `frontend/src/pages/AdminPage.tsx`
  - [x]14.2: Importer BusinessRulesPolicyPanel
  - [x]14.3: Ajouter onglet dans Tabs items :
    - key: 'business-rules'
    - label: 'Règles métier'
    - children: <BusinessRulesPolicyPanel />
  - [x]14.4: Positionner après 'integrations' et avant 'categories'

### Phase 6: Frontend — ActionWizard Sélecteur

- [x]Task 15: Créer composant BusinessRulePolicySelector (AC: #6)
  - [x]15.1: Créer `frontend/src/components/admin/BusinessRulePolicySelector.tsx`
  - [x]15.2: Props : value (business_rule_policy_id ou business_rule_policies), onChange, mode (create|edit)
  - [x]15.3: State : selectionMode ('predefined' | 'custom'), selectedPolicyId, customPolicyJson
  - [x]15.4: Radio.Group avec 2 options :
    - Option 1 : « Règle prédéfinie » → Select component
    - Option 2 : « Règle personnalisée (inline) » → BusinessRulePoliciesEditor
  - [x]15.5: Select component :
    - Fetch : GET /api/v1/admin/business-rule-policies/?is_active=true
    - Options : {id, name, description, step_type} → afficher "{name} — {description}" + badge step_type
    - Filtre : Select step_type dropdown
    - Bouton « Voir JSON » : Modal read-only avec policy_json
    - Option « Aucune » (id=null)
  - [x]15.6: onChange() : retourner { business_rule_policy_id, business_rule_policies } selon mode

- [x]Task 16: Intégrer BusinessRulePolicySelector dans ActionWizard (AC: #6)
  - [x]16.1: Ouvrir `frontend/src/components/admin/ActionWizard.tsx`
  - [x]16.2: Step 3 « Impact & Change » :
    - Remplacer BusinessRulePoliciesEditor par BusinessRulePolicySelector
    - State : businessRulePolicyId, businessRulePolicies (2 états séparés)
  - [x]16.3: Chargement édition :
    - Si action.business_rule_policy_id : sélectionner mode predefined + charger règle
    - Si action.business_rule_policies : sélectionner mode custom + charger JSON
  - [x]16.4: Sauvegarde :
    - Si mode predefined : PATCH { business_rule_policy_id, business_rule_policies: null }
    - Si mode custom : PATCH { business_rule_policy_id: null, business_rule_policies }

### Phase 7: Backend — Management Command Migration (AC: #8, optionnel)

- [x]Task 17: Créer command migrate_inline_policies (AC: #8)
  - [x]17.1: Créer `catalog/management/commands/migrate_inline_policies.py`
  - [x]17.2: Commande avec options :
    - --dry-run (par défaut) : affiche analyse sans modifier
    - --apply : exécute réellement la migration
  - [x]17.3: Logique :
    - Analyser actions avec business_rule_policies non NULL
    - Détecter règles identiques (normalize JSON + comparaison)
    - Proposer création de règles prédéfinies (name généré, description auto)
    - Créer BusinessRulePolicy (si --apply)
    - Mettre à jour actions avec business_rule_policy_id (si --apply)
    - Nullifier business_rule_policies (si --apply)
  - [x]17.4: Rapport : nombre actions analysées, règles créées, actions migrées
  - [x]17.5: Documentation README backend : section « Migration inline policies »

### Phase 8: Tests Frontend

- [x]Task 18: Créer tests BusinessRulesPolicyPanel (AC: #10)
  - [x]18.1: Créer `frontend/src/pages/admin/BusinessRulesPolicyPanel.test.tsx`
  - [x]18.2: test_render_business_rules_list : mock API, vérifier liste affichée
  - [x]18.3: test_create_business_rule : clic « Créer », saisie, sauvegarde réussie
  - [x]18.4: test_edit_business_rule : clic « Modifier », édition, sauvegarde réussie
  - [x]18.5: test_delete_business_rule : clic « Supprimer », confirmation, suppression réussie
  - [x]18.6: test_filter_by_step_type : filtre dropdown step_type fonctionne
  - [x]18.7: test_filter_by_is_active : checkbox « Actifs seulement » fonctionne

- [x]Task 19: Créer tests BusinessRulePolicySelector (AC: #10)
  - [x]19.1: Créer `frontend/src/components/admin/BusinessRulePolicySelector.test.tsx`
  - [x]19.2: test_select_predefined_rule : sélection règle → onChange { business_rule_policy_id }
  - [x]19.3: test_select_custom_rule : sélection custom → onChange { business_rule_policies }
  - [x]19.4: test_view_predefined_rule_json : clic « Voir JSON » → modal read-only
  - [x]19.5: test_filter_by_step_type : filtre dropdown fonctionne

- [x]Task 20: Étendre tests ActionWizard (AC: #10)
  - [x]20.1: Ouvrir `frontend/src/components/admin/ActionWizard.test.tsx`
  - [x]20.2: test_edit_action_with_predefined_rule : action.business_rule_policy_id → mode predefined
  - [x]20.3: test_edit_action_with_inline_rule : action.business_rule_policies → mode custom
  - [x]20.4: test_save_with_predefined_rule : sélection règle → PATCH { business_rule_policy_id }
  - [x]20.5: test_save_with_custom_rule : saisie JSON → PATCH { business_rule_policies }

### Phase 9: Validation Finale

- [x]Task 21: Validation système backend (AC: #9)
  - [x]21.1: python manage.py check → 0 issues
  - [x]21.2: pytest catalog/tests/test_business_rule_policy_api.py -v → tous passent
  - [x]21.3: pytest catalog/tests/test_action_model.py -v → tous passent
  - [x]21.4: pytest executions/tests/test_policy_integration.py -v → tous passent (y compris nouveaux tests)
  - [x]21.5: pytest executions/tests/ -v → 0 régression Story 28.3

- [x]Task 22: Validation système frontend (AC: #10)
  - [x]22.1: npm run test BusinessRulesPolicyPanel.test.tsx → tous passent
  - [x]22.2: npm run test BusinessRulePolicySelector.test.tsx → tous passent
  - [x]22.3: npm run test ActionWizard.test.tsx → tous passent (y compris nouveaux tests)
  - [x]22.4: npm run test → 0 régression

- [x]Task 23: Test end-to-end (AC: #1, #2, #6)
  - [x]23.1: Créer règle prédéfinie « Revue Terraform SQL sku_name » via UI Admin
  - [x]23.2: Créer action « Provision Azure SQL » avec règle prédéfinie sélectionnée
  - [x]23.3: Exécuter workflow Terraform avec plan modifiant sku_name → require_approval
  - [x]23.4: Modifier règle prédéfinie (ajouter attribut max_size_gb)
  - [x]23.5: Ré-exécuter workflow → nouvelle règle appliquée (max_size_gb détecté)
  - [x]23.6: Dupliquer action → sélectionner même règle prédéfinie (réutilisation)
  - [x]23.7: Désactiver règle prédéfinie (is_active=False) → RuleEngine log warning + ignore

## Dev Notes

### Contexte Architectural — Evolution Story 28.1 → 28.4

**Story 28.1 (état actuel) :**

Actions ont un champ `business_rule_policies` (JSON inline) :
- Éditable via BusinessRulePoliciesEditor dans ActionWizard Step 3
- Validation backend avec validate_business_rule_policies()
- Chaque action duplique la même règle JSON

**Limitations :**
- Duplication : mêmes règles copiées sur plusieurs actions
- Maintenance difficile : modifier une règle → modifier toutes les actions
- Pas de réutilisation : impossible de partager règles entre actions
- Pas de catalogue : pas de vue centralisée des règles métier

**Story 28.4 (architecture cible) :**

```
BusinessRulePolicy (catalogue central)
  ├── id: 1, name: "Revue Terraform SQL sku_name"
  ├── id: 2, name: "Revue AAP failed_tasks production"
  └── id: 3, name: "Auto-approve Terraform dev"

Action (référence FK ou inline legacy)
  ├── action_id: 10 → business_rule_policy_id: 1 (Revue Terraform SQL)
  ├── action_id: 11 → business_rule_policy_id: 1 (même règle réutilisée)
  ├── action_id: 12 → business_rule_policy_id: 2 (Revue AAP)
  └── action_id: 13 → business_rule_policies: {...} (legacy inline)

RuleEngine._load_policies()
  ├── Si action.business_rule_policy_id → charge BusinessRulePolicy.policy_json
  ├── Si action.business_rule_policies → charge inline (fallback)
  └── Sinon → None
```

**Avantages :**
- ✅ Réutilisation : règle créée une fois, associée à N actions
- ✅ Maintenance centralisée : modifier règle → toutes actions mises à jour automatiquement
- ✅ Catalogue : vue Admin dédiée avec filtres, recherche, audit
- ✅ Rétrocompatibilité : inline legacy supporté en fallback
- ✅ is_active : désactiver règle sans supprimer → toutes actions ignorent règle

[Source: _bmad-output/planning-artifacts/epics.md — Epic 28, Story 28.4]

### Technical Requirements — Modèle BusinessRulePolicy

**Table BUSINESS_RULE_POLICIES (Oracle) :**

```sql
CREATE TABLE BUSINESS_RULE_POLICIES (
  ID NUMBER GENERATED BY DEFAULT ON NULL AS IDENTITY PRIMARY KEY,
  NAME VARCHAR2(200) NOT NULL UNIQUE,
  DESCRIPTION VARCHAR2(500),
  POLICY_JSON CLOB NOT NULL,
  IS_ACTIVE NUMBER(1) DEFAULT 1 NOT NULL,
  CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  CREATED_BY_ID NUMBER NOT NULL,
  CONSTRAINT FK_POLICY_CREATED_BY FOREIGN KEY (CREATED_BY_ID) REFERENCES USERS(ID)
);

CREATE INDEX IDX_POLICY_IS_ACTIVE ON BUSINESS_RULE_POLICIES(IS_ACTIVE);
CREATE INDEX IDX_POLICY_CREATED_BY ON BUSINESS_RULE_POLICIES(CREATED_BY_ID);
```

**Modèle Django BusinessRulePolicy :**

```python
# catalog/models.py
class BusinessRulePolicy(models.Model):
    """
    Règle métier prédéfinie réutilisable par plusieurs actions.

    Les règles métier définissent les politiques d'approbation évaluées par le RuleEngine
    lors de l'exécution d'un workflow (ex. revue DBA si plan Terraform modifie sku_name).
    """
    id = models.AutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=200, unique=True, db_column='NAME')
    description = models.TextField(max_length=500, null=True, blank=True, db_column='DESCRIPTION')
    policy_json = OracleJSONField(db_column='POLICY_JSON', help_text='JSON schema business_rule_policies')
    is_active = models.BooleanField(default=True, db_column='IS_ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, db_column='CREATED_BY_ID')

    class Meta:
        db_table = 'BUSINESS_RULE_POLICIES'
        ordering = ['name']

    def clean(self):
        """Valide policy_json avec validate_business_rule_policies()."""
        from catalog.validators import validate_business_rule_policies
        try:
            validate_business_rule_policies(self.policy_json)
        except Exception as e:
            raise ValidationError({'policy_json': str(e)})

    def __str__(self):
        return self.name

    @property
    def step_type(self) -> str | None:
        """Extrait le step_type principal depuis policy_json (pour filtres UI)."""
        if not self.policy_json or 'on_step_output' not in self.policy_json:
            return None
        rules = self.policy_json['on_step_output']
        if rules and len(rules) > 0:
            return rules[0].get('when', {}).get('step_type')
        return None
```

**Extension modèle Action :**

```python
# catalog/models.py (classe Action)
class Action(models.Model):
    # ... champs existants ...

    # FK vers règle prédéfinie (Story 28.4)
    business_rule_policy = models.ForeignKey(
        BusinessRulePolicy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actions',
        db_column='BUSINESS_RULE_POLICY_ID',
        help_text='Règle métier prédéfinie (prioritaire sur business_rule_policies inline)'
    )

    # JSON inline legacy (Story 28.1)
    business_rule_policies = OracleJSONField(
        null=True,
        blank=True,
        db_column='BUSINESS_RULE_POLICIES',
        help_text='JSON schema business_rule_policies (legacy, fallback si business_rule_policy_id=null)'
    )

    @property
    def effective_business_rule_policies(self) -> dict | None:
        """
        Retourne les politiques métier effectives de cette action.

        Priorité :
        1. business_rule_policy.policy_json (si FK renseignée ET is_active=True)
        2. business_rule_policies (si inline renseigné)
        3. None (pas de règles)
        """
        if self.business_rule_policy_id:
            policy = self.business_rule_policy
            if policy.is_active:
                return policy.policy_json
            else:
                # Règle désactivée → ignorer
                logger.warning(
                    "business_rule_policy_inactive",
                    action_id=self.id,
                    policy_id=policy.id,
                    policy_name=policy.name
                )
                return None

        return self.business_rule_policies

    def clean(self):
        """Valide contrainte XOR : seulement 1 des 2 champs renseigné."""
        super().clean()

        if self.business_rule_policy_id and self.business_rule_policies:
            raise ValidationError(
                'Une action ne peut avoir à la fois business_rule_policy_id et business_rule_policies. '
                'Utilisez soit la règle prédéfinie (FK), soit la règle inline (JSON).'
            )
```

**Contrainte CHECK Oracle (XOR) :**

```sql
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CHK_ACTION_POLICY_XOR CHECK (
  (BUSINESS_RULE_POLICY_ID IS NOT NULL AND BUSINESS_RULE_POLICIES IS NULL) OR
  (BUSINESS_RULE_POLICY_ID IS NULL AND BUSINESS_RULE_POLICIES IS NOT NULL) OR
  (BUSINESS_RULE_POLICY_ID IS NULL AND BUSINESS_RULE_POLICIES IS NULL)
);
```

[Source: catalog/models.py, Story 28.1, Story 28.3]

### Architecture Compliance

**Pattern CRUD Admin aligné avec codebase :**

1. **Modèle BusinessRulePolicy** suit pattern existant (Profile, Integration, Category) :
   - Table Oracle avec IDENTITY column
   - Champs standard (name, description, is_active, created_at, updated_at, created_by)
   - Validation via clean() méthode
   - Ordering par name

2. **Serializers** suivent pattern DRF existant :
   - BusinessRulePolicyListSerializer (liste) : champs résumés
   - BusinessRulePolicySerializer (détail) : tous champs + validation
   - Validation custom : validate_policy_json() appelle validate_business_rule_policies()

3. **ViewSet** suit pattern existant (ProfilesViewSet, IntegrationsViewSet) :
   - ModelViewSet avec CRUD complet
   - Permissions : IsAuthenticated + IsDBAOrDBOPS
   - Filtres : filterset_fields + custom get_queryset()
   - Audit trail : AuditService dans create/update/destroy

4. **Frontend Panel** suit pattern existant (ProfilesAdminPanel, IntegrationsAdminPanel) :
   - Liste paginée avec colonnes
   - Filtres (step_type, is_active)
   - Bouton « Créer » → Modal
   - Boutons « Modifier » / « Supprimer » par ligne
   - Hooks : useCallback fetchPolicies(), handleCreate(), handleEdit(), handleDelete()

5. **Frontend Modal** suit pattern existant (ProfileModal, IntegrationModal) :
   - Props : open, policy (nullable), onSuccess, onCancel
   - Form.Item avec validation Ant Design
   - Boutons « Annuler » / « Enregistrer »

6. **ActionWizard extension** suit pattern Step 3 existant :
   - Radio.Group pour choix predefined/custom
   - Select component pour règle prédéfinie (comme Select integration)
   - BusinessRulePoliciesEditor pour règle custom (existant)

**Pas de divergence détectée** — pattern Business Rule Policy s'intègre naturellement dans stack Admin existant.

[Source: catalog/views.py ProfilesViewSet, pages/admin/ProfilesAdminPanel.tsx, components/admin/ActionWizard.tsx]

### Library & Framework Requirements

**Backend Python :**
- **Django 5.2** : ORM, modèles, migrations (déjà installé)
- **DRF 3.16** : ModelViewSet, Serializers (déjà installé)
- **structlog** : Logging structuré (déjà installé)
- **OracleJSONField** : CLOB JSON (déjà implémenté Story 28.1)

**Frontend React :**
- **React 18** : Composants, hooks (déjà installé)
- **Ant Design 6.2** : Table, Modal, Form, Select, Radio, Checkbox (déjà installé)
- **TypeScript** : Types API (déjà installé)

**Aucune dépendance supplémentaire nécessaire** — tous packages requis déjà installés.

**Dépendances existantes réutilisées :**
- BusinessRulePoliciesEditor (Story 28.1) : éditeur JSON pour règle custom
- validate_business_rule_policies() (Story 28.1) : validation backend
- RuleEngine._load_policies() (Story 28.3) : chargement règles (à étendre)
- ProfilesAdminPanel pattern : CRUD admin (à dupliquer)
- ActionWizard Step 3 : Impact & Change (à étendre)

[Source: idp-portal/django_backend/pyproject.toml, idp-portal/frontend/package.json]

### File Structure Requirements

**Fichiers à créer :**

**Backend :**
1. `catalog/tests/test_business_rule_policy_api.py` — Tests API CRUD BusinessRulePolicy (9+ tests)
2. `catalog/management/commands/migrate_inline_policies.py` — Management command migration inline → prédéfinie (optionnel)
3. `database/migrations/V074__add_business_rule_policies_to_actions_catalog.sql` — Migration Flyway table + FK

**Frontend :**
4. `frontend/src/pages/admin/BusinessRulesPolicyPanel.tsx` — Panel Admin liste + CRUD (200 lignes)
5. `frontend/src/components/admin/BusinessRulePolicyModal.tsx` — Modal création/édition (150 lignes)
6. `frontend/src/components/admin/BusinessRulePolicySelector.tsx` — Sélecteur predefined/custom (250 lignes)
7. `frontend/src/pages/admin/BusinessRulesPolicyPanel.test.tsx` — Tests panel (7+ tests)
8. `frontend/src/components/admin/BusinessRulePolicySelector.test.tsx` — Tests sélecteur (5+ tests)
9. `frontend/src/services/admin_service.ts` — Ajouter fonctions API (getBusinessRulePolicies, createBusinessRulePolicy, etc.)
10. `frontend/src/types/api/business_rule_policy.ts` — Types TypeScript (BusinessRulePolicyResponse, etc.)

**Fichiers à modifier :**

**Backend :**
1. `catalog/models.py` — Ajouter modèle BusinessRulePolicy + FK dans Action
2. `catalog/serializers.py` — Ajouter BusinessRulePolicySerializer + étendre ActionDetailSerializer
3. `catalog/views.py` — Ajouter BusinessRulePolicyViewSet
4. `catalog/urls.py` — Router BusinessRulePolicyViewSet
5. `core/models.py` — Ajouter AuditActionType (POLICY_CREATED, POLICY_UPDATED, POLICY_DELETED)
6. `executions/rule_engine.py` — Modifier _load_policies() pour charger FK
7. `executions/tests/test_policy_integration.py` — Ajouter tests FK (2+ tests)
8. `catalog/tests/test_action_model.py` — Ajouter tests effective_business_rule_policies (4+ tests)

**Frontend :**
9. `frontend/src/pages/AdminPage.tsx` — Ajouter onglet 'business-rules'
10. `frontend/src/components/admin/ActionWizard.tsx` — Remplacer BusinessRulePoliciesEditor par BusinessRulePolicySelector
11. `frontend/src/components/admin/ActionWizard.test.tsx` — Ajouter tests sélecteur (4+ tests)

**Naming conventions :**
- **Modèles** : BusinessRulePolicy (PascalCase)
- **Serializers** : BusinessRulePolicySerializer, BusinessRulePolicyListSerializer
- **ViewSet** : BusinessRulePolicyViewSet
- **Composants** : BusinessRulesPolicyPanel, BusinessRulePolicyModal, BusinessRulePolicySelector
- **Types** : BusinessRulePolicyResponse, BusinessRulePolicyListItem
- **Tests** : test_create_business_rule_policy, test_select_predefined_rule

[Source: Python PEP 8, React/TypeScript conventions, codebase patterns catalog/, pages/admin/]

### Testing Standards Summary

**Backend Tests (20+ tests requis) :**

1. **test_business_rule_policy_api.py** (9+ tests unitaires API) :
   - test_create_business_rule_policy : POST → 201 + audit trail
   - test_create_invalid_policy_json : POST JSON invalide → 400
   - test_list_business_rule_policies : GET → liste paginée
   - test_filter_by_step_type : GET ?step_type=terraform_cloud → filtré
   - test_filter_by_is_active : GET ?is_active=true → actifs seulement
   - test_update_business_rule_policy : PATCH → 200 + audit trail
   - test_delete_business_rule_policy : DELETE → 204 + audit trail
   - test_permissions_dbops_only : Non-DBOPS → 403
   - test_inactive_policy_not_applied : is_active=False → RuleEngine ignore

2. **test_action_model.py** (4+ tests modèle) :
   - test_action_with_predefined_policy : FK → effective_business_rule_policies retourne policy_json
   - test_action_with_inline_policy : inline → effective_business_rule_policies retourne JSON
   - test_action_with_no_policy : None → effective_business_rule_policies retourne None
   - test_action_with_both_policies_fails : FK + inline → IntegrityError

3. **test_policy_integration.py** (2+ tests intégration) :
   - test_rule_engine_with_predefined_policy : Action FK → RuleEngine charge policy_json
   - test_rule_engine_with_inactive_policy : FK is_active=False → RuleEngine log warning + ignore

**Frontend Tests (16+ tests requis) :**

4. **BusinessRulesPolicyPanel.test.tsx** (7+ tests panel) :
   - test_render_business_rules_list : liste affichée
   - test_create_business_rule : modal création + sauvegarde
   - test_edit_business_rule : modal édition + sauvegarde
   - test_delete_business_rule : confirmation + suppression
   - test_filter_by_step_type : filtre step_type
   - test_filter_by_is_active : filtre actifs
   - test_pagination : pagination 20 items

5. **BusinessRulePolicySelector.test.tsx** (5+ tests sélecteur) :
   - test_select_predefined_rule : sélection règle → onChange business_rule_policy_id
   - test_select_custom_rule : sélection custom → onChange business_rule_policies
   - test_view_predefined_rule_json : modal read-only
   - test_filter_by_step_type : filtre dropdown
   - test_none_option : sélection « Aucune » → id=null

6. **ActionWizard.test.tsx** (4+ tests ActionWizard étendus) :
   - test_edit_action_with_predefined_rule : FK → mode predefined
   - test_edit_action_with_inline_rule : inline → mode custom
   - test_save_with_predefined_rule : PATCH { business_rule_policy_id }
   - test_save_with_custom_rule : PATCH { business_rule_policies }

**Régression tests Story 28.3 :**
- ✅ pytest executions/tests/test_rule_engine.py -v → 0 régression (tous tests doivent passer)
- ✅ pytest executions/tests/test_policy_evaluator.py -v → 0 régression
- ✅ pytest executions/tests/test_policy_integration.py -v → 0 régression + 2 nouveaux tests

**Test execution commands :**
```bash
# Tests backend modèle + API
pytest catalog/tests/test_business_rule_policy_api.py -v
pytest catalog/tests/test_action_model.py -v

# Tests intégration RuleEngine
pytest executions/tests/test_policy_integration.py -v

# Régression Story 28.3
pytest executions/tests/test_rule_engine.py -v

# Tous tests backend
pytest catalog/tests/ executions/tests/ -v

# Tests frontend
npm run test BusinessRulesPolicyPanel.test.tsx
npm run test BusinessRulePolicySelector.test.tsx
npm run test ActionWizard.test.tsx

# Coverage backend
pytest catalog/tests/ executions/tests/ --cov=catalog/models --cov=catalog/views --cov=executions/rule_engine --cov-report=html
```

**Exigence couverture** : ≥85% sur BusinessRulePolicy model, BusinessRulePolicyViewSet, RuleEngine._load_policies()

[Source: pytest documentation, codebase test patterns catalog/tests/, frontend test patterns]

### Project Structure Notes

**Alignement avec unified project structure :**

```
idp-portal/
├── django_backend/
│   ├── catalog/
│   │   ├── models.py (MODIFIÉ : BusinessRulePolicy + Action.business_rule_policy FK)
│   │   ├── serializers.py (MODIFIÉ : BusinessRulePolicySerializer + ActionDetailSerializer)
│   │   ├── views.py (MODIFIÉ : BusinessRulePolicyViewSet)
│   │   ├── urls.py (MODIFIÉ : router business-rule-policies)
│   │   ├── management/commands/
│   │   │   └── migrate_inline_policies.py (NOUVEAU, optionnel)
│   │   └── tests/
│   │       ├── test_business_rule_policy_api.py (NOUVEAU, 9+ tests)
│   │       └── test_action_model.py (MODIFIÉ, 4+ tests ajoutés)
│   ├── executions/
│   │   ├── rule_engine.py (MODIFIÉ : _load_policies() charge FK)
│   │   └── tests/
│   │       └── test_policy_integration.py (MODIFIÉ : 2+ tests ajoutés)
│   ├── core/
│   │   └── models.py (MODIFIÉ : AuditActionType POLICY_*)
│   └── database/migrations/
│       └── V074__add_business_rule_policies_to_actions_catalog.sql (NOUVEAU)
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── AdminPage.tsx (MODIFIÉ : onglet business-rules)
│   │   │   └── admin/
│   │   │       ├── BusinessRulesPolicyPanel.tsx (NOUVEAU, 200 lignes)
│   │   │       └── BusinessRulesPolicyPanel.test.tsx (NOUVEAU, 7+ tests)
│   │   ├── components/admin/
│   │   │   ├── BusinessRulePolicyModal.tsx (NOUVEAU, 150 lignes)
│   │   │   ├── BusinessRulePolicySelector.tsx (NOUVEAU, 250 lignes)
│   │   │   ├── BusinessRulePolicySelector.test.tsx (NOUVEAU, 5+ tests)
│   │   │   ├── ActionWizard.tsx (MODIFIÉ : Step 3 BusinessRulePolicySelector)
│   │   │   └── ActionWizard.test.tsx (MODIFIÉ : 4+ tests ajoutés)
│   │   ├── services/
│   │   │   └── admin_service.ts (MODIFIÉ : API functions BusinessRulePolicy)
│   │   └── types/api/
│   │       └── business_rule_policy.ts (NOUVEAU : types TypeScript)
```

**Pas de conflit détecté** avec structure existante — BusinessRulePolicy s'intègre naturellement dans catalog/, panel Admin suit pattern existant.

**Couplage avec autres modules :**
- **catalog/** : Modèle Action référence BusinessRulePolicy (FK)
- **executions/** : RuleEngine._load_policies() charge BusinessRulePolicy.policy_json
- **audit/** : AuditService pour audit trail (POLICY_CREATED, POLICY_UPDATED, POLICY_DELETED)
- **frontend Admin** : Nouvel onglet « Règles métier » dans AdminPage

**Décision architectural : FK avec fallback inline**

Approche hybride choisie :
- ✅ BusinessRulePolicy (catalogue) : règles réutilisables, maintenance centralisée
- ✅ business_rule_policies (inline) : legacy supporté en fallback
- ✅ Contrainte XOR : garantit seulement 1 source active par action
- ✅ effective_business_rule_policies : abstraction uniforme pour RuleEngine

Alternative envisagée : migration forcée inline → prédéfinie → rejetée pour éviter breaking change.

[Source: idp-portal/django_backend/, idp-portal/frontend/src/, catalog/models.py, executions/rule_engine.py]

### Previous Story Intelligence

**Story 28.3 — RuleEngine + OutputInterpreter :**

**Learnings :**
- ✅ RuleEngine._load_policies() charge action.business_rule_policies (JSON inline)
- ✅ Pattern extensible OutputInterpreter + Registry bien établi
- ✅ 56 tests passent (26 refactorisés + 30 nouveaux), 0 régression
- ✅ Logging structuré avec correlation_id propagé
- ✅ Security hardening : DoS limits (MAX_POLICY_JSON_SIZE, MAX_CRITERIA_COUNT)

**Fichiers modifiés Story 28.3 :**
- `executions/rule_engine.py` (315 lignes) — RuleEngine._load_policies() charge business_rule_policies
- `executions/interpreters/` (nouveau package) — OutputInterpreter interface + Registry
- `executions/policy_evaluator.py` (refactorisé) — wrapper léger RuleEngine
- `docs/business-rule-policies.md` (enrichi) — architecture RuleEngine multi-plateforme

**Code à réutiliser dans Story 28.4 :**
- RuleEngine._load_policies() méthode → étendre pour charger FK BusinessRulePolicy
- validate_business_rule_policies() → réutiliser pour validation BusinessRulePolicy.policy_json
- PolicyDecision dataclass → retournée par RuleEngine (inchangé)
- BusinessRulePoliciesEditor component → réutiliser pour mode custom inline

**Problèmes Story 28.3 à résoudre dans 28.4 :**
- ✅ Duplication règles JSON → catalogue BusinessRulePolicy résout
- ✅ Maintenance difficile → modification règle prédéfinie → toutes actions mises à jour
- ⚠️ RuleEngine._load_policies() doit charger FK (actuellement charge seulement JSON inline)

[Source: _bmad-output/implementation-artifacts/28-3-moteur-regles-metier-intelligent-multi-plateforme.md]

**Story 28.1 — business_rule_policies schéma + validation + UI :**

**Learnings :**
- ✅ BusinessRulePoliciesEditor component créé (éditeur JSON + validation temps réel)
- ✅ validate_business_rule_policies() validateur backend robuste
- ✅ ActionWizard Step 3 intègre BusinessRulePoliciesEditor
- ✅ 37 tests passent (28 backend + 9 frontend)

**Code à réutiliser dans Story 28.4 :**
- BusinessRulePoliciesEditor → mode custom inline dans BusinessRulePolicySelector
- validate_business_rule_policies() → validation BusinessRulePolicy.policy_json
- Exemples JSON (TERRAFORM_EXAMPLE) → bouton « Insérer exemple Terraform » dans modal

[Source: _bmad-output/implementation-artifacts/28-1-modele-schema-regles-metier-business-rule-policies.md]

### Git Intelligence Summary

**Commits récents pertinents :**

1. **28-3** (2026-02-15) : feat: RuleEngine + OutputInterpreter multi-plateforme
   - RuleEngine._load_policies() charge business_rule_policies (inline)
   - À étendre : charger FK BusinessRulePolicy.policy_json

2. **28-1** (2026-02-15) : feat: business_rule_policies schema + BusinessRulePoliciesEditor
   - Champ business_rule_policies (JSON inline) ajouté au modèle Action
   - À compléter : FK business_rule_policy_id + effective_business_rule_policies

3. **Epic 26** (2026-02-13) : Refactoring qualité code
   - Pattern CRUD admin établi (ProfilesAdminPanel, IntegrationsAdminPanel)
   - À dupliquer : BusinessRulesPolicyPanel suivant même pattern

**Patterns établis (derniers commits) :**
- ✅ CRUD admin panels : liste paginée + modal création/édition + filtres
- ✅ ModelViewSet : CRUD complet + permissions IsDBAOrDBOPS + audit trail
- ✅ Serializers : List (résumé) + Detail (complet) + validation custom
- ✅ Frontend hooks : useCallback fetchData(), handleCreate(), handleEdit(), handleDelete()
- ✅ Types TypeScript : Response, ListItem, Create, Update

[Source: git log --oneline -10, commits 28-3, 28-1, Epic 26]

### Latest Technical Specifics

**Versions clés codebase (confirmées) :**
- Django 5.2 : ORM, migrations, model validation
- DRF 3.16 : ModelViewSet, Serializers, Permissions
- React 18 : Hooks, components
- Ant Design 6.2 : Table, Modal, Form, Select, Radio
- TypeScript 5 : Types API
- Oracle DB : CLOB JSON, constraints CHECK

**Aucune recherche web nécessaire** — tous les patterns CRUD admin sont déjà dans le codebase.

**Considérations versions :**
- ✅ Django 5.2 : ForeignKey SET_NULL supporté
- ✅ Oracle : CHECK constraint XOR supportée
- ✅ Ant Design 6.2 : Radio.Group, Select.Option API stable
- ✅ TypeScript 5 : Union types (business_rule_policy_id | business_rule_policies)

**API patterns réutilisés :**
- GET /api/v1/admin/profiles/ → GET /api/v1/admin/business-rule-policies/
- POST /api/v1/admin/integrations/ → POST /api/v1/admin/business-rule-policies/
- ProfilesAdminPanel → BusinessRulesPolicyPanel (même structure)
- ProfileModal → BusinessRulePolicyModal (même pattern)

[Source: catalog/views.py, pages/admin/ProfilesAdminPanel.tsx, services/admin_service.ts]

## References

### Source Principale
- [Source: _bmad-output/planning-artifacts/epics.md — Epic 28, Story 28-4]

### Stories Précédentes (Dépendances)
- [Source: _bmad-output/implementation-artifacts/28-3-moteur-regles-metier-intelligent-multi-plateforme.md] — RuleEngine + OutputInterpreter + Registry
- [Source: _bmad-output/implementation-artifacts/28-2-policy-evaluator-terraform-plan-review-if-modified.md] — PolicyEvaluator + parsing Terraform
- [Source: _bmad-output/implementation-artifacts/28-1-modele-schema-regles-metier-business-rule-policies.md] — business_rule_policies schéma + validation + BusinessRulePoliciesEditor

### Fichiers Backend Existants
- [Source: idp-portal/django_backend/catalog/models.py] — Modèle Action avec business_rule_policies (Story 28.1)
- [Source: idp-portal/django_backend/catalog/validators.py] — validate_business_rule_policies() (Story 28.1)
- [Source: idp-portal/django_backend/catalog/views.py] — ProfilesViewSet, IntegrationsViewSet (patterns CRUD)
- [Source: idp-portal/django_backend/catalog/serializers.py] — ActionDetailSerializer, ProfileSerializer (patterns)
- [Source: idp-portal/django_backend/executions/rule_engine.py] — RuleEngine._load_policies() (Story 28.3, à étendre)

### Fichiers Frontend Existants
- [Source: idp-portal/frontend/src/pages/AdminPage.tsx] — Tabs Admin avec onglets Actions, Profils, Intégrations
- [Source: idp-portal/frontend/src/pages/admin/ProfilesAdminPanel.tsx] — Pattern panel CRUD (à dupliquer)
- [Source: idp-portal/frontend/src/components/admin/BusinessRulePoliciesEditor.tsx] — Éditeur JSON (Story 28.1, à réutiliser)
- [Source: idp-portal/frontend/src/components/admin/ActionWizard.tsx] — Step 3 Impact & Change (à étendre)
- [Source: idp-portal/frontend/src/services/admin_service.ts] — API admin functions (à étendre)

### Documentation Produit
- [Source: idp-portal/docs/business-rule-policies.md] — Documentation business_rule_policies (Story 28.1 + 28.3)
- [Source: idp-portal/docs/architecture.md] — Architecture stack (Django, React, Oracle)
- [Source: _bmad-output/planning-artifacts/prd.md] — FR28 (règles métier par action)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Fixed `logger.warning()` kwargs in `catalog/models.py` — standard logging doesn't support structlog-style kwargs
- Fixed `response.data['results']` → `response.data['data']` in 3 tests — CustomPageNumberPagination format
- Fixed Ant Design button text split by icons — used `textContent?.includes()` instead of `getByText()`
- Fixed Radio label text encoding issues — used `getAllByRole('radio')` by index
- Fixed `Space direction` deprecated → `orientation` in Ant Design 6.2
- Fixed ActionWizard tests — added missing mocks for `updateBusinessRulePolicies` and `patchAction`
- Created `patchAction` in admin_service.ts instead of importing `apiFetch` directly (test mock compatibility)

### Completion Notes List

- All 23 tasks completed across 9 phases
- 30/30 backend tests pass (17 API CRUD + 13 integration)
- 40/40 frontend tests pass (7 panel + 8 selector + 25 ActionWizard)
- 0 TypeScript compilation errors
- 0 regressions on Story 28.3 tests
- Migration V076 created (V074 was already taken)
- Management command `migrate_inline_policies` created with `--dry-run` support

### File List

**Fichiers créés (Backend) :**
1. `catalog/tests/test_business_rule_policy_api.py` — Tests API CRUD + FK integration (17 tests)
2. `catalog/management/__init__.py` — Package init
3. `catalog/management/commands/__init__.py` — Package init
4. `catalog/management/commands/migrate_inline_policies.py` — Migration inline → prédéfinie
5. `catalog/migrations/0008_alter_action_business_rule_policies_and_more.py` — Django auto-migration
6. `database/migrations/V076__create_business_rule_policies_table_and_fk.sql` — Oracle migration

**Fichiers créés (Frontend) :**
7. `frontend/src/types/api/business_rules.ts` — Types BusinessRulePolicy
8. `frontend/src/services/business_rules_service.ts` — API service CRUD
9. `frontend/src/components/admin/BusinessRulePolicyModal.tsx` — Modal création/édition
10. `frontend/src/components/admin/BusinessRulesPolicyPanel.tsx` — Panel Admin liste + CRUD
11. `frontend/src/components/admin/BusinessRulePolicySelector.tsx` — Sélecteur predefined/inline
12. `frontend/src/pages/admin/BusinessRulesAdminPanel.tsx` — Wrapper lazy-loaded
13. `frontend/src/components/admin/BusinessRulesPolicyPanel.test.tsx` — Tests panel (7 tests)
14. `frontend/src/components/admin/BusinessRulePolicySelector.test.tsx` — Tests sélecteur (8 tests)

**Fichiers modifiés (Backend) :**
15. `catalog/models.py` — Ajout modèle BusinessRulePolicy + FK Action.business_rule_policy
16. `catalog/serializers.py` — Ajout BusinessRulePolicySerializer + extension ActionSerializer
17. `catalog/views.py` — Ajout BusinessRulePolicyViewSet
18. `catalog/urls.py` — Route business-rule-policies
19. `core/models.py` — Ajout AuditActionType POLICY_CREATED/UPDATED/DELETED + AuditEntityType BUSINESS_RULE_POLICY
20. `executions/rule_engine.py` — _load_policies() étendu pour FK predefined > inline > None
21. `executions/tests/test_policy_integration.py` — 3 tests ajoutés (TestRuleEngineWithPredefinedPolicy)

**Fichiers modifiés (Frontend) :**
22. `frontend/src/types/api/index.ts` — Re-export business_rules
23. `frontend/src/types/api/catalog.ts` — business_rule_policy_id/name sur ActionDetail
24. `frontend/src/services/admin_service.ts` — Ajout patchAction()
25. `frontend/src/pages/AdminPage.tsx` — Onglet « Règles métier »
26. `frontend/src/pages/admin/index.ts` — Export BusinessRulesAdminPanel
27. `frontend/src/components/admin/ActionWizard.tsx` — BusinessRulePolicySelector + FK save logic
28. `frontend/src/components/admin/ActionWizard.test.tsx` — Mocks updateBusinessRulePolicies + patchAction
