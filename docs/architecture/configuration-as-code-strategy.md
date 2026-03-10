# Stratégie Configuration-as-Code (CaC) — Portail IDP

## Paradigme : Git-as-source-of-truth

Le portail IDP adopte un paradigme Configuration-as-Code pour la gestion de sa configuration
opérationnelle. Le principe fondamental est :

| Couche | Rôle | Modificateurs |
|--------|------|---------------|
| **Git (`idp-config/`)** | Source de vérité canonique | Opérateurs, DevOps (via PR) |
| **Base de données** | Cache runtime, état courant | Pipeline CI/CD via API (`apply_idp_config.py`) |
| **Interface utilisateur** | Consultation et urgences uniquement | Admins (urgences opérationnelles) |

Toute configuration stable doit exister dans Git. Les modifications directes en UI sont
considérées comme temporaires et doivent être répercutées dans `idp-config/` au prochain cycle.

## Entités gérées

| Entité | Fichier YAML | Kind | Clé de lookup |
|--------|--------------|------|---------------|
| Moteurs de base de données | `reference/engines.yaml` | `ReferenceData` | `code` |
| Catégories d'actions | `reference/categories.yaml` | `ReferenceData` | `code` |
| Tags | `tags.yaml` | `Tags` | `name` (normalisé) |
| Feature Flags | `feature-flags.yaml` | `FeatureFlags` | `key` |
| Types d'intégrations | `integration-types/<code>.yaml` | `IntegrationTypeCatalogue` | `code` |
| Intégrations | `integrations/<name>.yaml` | `Integration` | `name` |
| Politiques de règles métier | `policies/<name>.yaml` | `BusinessRulePolicy` | `name` |
| Actions | `actions/<name>.yaml` | `Action` / `WorkflowAction` | `name` |
| Profils RBAC | `profiles/<name>.yaml` | `Profile` | `name` |

## Ordre de dépendances

Les entités respectent un graphe de dépendances acyclique. Les endpoints API d'import respectent
l'ordre suivant :

```
engines ──┐
categories─┤
tags ──────┤─→ (aucune dépendance externe)
flags ─────┤
           │
int-types──┤
           ↓
integrations ──────────→ (dépend de : int-types)
           ↓
policies ──┤─→ (aucune dépendance FK)
           ↓
actions ───────────────→ (dépend de : integrations, policies)
           ↓
profiles ──────────────→ (dépend de : actions)
```

**Règle absolue :** Ne jamais tenter d'importer une entité avant que ses dépendances soient
présentes en base. Une violation lève `REF_NOT_FOUND`.

## Flux CI/CD

### Vue d'ensemble

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌────────────────────────┐
│  PR créée   │───→│ Validate YAML│───→│ Dry-run staging │───→│    Apply staging       │
│ (Git push)  │    │ (syntax+env) │    │  (no DB writes) │    │ (apply_idp_config.py)  │
└─────────────┘    └──────────────┘    └─────────────────┘    └───────────┬────────────┘
                                                                          │
                                                              ┌───────────▼──────────┐
                                                              │  Apply production    │
                                                              │  (after approval)    │
                                                              └──────────────────────┘
```

### Étapes du pipeline

#### 1. Validate PR (`on: pull_request`)

```bash
python scripts/apply_idp_config.py --config-dir ./idp-config/ --validate-only
```

Vérifie la syntaxe YAML et la validité des envelopes (`apiVersion`, `kind`, `metadata`).
Bloque la PR si validation échoue.

#### 2. Dry-run staging (`on: pull_request`)

```bash
python scripts/apply_idp_config.py --config-dir ./idp-config/ --env staging --dry-run
```

Simule l'import complet via les endpoints API sans écriture. Affiche les fichiers valides et les erreurs potentielles.

#### 3. Apply staging (`on: merge to develop`)

```bash
python scripts/apply_idp_config.py --config-dir ./idp-config/ --env staging
```

Applique la configuration en mode `additive` sur l'environnement de staging via les endpoints API.

#### 4. Apply production (`on: merge to main`, après approbation)

```bash
python scripts/apply_idp_config.py --config-dir ./idp-config/ --env production
```

Applique la configuration en production via les endpoints API. Requiert une approbation manuelle.

### Script CI/CD dédié

```bash
python scripts/apply_idp_config.py --config-dir ./idp-config/ --env <staging|production>
```

## Modes de synchronisation

### Mode `additive` (défaut)

Comportement conservateur et non-destructif :

- ✅ Crée les entités absentes de la DB
- ✅ Met à jour les champs modifiés
- ❌ Ne supprime jamais d'entités existantes

**Utilisation :** Déploiements quotidiens, ajouts de configuration, mises à jour progressives.

### Mode `full`

Comportement déclaratif (état final = contenu du YAML) :

- ✅ Crée les entités absentes de la DB
- ✅ Met à jour les champs modifiés
- ✅ Supprime les entités orphelines (présentes en DB, absentes du YAML)

**Utilisation :** Nettoyage de configuration, migration, refactoring du catalogue.

**⚠️ Attention :** Toujours exécuter `--dry-run` avant `--mode full` en production.

## Hors scope — Données runtime exclues

Les données suivantes sont **exclues du périmètre CaC** et ne sont jamais gérées par le processus CaC :

| Données | Raison de l'exclusion |
|---------|----------------------|
| Exécutions d'actions (`Execution`) | État runtime, cycle de vie propre |
| Logs d'audit (`AuditLog`) | Données d'observabilité, immuables |
| Tâches planifiées (`ScheduledTask`) | État runtime, configurable via UI |
| Sessions utilisateurs | Données d'authentification éphémères |
| Tâches (`Target`) | Découverte dynamique depuis CMDB |
| Demandes (`Request`) | Workflow runtime, non configurable statiquement |

## Indicateurs de dérive (Drift)

Le portail fournit plusieurs mécanismes pour détecter une divergence entre Git et la DB :

### `detect_drift` (commande management)

```bash
python manage.py detect_drift --config-dir ./idp-config/
```

Compare le hash YAML stocké en DB (`last_synced_hash`) avec le hash courant du fichier Git.
Retourne l'un de quatre statuts par entité :

| Statut | Signification |
|--------|---------------|
| `in_sync` | Hash identique, aucune divergence |
| `diverged` | Fichier Git modifié depuis dernier sync |
| `missing_in_yaml` | Entité en DB sans fichier YAML correspondant |
| `missing_in_db` | Fichier YAML sans entité correspondante en DB |

### `DriftBadge` (interface utilisateur)

Composant frontend affiché dans le tableau de bord Config Sync. La commande `detect_drift`
distingue quatre statuts (`in_sync`, `diverged`, `missing_in_yaml`, `missing_in_db`). Le
composant DriftBadge regroupe intentionnellement `missing_in_yaml` et `missing_in_db` en un
seul badge `missing` pour simplifier l'affichage. La remédiation diffère selon le statut
sous-jacent : `missing_in_yaml` → créer un fichier YAML ; `missing_in_db` → un import via
l'API (CI/CD) pour créer l'entité.

### Config Sync Dashboard

Tableau de bord centralisé (`/admin/config-sync/`) affichant l'état de drift global et
permettant le déclenchement de synchronisation manuelle.

## Risques et mitigations

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Références circulaires dans YAML | Import bloqué (`REF_NOT_FOUND`) | Respecter strictement l'ordre de dépendances |
| Mode `full` destructif | Suppression accidentelle d'entités | Obligatoire : `--dry-run` avant `--mode full` |
| Secrets dans Git | Exposition de credentials | Export masque automatiquement `credential_ref` ; contrôle de pre-commit |
| Conflit UI/Git | Divergence silencieuse | Monitoring DriftBadge, alertes `detect_drift` en CI |
| YAML malformé en PR | Pipeline bloqué | Step `validate-only` dans la PR gate |
| Entités orphelines en mode `full` | Perte de données | Audit log systématique de chaque opération de suppression |

## Références

- [Guide d'implémentation CaC](configuration-as-code-implementation-guide.md) — patterns techniques
- [idp-config/ README](../../idp-portal/idp-config/README.md) — structure et commandes
- [Codes d'erreur CaC](../../idp-portal/idp-config/README.md#codes-derreur) — liste complète avec remédiation
