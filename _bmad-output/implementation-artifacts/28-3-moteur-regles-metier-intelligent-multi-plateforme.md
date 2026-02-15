# Story 28.3 : Moteur de règles métier intelligent multi-plateforme

Status: backlog

<!-- Note: Moteur générique qui s'adapte aux plateformes via des interpréteurs (OutputInterpreter) enregistrés par step_type. Dépend de 28.1 (schéma) et 28.2 (premier cas Terraform) ; généralise en RuleEngine + registre d'interpréteurs. -->

## Story

En tant qu'**équipe produit**,
je veux **un moteur de règles métier qui s'adapte aux différentes plateformes (Terraform Cloud, AAP, Azure DevOps, GitHub Actions, etc.) via des interpréteurs de sortie d'étape enregistrés**,
afin que **on puisse définir des politiques (revue, auto-approve, blocage) sur la sortie de n'importe quel type d'étape sans coder la logique en dur par plateforme dans le noyau**.

## Acceptance Criteria

**AC1 — RuleEngine et dispatch par step_type**

**Given** une action avec business_rule_policies ciblant un `when.step_type` (ex. terraform_cloud, aap, azure_devops),
**When** une étape de ce type a produit sa sortie (output),
**Then** le **moteur de règles** (RuleEngine) charge les règles de l'action, identifie la règle dont le `when` matche (step_type, output_key),
**And** il délègue à un **interpréteur** (OutputInterpreter) enregistré pour ce step_type : l'interpréteur transforme la sortie brute en un **artefact normalisé** (ex. pour Terraform : liste de changes avec resource_type, attribute_paths ; pour AAP : job_status, failed_tasks, etc.),
**And** le moteur applique la **politique** (review_if_modified, ou autres types futurs) sur cet artefact et retourne la décision (require_approval, auto_approved, block, etc.).

**AC2 — Extensibilité : nouvel interpréteur sans toucher au noyau**

**Given** une nouvelle plateforme (ex. nouveau type d'étape),
**When** on souhaite appliquer des règles métier sur sa sortie,
**Then** on peut **enregistrer un nouvel interpréteur** (classe ou module implémentant l'interface OutputInterpreter) sans modifier le noyau du moteur,
**And** le schéma des politiques peut rester générique ou accepter des critères spécifiques par type d'artefact (documentés par interpréteur).

**AC3 — Interpréteurs fournis et documentation**

**And** au minimum les interpréteurs **Terraform Cloud** (plan output) et **AAP** (job status / logs) sont fournis ou documentés comme premiers cas ; l'architecture permet d'ajouter Azure DevOps, GitHub Actions, etc.,
**And** la documentation décrit l'architecture (RuleEngine, registre d'interpréteurs, format artefact normalisé) et comment ajouter un interpréteur pour une nouvelle plateforme,
**And** des tests valident le dispatch par step_type et l'évaluation de la politique sur l'artefact produit par chaque interpréteur.

## Tasks / Subtasks

- [ ] Task 1 — Architecture RuleEngine et interface OutputInterpreter
  - [ ] 1.1 Définir l'interface OutputInterpreter : méthode `interpret(step_type, step_output) -> NormalizedArtifact` (structure commune ou typée par step_type)
  - [ ] 1.2 Définir un **registre** (registry) d'interpréteurs : step_type -> instance OutputInterpreter
  - [ ] 1.3 Implémenter le RuleEngine : entrée (action, step, step_output) ; chargement business_rule_policies ; sélection de la règle via when ; appel de l'interpréteur ; application de la politique sur l'artefact ; retour (require_approval, auto_approved, block, details)
  - [ ] 1.4 Définir le format **NormalizedArtifact** minimal (ou un type union par plateforme) pour que les politiques génériques (review_if_modified) puissent s'appuyer sur des champs communs (ex. changes[], resource_type, attribute_paths) ou déléguer au type d'artefact

- [ ] Task 2 — Interpréteur Terraform Cloud
  - [ ] 2.1 Réutiliser ou extraire le parsing du plan (Story 28.2) dans un TerraformPlanInterpreter implémentant OutputInterpreter
  - [ ] 2.2 Produire un artefact normalisé (ex. TerraformPlanArtifact avec resource_changes[{ resource_type, address, attribute_paths[] }])
  - [ ] 2.3 Enregistrer l'interpréteur pour step_type "terraform_cloud"

- [ ] Task 3 — Interpréteur AAP
  - [ ] 3.1 Définir AAPOutputInterpreter : entrée = sortie d'étape AAP (job status, logs, failed_tasks, etc.) ; sortie = artefact normalisé (ex. AAPJobArtifact avec status, failed_tasks[], changed_hosts[], etc.)
  - [ ] 3.2 Documenter les politiques applicables (ex. require_review_if_failed_tasks, auto_approve_if_success) et le schéma de règle correspondant
  - [ ] 3.3 Implémenter et enregistrer pour step_type "aap"

- [ ] Task 4 — Politiques génériques et spécifiques
  - [ ] 4.1 Le moteur supporte au moins le type de politique "review_if_modified" (déjà défini pour Terraform) ; pour AAP, définir un type de politique cohérent (ex. review_if_failure ou critères sur l'artefact AAP)
  - [ ] 4.2 Permettre des critères optionnels spécifiques par step_type dans la règle (ex. policy.terraform.require_review_if_modified, policy.aap.require_review_if_failed_tasks) tout en gardant une structure commune

- [ ] Task 5 — Documentation et tests
  - [ ] 5.1 Rédiger docs/ (ou implementation-artifacts/) : architecture du moteur, diagramme de séquence, comment enregistrer un nouvel interpréteur, format artefact par plateforme
  - [ ] 5.2 Tests unitaires : RuleEngine avec mocks (interpréteur mock, action avec règles), dispatch correct, décision selon artefact
  - [ ] 5.3 Tests par interpréteur : TerraformPlanInterpreter et AAPOutputInterpreter avec sorties mock, artefact attendu
  - [ ] 5.4 Test d'intégration : action avec règle Terraform + action avec règle AAP, étape produit output, moteur retourne la bonne décision

## Dev Notes

### Contexte

- **Epic 28** : Story 28.1 (schéma + UI), 28.2 (PolicyEvaluator + Terraform). Cette story **généralise** en un **moteur intelligent multi-plateforme** : un seul RuleEngine qui délègue à des interpréteurs par step_type, évitant de dupliquer la logique dans le noyau.
- "Intelligent" = **s'adapte** : le même moteur évalue les règles en fonction du type d'étape grâce aux interpréteurs qui normalisent la sortie en un artefact exploitable par les politiques.

### Architecture cible

```
RuleEngine
  ├── load business_rule_policies(action)
  ├── find rule where when.step_type == step.step_type [, when.output_key]
  ├── get OutputInterpreter(step_type) from Registry
  ├── artifact = interpreter.interpret(step_type, step_output)
  ├── decision = evaluate_policy(rule.policy, artifact)
  └── return decision (require_approval | auto_approved | block, details)

Registry
  ├── terraform_cloud -> TerraformPlanInterpreter
  ├── aap -> AAPOutputInterpreter
  └── (futur) azure_devops -> AzureDevOpsOutputInterpreter
```

### Format NormalizedArtifact

- Soit **une structure commune** (ex. `{ "changes": [{ "resource_type", "attribute_paths" }], "metadata": {} }`) que chaque interpréteur remplit selon ses capacités.
- Soit **des types dédiés par plateforme** (TerraformPlanArtifact, AAPJobArtifact) et le moteur délègue l'évaluation de la politique à un **PolicyHandler** par type de politique et/ou par type d'artefact. Pour garder un moteur simple au départ, une structure commune avec champs optionnels par plateforme est suffisante.

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 28, Stories 28.1 à 28.3.
- [Source: 28-2-policy-evaluator-terraform-plan-review-if-modified.md] — Premier cas Terraform, à factoriser en interpréteur.
- [Source: idp-portal/django_backend/adapters/] — Adapters par plateforme (structure extensible à réutiliser pour le registre).
