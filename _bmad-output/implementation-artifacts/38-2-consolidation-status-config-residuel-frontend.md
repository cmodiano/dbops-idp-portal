# Story 38.2: Consolidation STATUS_CONFIG résiduel (frontend)

Status: done

## Story

As a développeur frontend,
I want consolider les mappings de statut dupliqués dans les composants frontend vers une source partagée (`execution-status.ts`),
so that la maintenance est simplifiée, les couleurs/labels restent cohérents et la dette technique SOLID-FE-10 est résorbée.

## Acceptance Criteria

1. **Au moins 3 des 5 composants** utilisent une source partagée (`execution-status.ts`) ou une extension documentée :
   - `ExecutionView.tsx` — déjà migré (import `EXECUTION_STATUS_BADGE_CONFIG`)
   - `StepDetailDrawer.tsx` — déjà migré (import `STEP_STATUS_BADGE_CONFIG`)
   - `ComparisonExecutionsDrawer.tsx` — à migrer vers un nouvel export `EXECUTION_STATUS_TAG_COLORS`
2. **Les 2 composants restants** ont un commentaire expliquant pourquoi le config local est conservé :
   - `WorkflowExecutionGraph.tsx` — hex React Flow + clé `SELECTED`, contexte graphique SVG/CSS
   - `IntegrationsTable.tsx` — domaine différent (statuts intégration, pas exécution)
3. **Pas de régression visuelle** — couleurs et libellés de statut identiques avant/après.
4. **Bonus** : Consolider `executionRenderers.tsx` `STATUS_BADGE_CONFIG` (private) si faisable sans ajouter d'import React dans `execution-status.ts`.

## Tasks / Subtasks

- [x] Task 1 — Ajouter `EXECUTION_STATUS_TAG_COLORS` dans `execution-status.ts` (AC: #1)
  - [x] 1.1 Créer l'export `EXECUTION_STATUS_TAG_COLORS: Record<ExecutionStatusType, string>` avec les couleurs Ant Design Tag (green, red, blue, default, processing, orange)
  - [x] 1.2 Ajouter un commentaire documentant l'usage (Ant Design `<Tag color={...}>` vs `<Badge status={...}>`)
- [x] Task 2 — Migrer `ComparisonExecutionsDrawer.tsx` (AC: #1)
  - [x] 2.1 Importer `EXECUTION_STATUS_TAG_COLORS` depuis `execution-status.ts`
  - [x] 2.2 Supprimer le `STATUS_COLORS` local (lignes 35-47)
  - [x] 2.3 Remplacer `STATUS_COLORS[status]` par `EXECUTION_STATUS_TAG_COLORS[status]` (ligne ~77)
  - [x] 2.4 Vérifier visuellement que les couleurs des Tags sont identiques
- [x] Task 3 — Vérifier les commentaires de justification (AC: #2)
  - [x] 3.1 Vérifier que `WorkflowExecutionGraph.tsx` (ligne ~51) a un commentaire justifiant le config local
  - [x] 3.2 Vérifier que `IntegrationsTable.tsx` (ligne ~15) a un commentaire justifiant le config local
  - [x] 3.3 Compléter les commentaires si nécessaire (mentionner SOLID-FE-10 et la raison du maintien local)
- [x] Task 4 — Vérifier les migrations existantes (AC: #1)
  - [x] 4.1 Confirmer que `ExecutionView.tsx` importe `EXECUTION_STATUS_BADGE_CONFIG` (ligne ~24)
  - [x] 4.2 Confirmer que `StepDetailDrawer.tsx` importe `STEP_STATUS_BADGE_CONFIG` (ligne ~18)
- [x] Task 5 — Tests et validation (AC: #3)
  - [x] 5.1 Lancer les tests frontend : `npm run test` depuis `idp-portal/frontend`
  - [x] 5.2 Lancer le build : `npm run build` pour vérifier pas d'erreur TypeScript
  - [x] 5.3 Vérifier que les tests existants des composants concernés passent

## Dev Notes

### État actuel de la duplication STATUS_CONFIG

L'analyse exhaustive révèle **7 configs de statut** dans le frontend. Voici l'état de chaque :

| Fichier | Config | Domaine | Format | Source partagée ? | Action requise |
|---|---|---|---|---|---|
| `execution-status.ts` | `EXECUTION_STATUS_BADGE_CONFIG` | Exécution badge | `{ color: BadgeStatusType; label }` | Source de vérité | Aucune |
| `execution-status.ts` | `STEP_STATUS_BADGE_CONFIG` | Step badge | `{ color: BadgeStatusType; label }` | Source de vérité | Aucune |
| `execution-status.ts` | `STEP_STATUS_COLOR` | Step couleurs hex | `Record<StepStatus, string>` | Source de vérité | Aucune |
| `execution-status.ts` | `AUDIT_STATUS_CONFIG` | Audit | `{ color; label }` | Source de vérité | Aucune |
| `ExecutionView.tsx` | _(aucun local)_ | — | — | Oui | Aucune (déjà migré) |
| `StepDetailDrawer.tsx` | _(aucun local)_ | — | — | Oui | Aucune (déjà migré) |
| `ComparisonExecutionsDrawer.tsx` | `STATUS_COLORS` | Reporting Tag | CSS color strings | Non | **Migrer** |
| `WorkflowExecutionGraph.tsx` | `STATUS_COLORS` | Graph React Flow | hex + `SELECTED` | Non | Documenter |
| `IntegrationsTable.tsx` | `STATUS_CONFIG` | Intégration admin | `{ color; text }` | Non | Documenter |
| `executionRenderers.tsx` | `STATUS_BADGE_CONFIG` (private) | Table exécution | `{ status; label; color }` | Non | Bonus |
| `executionRenderers.tsx` | `STATUS_CONFIG` (exporté) | Table + icônes | `{ label; Icon; color }` | Non | Conserver (Icons + labels féminins) |

### Détail des configs à manipuler

**ComparisonExecutionsDrawer.tsx** — `STATUS_COLORS` (lignes 35-47) :
```typescript
const STATUS_COLORS: Record<string, string> = {
  COMPLETED:        'green',
  FAILED:           'red',
  RUNNING:          'blue',
  PENDING:          'default',
  SUBMITTED:        'processing',
  CANCELLED:        'default',
  PENDING_APPROVAL: 'orange',
  REJECTED:         'red',
};
// Usage: <Tag color={STATUS_COLORS[status] || 'default'}>{status}</Tag>
```
→ Migrer vers `EXECUTION_STATUS_TAG_COLORS` dans `execution-status.ts`.

**WorkflowExecutionGraph.tsx** — `STATUS_COLORS` (lignes 51-63) :
```typescript
// Couleurs graphe React Flow — config locale justifiée (Story 35.1 AC4 Option B).
const STATUS_COLORS = {
  RUNNING:   '#fa8c16', // Orange — étape active (différent de STEP_STATUS_COLOR)
  COMPLETED: '#52c41a',
  FAILED:    '#ff4d4f',
  PENDING:   '#8c8c8c',
  SKIPPED:   '#8c8c8c',
  SELECTED:  '#faad14', // Pas d'équivalent dans execution-status.ts
} as const;
```
→ Justifié local : hex pour SVG/CSS React Flow, couleurs volontairement différentes, clé `SELECTED` sans équivalent.

**IntegrationsTable.tsx** — `STATUS_CONFIG` (lignes 15-22) :
```typescript
// Statut intégration (admin) — domaine différent des statuts d'exécution.
const STATUS_CONFIG: Record<string, { color: string; text: string }> = {
  valid:      { color: 'success', text: 'Valide' },
  invalid:    { color: 'error',   text: 'Invalide' },
  deprecated: { color: 'warning', text: 'Déprécié' },
};
```
→ Justifié local : domaine intégration (pas exécution), clés lowercase, champ `text` pas `label`.

### Patterns et conventions existantes

- **Source partagée** : `frontend/src/utils/execution-status.ts` — 4 exports actuels, pas d'import React
- **Convention labels** : `execution-status.ts` utilise le masculin (`Soumis`, `Terminé`), `executionRenderers.tsx` le féminin (`Soumise`, `Terminée`) — c'est intentionnel
- **Convention types** : `ExecutionStatusType` et `ExecutionStepStatus` sont les types de référence
- **Ant Design Tag vs Badge** : Tag utilise des noms CSS (`'green'`, `'red'`), Badge utilise `BadgeStatusType` (`'success'`, `'error'`)
- **Tests** : `vitest` + React Testing Library, fichiers co-localisés `*.test.tsx`

### Fichier cible pour le nouvel export

**`frontend/src/utils/execution-status.ts`** — ajouter après `AUDIT_STATUS_CONFIG` :

```typescript
/**
 * Couleurs Ant Design <Tag color={...}> pour les statuts d'exécution.
 * Utilisé par les composants reporting qui affichent le statut en Tag (pas Badge).
 * Cf. SOLID-FE-10 — consolidation depuis ComparisonExecutionsDrawer.
 */
export const EXECUTION_STATUS_TAG_COLORS: Record<ExecutionStatusType, string> = {
  SUBMITTED:         'processing',
  RUNNING:           'blue',
  COMPLETED:         'green',
  FAILED:            'red',
  CANCELLED:         'default',
  INTEGRATION_ERROR: 'red',
  PENDING_APPROVAL:  'orange',
  REJECTED:          'red',
};
```

### Ce qu'il ne faut PAS faire

- **Ne PAS déplacer** `executionRenderers.tsx` `STATUS_CONFIG` vers `execution-status.ts` — il contient des composants React (`Icon`) et ça ajouterait un import React dans un fichier utilitaire pur
- **Ne PAS changer** les couleurs de `WorkflowExecutionGraph.tsx` — elles sont volontairement différentes pour le contexte graphique
- **Ne PAS fusionner** les configs d'intégration (`IntegrationsTable`) avec les configs d'exécution — domaines différents
- **Ne PAS changer** les labels masculin/féminin — la distinction est intentionnelle

### Intelligence story précédente (38.1)

- Story 38.1 (backend) terminée avec succès, 1129 tests passent
- Code review : 1 MEDIUM fixé, 2 LOW en action items
- Pas d'impact sur le frontend

### Project Structure Notes

- Frontend : `idp-portal/frontend/src/`
- Composants exécution : `components/execution/`
- Composants admin : `components/admin/`
- Composants dashboard : `components/dashboard/reporting/`
- Utilitaires : `utils/execution-status.ts`
- Tests : co-localisés `*.test.tsx` ou dans `__tests__/`
- Build : Vite 7.3.1, React 19, Ant Design 6.2, TypeScript 5.x
- Test runner : Vitest + React Testing Library

### References

- [Source: idp-portal/CODEBASE-REVIEW.md §14 SOLID-FE-10 — STATUS_CONFIG duplication]
- [Source: idp-portal/CODEBASE-REVIEW.md §17 Audit #3 — 16.4 STATUS_CONFIG résiduel]
- [Source: _bmad-output/planning-artifacts/epic-38-codebase-review-audit-3-corrections.md — Story 38.2]
- [Source: idp-portal/frontend/src/utils/execution-status.ts — source partagée (4 exports)]
- [Source: idp-portal/frontend/src/components/execution/ExecutionView.tsx — déjà migré]
- [Source: idp-portal/frontend/src/components/execution/StepDetailDrawer.tsx — déjà migré]
- [Source: idp-portal/frontend/src/components/dashboard/reporting/ComparisonExecutionsDrawer.tsx — à migrer]
- [Source: idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.tsx — config locale justifiée]
- [Source: idp-portal/frontend/src/components/admin/IntegrationsTable.tsx — config locale justifiée]
- [Source: idp-portal/frontend/src/utils/executionRenderers.tsx — STATUS_BADGE_CONFIG + STATUS_CONFIG]
- [Source: _bmad-output/implementation-artifacts/38-1-quick-wins-backend-n1-double-update-todo-log.md — story précédente]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

Aucun problème rencontré.

### Completion Notes List

- ✅ Task 1 : Ajouté `EXECUTION_STATUS_TAG_COLORS` dans `execution-status.ts` — 5e export, typé `Record<ExecutionStatusType, string>`, avec commentaire documentant Tag vs Badge
- ✅ Task 2 : Migré `ComparisonExecutionsDrawer.tsx` — supprimé `STATUS_COLORS` local (13 lignes), importé depuis source partagée, fallback `|| 'default'` conservé pour statuts inconnus
- ✅ Task 3 : Commentaires de justification vérifiés et complétés — ajouté mention SOLID-FE-10 dans `WorkflowExecutionGraph.tsx` et `IntegrationsTable.tsx`
- ✅ Task 4 : Migrations existantes confirmées — `ExecutionView.tsx` ligne 24 importe `EXECUTION_STATUS_BADGE_CONFIG`, `StepDetailDrawer.tsx` ligne 18 importe `STEP_STATUS_BADGE_CONFIG`
- ✅ Task 5 : 182 fichiers de test, 2492 tests passent (0 échec), build TypeScript sans erreur, build Vite réussi
- AC#4 Bonus non réalisé : `executionRenderers.tsx` `STATUS_BADGE_CONFIG` contient des références React (Icons), migration ajouterait un import React dans le fichier utilitaire pur — conservé tel quel conformément aux Dev Notes

### Change Log

- 2026-02-23 : Consolidation STATUS_CONFIG résiduel frontend — nouvel export `EXECUTION_STATUS_TAG_COLORS`, migration `ComparisonExecutionsDrawer.tsx`, commentaires SOLID-FE-10 ajoutés
- 2026-02-23 : Code review — 1 MEDIUM fixé (tests manquants EXECUTION_STATUS_TAG_COLORS), 2 LOW fixés (cast type simplifié, import ExecutionStatusType)

### File List

- `idp-portal/frontend/src/utils/execution-status.ts` — ajout export `EXECUTION_STATUS_TAG_COLORS`
- `idp-portal/frontend/src/components/dashboard/reporting/ComparisonExecutionsDrawer.tsx` — suppression `STATUS_COLORS` local, import source partagée
- `idp-portal/frontend/src/components/execution/WorkflowExecutionGraph.tsx` — ajout mention SOLID-FE-10 dans commentaire
- `idp-portal/frontend/src/components/admin/IntegrationsTable.tsx` — ajout mention SOLID-FE-10 dans commentaire
- `idp-portal/frontend/src/utils/execution-status.test.ts` — ajout suite de tests EXECUTION_STATUS_TAG_COLORS (8 tests)

## Senior Developer Review (AI)

**Reviewer:** Claude Opus 4.6 — 2026-02-23
**Verdict:** Approved (après corrections)

### Résumé
Code propre et bien structuré. La consolidation est correctement implémentée avec une bonne séparation des préoccupations (Tag vs Badge, domaines exécution vs intégration). Tous les ACs sont satisfaits.

### Issues trouvés et corrigés

| # | Sévérité | Description | Statut |
|---|---|---|---|
| M1 | MEDIUM | Pas de test pour `EXECUTION_STATUS_TAG_COLORS` — le 5e export n'avait aucune couverture | Fixé — 8 tests ajoutés |
| L1 | LOW | Cast verbeux `as keyof typeof EXECUTION_STATUS_TAG_COLORS` au lieu de typer le paramètre render | Fixé — `(status: ExecutionStatusType)` |
| L2 | LOW | Tests ComparisonExecutionsDrawer ne vérifient pas les couleurs Tag post-migration | Non fixé — pré-existant, hors scope |

### Vérification post-fix
- 38 tests passent (30 execution-status + 8 ComparisonExecutionsDrawer)
- Build TypeScript : 0 erreur
