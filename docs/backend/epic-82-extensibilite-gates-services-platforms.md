# Epic 82 : Extensibilité des gates, services et plateformes

**Date :** 2026-03-14  
**Statut :** Draft  
**Réf :** docs/reference/extensibility-plan-gates-services-platforms.md  
**Périmètre :** Backend (integrations, executions, catalog), Frontend (admin, workflow)

---

## 1. Objectif

Rendre les **gates**, **services** et **plateformes** facilement extensibles :

- **Backend** : ajout d'un nouveau type sans dispersion dans de multiples fichiers
- **Frontend** : affichage et configuration sans branches hard-codées
- **Actions** : nouveau type sélectionnable et configurable
- **Workflows** : nouveau type utilisable dans les steps et validé avant exécution

**Cible** : une source de vérité unique, des registres backend, une API de capacités, des formulaires et validateurs pilotés par schéma.

---

## 2. Problèmes actuels

1. Intégrations cataloguees mais comportement hard-codé (allowlists, mappings)
2. Métadonnées services dupliquées (catalogue, allowlist runtime, constantes frontend)
3. Gates sans modèle extensible (validation, mapping, évaluation dispersés)
4. Plateformes : plusieurs taxonomies (codes canoniques, aliases, connector_type)
5. Formulaires frontend non pilotés par schéma

---

## 3. Stories (alignées phases 0–4 + priorité recommandée)

### Story 82.1 — Phase 0 : Stabilisation et réduction de dérive

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
Supprimer les incohérences existantes avant le refactoring.

**Acceptance criteria :**
- AC1 : Aligner gates valides et gates évaluables.
- AC2 : Recenser aliases historiques et définir codes canoniques.
- AC3 : Documenter chemins runtime qui injectent kwargs plateforme.
- AC4 : Recenser mappings frontend (services, opérations, plateformes, labels, icônes, gate types).
- AC5 : Livrable : matrice compatibilité type → backend → frontend → workflow + liste mappings à supprimer.

---

### Story 82.2 — PlatformDefinition et registre plateformes

**Priorité :** Haute  
**Effort estimé :** L

**Description :**  
Introduire une définition de capacités plateforme et dériver health checks, validation et runtime depuis cette source.

**Acceptance criteria :**
- AC1 : Créer `platforms/definitions.py`, `platforms/capabilities.py` avec structure (code, display_name, aliases, icon, connector_type, action_platform_code, supports_health_check, schemas).
- AC2 : Remplacer validation enum rigide par validation catalogue/capability dans integrations.
- AC3 : Dériver health checks depuis la définition (supprimer _ADAPTER_TYPES, _SERVICE_TYPES manuels).
- AC4 : Centraliser `build_platform_runtime_config(integration, action_or_step)` dans adapters/runtime_config.py.
- AC5 : Unifier plateforme canonique / alias / code action dans une couche backend unique.

---

### Story 82.3 — ServiceDefinition et registre services

**Priorité :** Haute  
**Effort estimé :** L

**Description :**  
Fusionner métadonnées catalogue et allowlist runtime ; introduire définition de service.

**Acceptance criteria :**
- AC1 : Créer `services/definitions.py`, `services/capabilities.py` (code, display_name, credential_mode, operations, input/output_schema, ui_hints).
- AC2 : L'allowlist runtime dérivée de la définition (supprimer _ALLOWED_OPERATIONS manuel).
- AC3 : service_call_handler devient orchestrateur générique (vérifier opération dans définition, valider params via schéma).
- AC4 : Remplacer SERVICE_TYPES dupliqué par dérivé du registre.
- AC5 : Faire remonter schémas d'opération au frontend (labels, required/optional params, ui_hints).

---

### Story 82.4 — API de capacités backend

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
Exposer une API de capacités consommable par le frontend.

**Acceptance criteria :**
- AC1 : Créer `capabilities/views.py`, `capabilities/serializers.py`, `capabilities/urls.py`.
- AC2 : `GET /api/v1/capabilities/integrations` — plateformes + services avec opérations et schémas.
- AC3 : `GET /api/v1/capabilities/workflow-steps` — step_types avec variants (gates) et config_schema.
- AC4 : Enrichir ou réutiliser endpoints existants si préférable.
- AC5 : Tests : nouveau type visible via API de capacités.

---

### Story 82.5 — GateRegistry et GateDefinition

**Priorité :** Haute  
**Effort estimé :** L

**Description :**  
Créer un registre de gates équivalent à ServiceRegistry / AdapterRegistry.

**Acceptance criteria :**
- AC1 : Créer `executions/gates/registry.py`, `executions/gates/definitions.py`.
- AC2 : Interface GateDefinition (code, display_name, category, config_schema, supports_timeout, requires_manual_resolution, serialize_condition, evaluate).
- AC3 : Refactorer GateHandler pour utiliser le registre.
- AC4 : Refactorer GateEvaluator pour déléguer au registre.
- AC5 : Remplacer VALID_GATE_CONDITION_TYPES par interrogation du registre dans catalog/validators.py.
- AC6 : Tests : validation gate via registre, évaluation runtime.

---

### Story 82.6 — Frontend : client capacités et hooks

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
Créer le client frontend pour les capacités et remplacer les constantes locales.

**Acceptance criteria :**
- AC1 : Créer `capabilities_service.ts`, `useCapabilities.ts`, `useWorkflowStepCapabilities.ts`.
- AC2 : Remplacer mappings codés dans integrationHelpers.ts par capacités backend.
- AC3 : Construire ServiceCallStepConfig à partir de metadata backend (services, opérations, champs).
- AC4 : Construire GateStepConfig depuis schéma (remplacer GATE_TYPE_OPTIONS).
- AC5 : Unifier labels et icônes (WorkflowStepNode, executionRenderers, ActionWizard) depuis capacités.

---

### Story 82.7 — ActionWizard et formulaires schema-driven

**Priorité :** Moyenne  
**Effort estimé :** L

**Description :**  
Rendre l'ActionWizard et les formulaires d'action pilotés par schéma.

**Acceptance criteria :**
- AC1 : Le choix de plateforme charge opérations disponibles, config spécifique, champs obligatoires depuis capacités.
- AC2 : Section AAP/Tower devient cas standard de "plugin plateforme".
- AC3 : Validation inline frontend alignée avec schémas backend.
- AC4 : Supprimer ou réduire fortement serviceCallConstants.ts comme source de vérité.
- AC5 : Tests : ActionWizard avec plateforme générée par metadata.

---

### Story 82.8 — Actions et workflows consomment capacités

**Priorité :** Moyenne  
**Effort estimé :** M

**Description :**  
Faire des actions et workflows des consommateurs standards des capacités.

**Acceptance criteria :**
- AC1 : Action de type plateforme configurée à partir des capacités de la plateforme sélectionnée.
- AC2 : Backend valide config d'action via schéma.
- AC3 : Palette des steps workflow pilotée par step definitions disponibles.
- AC4 : Chaque step déclare label, schema, contraintes, prérequis runtime.
- AC5 : Tests : nouveau step service_call ou gate déclaré uniquement via définition backend.

---

### Story 82.9 — Migration et nettoyage constantes legacy

**Priorité :** Moyenne  
**Effort estimé :** L

**Description :**  
Supprimer la dette de compatibilité devenue inutile.

**Acceptance criteria :**
- AC1 : Supprimer mappings frontend obsolètes (integrationHelpers, serviceCallConstants).
- AC2 : Supprimer aliases backend redondants.
- AC3 : Dépréquer anciens champs/constantes.
- AC4 : Tests de non-régression "nouveau plugin visible partout".
- AC5 : E2E : créer intégration nouveau type → action → workflow → exécuter → cohérence UI/runtime.

---

## 4. Critères de succès (Epic)

- **Ajouter une nouvelle plateforme** : adapter + définition + enregistrement → visible partout, pas de modif frontend pour lister.
- **Ajouter un nouveau service** : client + définition opérations → pas de duplication constantes frontend/backend.
- **Ajouter un nouveau gate** : définition enregistrée → pas de switch dispersés.
- **Actions et workflows** consomment les mêmes capacités que le runtime.

---

## 5. Ordre recommandé

1. 82-1 (Phase 0)
2. 82-2, 82-3 (Platform + Service definitions)
3. 82-4 (API capacités)
4. 82-5 (GateRegistry)
5. 82-6, 82-7 (Frontend schema-driven)
6. 82-8 (Actions/workflows)
7. 82-9 (Nettoyage)
