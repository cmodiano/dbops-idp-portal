# Epic 35 : Points restants — Codebase Review IDP Portal (post-refactoring 23 février 2026)

**En tant que** équipe de développement,  
**je veux** traiter les derniers points ouverts du CODEBASE-REVIEW après le refactoring SOLID (34.x),  
**afin de** clôturer la dette technique résiduelle et consolider la maintenabilité.

---

## Contexte

**Source :** `idp-portal/CODEBASE-REVIEW.md` (mise à jour 2026-02-23)

**Bilan post-Epic 34 :** 96/97 findings résolus. **5 issues ouvertes** (+ 1 INFO) :

| Priorité | Issue | Description |
|----------|--------|-------------|
| **HIGH** | SOLID-FE-4 | ~25 composants importent directement les services (couplage DIP) — effort élevé |
| **MEDIUM** | 16.1 | Fichiers backend encore volumineux (6 fichiers > 700 lignes) — observationnel |
| **MEDIUM** | SOLID-FE-10 | STATUS_CONFIG duplication résiduelle dans 5 fichiers — effort faible |
| **LOW** | 16.2 | `except Exception` résiduels (33 occurrences backend) — audit/documentation |
| **LOW** | 16.3 | `.catch(() => {})` résiduels (21 occurrences frontend) — audit/documentation |
| **INFO** | 16.4 | STATUS_CONFIG locaux potentiellement consolidables (recoupe SOLID-FE-10) |

**Recommandations du document :**
- **Sprint immédiat (quick wins) :** SOLID-FE-10 (consolider STATUS_CONFIG), 16.2/16.3 (audit except/catch)
- **Backlog structurel :** SOLID-FE-4 (migration progressive vers hooks/DI)

---

## Stories

| # | Story | Issues couvertes | Priorité |
|---|-------|------------------|----------|
| 35.1 | Consolidation STATUS_CONFIG résiduel | SOLID-FE-10, 16.4 | Haute |
| 35.2 | Audit `except Exception` et `.catch()` résiduels | 16.2, 16.3 | Moyenne |
| 35.3 | Migration DIP services — Phase 1 (composants prioritaires) | SOLID-FE-4 | Backlog |
| 35.4 | Revue fichiers backend volumineux (documentation / découpage optionnel) | 16.1 | Basse |
| 35.5 | Corriger ou supprimer les tests en échec | Qualité / CI | Haute |

---

## Détail des stories

### 35.1 — Consolidation STATUS_CONFIG résiduel (Haute)

**Objectif :** Réduire la duplication des mappings de statut en important depuis `utils/execution-status.ts` là où le domaine est aligné.

**Périmètre :**
- `ExecutionView.tsx` (ligne ~45) — status exécution → importer ou étendre depuis `execution-status.ts`
- `StepDetailDrawer.tsx` (ligne ~22) — status step → idem
- `WorkflowExecutionGraph.tsx` (ligne ~52) — couleurs nœuds graph → consolider si possible
- Documenter les cas où un STATUS_CONFIG local reste justifié : `IntegrationsTable.tsx` (status intégration, domaine différent), `ComparisonExecutionsDrawer.tsx` (cas spécialisé)

**Critères d’acceptation :**
- Au moins 3 des 5 composants utilisent une source partagée ou une extension documentée de `execution-status.ts`
- Les 2 restants ont un commentaire expliquant pourquoi le config local est conservé

---

### 35.2 — Audit `except Exception` et `.catch()` résiduels (Moyenne)

**Objectif :** S’assurer que chaque usage est intentionnel et documenté ou corrigé.

**Périmètre :**
- **Backend :** 33 occurrences de `except Exception` dans `executions/` (16 fichiers). Vérifier que chaque cas est soit `noqa: BLE001` avec justification, soit remplacé par une exception plus spécifique.
- **Frontend :** 21 occurrences de `.catch(() => {})` ou `.catch(err => {})` dans 16 fichiers. Vérifier que l’erreur est gérée (state, log, cleanup) ou documenter l’intention.

**Critères d’acceptation :**
- Liste (ou tableau) des fichiers/lignes audités avec statut : OK (documenté/justifié) ou FIX (corrigé)
- Aucun `except Exception` ni `.catch()` avalant l’erreur sans trace (log ou remontée) sans justification documentée

---

### 35.3 — Migration DIP services — Phase 1 (Backlog)

**Objectif :** Réduire le couplage direct aux services en migrant un premier lot de composants vers hooks ou injection (props/context).

**Périmètre (exemples cités dans le review) :**
- Composants prioritaires : `ExecutionWizard.tsx`, `ActionWizard.tsx`, `WorkflowStepsEditor.tsx`, `ProfileForm.tsx`, `ProfileWizard.tsx`, `IntegrationForm.tsx`, etc.
- Pattern cible : même approche que `useCatalogState`, `useAuditFilters`, `useExecutionWizardState` — logique dans un hook, services injectés ou fournis par un context.

**Critères d’acceptation :**
- Liste des composants choisis pour la Phase 1 (5–8 composants) avec justification
- Au moins 3 composants migrés vers hook ou DI (plus d’import direct de `admin_service` / `catalog_service` / `execution_service` dans le composant)
- Tests existants verts, pas de régression

---

### 35.4 — Revue fichiers backend volumineux (Basse)

**Objectif :** Documenter ou, si pertinent, proposer un découpage optionnel pour les fichiers > 700 lignes.

**Périmètre (liste du review) :**
- `executions/services.py` (856), `catalog/services.py` (823), `catalog/serializers.py` (737)
- `adapters/terraform_cloud_adapter.py` (747), `adapters/github_actions_adapter.py` (718)
- `inventory/services.py` (711), `executions/container_workflow_runtime.py` (681), `inventory/query_executor.py` (667)

**Critères d’acceptation :**
- Note ou section dans la doc (ou CODEBASE-REVIEW) indiquant pour chaque fichier : responsabilité cohérente / complexité inhérente (adapters) / découpage optionnel recommandé ou non
- Aucun changement de code obligatoire ; découpage uniquement si l’équipe le valide

---

### 35.5 — Corriger ou supprimer les tests en échec (Haute)

**Objectif :** Remettre la suite de tests au vert. Pour chaque test en échec : le corriger s’il apporte de la valeur ; le supprimer s’il est obsolète ou ne sert plus un objectif clair.

**Périmètre :**
- Backend : pytest (Django)
- Frontend : Vitest / React Testing Library
- CI : tous les jobs de test concernés doivent passer

**Règles :**
- **Corriger** : le test vérifie un comportement ou une régression utile ; adapter assertions, mocks ou setup pour qu’il passe après les refactorings (ex. Epic 33/34).
- **Supprimer** : le test est redondant, teste un détail d’implémentation obsolète, ou ne couvre plus un cas métier ; documenter brièvement la raison de la suppression (ex. dans le commit ou un commentaire).

**Critères d’acceptation :**
- Tous les tests exécutés en CI sont verts (backend + frontend).
- Pour chaque test modifié ou supprimé : raison explicite (fix pour régression / refactoring, ou suppression car obsolète / sans objectif).
- Aucune régression fonctionnelle introduite ; les tests restants restent pertinents.

---

## Références

- `idp-portal/CODEBASE-REVIEW.md` — sections 15 (SOLID Frontend), 16 (Observations post-refactoring), 17 (Récapitulatif)
- Epic 34 (Codebase Review restant) — complété ; Epic 35 enchaîne sur les points restants post-refactoring
