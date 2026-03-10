# idp-config/ — Configuration CaC du portail IDP

## Présentation

Ce répertoire contient la **source de vérité** de la configuration du portail IDP, gérée en
Configuration-as-Code (CaC). Le principe fondamental est :

> **Git = source de vérité. Base de données = cache runtime.**

Toute modification de configuration passe par un commit dans ce répertoire, puis le pipeline
CI/CD applique la configuration via l'API (script `apply_idp_config.py` → endpoints `POST .../sync/`).
Les modifications directes en UI sont réservées aux urgences opérationnelles et doivent être
répercutées dans Git dès que possible.

## Structure du répertoire

```
idp-config/
├── README.md                         ← Ce fichier
├── reference/
│   ├── engines.yaml                  # kind: ReferenceData, metadata.type: engines
│   └── categories.yaml               # kind: ReferenceData, metadata.type: categories
├── tags.yaml                         # kind: Tags
├── feature-flags.yaml                # kind: FeatureFlags
├── integration-types/
│   └── <code>.yaml                   # kind: IntegrationTypeCatalogue (un fichier par type)
├── integrations/
│   └── <name>.yaml                   # kind: Integration (un fichier par intégration)
├── policies/
│   └── <name>.yaml                   # kind: BusinessRulePolicy (un fichier par policy)
├── actions/
│   └── <name>.yaml                   # kind: Action | WorkflowAction (un fichier par action)
└── profiles/
    └── <name>.yaml                   # kind: Profile (un fichier par profil)
```

## Format des fichiers YAML (envelope CaC)

Chaque fichier YAML respecte l'envelope standard :

```yaml
apiVersion: idp/v1
kind: <Kind>
metadata:
  name: <identifiant-unique>    # Pour les entités nommées
  # ou
  type: <type>                  # Pour ReferenceData (engines/categories)
spec:
  # Champs spécifiques à l'entité
```

### Kinds valides

| Kind                     | Répertoire/fichier           | Clé de lookup        |
|--------------------------|------------------------------|----------------------|
| `ReferenceData`          | `reference/engines.yaml`     | `code`               |
| `ReferenceData`          | `reference/categories.yaml`  | `code`               |
| `Tags`                   | `tags.yaml`                  | `name` (normalisé)   |
| `FeatureFlags`           | `feature-flags.yaml`         | `key`                |
| `IntegrationTypeCatalogue` | `integration-types/<code>.yaml` | `code`           |
| `Integration`            | `integrations/<name>.yaml`   | `name`               |
| `BusinessRulePolicy`     | `policies/<name>.yaml`       | `name`               |
| `Action`                 | `actions/<name>.yaml`        | `name`               |
| `WorkflowAction`         | `actions/<name>.yaml`        | `name`               |
| `Profile`                | `profiles/<name>.yaml`       | `name`               |

## Commandes disponibles

### Import via API (CI/CD)

L'import de la configuration en base se fait exclusivement via les endpoints API `POST .../sync/`,
appelés par le script de pipeline `apply_idp_config.py`. Il n'y a pas de commande management
Django pour l'import.

**Endpoints d'import :**

| Entité              | Endpoint                                          |
|---------------------|---------------------------------------------------|
| Actions (catalogue) | `POST /api/iac/catalog/actions/sync/`             |
| Profils             | `POST /api/iac/catalog/profiles/sync/`            |
| Intégrations        | `POST /api/iac/integrations/sync/`                |
| Données de référence| `POST /api/iac/reference-data/sync/`              |

**Modes disponibles :** `additive` (défaut) ou `full` (avec suppression des orphelins).

### `detect_drift` — Détecter les divergences Git ↔ DB

```bash
# Rapport de dérive textuel (défaut)
python manage.py detect_drift --config-dir ./idp-config/

# Rapport JSON (pour intégration CI/CD)
python manage.py detect_drift --config-dir ./idp-config/ --format json

# Dérive sur un type spécifique seulement
python manage.py detect_drift --config-dir ./idp-config/ --type engines
```

### `apply_idp_config.py` — Script CI/CD

Script de pipeline qui orchestre validation → dry-run → application. À utiliser dans le
pipeline GitHub Actions ou GitLab CI.

```bash
python scripts/apply_idp_config.py --config-dir ./idp-config/ --env staging
```

## Flux complet : exemple export → modification → sync

**Objectif :** Modifier la description d'une action existante.

### 1. Exporter l'action depuis la DB (optionnel si le fichier YAML existe déjà)

```bash
# Via l'API (endpoint export single-entity)
curl -H "Authorization: Bearer $TOKEN" \
     https://idp.example.com/api/iac/catalog/actions/deploy-oracle/export/ \
     -o idp-config/actions/deploy-oracle.yaml
```

### 2. Modifier le fichier YAML

```yaml
# idp-config/actions/deploy-oracle.yaml
apiVersion: idp/v1
kind: Action
metadata:
  name: deploy-oracle
spec:
  engine: Oracle
  platform: AAP
  status: published
  item_type: action
  requires_target: true
  description: "Déploiement Oracle via Ansible Automation Platform"  # ← modifié
  integration_ref: aap-prod
```

### 3. Committer et pousser

```bash
git add idp-config/actions/deploy-oracle.yaml
git commit -m "feat(config): update deploy-oracle description"
git push
```

### 4. Le pipeline CI/CD applique automatiquement la configuration

```
Validate YAML → Dry-run staging → Apply staging → Apply production
```

Le script `apply_idp_config.py` orchestre la validation et l'application via les endpoints API.

## Ordre de dépendances

Les entités sont synchronisées dans cet ordre strict (respecté par les endpoints API d'import) :

```
1. reference/engines.yaml      (aucune dépendance)
2. reference/categories.yaml   (aucune dépendance)
3. tags.yaml                   (aucune dépendance)
4. feature-flags.yaml          (aucune dépendance)
5. integration-types/          (aucune dépendance)
6. integrations/               (→ integration-types)
7. policies/                   (aucune dépendance FK)
8. actions/                    (→ integrations, policies)
9. profiles/                   (→ actions)
```

**Important :** Ne jamais inverser cet ordre lors d'imports manuels. Une action référençant
une intégration non encore créée lèvera `REF_NOT_FOUND`.

## Modes de synchronisation

### Mode `additive` (défaut)

- Crée les entités absentes de la DB.
- Met à jour les entités modifiées.
- **Ne supprime jamais** les entités présentes en DB mais absentes du YAML.

Utilisation : déploiements quotidiens, ajouts de configuration.

### Mode `full`

- Crée, met à jour **et supprime** les entités orphelines (présentes en DB, absentes du YAML).
- Pour les entités M2M (tags d'actions, mutex) : remplace la liste complète.
- Pour les intégrations individuelles : ne supprime pas les autres intégrations.

**Attention :** Le mode `full` est destructif pour les données de référence et les profils.
Toujours exécuter un dry-run via `apply_idp_config.py --dry-run` ou l'API avant `--mode full`
en production.

## Règles de sécurité

### Secrets : jamais dans les fichiers YAML

Les `credential_ref` des intégrations référencent des chemins Vault. À l'**export**, le dernier
segment du chemin est masqué automatiquement (`secret/integrations/***`). Ne jamais écrire le
chemin complet dans Git.

```yaml
# ✅ Correct (masqué)
spec:
  credential_ref: "secret/integrations/***"

# ❌ Interdit (secret exposé)
spec:
  credential_ref: "secret/integrations/aap-prod-token"
```

### Validation des références

Toute `integration_ref`, `business_rule_policy_ref` ou `action_names` doit correspondre à une
entité existante en DB (déjà importée ou présente). Sinon, l'import lève `REF_NOT_FOUND`.

## Codes d'erreur

| Code                    | Description                                              | Cause typique                                      | Remédiation                                            |
|-------------------------|----------------------------------------------------------|----------------------------------------------------|--------------------------------------------------------|
| `INVALID_YAML_SYNTAX`   | YAML syntaxiquement invalide                             | Indentation incorrecte, brackets non fermés        | Corriger la syntaxe YAML avec un linter                |
| `ENVELOPE_MISSING_FIELD`| Champ obligatoire absent de l'envelope                   | `apiVersion`, `kind` ou `metadata` manquant        | Vérifier que tous les champs de l'envelope sont présents |
| `UNSUPPORTED_KIND`      | Valeur de `kind` non reconnue                            | Faute de frappe ou kind non supporté               | Utiliser un kind valide (voir tableau ci-dessus)       |
| `REF_NOT_FOUND`         | Référence FK non trouvée en DB                           | Entité référencée non encore importée              | Respecter l'ordre de dépendances, vérifier le nom      |
| `DUPLICATE_KEY`         | Clé unique dupliquée dans un import batch                | Même tag ou même nom présent deux fois dans le YAML | Supprimer le doublon dans le fichier YAML              |

### Codes additionnels

| Code                    | Description                                              |
|-------------------------|-------------------------------------------------------------|
| `INVALID_API_VERSION`   | `apiVersion` absent ou != `idp/v1`                       |
| `INVALID_KIND`          | `kind` absent, null, ou non reconnu dans VALID_KINDS     |
| `INVALID_METADATA`      | `metadata` absent ou non-dictionnaire                    |
| `WRONG_KIND`            | `kind` présent mais différent du kind attendu            |
| `INVALID_IMPORT_MODE`   | `mode` != `additive` et != `full`                        |
| `REF_TYPE_MISMATCH`     | Le `metadata.type` YAML ne correspond pas au `ref_type` attendu |

## Ressources

- [Stratégie CaC](../../docs/architecture/configuration-as-code-strategy.md) — paradigme et flux CI/CD
- [Guide d'implémentation CaC](../../docs/architecture/configuration-as-code-implementation-guide.md) — patterns techniques
- Commandes : `python manage.py detect_drift --help`
