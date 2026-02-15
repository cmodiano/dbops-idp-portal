# Story 28.2 : PolicyEvaluator et politique Terraform plan (revue si champs modifiés)

Status: backlog

<!-- Note: Évalue business_rule_policies après qu'une étape Terraform Plan ait produit sa sortie ; require_review_if_modified (resource_type, attribute_paths) ; branchement approbation DBA ou auto-approve. Dépend de 28.1 (champ business_rule_policies). -->

## Story

En tant que **système**,
je veux **évaluer les politiques business_rule_policies après qu'une étape ait produit sa sortie (ex. plan Terraform) et déclencher revue DBA ou auto-approbation selon la liste des champs/types modifiés**,
afin que **les actions (ex. provisionnement Azure SQL) puissent exiger une revue uniquement quand des champs sensibles sont modifiés dans le plan**.

## Acceptance Criteria

**AC1 — PolicyEvaluator et analyse du plan Terraform**

**Given** une action avec business_rule_policies contenant une politique de type "review_if_modified" sur une étape Terraform Cloud (output plan),
**When** l'étape Terraform Plan a produit sa sortie (plan output récupéré depuis Terraform Cloud),
**Then** un **PolicyEvaluator** (ou service dédié) analyse le plan (JSON ou texte parsé) et compare les changements à la liste **require_review_if_modified**,
**And** les entrées peuvent être : resource_type seul (toute modif sur ce type), resource_type + attribute_paths (seulement ces attributs), ou attribute_paths seul (n'importe quelle ressource),
**And** si au moins une entrée matche → la gate approbation est activée (require_approval, étape WAITING jusqu'à approbation DBA),
**And** si aucune ne matche et auto_approve_if_none_match est true → la gate est considérée satisfaite (auto-approuvé).

**AC2 — Branchement avec le flux d'approbation existant**

**Given** le PolicyEvaluator a déterminé "require_approval",
**When** le moteur d'exécution traite l'étape,
**Then** l'ExecutionStep reste en WAITING et le flux d'approbation existant (Epic 7) est utilisé ; le DBA peut approuver ou rejeter,
**And** une fois approuvé, l'étape peut passer à RUNNING (ou l'étape suivante "Apply" peut être déclenchée selon le design du workflow).

**AC3 — Parsing plan et tests**

**And** le parsing du plan Terraform (format Terraform Cloud / plan JSON ou sortie texte) est documenté ou implémenté pour extraire resource changes et attribute paths,
**And** des tests unitaires (plan mock) valident la logique de matching et la décision require_approval vs auto_approve,
**And** des tests d'intégration (optionnel) valident le branchement avec le GateEvaluator ou le flux d'approbation existant.

## Tasks / Subtasks

- [ ] Task 1 — Parsing du plan Terraform
  - [ ] 1.1 Définir la source du plan : sortie Terraform Cloud (logs plan, ou plan JSON si disponible via API Terraform Cloud)
  - [ ] 1.2 Implémenter un parser (ex. executions/terraform_plan_parser.py) qui extrait la liste des changements : resource address, resource_type, attribute paths modifiés (create/update/delete)
  - [ ] 1.3 Gérer le format plan JSON (terraform show -json) ou la sortie texte selon ce que Terraform Cloud expose

- [ ] Task 2 — PolicyEvaluator
  - [ ] 2.1 Créer un service PolicyEvaluator (ex. executions/policy_evaluator.py) qui : reçoit (action, step, step_output), charge business_rule_policies de l'action, trouve la règle dont when matche (step_type, output_key)
  - [ ] 2.2 Pour la politique "review_if_modified", comparer les changements du plan à require_review_if_modified (resource_type, attribute_paths) et retourner require_approval (bool) ou auto_approved
  - [ ] 2.3 Retourner un résultat structuré (require_approval, matched_rules, reason) pour que le moteur puisse créer une gate WAITING ou marquer la gate satisfaite

- [ ] Task 3 — Intégration dans le moteur d'exécution
  - [ ] 3.1 Après qu'une étape Terraform Cloud (plan) soit terminée avec succès, appeler le PolicyEvaluator avec l'output de l'étape
  - [ ] 3.2 Si require_approval : créer ou mettre à jour l'ExecutionStep en WAITING avec gate_conditions appropriées (approval_granted), ou déclencher le flux PENDING_APPROVAL existant (Epic 7)
  - [ ] 3.3 Si auto_approve : marquer la gate comme satisfaite et permettre la transition vers l'étape suivante (ou déclencher Apply)

- [ ] Task 4 — Documentation et tests
  - [ ] 4.1 Documenter le format du plan utilisé (JSON vs texte) et le mapping vers resource_type / attribute_paths
  - [ ] 4.2 Tests unitaires : parser avec plan mock (plusieurs resources, attribute_paths), PolicyEvaluator avec règles mock (match / no match, auto_approve_if_none_match)
  - [ ] 4.3 Tests d'intégration (optionnel) : exécution avec action ayant business_rule_policies, étape Terraform plan, vérifier WAITING ou passage suivant selon le plan

## Dev Notes

### Contexte

- **Epic 28** : Story 28.1 ajoute le champ business_rule_policies et l'UI. Cette story ajoute **l'évaluation** et le **branchement** avec approbation.
- **GateEvaluator** existant (Story 25.3) gère maintenance_window, approval_granted. Le PolicyEvaluator peut **alimenter** la gate approval_granted (en créant une demande d'approbation quand require_approval) ou en marquant la gate satisfaite (auto-approve).

### Format require_review_if_modified

- Objet avec `resource_type` seul : tout changement sur ce type de ressource.
- Objet avec `resource_type` + `attribute_paths` : seulement si un des attributs listés est dans le diff pour ce type.
- Objet avec `attribute_paths` seul : si un de ces attributs apparaît dans le plan (quelle que soit la ressource).

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 28, Stories 28.1 et 28.2.
- [Source: 28-1-modele-schema-regles-metier-business-rule-policies.md] — Schéma business_rule_policies.
- [Source: idp-portal/django_backend/executions/gate_evaluator.py] — GateEvaluator, gate approval_granted.
- [Source: idp-portal/django_backend/executions/views/approval_views.py] — Flux approbation Epic 7.
- [Source: Terraform plan JSON] — Structure du plan (resource_changes, change.actions, address, type).
