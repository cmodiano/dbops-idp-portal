# Story 28.1 : Modèle et schéma des règles métier (business_rule_policies) — stockage et édition

Status: backlog

<!-- Note: Règles métier "politique sur sortie d'étape" : champ JSON business_rule_policies sur Action, éditable via menu dédié admin. Pas d'évaluation runtime dans cette story. -->

## Story

En tant que **DBOPS**,
je veux **définir des règles métier par action dans un schéma JSON (business_rule_policies) stocké en base et éditable via un menu dédié dans l'admin**,
afin que **il soit facile de configurer quelles politiques s'appliquent à une action (ex. revue si certains champs du plan Terraform sont modifiés) sans coder**.

## Acceptance Criteria

**AC1 — Champ business_rule_policies sur Action**

**Given** le modèle Action existant,
**When** on étend le modèle pour supporter les règles métier "politique sur sortie d'étape",
**Then** un champ **business_rule_policies** (JSON, optionnel) est ajouté sur l'action (migration + modèle),
**And** le schéma JSON est documenté : structure `on_step_output[]` avec `when` (step_type, output_key), `policy` (type, require_review_if_modified avec resource_type / attribute_paths, auto_approve_if_none_match),
**And** une validation backend (validators) vérifie la conformité du JSON au schéma lors de la création/mise à jour de l'action.

**AC2 — Menu dédié admin pour éditer les règles**

**Given** un admin édite une action (catalogue admin),
**When** il accède à la section ou menu dédié "Règles métier" (onglet ou page),
**Then** il peut consulter et modifier le JSON business_rule_policies (formulaire structuré ou éditeur JSON avec schéma),
**And** les modifications sont persistées via l'API existante (PATCH action ou endpoint dédié),
**And** les règles ne sont pas liées à une plateforme globale mais à l'action ; le `when` peut référencer un step_type (ex. terraform_cloud) pour cibler l'étape concernée.

**AC3 — Documentation et tests**

**And** la documentation décrit la typologie des règles (impact_rules, change_type_config, gate_conditions, remediation_rules, business_rule_policies) et quand chacune est évaluée,
**And** des tests unitaires valident la validation du schéma et la persistance.

## Tasks / Subtasks

- [ ] Task 1 — Backend : champ et migration
  - [ ] 1.1 Ajouter champ business_rule_policies (OracleJSONField ou JSONField, null=True, blank=True) sur modèle Action
  - [ ] 1.2 Créer migration (Flyway/Oracle ou Django migration) pour la colonne BUSINESS_RULE_POLICIES (CLOB/JSON)
  - [ ] 1.3 Exposer le champ dans les serializers (lecture/écriture) et dans l'API catalogue (GET/PATCH action)

- [ ] Task 2 — Schéma et validation
  - [ ] 2.1 Documenter le schéma JSON dans docs/ (ex. docs/business-rule-policies-schema.md) : on_step_output[], when { step_type, output_key }, policy { type, require_review_if_modified[], auto_approve_if_none_match }
  - [ ] 2.2 Implémenter un validateur (catalog/validators.py ou dédié) qui vérifie la structure (liste, types, champs requis)
  - [ ] 2.3 Appeler le validateur dans le service catalogue (create/update action) et retourner erreur 400 si invalide

- [ ] Task 3 — Frontend : menu dédié "Règles métier"
  - [ ] 3.1 Ajouter un onglet ou une section "Règles métier" dans l'édition d'action (Admin catalogue) — selon structure actuelle (wizard, onglets, etc.)
  - [ ] 3.2 Afficher le contenu business_rule_policies : soit formulaire structuré (liste de règles, when/policy par règle), soit éditeur JSON avec validation côté client (schéma JSON Schema)
  - [ ] 3.3 Sauvegarder via PATCH action (ou endpoint dédié PATCH .../actions/{id}/business-rule-policies) et gérer erreurs de validation

- [ ] Task 4 — Documentation typologie des règles
  - [ ] 4.1 Rédiger ou mettre à jour un doc (docs/ ou implementation-artifacts/) listant : impact_rules, change_type_config, gate_conditions, remediation_rules, business_rule_policies — rôle de chaque bloc et moment d'évaluation

- [ ] Task 5 — Tests
  - [ ] 5.1 Tests unitaires : validation du schéma (entrées valides, invalides, champs manquants)
  - [ ] 5.2 Tests API : création/mise à jour action avec business_rule_policies, lecture
  - [ ] 5.3 Tests frontend (optionnel) : affichage et envoi du formulaire/éditeur

## Dev Notes

### Contexte

- **Epic 28** : Règles métier et politiques d'approbation. Cette story pose le **modèle et le stockage** ; l'évaluation runtime (PolicyEvaluator) est en Story 28.2.
- Les règles sont **par action**, pas par plateforme globale. Le `when.step_type` (ex. terraform_cloud) cible l'étape concernée pour l'évaluation future.

### Schéma JSON de référence (exemple)

```json
{
  "on_step_output": [
    {
      "id": "terraform_plan_review",
      "description": "Revue DBA si certains champs du plan sont modifiés",
      "when": {
        "step_type": "terraform_cloud",
        "output_key": "plan_output"
      },
      "policy": {
        "type": "review_if_modified",
        "require_review_if_modified": [
          { "resource_type": "azurerm_mssql_database" },
          { "resource_type": "azurerm_mssql_server", "attribute_paths": ["sku_name", "administrator_login"] },
          { "attribute_paths": ["max_size_gb", "zone_redundant"] }
        ],
        "auto_approve_if_none_match": true
      }
    }
  ]
}
```

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 28, Stories 28.1 et 28.2.
- [Source: idp-portal/django_backend/catalog/models.py] — Modèle Action (impact_rules, execution_steps, gate_conditions, remediation_rules).
- [Source: idp-portal/django_backend/catalog/validators.py] — validate_gate_conditions, pattern de validation.
