# Epic 80 : Reset dev workflows/actions via seed

**Date :** 2026-03-14  
**Statut :** Draft  
**Réf :** docs/architecture/dev-reset-workflows-actions-via-seed.md  
**Périmètre :** `idp-portal/scripts/seed_dev_data.py`, tables orchestration

---

## 1. Contexte et décision

La plateforme n'est pas encore utilisée en production (phase dev). On valide une approche simple :

- supprimer les workflows/actions existants (et les données runtime associées)
- recréer un jeu propre avec la nouvelle structure via le script de seed

Objectif : accélérer le cleanup de l'ancien code path sans maintenir une compatibilité longue inutile en dev.

---

## 2. Scope du reset

1. **Définitions catalogue** : actions / workflows (structure legacy et nouvelle)
2. **Permissions et rattachements** : tags, favoris, permissions de profils
3. **Runtime** : executions, steps, planifications, events, runnable steps, commandes, outbox

---

## 3. Stories

### Story 80.1 — Purge des tables orchestration dans le reset

**Priorité :** Haute  
**Effort estimé :** S

**Description :**  
Vérifier que le script `seed_dev_data.py --reset` purge les tables orchestration dans le bon ordre (FK) : `WORKFLOW_EVENTS`, `RUNNABLE_STEPS`, `WORKFLOW_COMMANDS`, `EXECUTION_OUTBOX` **avant** la suppression de `EXECUTIONS`. Si ces tables ne sont pas déjà vidées, ajouter leur purge.

**Acceptance criteria :**
- AC1 : Ordre de suppression respecte les FK (children → parents).
- AC2 : Toutes les tables orchestration listées sont purgées par `--reset`.
- AC3 : Le script termine sans erreur.

---

### Story 80.2 — Garde-fous environnement dev

**Priorité :** Haute  
**Effort estimé :** S

**Description :**  
Renforcer les garde-fous pour interdire le reset hors environnement dev.

**Acceptance criteria :**
- AC1 : Check `APP_ENV` + `--env=dev` obligatoire ; refus explicite si staging/prod.
- AC2 : Documentation des garde-fous dans le doc architecture.

---

### Story 80.3 — Trace opérationnelle du reset

**Priorité :** Moyenne  
**Effort estimé :** S

**Description :**  
Journaliser qui a lancé le reset et quand (user, timestamp, environnement).

**Acceptance criteria :**
- AC1 : Log structuré au démarrage du reset (qui, quand, env).
- AC2 : Facilite l'audit et l'annonce à l'équipe.

---

### Story 80.4 — Validation QA reset + reseed

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
Scénarios QA de base après reset + reseed pour valider la nouvelle structure.

**Acceptance criteria :**
- AC1 : Script termine sans erreur.
- AC2 : Résumé final affiche des volumes cohérents (users, actions, executions).
- AC3 : Frontend charge correctement : catalogue actions, écran executions, pages admin principales.
- AC4 : Aucune donnée legacy bloquante restante.

---

## 4. Definition of done (Epic)

- reset + reseed exécutés avec succès en dev
- aucune donnée legacy bloquante restante pour les workflows/actions
- scénarios QA de base passants sur la nouvelle structure
- décision documentée et partagée avec l'équipe
