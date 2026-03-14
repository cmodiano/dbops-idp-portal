# Reset dev des workflows/actions via seed

Date: 2026-03-13  
Statut: Decision de travail (environnement DEV uniquement)  
Audience: Backend, DBA, QA

---

## 1) Contexte et decision

Le contexte confirme que la plateforme n'est pas encore utilisee en production (phase dev).  
Dans ce cadre, on valide une approche simple:

- supprimer les workflows/actions existants (et les donnees runtime associees)
- recreer un jeu propre avec la nouvelle structure via le script de seed

Objectif: accelerer le cleanup de l'ancien code path sans maintenir une compatibilite longue inutile en dev.

---

## 2) Pourquoi cette approche est adaptee (en dev)

1. **Faible risque metier**: pas d'historique client a preserver.
2. **Simplicite**: evite une migration complexe old->new pour des donnees jetables.
3. **Vitesse d'iteration**: permet de tester rapidement la nouvelle structure end-to-end.
4. **Lisibilite technique**: on supprime les cas hybrides (ancien + nouveau) dans les jeux de test.

---

## 3) Scope du reset

Le reset doit couvrir les domaines suivants pour repartir proprement:

1. **Definitions catalogue**
   - actions / workflows (structure legacy et nouvelle structure si presente)
2. **Permissions et rattachements**
   - tags, favoris, permissions de profils liees aux actions
3. **Runtime**
   - executions, steps, planifications
   - events / runnable steps / commandes / outbox (si alimentes)

Note: en pratique, l'ordre de suppression doit respecter les FK (children -> parents).

---

## 4) Procedure standard (DEV only)

## 4.1 Preconditions

- environnement explicitement `dev` / `development`
- workers d'orchestration arretes pendant le reset (eviter les ecritures concurrentes)
- base accessible avec credentials dev

## 4.2 Execution

Commande de reference:

```bash
python3 idp-portal/scripts/seed_dev_data.py --env=dev --reset
```

Ce mode:

- purge les donnees seed existantes
- recree users/profiles/tags/integrations/actions
- recree permissions/favoris/executions/steps de test

## 4.3 Verification minimale

1. Le script termine sans erreur.
2. Le resume final affiche des volumes coherents (users, actions, executions).
3. Le frontend charge correctement:
   - catalogue actions
   - ecran executions
   - pages admin principales

---

## 5) Garde-fous obligatoires

### 5.1 Valeurs d'environnement bloquées

Le script refuse explicitement toute exécution si l'une des valeurs suivantes est détectée dans `APP_ENV` **ou** `--env` :

- `staging`
- `production`
- `prod`

Ces valeurs sont définies dans la constante `BLOCKED_ENVIRONMENTS` dans `seed_dev_data.py`.

### 5.2 Logique de vérification (AND)

La logique est **AND** (vérification en quatre étapes distinctes) :

1. **Validation `--env`** : si `--env` est fourni, sa valeur doit être reconnue (présente dans `ALLOWED_ENVIRONMENTS` ou `BLOCKED_ENVIRONMENTS`). Toute valeur inconnue → `sys.exit(1)`.
2. **Blocage explicite** : si `APP_ENV` **ou** `--env` contient une valeur bloquée → `sys.exit(1)` immédiat avec message indiquant la source et la valeur détectée.
3. **Exigence dev** : au moins une des deux valeurs (`APP_ENV` ou `--env`) doit être dans `ALLOWED_ENVIRONMENTS` (`"development"`, `"dev"`). Si aucune n'est présente → `sys.exit(1)`.
4. **Double indicateur pour `--reset`** : en mode `--reset` (opération destructive), **les deux** indicateurs (`APP_ENV` et `--env`) doivent être explicitement définis à une valeur dev. Si l'un des deux est absent → `sys.exit(1)`.

Cette logique évite le cas où `--env=dev` masquerait silencieusement un `APP_ENV=staging`, et renforce la sécurité pour les opérations de purge.

### 5.3 Messages d'erreur attendus

| Situation | Message produit |
|-----------|----------------|
| `--env=foobar` (valeur inconnue) | `ERROR: Unrecognized --env value: 'foobar'.\nAccepted values: development, dev\nBlocked values: staging, production, prod` |
| `APP_ENV=staging` | `ERROR: Refused to run on APP_ENV=staging.\nThis script is NEVER allowed on staging or production environments.\nDetected: APP_ENV=staging, --env=(not set)` |
| `--env=prod` | `ERROR: Refused to run on --env=prod.\nThis script is NEVER allowed on staging or production environments.\nDetected: APP_ENV=(not set), --env=prod` |
| Aucun indicateur dev | `ERROR: This script can only run in development environment.\nCurrent: APP_ENV=(not set), --env=(not set)\nUse --env=dev or set APP_ENV=development` |
| `--reset` sans les deux indicateurs | `ERROR: --reset requires BOTH APP_ENV and --env to be explicitly set to a dev value.\nExample: APP_ENV=development python3 seed_dev_data.py --env=dev --reset` |
| Environnement valide | `Environment check passed: {valeur_dev}` (valeur `--env` si fournie, sinon `APP_ENV`) |

### 5.4 Autres garde-fous

4. **Trace operationnelle**: journaliser qui a lance le reset et quand (story 80.3).
5. **Fenetre de maintenance dev**: annoncer le reset a l'equipe pour eviter les faux positifs QA.

---

## 6) Ajustements recommandes au script de seed

Pour aligner completement avec la nouvelle orchestration, verifier que le reset inclut aussi (si utilisees):

- `WORKFLOW_EVENTS`
- `RUNNABLE_STEPS`
- `WORKFLOW_COMMANDS`
- `EXECUTION_OUTBOX`

Si ces tables ne sont pas deja videes par `--reset`, ajouter leur purge **avant** la suppression de `EXECUTIONS`.

---

## 7) Impact sur la roadmap cleanup

Cette decision permet de simplifier la suite:

1. Cutover vers le nouveau runtime sans conserver de jeux legacy.
2. Suppression plus rapide des chemins anciens (runtime/thread/retry legacy).
3. Reduction de la charge de tests de compatibilite historique.

En contrepartie, l'equipe accepte explicitement la perte des donnees dev existantes.

---

## 8) Definition of done

- reset + reseed executes avec succes en dev
- aucune donnee legacy bloquante restante pour les workflows/actions
- scenarios QA de base passants sur la nouvelle structure
- decision documentee et partagee avec l'equipe

---

## 9) Complement decommission code path

Le present document traite le reset de donnees.

Le plan de suppression du code legacy est detaille ici:

- [Decommission ancien code path workflow (dev-only)](dev-decommission-legacy-workflow-code-path.md)
