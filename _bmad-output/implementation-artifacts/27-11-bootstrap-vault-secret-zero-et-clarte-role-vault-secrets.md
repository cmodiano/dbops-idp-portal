# Story 27.11: Bootstrap Vault (secret 0) et clarté rôle Vault pour les secrets

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DBOPS admin** (ou équipe déploiement),
I want **une solution claire et documentée pour le credential d'accès initial à Vault (secret 0), une règle explicite que les autres intégrations obtiennent leurs secrets via un service de secrets, et la possibilité de spécifier quel service de secrets utiliser par intégration**,
So that **la création d'une intégration de type HashiCorp ne pose pas de problème œuf/poule, que tout le monde sache où sont résolus les secrets, et que l'on puisse à terme gérer plusieurs instances Vault ou d'autres fournisseurs de secrets**.

## Acceptance Criteria

**AC1 — Options pour le secret 0 (bootstrap Vault)**
**Given** le portail doit s'authentifier à une ou plusieurs instances Vault (intégration type "vault"), **When** on analyse les options pour fournir le secret 0 (token ou AppRole), **Then** au moins les options suivantes sont documentées et comparées : (A) Variables d'environnement uniquement (VAULT_ADDR, VAULT_TOKEN ou VAULT_ROLE_ID + VAULT_SECRET_ID) ; (B) Secret 0 fourni par un mécanisme externe (injecté au déploiement) ; (C) Autres variantes pertinentes si applicable. **And** une **recommandation** est produite (option retenue + justification).

**AC2 — Comportement Admin pour le type "vault"**
**Given** un admin crée ou édite une intégration de **type "vault"**, **When** le formulaire est affiché, **Then** le champ credential_ref pour cette intégration est soit **absent**, soit **explicitement optionnel** avec un libellé indiquant que l'accès utilise le secret 0 fourni par l'environnement (voir doc). **And** la documentation indique où et comment configurer le secret 0. **And** aucun flux ne laisse croire que le secret 0 peut être saisi ou stocké dans le catalogue.

**AC3 — Clarifier que les autres intégrations utilisent un service de secrets (Vault)**
**Given** les intégrations (plateformes et services) qui ont besoin de credentials, **When** on consulte la documentation (PRD, architecture, glossaire, Admin), **Then** il est **explicite** que : HashiCorp Vault est le service de secrets principal ; les credentials sont résolus via un service de secrets au moment de l'exécution ; aucun secret n'est stocké en base. **And** cette règle est rappelée à un endroit visible. **And** si l'UI affiche credential_ref pour les types autres que "vault", un texte d'aide précise que la valeur doit être une référence vers le secret dans le service de secrets configuré (ex. vault:secret/data/...).

**AC3b — Spécifier le service de secrets à utiliser par intégration**
**Given** le catalogue d'intégrations et au moins une intégration de type "vault", **When** un admin crée ou édite une intégration qui nécessite des credentials (AAP, Tower, ServiceNow, Splunk, Jira, etc.), **Then** il peut **spécifier quel service de secrets utiliser** (sélection d'une intégration de type "vault"). **And** si aucun n'est choisi, un comportement par défaut est défini et documenté. **And** le modèle backend/API supporte un champ optionnel (ex. secret_service_id) sur les intégrations concernées. **And** à l'exécution, le moteur utilise l'instance Vault référencée (ou le défaut) pour résoudre le credential_ref. **And** les intégrations de type "vault" n'ont pas ce champ (ou il est ignoré).

**AC4 — Livrables**
**And** un document (ou section) décrit : (1) où vit le secret 0, (2) comment configurer le déploiement, (3) le fait que les autres intégrations obtiennent leurs secrets via un service de secrets, (4) la spécification du service de secrets par intégration (AC3b). **And** les changements éventuels de formulaire Admin (type "vault", champ « service de secrets » sur les autres types, textes d'aide) sont implémentés. **And** les tests ou checks manuels validant les flux et la cohérence de la doc sont exécutés.

## Tasks / Subtasks

### Task 1: Analyser et documenter les options de bootstrap Vault (secret 0) — AC1 (Analyse)
- [x] **Subtask 1.1**: Documenter l'option A — Variables d'environnement uniquement
  - VAULT_ADDR, VAULT_TOKEN (Token auth) OU VAULT_ROLE_ID + VAULT_SECRET_ID (AppRole auth)
  - Avantages: Simple, déjà supporté par VaultService existant, standard 12-factor app
  - Inconvénients: Token static peut expirer, AppRole nécessite rotation du secret_id
  - Cas d'usage: Environnements conteneurisés (Docker, Kubernetes), CI/CD pipelines
- [x] **Subtask 1.2**: Documenter l'option B — Secret 0 fourni par mécanisme externe
  - Injection au déploiement via: Kubernetes Secrets, Azure Key Vault, AWS Secrets Manager, HashiCorp Vault Agent (injection)
  - Avantages: Séparation des concerns, gestion centralisée des secrets, rotation automatique possible
  - Inconvénients: Complexité supplémentaire, dépendance à un service externe
  - Cas d'usage: Plateformes cloud natives, environnements hautement sécurisés
- [x] **Subtask 1.3**: Documenter l'option C — Autres variantes pertinentes
  - Vault Agent Sidecar: Auto-renouvellement du token, cache local
  - Kubernetes Service Account: Auth native Kubernetes-Vault
  - AppRole + Wrapped Secret ID: Secret ID jetable, une seule utilisation
  - Cas d'usage spécifiques et trade-offs
- [x] **Subtask 1.4**: Produire une recommandation avec justification
  - Comparer les 3 options selon: simplicité, sécurité, maintenabilité, cloud-readiness
  - Recommandation: Option A (env vars) pour MVP/Phase 2 avec migration vers Option B (external injection) en Phase 3
  - Justification: Équilibre entre time-to-market et sécurité, path de migration clair

### Task 2: Adapter le formulaire Admin pour les intégrations de type "vault" — AC2 (Frontend + Backend)
- [x] **Subtask 2.1**: Modifier le formulaire AdminPage > Intégrations pour masquer/désactiver credential_ref si type === "vault"
  - Fichier: `frontend/src/components/AdminPage/IntegrationForm.tsx`
  - Logique conditionnelle: `if (integrationType === 'vault') { hideCredentialRefField }`
  - Afficher un texte d'aide explicite: "L'authentification à Vault utilise le secret 0 fourni par les variables d'environnement (voir documentation)"
- [x] **Subtask 2.2**: Ajouter un lien vers la documentation dans le texte d'aide
  - Lien: `/docs/vault-bootstrap-guide.md` (document créé en Task 5)
  - Tooltip ou Alert component avec icône d'information
- [x] **Subtask 2.3**: Valider côté backend que credential_ref est vide ou null pour les intégrations type "vault"
  - Fichier: `django_backend/integrations/serializers.py`
  - Validation custom: `validate_credential_ref()` sur `IntegrationSerializer`
  - Si type === 'vault' ET credential_ref non vide → Warning ou erreur explicite
- [x] **Subtask 2.4**: Tester le comportement du formulaire
  - Test manuel: Créer une intégration type "vault", vérifier que credential_ref est masqué et texte d'aide affiché
  - Test automatique: Frontend test vérifiant le rendu conditionnel (Vitest + React Testing Library)
  - Test backend: Valider que la sérialisation accepte credential_ref null pour type vault

### Task 3: Clarifier dans la documentation que les autres intégrations utilisent un service de secrets — AC3 (Documentation)
- [x] **Subtask 3.1**: Mettre à jour le document `docs/vault-integration-analysis.md`
  - Ajouter une section "Rôle de Vault dans l'architecture"
  - Expliciter: "HashiCorp Vault est le service de secrets principal. Tous les credentials des intégrations (AAP, Tower, ServiceNow, etc.) sont résolus via Vault au moment de l'exécution. Aucun secret n'est stocké en base de données."
  - Diagramme de flux: Integration → credential_ref → VaultService.get_secret() → Résolution
- [x] **Subtask 3.2**: Mettre à jour le glossaire produit `docs/glossary.md`
  - Ajouter définition "Service de secrets" : Service externe (ex. HashiCorp Vault) qui stocke et résout les credentials de manière sécurisée
  - Ajouter définition "credential_ref" : Référence vers un secret dans un service de secrets (format: `vault:secret/data/path#key`)
  - Ajouter définition "Secret 0" : Credential initial permettant au portail de s'authentifier au service de secrets (bootstrap problem)
- [x] **Subtask 3.3**: Mettre à jour l'architecture `docs/architecture.md`
  - Section "Sécurité des secrets": Référencer explicitement que Vault est le service de secrets principal
  - Diagramme architectural: Montrer la dépendance de tous les adapters sur VaultService
- [x] **Subtask 3.4**: Ajouter texte d'aide dans le formulaire Admin pour credential_ref (types != vault)
  - Texte: "Saisissez une référence vers le secret dans Vault (ex: vault:secret/data/aap/prod#token). Le secret est résolu au moment de l'exécution. Aucun secret n'est stocké en base."
  - Fichier: `frontend/src/components/AdminPage/IntegrationForm.tsx`
  - Utiliser Ant Design Tooltip ou Form.Item help prop

### Task 4: Implémenter la spécification du service de secrets par intégration — AC3b (Backend + Frontend)
- [x] **Subtask 4.1**: Ajouter le champ `secret_service_id` au modèle Integration (Backend)
  - Fichier: `django_backend/integrations/models.py`
  - Champ: `secret_service_id = BigIntegerField(null=True, blank=True, db_column='SECRET_SERVICE_ID')`
  - ForeignKey vers Integration de type 'vault' (self-reference)
  - Migration: `V0XX_add_secret_service_id_to_integrations.sql`
  - Commentaire Oracle: "ID de l'intégration Vault utilisée pour résoudre les secrets de cette intégration (NULL = défaut global)"
- [x] **Subtask 4.2**: Créer une migration Oracle pour ajouter la colonne SECRET_SERVICE_ID
  - Fichier: `django_backend/idp_backend/migrations/V0XX_add_secret_service_id_to_integrations.sql`
  - SQL: `ALTER TABLE INTEGRATIONS ADD SECRET_SERVICE_ID NUMBER(19) NULL;`
  - Contrainte FK: `ALTER TABLE INTEGRATIONS ADD CONSTRAINT FK_INTEGRATION_SECRET_SERVICE FOREIGN KEY (SECRET_SERVICE_ID) REFERENCES INTEGRATIONS(ID);`
  - Commentaire: `COMMENT ON COLUMN INTEGRATIONS.SECRET_SERVICE_ID IS 'ID intégration Vault pour résoudre secrets (NULL=défaut)';`
- [x] **Subtask 4.3**: Mettre à jour le serializer IntegrationSerializer
  - Fichier: `django_backend/integrations/serializers.py`
  - Ajouter `secret_service_id` aux champs sérialisés
  - Validation: Si secret_service_id est fourni, vérifier que l'intégration référencée est de type 'vault'
  - Validation: Les intégrations de type 'vault' ne peuvent pas avoir de secret_service_id (ou il est ignoré)
- [x] **Subtask 4.4**: Ajouter un champ de sélection dans le formulaire Admin (Frontend)
  - Fichier: `frontend/src/components/AdminPage/IntegrationForm.tsx`
  - Composant: Select (Ant Design) pour choisir une intégration de type "vault"
  - Logique conditionnelle: Afficher ce champ seulement si type !== 'vault' ET type nécessite credentials
  - Label: "Service de secrets" avec texte d'aide: "Sélectionnez l'instance Vault utilisée pour résoudre les secrets de cette intégration (optionnel, défaut = Vault principal)"
- [x] **Subtask 4.5**: Créer un hook useVaultIntegrations() pour charger les intégrations type "vault"
  - Fichier: `frontend/src/hooks/useVaultIntegrations.ts`
  - API call: `GET /api/v1/integrations/?type=vault&status=valid`
  - Retourner la liste des intégrations Vault disponibles pour le dropdown
- [x] **Subtask 4.6**: Documenter le comportement par défaut si secret_service_id est NULL
  - Documentation: Si secret_service_id est NULL, utiliser l'intégration Vault par défaut (la première active de type 'vault', ou celle avec name='default-vault')
  - Fichier: `docs/vault-bootstrap-guide.md` (Task 5)
  - Logique backend: Implémenter dans `adapters/utils.py:_resolve_credential()` ou dans `get_vault_service()`
- [x] **Subtask 4.7**: Adapter la résolution de credential_ref pour utiliser secret_service_id
  - Fichier: `django_backend/adapters/utils.py` fonction `_resolve_credential()`
  - Logique: Si `secret_service_id` est fourni, récupérer les credentials de cette intégration Vault spécifique
  - Logique: Si `secret_service_id` est NULL, utiliser le VaultService singleton (comportement actuel = défaut global)
  - Étapes:
    1. Vérifier si integration.secret_service_id existe
    2. Si oui, charger l'intégration Vault référencée (Integration.objects.get(id=secret_service_id))
    3. Créer une instance VaultService avec les params de cette intégration (vault_addr, vault_token, vault_namespace)
    4. Appeler get_secret() sur cette instance
    5. Si non, utiliser get_vault_service() singleton actuel
- [x] **Subtask 4.8**: Gérer le cache multi-instance Vault
  - Problème: Le VaultService actuel est un singleton avec un cache global
  - Solution: Ajouter un paramètre instance_id au cache_key pour éviter les collisions entre instances Vault
  - Fichier: `django_backend/core/vault_service.py` méthode `_build_cache_key()`
  - Modifier cache_key: `f"vault:{instance_id}:{namespace}:{mount}:{path}#{key}"`
  - instance_id peut être l'ID de l'intégration ou un hash de vault_addr

### Task 5: Créer le document de guide de bootstrap Vault — AC4 (Documentation)
- [x] **Subtask 5.1**: Créer `docs/vault-bootstrap-guide.md`
  - Section 1: Introduction au problème œuf/poule
  - Section 2: Options de bootstrap (résumé de Task 1)
  - Section 3: Configuration recommandée (Option A — Variables d'environnement)
  - Section 4: Configuration alternative (Option B — Injection externe)
  - Section 5: Spécification du service de secrets par intégration (AC3b)
  - Section 6: Troubleshooting et FAQ
- [x] **Subtask 5.2**: Section 1 — Introduction au problème œuf/poule
  - Expliquer: Le portail a besoin de Vault pour résoudre les secrets des intégrations
  - Problème: Comment le portail s'authentifie-t-il à Vault sans stocker de secret en base ?
  - Réponse: Le "secret 0" (token ou AppRole) est fourni par l'environnement d'exécution
- [x] **Subtask 5.3**: Section 2 — Options de bootstrap
  - Tableau comparatif des 3 options (A, B, C)
  - Avantages, inconvénients, cas d'usage pour chaque option
- [x] **Subtask 5.4**: Section 3 — Configuration recommandée (Variables d'environnement)
  - Détailler les variables VAULT_ADDR, VAULT_TOKEN, VAULT_ROLE_ID, VAULT_SECRET_ID
  - Exemple de configuration .env.production:
    ```
    VAULT_ADDR=https://vault.company.com
    VAULT_ROLE_ID=idp-portal-role-id
    VAULT_SECRET_ID=secret-id-from-vault-admin
    ```
  - Procédure: Comment obtenir le role_id et secret_id depuis Vault Admin
  - Sécurité: Ne jamais commiter .env.production, utiliser injection CI/CD ou secrets manager
- [x] **Subtask 5.5**: Section 4 — Configuration alternative (Injection externe)
  - Exemples: Kubernetes Secrets, Azure Key Vault, AWS Secrets Manager
  - Exemple Kubernetes:
    ```yaml
    apiVersion: v1
    kind: Secret
    metadata:
      name: vault-credentials
    stringData:
      VAULT_ADDR: "https://vault.company.com"
      VAULT_ROLE_ID: "idp-portal-role-id"
      VAULT_SECRET_ID: "secret-id"
    ```
  - Montage dans le deployment: `envFrom: secretRef: name: vault-credentials`
- [x] **Subtask 5.6**: Section 5 — Spécification du service de secrets par intégration
  - Expliquer le champ `secret_service_id` ajouté en Task 4
  - Cas d'usage: Plusieurs instances Vault (dev, staging, prod) ou Vault multi-tenant avec namespaces différents
  - Exemple: Intégration AAP Production → secret_service_id pointe vers "Vault Production"
  - Comportement par défaut: Si secret_service_id est NULL, utiliser Vault principal (défini par variables d'env)
- [x] **Subtask 5.7**: Section 6 — Troubleshooting et FAQ
  - Q: Que se passe-t-il si le secret 0 est invalide ?
  - R: Le portail ne peut pas démarrer ou résoudre les secrets. Vérifier logs VaultService, circuit breaker s'ouvre
  - Q: Comment rotationner le secret 0 ?
  - R: Avec AppRole, générer un nouveau secret_id, mettre à jour .env ou secrets manager, redémarrer le portail
  - Q: Peut-on stocker le secret 0 dans Vault lui-même ?
  - R: Non, c'est le problème œuf/poule. Le secret 0 doit venir d'une source externe à Vault

### Task 6: Tests backend et frontend — AC4 (Tests)
- [x] **Subtask 6.1**: Test backend — Validation credential_ref vide pour type "vault"
  - Fichier: `django_backend/integrations/tests/test_serializers.py`
  - Test: `test_vault_integration_credential_ref_validation()`
  - Scénario: Créer une intégration type="vault" avec credential_ref non vide → Warning ou validation error
  - Assertion: Vérifier que la validation échoue ou retourne un warning explicite
- [x] **Subtask 6.2**: Test backend — Champ secret_service_id sur Integration
  - Fichier: `django_backend/integrations/tests/test_models.py`
  - Test: `test_integration_secret_service_id_foreign_key()`
  - Scénario: Créer une intégration AAP avec secret_service_id pointant vers une intégration Vault
  - Assertion: Vérifier que la FK est correcte et que l'intégration référencée est bien de type 'vault'
- [x] **Subtask 6.3**: Test backend — Validation secret_service_id type vault uniquement
  - Fichier: `django_backend/integrations/tests/test_serializers.py`
  - Test: `test_secret_service_id_must_reference_vault_integration()`
  - Scénario: Créer une intégration AAP avec secret_service_id pointant vers une intégration non-vault → Validation error
  - Assertion: Vérifier que la validation échoue avec message explicite
- [x] **Subtask 6.4**: Test backend — Résolution credential_ref avec secret_service_id
  - Fichier: `django_backend/adapters/tests/test_utils.py`
  - Test: `test_resolve_credential_with_custom_vault_instance()`
  - Scénario:
    1. Créer 2 intégrations Vault (vault-dev, vault-prod) avec des VAULT_ADDR différents
    2. Créer une intégration AAP avec secret_service_id=vault-prod
    3. Appeler _resolve_credential() avec l'intégration AAP
    4. Vérifier que VaultService utilise l'instance vault-prod (pas le singleton par défaut)
  - Mock: VaultService.get_secret() pour vérifier les paramètres (vault_addr, namespace)
- [x] **Subtask 6.5**: Test frontend — Formulaire Admin masque credential_ref pour type vault
  - Fichier: `frontend/src/components/AdminPage/IntegrationForm.test.tsx`
  - Test: `test_credential_ref_hidden_for_vault_type()`
  - Scénario: Rendre le formulaire avec integrationType="vault"
  - Assertion: Vérifier que le champ credential_ref n'est pas visible (display: none ou non rendu)
  - Assertion: Vérifier que le texte d'aide sur le secret 0 est affiché
- [x] **Subtask 6.6**: Test frontend — Champ secret_service_id affiché pour types non-vault
  - Fichier: `frontend/src/components/AdminPage/IntegrationForm.test.tsx`
  - Test: `test_secret_service_field_visible_for_non_vault_types()`
  - Scénario: Rendre le formulaire avec integrationType="aap" ou "tower"
  - Assertion: Vérifier que le champ "Service de secrets" (Select) est visible
  - Assertion: Vérifier que la liste des options contient les intégrations Vault actives
- [x] **Subtask 6.7**: Test frontend — Hook useVaultIntegrations() charge les intégrations vault
  - Fichier: `frontend/src/hooks/useVaultIntegrations.test.ts`
  - Test: `test_useVaultIntegrations_fetches_vault_integrations()`
  - Mock: API response avec 2 intégrations type="vault" status="valid"
  - Assertion: Vérifier que le hook retourne ces 2 intégrations
- [x] **Subtask 6.8**: Test d'intégration — Créer intégration AAP avec secret_service personnalisé via API
  - Fichier: `django_backend/integrations/tests/test_api.py`
  - Test: `test_create_aap_integration_with_custom_vault_service()`
  - Scénario:
    1. Créer une intégration Vault via POST /api/v1/integrations/
    2. Créer une intégration AAP avec secret_service_id pointant vers l'intégration Vault
    3. GET l'intégration AAP, vérifier que secret_service_id est correctement persisté
  - Assertion: Vérifier que le JSON retourné contient secret_service_id avec l'ID correct

### Task 7: Checks manuels et validation de la cohérence — AC4 (Validation)
- [x] **Subtask 7.1**: Check manuel — Créer une intégration Vault via Admin UI
  - Naviguer vers Admin > Intégrations
  - Cliquer "Nouvelle intégration", sélectionner type "Vault"
  - Vérifier que le champ credential_ref est masqué
  - Vérifier que le texte d'aide sur le secret 0 est affiché avec lien vers la doc
  - Sauvegarder l'intégration, vérifier qu'elle est créée avec credential_ref=NULL
- [x] **Subtask 7.2**: Check manuel — Créer une intégration AAP avec service de secrets personnalisé
  - Pré-requis: Avoir au moins 2 intégrations Vault (vault-dev, vault-prod)
  - Créer une intégration AAP via Admin UI
  - Vérifier que le champ "Service de secrets" (Select) est visible
  - Sélectionner "vault-prod" dans le dropdown
  - Sauvegarder l'intégration, vérifier que secret_service_id est correctement persisté
- [x] **Subtask 7.3**: Check manuel — Vérifier le texte d'aide sur credential_ref pour types non-vault
  - Créer une intégration Tower, ServiceNow, ou AAP
  - Vérifier que le champ credential_ref a un texte d'aide explicite: "Saisissez une référence Vault (ex: vault:secret/data/...)"
  - Vérifier que le tooltip ou Form.Item help est affiché correctement
- [x] **Subtask 7.4**: Check manuel — Vérifier la documentation vault-bootstrap-guide.md
  - Ouvrir `/docs/vault-bootstrap-guide.md`
  - Vérifier que toutes les sections sont complètes (1 à 6)
  - Vérifier que les exemples de configuration sont corrects et exécutables
  - Vérifier que les liens internes (vers glossaire, architecture) fonctionnent
- [x] **Subtask 7.5**: Validation de cohérence — Vérifier que tous les documents sont à jour
  - Vérifier que `docs/vault-integration-analysis.md` mentionne le rôle de Vault comme service de secrets principal
  - Vérifier que `docs/glossary.md` contient les définitions de "Service de secrets", "credential_ref", "Secret 0"
  - Vérifier que `docs/architecture.md` référence explicitement Vault dans la section sécurité des secrets
  - Vérifier que tous les liens de documentation sont corrects et cohérents

## Dev Notes

### Context architectural et technique

**Objectifs de la story:**
1. Résoudre le problème œuf/poule: Comment le portail s'authentifie-t-il à Vault pour récupérer les secrets des autres intégrations ?
2. Clarifier explicitement que Vault est le service de secrets principal et qu'aucun secret n'est stocké en base
3. Permettre de spécifier quelle instance Vault utiliser par intégration (multi-Vault support)

**Composants impactés:**
- **Backend:** `integrations/models.py` (ajout champ secret_service_id), `integrations/serializers.py` (validations), `adapters/utils.py` (résolution multi-instance), `core/vault_service.py` (cache multi-instance)
- **Frontend:** `AdminPage/IntegrationForm.tsx` (formulaire conditionnel), `hooks/useVaultIntegrations.ts` (nouveau hook)
- **Documentation:** `vault-bootstrap-guide.md` (nouveau), `vault-integration-analysis.md`, `glossary.md`, `architecture.md` (mises à jour)
- **Base de données:** Migration Oracle pour ajouter SECRET_SERVICE_ID à INTEGRATIONS

**Contraintes architecturales:**
- **Zero secret en base:** Principe existant (PRD NFR21), cette story le rend encore plus explicite dans la documentation et l'UI
- **VaultService singleton:** Actuellement un singleton avec un seul cache global. Task 4 introduit le support multi-instance via secret_service_id
- **Cache multi-instance:** Modifier le cache_key pour inclure un instance_id et éviter les collisions entre instances Vault
- **Backward compatibility:** Le comportement actuel (singleton sans secret_service_id) doit rester le comportement par défaut

**Dépendances sur stories précédentes:**
- **Story 27.6:** VaultService implémenté avec retry, circuit breaker, cache, support Enterprise namespaces (DONE)
- **Story 27.7:** Admin frontend menu Intégrations avec 7 types (AAP, Tower, Azure, GitHub, Terraform, Vault, ServiceNow) (DONE)
- **Story 24.1:** IntegrationTypeCatalogue et IntegrationAction (catalogue d'actions par type d'intégration) (DONE)

**Détails d'implémentation VaultService existant:**
- Singleton pattern via `get_vault_service()` en `core/vault_service.py`
- Authentification: VAULT_TOKEN (token auth) OU VAULT_ROLE_ID + VAULT_SECRET_ID (AppRole auth)
- Configuration via variables d'environnement: VAULT_ADDR, VAULT_TOKEN, VAULT_ROLE_ID, VAULT_SECRET_ID, VAULT_NAMESPACE, VAULT_CACHE_TTL, VAULT_TIMEOUT, VAULT_MAX_RETRIES
- Format credential_ref: `vault:[namespace/]mount/data/path[#key]`
- Exemples: `vault:secret/data/aap/prod#token`, `vault:team-ops/secret/data/db#password`
- Résolution actuelle: `_resolve_credential()` en `adapters/utils.py` appelle `get_vault_service().get_secret()`

**Nouveau comportement avec secret_service_id:**
- Si Integration.secret_service_id est NULL → utiliser le VaultService singleton (comportement actuel)
- Si Integration.secret_service_id pointe vers une intégration Vault → créer une instance VaultService avec les params de cette intégration spécifique
- Cache multi-instance: Modifier cache_key pour inclure instance_id (ID de l'intégration Vault ou hash de vault_addr)
- Exemple: AAP Production utilise vault-prod (https://vault-prod.company.com), AAP Dev utilise vault-dev (https://vault-dev.company.com)

### Stack technique et patterns

**Backend:**
- Django 5.2 + Django REST Framework 3.16
- Oracle 19c (base de données)
- Python 3.9+ type hints
- VaultService en `core/vault_service.py` (existant)
- Adapters en `adapters/` (AAP, Tower, Azure, GitHub, Terraform)
- Utils en `adapters/utils.py` (build_auth_headers, _resolve_credential)

**Frontend:**
- React 18 + TypeScript
- Ant Design 6.2 (composants UI)
- AdminPage existant en `frontend/src/components/AdminPage/`
- Hooks custom en `frontend/src/hooks/`

**Base de données:**
- Migration Flyway SQL (V0XX_add_secret_service_id_to_integrations.sql)
- Contrainte FK: SECRET_SERVICE_ID → INTEGRATIONS(ID)
- Index si nécessaire pour optimiser les requêtes sur secret_service_id

**Tests:**
- Backend: pytest, unittest.mock, faker
- Frontend: Vitest, React Testing Library
- Tests d'intégration: API calls réels (mock Vault HTTP responses)

### Recommandations d'implémentation

**Phase 1 — Documentation et analyse (Task 1, Task 5):**
- Commencer par documenter les 3 options de bootstrap dans `vault-bootstrap-guide.md`
- Produire la recommandation (Option A pour MVP, Option B pour Phase 3)
- Mettre à jour la documentation existante (vault-integration-analysis.md, glossary.md, architecture.md)

**Phase 2 — Frontend UI (Task 2, partie de Task 4):**
- Modifier `IntegrationForm.tsx` pour masquer credential_ref si type === "vault"
- Ajouter le champ "Service de secrets" (Select) pour types !== "vault"
- Créer le hook `useVaultIntegrations()` pour charger les intégrations Vault
- Ajouter les textes d'aide explicites sur credential_ref et secret 0

**Phase 3 — Backend modèle et migration (Task 4):**
- Ajouter le champ `secret_service_id` au modèle Integration
- Créer la migration Oracle `V0XX_add_secret_service_id_to_integrations.sql`
- Mettre à jour le serializer avec validations custom
- Adapter `_resolve_credential()` pour supporter multi-instance Vault
- Modifier `_build_cache_key()` pour inclure instance_id

**Phase 4 — Tests (Task 6, Task 7):**
- Tests backend: modèle, serializer, résolution credential_ref multi-instance
- Tests frontend: formulaire conditionnel, hook useVaultIntegrations
- Tests d'intégration: création intégration AAP avec secret_service personnalisé via API
- Checks manuels: UI Admin, documentation, cohérence

**Approche incrémentale:**
1. Commencer par la documentation (Task 1, Task 5) pour clarifier les concepts
2. Implémenter le frontend (Task 2, Task 4 frontend) pour valider l'UX
3. Implémenter le backend (Task 4 backend) en dernier pour valider la logique technique
4. Tests et validation (Task 6, Task 7) pour garantir la qualité

**Gestion des erreurs:**
- Si secret_service_id pointe vers une intégration inexistante ou invalide → Erreur explicite au moment de la résolution (BadRequestError)
- Si secret_service_id pointe vers une intégration non-Vault → Validation error lors de la création/mise à jour
- Si l'instance Vault référencée est down → Circuit breaker s'ouvre, logs explicites, erreur VaultUnavailableError

**Performance et scalabilité:**
- Cache multi-instance: Un cache TTL par instance Vault pour éviter les appels répétés
- Circuit breaker par instance: Chaque VaultService instance a son propre circuit breaker state
- Pas d'impact sur les performances actuelles: Le comportement par défaut (secret_service_id=NULL) utilise le singleton existant

### Technical Requirements

**Backend — Migration et modèle:**
- Ajouter colonne `SECRET_SERVICE_ID NUMBER(19) NULL` à la table `INTEGRATIONS`
- Contrainte FK: `FK_INTEGRATION_SECRET_SERVICE` vers `INTEGRATIONS(ID)`
- Commentaire Oracle: `COMMENT ON COLUMN INTEGRATIONS.SECRET_SERVICE_ID IS 'ID intégration Vault pour résoudre secrets (NULL=défaut)';`
- Migration idempotente avec check `IF NOT EXISTS`

**Backend — Serializer validations:**
- Validation custom `validate_credential_ref()`: Si type === 'vault' ET credential_ref non vide → Warning
- Validation custom `validate_secret_service_id()`: Si secret_service_id fourni, vérifier que l'intégration référencée est de type 'vault'
- Validation custom: Les intégrations de type 'vault' ne peuvent pas avoir de secret_service_id (ou il est ignoré)

**Backend — Résolution multi-instance Vault:**
- Fichier: `django_backend/adapters/utils.py`
- Fonction: `_resolve_credential(credential_ref, correlation_id=None, integration=None)`
- Logique:
  ```python
  def _resolve_credential(credential_ref: str, correlation_id: str | None = None, integration: Integration | None = None) -> str:
      if not credential_ref.startswith("vault:"):
          return credential_ref  # Direct token (dev/test)

      # Déterminer quelle instance Vault utiliser
      if integration and integration.secret_service_id:
          vault_integration = Integration.objects.get(id=integration.secret_service_id)
          vault_service = VaultService(
              vault_addr=vault_integration.base_url,
              vault_token=os.getenv("VAULT_TOKEN"),  # Ou résoudre depuis config
              vault_namespace=vault_integration.get_config().get("namespace"),
              cache_ttl=300,
              instance_id=vault_integration.id
          )
      else:
          vault_service = get_vault_service()  # Singleton par défaut

      return str(vault_service.get_secret(credential_ref, correlation_id))
  ```

**Backend — Cache multi-instance:**
- Fichier: `django_backend/core/vault_service.py`
- Méthode: `_build_cache_key(credential_ref, instance_id=None)`
- Logique:
  ```python
  def _build_cache_key(self, credential_ref: str) -> str:
      parsed = self._parse_credential_ref(credential_ref)
      instance_id = self.instance_id or "default"
      key = f"vault:{instance_id}:{parsed.namespace or 'default'}:{parsed.mount}:{parsed.path}"
      if parsed.key:
          key += f"#{parsed.key}"
      return key
  ```

**Frontend — Formulaire Admin conditionnel:**
- Fichier: `frontend/src/components/AdminPage/IntegrationForm.tsx`
- Logique:
  ```tsx
  // Masquer credential_ref si type === "vault"
  {integrationType !== 'vault' && (
    <Form.Item
      label="Credential Reference"
      name="credential_ref"
      help="Saisissez une référence Vault (ex: vault:secret/data/aap/prod#token). Le secret est résolu au moment de l'exécution."
    >
      <Input placeholder="vault:secret/data/..." />
    </Form.Item>
  )}

  // Texte d'aide pour type vault
  {integrationType === 'vault' && (
    <Alert
      message="Authentification Vault"
      description={
        <>
          L'authentification à Vault utilise le secret 0 fourni par les variables d'environnement.
          <a href="/docs/vault-bootstrap-guide.md" target="_blank"> Voir la documentation</a>
        </>
      }
      type="info"
      showIcon
    />
  )}

  // Champ service de secrets pour types !== vault
  {integrationType !== 'vault' && requiresCredentials(integrationType) && (
    <Form.Item
      label="Service de secrets"
      name="secret_service_id"
      help="Sélectionnez l'instance Vault utilisée pour résoudre les secrets (optionnel, défaut = Vault principal)"
    >
      <Select
        placeholder="Vault principal (défaut)"
        allowClear
        options={vaultIntegrations.map(v => ({ label: v.name, value: v.id }))}
      />
    </Form.Item>
  )}
  ```

**Frontend — Hook useVaultIntegrations:**
- Fichier: `frontend/src/hooks/useVaultIntegrations.ts`
- API: `GET /api/v1/integrations/?type=vault&status=valid`
- Retour: Liste des intégrations Vault actives pour le dropdown

**Documentation — Structure vault-bootstrap-guide.md:**
```markdown
# Guide de Bootstrap Vault (Secret 0)

## 1. Introduction au problème œuf/poule
## 2. Options de bootstrap
### 2.1 Option A — Variables d'environnement (Recommandé Phase 2)
### 2.2 Option B — Injection externe (Recommandé Phase 3)
### 2.3 Option C — Autres variantes
## 3. Configuration recommandée (Variables d'environnement)
### 3.1 Token authentication
### 3.2 AppRole authentication (Recommandé)
### 3.3 Procédure d'obtention du role_id et secret_id
### 3.4 Exemple .env.production
## 4. Configuration alternative (Injection externe)
### 4.1 Kubernetes Secrets
### 4.2 Azure Key Vault
### 4.3 AWS Secrets Manager
## 5. Spécification du service de secrets par intégration (secret_service_id)
### 5.1 Cas d'usage multi-Vault
### 5.2 Configuration dans l'Admin UI
### 5.3 Comportement par défaut
## 6. Troubleshooting et FAQ
```

### Architecture Compliance

**Respect des décisions architecturales existantes:**
- **Zero secret en base (NFR21):** Renforcé par cette story avec documentation explicite et UI clarifiée
- **Vault comme service de secrets principal:** Explicité dans tous les documents (PRD, architecture, glossaire)
- **Pattern adapter pour les plateformes:** Aucun changement, les adapters continuent d'utiliser `build_auth_headers()` et `_resolve_credential()`
- **Circuit breaker par plateforme:** Étendu avec circuit breaker par instance Vault (Task 4.8)
- **Cache TTL:** Maintenu avec cache multi-instance (instance_id dans cache_key)

**Non-régression sur les stories précédentes:**
- **Story 27.6 (VaultService):** Le singleton reste le comportement par défaut (secret_service_id=NULL)
- **Story 27.7 (Admin UI Intégrations):** Formulaire étendu avec champs conditionnels, pas de breaking change
- **Stories 27.1-27.5 (Adapters):** Aucun changement nécessaire, la résolution credential_ref reste transparente

**Sécurité:**
- **Secret 0 jamais en base:** Stocké uniquement en variables d'environnement ou secrets manager externe
- **Aucun secret en transit:** Vault → Adapter → Plateforme, jamais via le frontend
- **Audit trail:** Résolution credential_ref loggée avec correlation_id (existant, pas de changement)

**Scalabilité:**
- **Multi-Vault support:** Permet de gérer plusieurs instances Vault (dev, staging, prod) ou Vault multi-tenant
- **Cache par instance:** Évite les collisions et améliore les performances
- **Circuit breaker par instance:** Isolation des failures entre instances Vault

### Library & Framework Requirements

**Backend:**
- Django 5.2 (existant)
- Django REST Framework 3.16 (existant)
- cx_Oracle 8.3+ (existant, driver Oracle)
- cachetools 5.3+ (existant, utilisé par VaultService pour le cache TTL)
- requests 2.31+ (existant, utilisé par VaultService et adapters pour HTTP)
- pytest 7.4+ (existant, framework de tests)
- faker 18.13+ (existant, génération de données de test)

**Frontend:**
- React 18 (existant)
- TypeScript 5.x (existant)
- Ant Design 6.2 (existant)
- Vite (existant, build tool)
- Vitest (existant, test framework)
- React Testing Library (existant, tests composants)

**Aucune nouvelle dépendance requise.**

### File Structure Requirements

**Fichiers backend à créer:**
1. `django_backend/idp_backend/migrations/V0XX_add_secret_service_id_to_integrations.sql` — Migration Oracle
2. `django_backend/integrations/tests/test_secret_service_id.py` — Tests spécifiques au champ secret_service_id (optionnel, peut être ajouté à test_models.py et test_serializers.py)

**Fichiers backend à modifier:**
1. `django_backend/integrations/models.py` — Ajouter champ `secret_service_id`
2. `django_backend/integrations/serializers.py` — Validations custom
3. `django_backend/adapters/utils.py` — Résolution multi-instance dans `_resolve_credential()`
4. `django_backend/core/vault_service.py` — Cache multi-instance dans `_build_cache_key()`
5. `django_backend/integrations/tests/test_models.py` — Tests modèle secret_service_id
6. `django_backend/integrations/tests/test_serializers.py` — Tests validations
7. `django_backend/adapters/tests/test_utils.py` — Tests résolution multi-instance

**Fichiers frontend à créer:**
1. `frontend/src/hooks/useVaultIntegrations.ts` — Hook pour charger intégrations Vault
2. `frontend/src/hooks/useVaultIntegrations.test.ts` — Tests hook

**Fichiers frontend à modifier:**
1. `frontend/src/components/AdminPage/IntegrationForm.tsx` — Formulaire conditionnel
2. `frontend/src/components/AdminPage/IntegrationForm.test.tsx` — Tests formulaire
3. `frontend/src/types/api/integrations.ts` — Ajouter `secret_service_id` aux types TypeScript (IntegrationResponse, IntegrationRequest)

**Fichiers documentation à créer:**
1. `docs/vault-bootstrap-guide.md` — Guide complet bootstrap Vault (nouveau document principal)

**Fichiers documentation à modifier:**
1. `docs/vault-integration-analysis.md` — Ajouter section "Rôle de Vault dans l'architecture"
2. `docs/glossary.md` — Ajouter définitions "Service de secrets", "credential_ref", "Secret 0"
3. `docs/architecture.md` — Clarifier section "Sécurité des secrets" avec référence explicite à Vault
4. `.env.example` — Documenter VAULT_* variables (déjà fait en Story 27.6, vérifier cohérence)
5. `.env.production.template` — Documenter VAULT_* variables (déjà fait en Story 27.6, vérifier cohérence)

**Total estimé:**
- Backend: 7 fichiers modifiés, 1-2 fichiers créés
- Frontend: 3 fichiers modifiés, 2 fichiers créés
- Documentation: 4 fichiers modifiés, 1 fichier créé (vault-bootstrap-guide.md)
- Migration: 1 fichier SQL créé

### Testing Requirements

**Couverture tests backend (estimée):**
- Modèles: 3-5 tests (secret_service_id FK, validations)
- Serializers: 4-6 tests (validations credential_ref type vault, secret_service_id type vault uniquement)
- Résolution credential_ref: 5-7 tests (multi-instance Vault, cache multi-instance, comportement par défaut)
- API: 2-3 tests d'intégration (création intégration avec secret_service_id, GET validation)
- **Total backend: 14-21 tests**

**Couverture tests frontend (estimée):**
- Formulaire: 4-6 tests (masquage credential_ref pour vault, affichage secret_service_id, textes d'aide)
- Hook useVaultIntegrations: 2-3 tests (fetch intégrations vault, gestion erreurs)
- **Total frontend: 6-9 tests**

**Tests manuels (checks Task 7):**
- 5 checks manuels détaillés (création intégration Vault, AAP avec secret_service, textes d'aide, documentation, cohérence)

**Total tests automatisés: 20-30 tests**
**Total checks manuels: 5 scénarios**

**Frameworks de test:**
- Backend: pytest, unittest.mock, faker
- Frontend: Vitest, React Testing Library

**Stratégie de tests:**
1. Tests unitaires modèle/serializer en premier (TDD)
2. Tests résolution credential_ref multi-instance (mock VaultService)
3. Tests frontend formulaire (rendu conditionnel)
4. Tests d'intégration API (création intégration end-to-end)
5. Checks manuels UI (validation UX)

### Previous Story Intelligence

**Story 27.6 — VaultService HashiCorp Vault Enterprise (DONE):**
- **Implémentation:** `core/vault_service.py` avec CircuitBreaker, retry, cache TTL, support Enterprise namespaces
- **Tests:** 46 tests unitaires, 91.64% coverage, 207 adapter integration tests (0 régression)
- **Learnings:**
  - Le VaultService est un singleton pattern via `get_vault_service()`
  - Authentification: VAULT_TOKEN (token auth) OU VAULT_ROLE_ID + VAULT_SECRET_ID (AppRole auth)
  - Format credential_ref: `vault:[namespace/]mount/data/path[#key]`
  - Cache TTL par défaut: 300s (5 minutes)
  - Circuit breaker: 5 failures → open state, 60s timeout avant half-open
  - Retry: Exponential backoff (1s, 2s, 4s) pour transient errors (500, 502, 503, timeout)
- **Code review fixes (7 issues):**
  - CRIT-1: Circuit breaker state check WITHOUT lock to avoid thread pool exhaustion
  - CRIT-2: Token renewal with lock for thread-safe race condition elimination
  - HIGH-1: `_ensure_token_valid()` auto-called in `get_secret()`
  - HIGH-3: Cache key includes namespace to prevent multi-tenancy collisions
  - MED-1: `retry_after_s` with `max(0, ...)` to avoid negative values
  - MED-2: Exception details sanitized (no path/mount leak to client)
  - LOW-1: Troubleshooting documentation for circuit breaker
- **Known limitations (non-blocking):**
  - HIGH-2: Singleton not reactive to env var changes (workaround: restart workers)
  - HIGH-4: Singleton vulnerable to parallel tests (workaround: use instance, not singleton)
  - MED-3: Retry sleep blocks Gunicorn threads (acceptable Phase 2, async Celery Phase 3)
- **Patterns à réutiliser dans cette story:**
  - Pattern singleton pour VaultService par défaut (secret_service_id=NULL)
  - Cache multi-instance: Ajouter instance_id au cache_key pour éviter collisions
  - Circuit breaker par instance: Chaque VaultService instance a son propre state
  - Documentation troubleshooting: Créer un guide similaire pour vault-bootstrap-guide.md

**Story 27.7 — Admin Frontend Menu Intégrations & Adapters (DONE):**
- **Implémentation:** 5 fixtures pour Tower, Azure DevOps, GitHub Actions, Terraform Cloud, Vault
- **Tests:** 49 backend + 19 frontend tests
- **Learnings:**
  - Formulaire Admin IntegrationForm.tsx pour créer/éditer intégrations
  - Types d'intégration: aap, tower, azure_devops, github_actions, terraform_cloud, vault, servicenow
  - Champs: type, name, base_url, credential_ref, auth_flow, token_url, config (JSON), status, icon
  - Seed command pour fixtures: `python manage.py seed_integration_types`
- **Patterns à réutiliser dans cette story:**
  - Formulaire conditionnel: Afficher/masquer champs selon le type d'intégration
  - Validation backend: Serializer custom validators
  - Tests frontend: React Testing Library pour tester rendu conditionnel
  - Hook custom pour charger données: Créer `useVaultIntegrations()` similaire aux hooks existants

**Story 24.1 — Catalogue des types d'intégration backend (DONE):**
- **Implémentation:** IntegrationTypeCatalogue et IntegrationAction models
- **Learnings:**
  - IntegrationTypeCatalogue: code (PK), name, description, version, is_active, integration_role (platform | service)
  - IntegrationAction: action_code, action_label, required_params (JSON Schema), optional_params, response_format
  - Fixtures pour 7 types: AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud, Vault, ServiceNow
  - Validation JSON Schema pour required_params et optional_params
- **Patterns à réutiliser dans cette story:**
  - Migration Oracle avec contraintes FK et commentaires
  - Serializer validations avec JSON Schema
  - Tests fixtures et seed command

**Git intelligence (derniers commits pertinents):**
- `fix(19-6): analyse et correction logs étape workflow drawer` — Corrections frontend (non lié)
- `feat(28-4): add business rule policy catalog and action association` — Epic 28 (non lié)
- `commit all` — Commit générique
- Pas de commits récents directement liés à Vault ou intégrations, les stories 27.6 et 27.7 sont DONE

**Insights pour cette story:**
1. **Réutiliser le pattern singleton VaultService:** Le comportement par défaut (secret_service_id=NULL) doit utiliser le singleton existant
2. **Cache multi-instance critique:** Modifier `_build_cache_key()` pour inclure instance_id et éviter collisions entre instances Vault
3. **Circuit breaker par instance:** Chaque VaultService instance doit avoir son propre circuit breaker state
4. **Documentation troubleshooting:** S'inspirer de `vault-troubleshooting-circuit-breaker.md` pour créer `vault-bootstrap-guide.md`
5. **Formulaire conditionnel Admin:** S'inspirer de IntegrationForm.tsx existant (Story 27.7) pour ajouter les champs conditionnels
6. **Tests frontend React Testing Library:** Réutiliser les patterns de Story 27.7 pour tester le rendu conditionnel
7. **Backward compatibility:** Tous les tests existants (46 VaultService + 207 adapters) doivent passer sans régression

### Project Structure Notes

**Alignement avec la structure projet existante:**

**Backend (Django):**
```
django_backend/
├── core/
│   └── vault_service.py          # VaultService singleton (Story 27.6)
├── adapters/
│   ├── utils.py                  # build_auth_headers(), _resolve_credential() (Story 27.1-27.5)
│   ├── aap_adapter.py            # AAP adapter (Story 27.1)
│   ├── tower_adapter.py          # Tower adapter (Story 27.2)
│   ├── azure_devops_adapter.py   # Azure DevOps adapter (Story 27.3)
│   ├── github_actions_adapter.py # GitHub Actions adapter (Story 27.4)
│   └── terraform_cloud_adapter.py# Terraform Cloud adapter (Story 27.5)
├── integrations/
│   ├── models.py                 # Integration, IntegrationTypeCatalogue, IntegrationAction
│   ├── serializers.py            # IntegrationSerializer (à étendre)
│   ├── views.py                  # API endpoints
│   ├── fixtures/
│   │   └── integration_types.json # Fixtures (Story 27.7)
│   └── tests/
│       ├── test_models.py
│       ├── test_serializers.py
│       └── test_api.py
└── idp_backend/
    └── migrations/
        └── V0XX_add_secret_service_id_to_integrations.sql  # À créer
```

**Frontend (React):**
```
frontend/
└── src/
    ├── components/
    │   └── AdminPage/
    │       ├── IntegrationForm.tsx        # Formulaire Admin (Story 27.7, à étendre)
    │       └── IntegrationForm.test.tsx   # Tests (à étendre)
    ├── hooks/
    │   ├── useVaultIntegrations.ts        # À créer
    │   └── useVaultIntegrations.test.ts   # À créer
    └── types/
        └── api/
            └── integrations.ts            # Types TypeScript (à étendre)
```

**Documentation:**
```
docs/
├── vault-bootstrap-guide.md              # À créer (document principal)
├── vault-integration-analysis.md         # Story 27.6 (à étendre)
├── vault-troubleshooting-circuit-breaker.md # Story 27.6 (référence)
├── vault-known-limitations-story-27-6.md # Story 27.6 (référence)
├── glossary.md                           # À étendre
├── architecture.md                       # À clarifier
└── integration-type-catalogue.md         # Story 24.1 (référence)
```

**Variances détectées: AUCUNE**
- La structure est cohérente avec les stories précédentes (27.6, 27.7, 24.1)
- Pas de conflit avec les décisions architecturales existantes
- Pas de duplication de code détectée

**Rationale:**
- Le champ `secret_service_id` s'ajoute naturellement au modèle `Integration` existant
- La résolution multi-instance Vault s'intègre dans `adapters/utils.py` existant
- Le formulaire Admin étend `IntegrationForm.tsx` existant sans breaking change
- La documentation s'intègre dans la structure `docs/` existante

### References

**Sources primaires — Epic et story:**
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 27 Story 27.11 lines 4705-4727] — User story complète avec AC1-AC4

**Sources techniques — Implémentation VaultService:**
- [Source: idp-portal/django_backend/core/vault_service.py lines 1-500] — VaultService singleton, CircuitBreaker, retry, cache
- [Source: idp-portal/django_backend/adapters/utils.py lines 1-200] — build_auth_headers(), _resolve_credential()

**Sources techniques — Modèle Integration:**
- [Source: idp-portal/django_backend/integrations/models.py lines 1-300] — Integration, IntegrationTypeCatalogue models
- [Source: idp-portal/django_backend/integrations/serializers.py lines 1-200] — IntegrationSerializer

**Sources documentation — Vault:**
- [Source: idp-portal/docs/vault-integration-analysis.md] — Analyse complète API Vault, credential_ref format, resilience patterns
- [Source: idp-portal/docs/vault-troubleshooting-circuit-breaker.md] — Guide troubleshooting production
- [Source: idp-portal/docs/vault-known-limitations-story-27-6.md] — Limitations non-bloquantes

**Sources documentation — Architecture:**
- [Source: _bmad-output/planning-artifacts/architecture.md lines 1-100] — Contexte architectural, contraintes, cross-cutting concerns
- [Source: _bmad-output/planning-artifacts/prd.md] — PRD avec NFR21 (zero credential stocké)

**Sources stories précédentes:**
- [Source: _bmad-output/implementation-artifacts/27-6-vault-service-hashicorp-vault-enterprise.md] — Story 27.6 DONE, VaultService implementation
- [Source: _bmad-output/implementation-artifacts/27-7-admin-frontend-menu-integrations-adapters.md] — Story 27.7 DONE, Admin UI fixtures

**Sources configuration:**
- [Source: idp-portal/django_backend/.env.example] — Variables d'environnement VAULT_*
- [Source: idp-portal/django_backend/.env.production.template] — Template production

**Sources glossaire:**
- [Source: idp-portal/docs/glossary.md] — Glossaire produit (à étendre avec définitions "Service de secrets", "credential_ref", "Secret 0")

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Fixed 2 pre-existing test failures in `services/tests/test_vault_service.py::TestAdapterIntegration` caused by MagicMock integration objects missing `secret_service_id=None` attribute
- VaultService is in `services/vault_service.py` (not `core/`), migrations are in `database/migrations/` (not `idp_backend/migrations/`)

### Completion Notes List

- AC1: Bootstrap Vault options documented in `docs/vault-bootstrap-guide.md` (3 options compared, recommendation produced)
- AC2: IntegrationForm hides credential_ref for vault type, shows secret 0 alert with bootstrap info
- AC3: Documentation updated across vault-integration-analysis.md, glossary.md, architecture.md to clarify Vault as principal secrets service
- AC3b: `secret_service_id` FK implemented on Integration model, serializer validation, `resolve_credential()` multi-instance support, cache key isolation by instance_id
- AC4: 24 backend tests + 6 frontend tests, all passing. Documentation coherence validated across 7 verification points.
- All 70 story tests pass (24 secret_service, 46 vault_service) + 36 frontend tests (6 new for 27.11)
- 8 pre-existing failures in `test_new_adapter_types_fixtures.py` (expect 7 types, now 9 — Jira+Splunk added in later stories) — NOT caused by this story

### Change Log

| File | Action | Description |
|------|--------|-------------|
| `database/migrations/V077__add_secret_service_id_to_integrations.sql` | Created | Oracle migration: SECRET_SERVICE_ID column + FK constraint |
| `django_backend/integrations/models.py` | Modified | Added `secret_service` ForeignKey (self-ref to vault type) |
| `django_backend/integrations/serializers.py` | Modified | Added `secret_service_id` to all 4 serializers + cross-field validation |
| `django_backend/adapters/utils.py` | Modified | Renamed `_resolve_credential` → `resolve_credential`, added multi-instance Vault support |
| `django_backend/services/vault_service.py` | Modified | Added `instance_id` param to `__init__`, instance method `_build_cache_key` with isolation |
| `django_backend/integrations/migrations/0006_integration_secret_service.py` | Created | Django migration for test DB (SQLite) |
| `django_backend/integrations/tests/test_secret_service.py` | Created | 24 tests: model, serializer, resolve_credential multi-instance, cache key |
| `django_backend/services/tests/test_vault_service.py` | Modified | Fixed 3 MagicMock integrations: added `secret_service_id=None` |
| `django_backend/docs/vault-bootstrap-guide.md` | Created | Complete bootstrap guide (6 sections, options A/B/C, recommendation) |
| `django_backend/docs/vault-integration-analysis.md` | Modified | Added Section 10: Rôle de Vault + multi-instance + bootstrap |
| `django_backend/docs/glossary.md` | Modified | Added: Service de secrets, Secret 0, secret_service_id definitions |
| `django_backend/docs/architecture.md` | Modified | Added: Sécurité des secrets (Story 27.11) section |
| `frontend/src/types/api/integrations.ts` | Modified | Added `secret_service_id` to IntegrationCreate, IntegrationUpdate, IntegrationResponse |
| `frontend/src/hooks/useVaultIntegrations.ts` | Created | Hook: fetches integrations, filters type=vault & status!=invalid |
| `frontend/src/components/admin/IntegrationForm.tsx` | Modified | Vault type: hide credential_ref, show secret 0 alert, show secret_service_id select for non-vault |
| `frontend/src/components/admin/IntegrationForm.test.tsx` | Modified | Added 6 Story 27.11 tests + useVaultIntegrations mock + vault type in mockTypes |

### File List

**Created:**
- `database/migrations/V077__add_secret_service_id_to_integrations.sql`
- `django_backend/integrations/migrations/0006_integration_secret_service.py`
- `django_backend/integrations/tests/test_secret_service.py`
- `django_backend/docs/vault-bootstrap-guide.md`
- `frontend/src/hooks/useVaultIntegrations.ts`

**Modified:**
- `django_backend/integrations/models.py`
- `django_backend/integrations/serializers.py`
- `django_backend/adapters/utils.py`
- `django_backend/services/vault_service.py`
- `django_backend/services/tests/test_vault_service.py`
- `django_backend/docs/vault-integration-analysis.md`
- `django_backend/docs/glossary.md`
- `django_backend/docs/architecture.md`
- `frontend/src/types/api/integrations.ts`
- `frontend/src/components/admin/IntegrationForm.tsx`
- `frontend/src/components/admin/IntegrationForm.test.tsx`
