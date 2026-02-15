# Mapping REF_PLATFORMS ↔ IntegrationTypeCatalogue

> **Story 29.4** — Lien explicite entre les codes plateformes du catalogue d'actions et les types d'intégration.

## Objectif

Garantir la cohérence entre `action.platform` (référence REF_PLATFORMS) et `integration.type` (IntegrationTypeCatalogue) lorsque les deux champs sont renseignés sur une action du catalogue.

## Tableau de mapping

| REF_PLATFORMS.CODE | IntegrationTypeCatalogue.code | Cohérence | Notes |
|--------------------|-------------------------------|-----------|-------|
| AAP                | aap                           | ✓ Cohérent | Casse différente mais même entité |
| Tower              | tower                         | ✓ Cohérent | Ajouté Story 29.4 (migration V073) |
| GitHub Actions     | github_actions                | ✓ Cohérent | Espaces → underscores (convention) |
| Azure DevOps       | azure_devops                  | ✓ Cohérent | Espaces → underscores (convention) |
| Terraform          | terraform_cloud               | ⚠️ Partiel | Terraform générique vs Cloud spécifique |
| Terraform Cloud    | terraform_cloud               | ✓ Cohérent | Ajouté Story 29.4 (migration V073) |

## Convention de normalisation

La transformation pour le matching suit la même convention que Story 29.3 (REF_ENGINES ↔ engine_type) :

- **REF_PLATFORMS.CODE** : Title Case, espaces autorisés (ex. `GitHub Actions`)
- **IntegrationTypeCatalogue.code** : snake_case minuscules (ex. `github_actions`)
- **Transformation** : `.lower().replace(' ', '_')`

```python
def normalize_platform_code(ref_platform_code: str) -> str:
    """
    Normalise REF_PLATFORMS.CODE vers format IntegrationTypeCatalogue.code.

    Examples:
        "AAP" → "aap"
        "GitHub Actions" → "github_actions"
        "Terraform Cloud" → "terraform_cloud"
    """
    return ref_platform_code.lower().replace(' ', '_')
```

## Règles de validation

### Quand la validation s'applique

La validation cohérence `platform ↔ integration.type` s'applique **uniquement** quand les deux champs sont fournis lors de la création ou édition d'une action :

| platform | integration_id | Validation |
|----------|---------------|------------|
| Fourni   | Fourni        | ✓ Validation cohérence appliquée |
| Fourni   | Absent        | ✗ Skip (platform seul est valide) |
| Absent   | Fourni        | ✗ Skip (integration seul est valide) |
| Absent   | Absent        | ✗ Skip |

### Vérifications effectuées

1. **Rôle de l'intégration** : si l'intégration est un **service** (vault, servicenow, jira, splunk), la combinaison avec `platform` est invalide — les services ne sont pas des plateformes d'exécution.
2. **Cohérence des codes** : le code platform normalisé doit correspondre au type d'intégration (ex. `GitHub Actions` → `github_actions`).

### Exemples valides

```json
// AAP avec intégration AAP → OK
{
  "platform": "AAP",
  "integration_id": 1  // integration.type = "aap"
}

// GitHub Actions avec intégration GitHub Actions → OK
{
  "platform": "GitHub Actions",
  "integration_id": 2  // integration.type = "github_actions"
}

// Platform seul, pas d'intégration → OK (skip validation)
{
  "platform": "Terraform Cloud"
}
```

### Exemples invalides

```json
// Platform AAP avec intégration ServiceNow (service, pas plateforme) → 400
{
  "platform": "AAP",
  "integration_id": 5  // integration.type = "servicenow", role = "service"
}
// Erreur: "Integration 'XXX' is a service (type 'servicenow'), but action.platform is set."

// Platform AAP avec intégration GitHub Actions (incohérent) → 400
{
  "platform": "AAP",
  "integration_id": 2  // integration.type = "github_actions"
}
// Erreur: "Platform 'AAP' is inconsistent with integration type 'github_actions'."
```

## Cas particulier : Terraform vs Terraform Cloud

REF_PLATFORMS contient à la fois `Terraform` (générique) et `Terraform Cloud` (spécifique). Seul `Terraform Cloud` a un mapping exact avec IntegrationTypeCatalogue (`terraform_cloud`).

- `Terraform` normalisé = `terraform` ≠ `terraform_cloud` → **incohérent** si couplé avec une intégration terraform_cloud
- `Terraform Cloud` normalisé = `terraform_cloud` = `terraform_cloud` → **cohérent**

### Migration des actions existantes

**Pour les actions avec `platform='Terraform'` existantes :**

1. **Pas d'intégration liée** : Aucune action requise — `Terraform` reste valide comme plateforme générique.
2. **Intégration Terraform Cloud liée** : L'action sera **rejetée** par la validation si vous essayez de la modifier. Solutions :
   - **Option A (recommandé)** : Mettre à jour `platform` de `Terraform` → `Terraform Cloud` pour cohérence.
   - **Option B** : Retirer le lien `integration_id` si l'intégration n'est pas nécessaire.

**Recommandation future :** Utiliser `Terraform Cloud` pour toutes les nouvelles actions liées à une intégration Terraform Cloud spécifique. Réserver `Terraform` pour des actions génériques non liées à une intégration spécifique.

## Références

- [Glossaire Platform/Engine/Service](../../docs/glossaire-plateforme-moteur-service.md)
- [Rapport technique Section 2.2](../../docs/rapport-bases-moteurs-technologies-integrations.md)
- [Inventory mapping guide (Story 29.3)](./inventory-mapping-guide.md)
- Migration V051 : création REF_PLATFORMS
- Migration V073 : ajout Tower et Terraform Cloud
