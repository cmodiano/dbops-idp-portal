# Story 31.4 : Refonte UX — Panneau « Changement ServiceNow par environnement »

Status: done

## Story

En tant que DBOPS,
je veux que le panneau de configuration par environnement soit plus clair et utilisable : **séparer** les gates (Approbation, Plage maintenance) de la partie « Changement ServiceNow », et **fusionner** « Code modèle » et « Template ID » en un seul champ (ils désignent la même chose),
afin de ne plus mélanger des concepts différents dans une seule grille et éviter la redondance de saisie.

## Acceptance Criteria

1. **Given** le formulaire d'action (ActionForm ou ActionWizard) affiche la section « Changement ServiceNow par environnement », **When** le DBOPS consulte cette section, **Then** elle est structurée en **deux blocs distincts** avec titre/sous-titre explicite :
   - **Bloc 1 — « Gates — Conditions d'exécution par environnement »** : uniquement les colonnes « Autorisé », « Plage maintenance », « Approbation » (switches par environnement)
   - **Bloc 2 — « Changement ServiceNow par environnement »** : « Changement requis » (switch), et **un seul champ** pour l'identifiant du modèle/template (libellé « Modèle / Template ID »), éventuellement « Change type » si conservé

2. **And** il n'y a plus deux colonnes séparées « Code modèle » et « Template ID » : un seul champ dont la valeur est lue en priorité depuis `template_id`, puis `change_model_code` en fallback, et écrite sur **les deux champs** (`change_model_code` ET `template_id`) pour maintenir la rétrocompatibilité sans changer le contrat API backend.

3. **And** la densité visuelle est réduite (espacement amélioré entre les deux blocs, grilles plus lisibles) pour améliorer la lisibilité globale.

4. **And** les tests existants dans `ChangeTypeConfig.test.tsx` sont adaptés : les références à l'aria-label « Code modèle pour X » et à la colonne « Code modèle » sont mises à jour ; les tests de comptage de lignes (row count) sont adaptés aux deux grilles séparées.

5. **And** aucun changement de contrat API backend n'est requis : le format `ChangeTypeConfigEntry` (champs `required`, `change_model_code`, `template_id`, `allowed`, `requires_maintenance_window`, `requires_approval`) reste identique.

## Tasks / Subtasks

- [x] **Tâche 1 : Refactoriser `ChangeTypeConfig.tsx`** (AC: #1, #2, #3)
  - [x] 1.1 — Remplacer la grille unique 8 colonnes par deux blocs séparés avec en-têtes (`Typography.Title` ou `Text strong` + séparateur `Divider`)
  - [x] 1.2 — **Bloc 1 (Gates)** : grille 4 colonnes (`Environnement | Autorisé | Plage maintenance | Approbation`), `gridTemplateColumns: '1fr auto auto auto'`
  - [x] 1.3 — **Bloc 2 (ServiceNow)** : grille 4 colonnes (`Environnement | Changement requis | Modèle / Template ID | Change type`), `gridTemplateColumns: '1fr auto 1fr 1fr'`
  - [x] 1.4 — Fusionner `Code modèle` + `Template ID` : lecture = `entry.template_id ?? entry.change_model_code ?? ''` ; écriture = `handleModelTemplateChange` écrit sur les **deux** champs
  - [x] 1.5 — Supprimer les handlers `handleCodeChange` et `handleTemplateIdChange` séparés, remplacés par `handleModelTemplateChange`
  - [x] 1.6 — Mettre à jour les `aria-label` : `"Modèle / Template ID pour ${env}"`
  - [x] 1.7 — Ajuster les styles CSS : `Divider` entre les deux blocs, `marginTop: 8` sur les headers, espacements internes
  - [x] 1.8 — Mettre à jour le commentaire JSDoc en haut du fichier

- [x] **Tâche 2 : Mettre à jour `ChangeTypeConfig.test.tsx`** (AC: #4)
  - [x] 2.1 — Test `'renders two-block headers: Gates and Changement ServiceNow'` vérifie les `role="group"` et headers des deux blocs
  - [x] 2.2 — Mis à jour vers `getByLabelText(/Modèle \/ Template ID pour prod/i)`
  - [x] 2.3 — Mis à jour dans le test de saisie unifié
  - [x] 2.4 — Row counts adaptés : 2 headers + 2×N data rows (ex: 4 envs → 10 rows)
  - [x] 2.5 — Test `'renders new env with default values (not required)'` reste valide
  - [x] 2.6 — Ajouté tests : `'displays template_id value in the unified field'` + `'falls back to change_model_code when template_id is empty'`

- [x] **Tâche 3 : Vérifier `ActionForm.tsx` et `ActionWizard.tsx`** (AC: #1)
  - [x] 3.1 — Label de section "Changement ServiceNow par environnement" correct, tooltip mis à jour
  - [x] 3.2 — ActionWizard.tsx tooltip mis à jour pour refléter les deux blocs
  - [x] 3.3 — Aucune modification fonctionnelle requise (labels corrects)

- [x] **Tâche 4 : Tests TypeScript et validation** (AC: #4, #5)
  - [x] 4.1 — `npx tsc --noEmit` passe sans erreur (0 erreurs)
  - [x] 4.2 — `npx vitest run src/components/admin/ChangeTypeConfig.test.tsx` : 13/13 tests passent
  - [x] 4.3 — Tous les tests (nouveaux et existants) passent

## Dev Notes

### Contexte fonctionnel

Le composant `ChangeTypeConfig` configure, pour chaque environnement, les conditions d'exécution (gates) et le changement ServiceNow. Actuellement, toutes les colonnes sont dans une **seule grille à 8 colonnes**, ce qui mélange visuellement deux concepts distincts :
- **Gates** : contrôlent si l'exécution est autorisée pour un environnement (`allowed`, `requires_maintenance_window`, `requires_approval`)
- **Changement ServiceNow** : paramètres du changement à créer avant l'exécution (`required`, `change_model_code`, `template_id`)

De plus, `change_model_code` et `template_id` désignent le même identifiant de template ServiceNow (Code modèle = Template ID). La fusion en un seul champ élimine la redondance.

### Structure actuelle à remplacer (ChangeTypeConfig.tsx)

```typescript
// AVANT — grille unique 8 colonnes
gridTemplateColumns: '1fr auto auto auto auto 1fr 1fr 1fr'
// Colonnes : Environnement | Autorisé | Changement requis | Plage maintenance | Approbation | Code modèle | Change type | Template ID

// En-têtes actuels (lignes 113-120) :
<Text strong>Environnement</Text>
<Text strong>Autorisé</Text>
<Text strong>Changement requis</Text>
<Text strong>Plage maintenance</Text>
<Text strong>Approbation</Text>
<Text strong>Code modèle</Text>        // ← À FUSIONNER
<Text strong>Change type</Text>
<Text strong>Template ID</Text>        // ← À FUSIONNER
```

### Structure cible (deux blocs)

```typescript
// APRÈS — Bloc 1 : Gates
// Titre : "Gates — Conditions d'exécution par environnement"
// gridTemplateColumns: '1fr auto auto auto'
// Colonnes : Environnement | Autorisé | Plage maintenance | Approbation

// APRÈS — Bloc 2 : Changement ServiceNow
// Titre : "Changement ServiceNow par environnement"
// gridTemplateColumns: '1fr auto 1fr auto'  (ou '1fr auto 1fr 1fr' si Change type conservé)
// Colonnes : Environnement | Changement requis | Modèle / Template ID | Change type (optionnel)
```

### Logique de fusion Code modèle + Template ID

```typescript
// Lecture du champ unifié (priorité template_id)
const modelTemplateValue = entry.template_id ?? entry.change_model_code ?? '';

// Handler unifié — écrit sur les deux champs
const handleModelTemplateChange = (env: string, v: string) => {
  const entry = getEntry(env);
  const newConfig = {
    ...value,
    [env]: { ...entry, change_model_code: v || undefined, template_id: v || undefined },
  };
  onChange?.(newConfig);
};

// Validation inchangée (même pattern)
// CODE_PATTERN = /^[A-Za-z0-9]*$/  — à conserver ou assouplir (Template ID peut contenir _-)
// ATTENTION : si Template ID peut contenir des tirets ou underscores, adapter CODE_PATTERN
// Décision recommandée : assouplir à /^[A-Za-z0-9_-]*$/ pour couvrir les deux cas
```

### Aria-labels à mettre à jour dans les tests

| Avant | Après |
|-------|-------|
| `aria-label="Code modèle pour ${env}"` | `aria-label="Modèle / Template ID pour ${env}"` |
| `getByLabelText(/Code modèle pour prod/i)` | `getByLabelText(/Modèle \/ Template ID pour prod/i)` |
| `getByText('Code modèle')` (header) | Supprimer ou remplacer par header du Bloc 2 |
| `getByText('Template ID')` (header) | N/A (fusionné) |

### Tests de comptage de lignes — impact

Actuellement, les tests comptent les `role="row"` dans **une seule** grille :
```typescript
// AVANT : 1 grille → header row + N data rows = N+1
expect(rows.length).toBe(5); // 4 envs → 5 rows

// APRÈS : 2 grilles séparées → 2 × (header + N data rows) = 2×(N+1)
// Option A : si les deux blocs ont role="table", getAllByRole('row') retourne 2×(N+1)
// Option B : si un seul aria-label "table" → garder sur le conteneur principal ou Bloc 1
// Recommandation : conserver role="table" / aria-label sur le conteneur global,
// chaque bloc peut avoir role="group" avec aria-label
```

**Décision recommandée** : Garder `role="table"` sur le `<div>` conteneur externe (ligne 100 actuelle), les deux blocs internes n'ont pas de `role="table"` mais des `role="group"`. Ainsi `getAllByRole('row')` retourne `2×(N+1)` rows (les deux grilles). Mettre à jour les tests en conséquence.

### Fichiers impactés

| Fichier | Type de changement |
|---------|-------------------|
| `frontend/src/components/admin/ChangeTypeConfig.tsx` | **Refactoring principal** — 2 blocs, fusion champ |
| `frontend/src/components/admin/ChangeTypeConfig.test.tsx` | **Mise à jour tests** — aria-labels, headers, row counts |
| `frontend/src/components/admin/ActionForm.tsx` | **Vérification seulement** — label section si pertinent |
| `frontend/src/components/admin/ActionWizard.tsx` | **Vérification seulement** — label Step 2 si pertinent |

### Imports Ant Design disponibles

```typescript
// Actuellement importé (ligne 7) :
import { Switch, Input, Space, Typography, theme, Skeleton, Alert } from 'antd';
// Ajouter si besoin : Divider (pour séparer les 2 blocs visuellement)
import { Switch, Input, Space, Typography, theme, Skeleton, Alert, Divider } from 'antd';
const { Text, Title } = Typography;
```

### Pattern d'espacement (Token design)

Utiliser les tokens existants du projet :
```typescript
const { token } = theme.useToken();
// token.colorFillTertiary → fond des en-têtes de grille
// token.borderRadius → arrondi des blocs
// token.colorBorderSecondary → séparateur lignes
// Nouvel espacement entre blocs : marginTop: token.marginLG (24px)
```

### Contexte git récent (Stories 31.1–31.3)

- `feat(31-3)` : ajout `icon_url` sur REF_ENGINES, hook `useEngineIconCache`, `renderEngineIcon` avec fallback cascade
- `feat(31-2)` : suppression intégration → désactivation actions orphelines (backend signal)
- `feat(31-1)` : formulaire action → liste = intégrations (role=platform), `usePlatformIntegrations()`, `integration_id`

**Pattern établi par 31.1 à noter :** ActionWizard.tsx utilise `usePlatformIntegrations()` (ligne ~99-107) et `integrationTypeToPlatformCode()` (ligne ~348). Ces éléments ne sont **pas impactés** par la story 31.4.

### Fichiers de référence à lire avant implémentation

- `[Source: frontend/src/components/admin/ChangeTypeConfig.tsx]` — composant complet actuel (212 lignes)
- `[Source: frontend/src/components/admin/ChangeTypeConfig.test.tsx]` — tests complets actuels (179 lignes)
- `[Source: frontend/src/components/admin/ActionForm.tsx#L611-L625]` — usage ChangeTypeConfig dans ActionForm
- `[Source: frontend/src/components/admin/ActionWizard.tsx#L718-L724]` — usage ChangeTypeConfig dans ActionWizard
- `[Source: frontend/src/types/api.ts]` — type `ChangeTypeConfigEntry` (champs à ne pas modifier)

### Project Structure Notes

- Composants admin : `frontend/src/components/admin/`
- Hooks : `frontend/src/hooks/`
- Types API : `frontend/src/types/api.ts`
- Tests : colocalisés avec les composants (`*.test.tsx`)
- Framework de test : Vitest + React Testing Library + userEvent

### Contraintes importantes

1. **Aucun changement backend** : le contrat API (`ChangeTypeConfigEntry`) doit rester identique
2. **Rétrocompatibilité** : une action existante avec `change_model_code` (sans `template_id`) doit afficher correctement la valeur dans le champ unifié
3. **Pattern CODE_PATTERN** : si on assouplit le regex pour les Template IDs (ex. `CHG_TPL_001`), adapter aussi la validation
4. **Accessibilité** : maintenir les `role` ARIA et `aria-label` sur tous les contrôles interactifs

### References

- [Source: _bmad-output/planning-artifacts/epic-31-admin-catalogue-integrations-et-icones-moteurs.md#Story-31.4]
- [Source: frontend/src/components/admin/ChangeTypeConfig.tsx]
- [Source: frontend/src/components/admin/ChangeTypeConfig.test.tsx]
- [Source: frontend/src/components/admin/ActionForm.tsx#L611-L620]
- [Source: frontend/src/components/admin/ActionWizard.tsx#L718-L724]

## Dev Agent Record

### Agent Model Used

claude-opus-4-6

### Debug Log References

### Completion Notes List

- ✅ Refactoring ChangeTypeConfig.tsx : grille unique 8 colonnes → 2 blocs distincts (Gates + ServiceNow) séparés par un Divider
- ✅ Fusion Code modèle + Template ID en champ unifié « Modèle / Template ID » avec lecture priorité `template_id` → fallback `change_model_code`, écriture sur les deux champs
- ✅ Handlers `handleCodeChange` et `handleTemplateIdChange` supprimés, remplacés par `handleModelTemplateChange`
- ✅ CODE_PATTERN assoupli : `/^[A-Za-z0-9]*$/` → `/^[A-Za-z0-9_-]*$/` pour supporter les Template IDs avec underscores/tirets
- ✅ Alert `message=` → `title=` (fix dépréciation Ant Design 6.2)
- ✅ Tooltips ActionForm.tsx et ActionWizard.tsx mis à jour pour refléter la structure deux blocs
- ✅ Tests adaptés : 13/13 passent (headers deux blocs, aria-labels, row counts, fusion template_id/change_model_code, fallback)
- ✅ `tsc --noEmit` : 0 erreurs TypeScript

### Senior Developer Review (AI)

**Date :** 2026-02-19 | **Reviewer :** Claude Sonnet 4.6 (adversarial)
**Résultat :** Approuvé avec corrections

#### Issues trouvés et corrigés automatiquement

| Sévérité | Issue | Fichier(s) | Fix |
|---|---|---|---|
| 🔴 HIGH | Validation regex obsolète — `^[A-Za-z0-9]+$` rejetait les valeurs avec `_/-` (ex: `CHG_TPL_001`) acceptées par le composant | `ActionForm.tsx:277`, `ActionWizard.tsx:308` | Regex mise à jour : `^[A-Za-z0-9_-]+$` |
| 🔴 HIGH | Validation lisait uniquement `change_model_code` — une action avec `template_id` défini et `change_model_code=null` échouait faussement | `ActionForm.tsx:272`, `ActionWizard.tsx:303` | Lecture unifiée : `entry.template_id ?? entry.change_model_code` |
| 🟡 MEDIUM | Messages d'erreur référençaient "code modèle" — label renommé non propagé | `ActionForm.tsx:273,278`, `ActionWizard.tsx:305,310` | Messages mis à jour vers "Modèle / Template ID" |
| 🟡 MEDIUM | Aucun test pour les switches du Bloc Gates (Autorisé, Plage maintenance, Approbation) | `ChangeTypeConfig.test.tsx` | 3 tests ajoutés : switches allowed, requires_maintenance_window, requires_approval |

#### False positive identifié

- `Space orientation="vertical"` — vérifié : Ant Design 6.2.2 a déprécié `direction` en faveur de `orientation`. Code original correct.

#### Issues non-bloquants (LOW — non corrigés)

- `role="rowgroup"` manquant dans la structure `role="table"` (amélioration accessibilité ARIA)
- Incohérence documentation Dev Notes (`'1fr auto 1fr auto'` vs implémentation `'1fr auto 1fr 1fr'`) — cosmétique

#### Résultat tests post-fix

- `ChangeTypeConfig.test.tsx` : **16/16 ✅** (13 existants + 3 nouveaux Gates switches)
- `tsc --noEmit` : **0 erreurs ✅**

### Change Log

- 2026-02-19 : Story 31.4 implémentée — refonte UX ChangeTypeConfig en deux blocs (Gates + ServiceNow), fusion champ modèle/template, tests adaptés
- 2026-02-19 : Code review (AI) — 4 issues corrigés (H1: regex, H2: validation template_id, M4: messages erreur, M5: tests Gates switches) ; 16/16 tests ✅

### File List

- `frontend/src/components/admin/ChangeTypeConfig.tsx` — **Modifié** : refactoring 2 blocs, fusion champs, Divider, aria-labels
- `frontend/src/components/admin/ChangeTypeConfig.test.tsx` — **Modifié** : tests adaptés headers, aria-labels, row counts, ajout tests fusion
- `frontend/src/components/admin/ActionForm.tsx` — **Modifié** : tooltip mis à jour
- `frontend/src/components/admin/ActionWizard.tsx` — **Modifié** : tooltip mis à jour
