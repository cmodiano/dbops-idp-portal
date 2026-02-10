# Guide de migration des intégrations (Epic 24)

## Vue d'ensemble

L'Epic 24 introduit un **catalogue de types d'intégration** qui encadre les types et actions supportés par le backend (AAP, ServiceNow, etc.). Les intégrations créées avant ce catalogue doivent être validées et migrées pour assurer la cohérence du système.

**Objectifs :**
- Identifier les intégrations non conformes au catalogue
- Mettre à jour automatiquement les statuts (`valid`, `deprecated`, `invalid`)
- Marquer les intégrations irrécupérables comme `legacy`
- Bloquer l'exécution avec des intégrations invalides

**Documentation associée :**
- [Catalogue des types d'intégration](integration-type-catalogue.md) (Story 24.1)
- [Validation des statuts d'intégration](integration-status-validation.md) (Story 24.3)

## Étapes de migration

### Étape 1 : Analyse (`analyze_integrations`)

Analyse en lecture seule — aucune modification en base.

```bash
python manage.py analyze_integrations
```

**Sortie exemple :**
```
=== ANALYSE DES INTÉGRATIONS EXISTANTES ===
Catalogue chargé : 2 types actifs (aap, servicenow)

Intégrations trouvées : 15 total
  ✓ Valides (type dans catalogue actif) : 10
    - ID 1: AAP Dev (type: aap) ✓
    - ID 2: AAP Prod (type: aap) ✓

  ⚠ Dépréciées (type dans catalogue mais is_active=False) : 2
    - ID 8: Terraform Cloud (type: terraform) — type déprécié

  ✗ Invalides (type inexistant dans catalogue) : 3
    - ID 12: Custom Script Runner (type: custom_script) — type inconnu
```

Un rapport JSON est sauvegardé automatiquement : `integration_analysis_YYYYMMDD_HHMMSS.json`

### Étape 2 : Validation catalogue

Si des intégrations sont invalides parce que leur type n'existe pas dans le catalogue, vous pouvez créer les types manquants :

```python
from integrations.models import IntegrationTypeCatalogue

IntegrationTypeCatalogue.objects.create(
    code='jenkins',
    name='Jenkins',
    description='Jenkins CI/CD',
    version='1.0',
    is_active=True,
)
```

### Étape 3 : Migration automatique (`migrate_integrations --auto`)

Prévisualiser d'abord avec `--dry-run` :

```bash
python manage.py migrate_integrations --auto --dry-run
```

```
=== MIGRATION DES INTÉGRATIONS (DRY-RUN) ===
⚠ MODE DRY-RUN : Aucune modification ne sera effectuée

Changements prévus :
  - ID 8: Terraform Cloud — valid → deprecated
  - ID 12: Custom Script Runner — valid → invalid

Total : 2 intégrations seraient mises à jour
```

Appliquer les changements :

```bash
python manage.py migrate_integrations --auto
```

Chaque mise à jour crée une entrée d'audit `INTEGRATION_STATUS_UPDATED` avec le `correlation_id` de la migration.

### Étape 4 : Marquage legacy (`migrate_integrations --mark-legacy`)

Pour les intégrations invalides qui ne peuvent pas être corrigées :

```bash
python manage.py migrate_integrations --mark-legacy
```

Cette commande :
- Ajoute `"_legacy": true` dans le champ `config` JSON de chaque intégration `INVALID`
- Crée des entrées d'audit `INTEGRATION_MARKED_LEGACY`
- Affiche les actions/workflows utilisant ces intégrations

### Étape 5 : Mise à jour workflows impactés

La commande `--mark-legacy` affiche les actions liées aux intégrations legacy :

```
Workflows/Actions existants utilisant ces intégrations :
  - Action "Deploy to Azure" (ID 42) utilise ID 9 (Azure DevOps Legacy)
  → ACTION REQUISE : Mettre à jour l'action pour utiliser une intégration valide
```

## Scénarios de migration

### Scénario A : Toutes les intégrations sont valides

Aucune action nécessaire. Le rapport `analyze_integrations` confirmera :
```
Intégrations trouvées : 10 total
  ✓ Valides : 10
```

### Scénario B : Quelques intégrations dépréciées

1. Exécuter `migrate_integrations --auto` pour mettre à jour les statuts
2. Planifier la migration des actions utilisant ces intégrations vers des types actifs
3. Les exécutions avec intégrations dépréciées fonctionnent toujours (avec un avertissement)

### Scénario C : Intégrations invalides

1. **Option 1** : Créer les types manquants dans `IntegrationTypeCatalogue`
2. **Option 2** : Marquer comme legacy avec `--mark-legacy`
3. Les exécutions avec intégrations invalides sont **bloquées** (HTTP 400)

## Dépannage

### Que faire si une intégration est marquée INVALID ?

1. Vérifier si le type existe dans le catalogue : `python manage.py shell -c "from integrations.models import IntegrationTypeCatalogue; print(list(IntegrationTypeCatalogue.objects.values_list('code', flat=True)))"`
2. Si le type manque : créer l'entrée dans `IntegrationTypeCatalogue`
3. Si le type est obsolète : soit marquer comme legacy (`--mark-legacy`), soit migrer l'action vers un type supporté

### Comment réactiver une intégration legacy ?

1. Créer le type correspondant dans `IntegrationTypeCatalogue` (si nécessaire)
2. Exécuter : `python manage.py migrate_integrations --auto` (MEDIUM-2 FIX: commande corrigée)
3. Retirer la clé `"_legacy"` du champ `config` de l'intégration

### Comment savoir quels workflows sont impactés ?

Exécuter `migrate_integrations --mark-legacy --dry-run` pour lister les actions liées aux intégrations invalides sans modifier la base.

## Référence des commandes

### `analyze_integrations`

```
python manage.py analyze_integrations
```

| Option | Description |
|--------|-------------|
| *(aucune)* | Analyse en lecture seule, rapport console + JSON |

### `migrate_integrations`

```
python manage.py migrate_integrations [--auto] [--mark-legacy] [--dry-run]
```

| Option | Description |
|--------|-------------|
| `--auto` | Met à jour le statut de chaque intégration selon le catalogue |
| `--mark-legacy` | Ajoute `_legacy: true` aux intégrations INVALID |
| `--dry-run` | Prévisualise sans modifier la base (compatible avec `--auto` et `--mark-legacy`) |

### Validation automatique (Story 24.3)

**MEDIUM-2 FIX:** La validation des intégrations se fait automatiquement lors de la création/mise à jour via `IntegrationService`. Il n'existe **pas** de commande standalone `validate_integrations`.

Pour forcer une re-validation de toutes les intégrations existantes, utilisez :
```bash
python manage.py migrate_integrations --auto [--dry-run]
```

## Garde-fous d'exécution

### Blocage des intégrations invalides (AC4)

Toute tentative d'exécution avec une intégration `INVALID` retourne :
- **HTTP 400** avec code `INVALID_INTEGRATION`
- Entrée d'audit `EXECUTION_BLOCKED_INVALID_INTEGRATION`
- Aucune exécution n'est créée

### Avertissement pour intégrations dépréciées (AC4)

Les exécutions avec une intégration `DEPRECATED` :
- **Sont autorisées** normalement
- Génèrent un **WARNING** structlog
- Créent une entrée d'audit `EXECUTION_DEPRECATED_INTEGRATION_WARNING`

### Workflows (AC5)

Les mêmes règles s'appliquent aux steps de workflow :
- Intégration `INVALID` → workflow marqué `FAILED`
- Intégration `DEPRECATED` → avertissement, exécution continue
