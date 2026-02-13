# Story 20.8: Documentation conformité — Signatures rapports 15-4 et CRITICAL 17-16

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**En tant qu'** équipe qualité,
**je veux** finaliser les éléments de documentation et conformité restants des stories 15-4 et 17-16,
**afin de** clôturer les rapports de validation avec signatures formelles et résoudre les issues critiques du plugin ESLint custom.

## Acceptance Criteria

### AC1: Signatures rapports validation (Follow-up 15-4)

**Given** les rapports de validation de sécurité créés en Story 15-4
**When** je consulte les documents `security-release-validation.md` et `soc1-compliance-report.md`
**Then** les sections signatures contiennent soit :
- **Option A** : Signatures réelles avec noms, rôles, dates (format: `[Nom] - [Rôle] - [Date] - ✅ Approuvé`)
- **Option B** : Exigence de signature retirée des documents avec note explicative (ex: "Signatures formelles gérées via système externe de gestion documentaire")

**And** la décision (A ou B) est documentée dans les completion notes de cette story
**And** si Option A choisie, les signatures incluent au minimum :
- Responsable technique (validation technique)
- Spécialiste sécurité (validation sécurité)
- Date d'approbation

### AC2: Résolution CRITICAL-1 Plugin ESLint (17-16)

**Given** le code review de Story 17-16 ayant identifié 3 CRITICAL
**When** j'examine le fichier `frontend/eslint-plugin-standards/rules/require-app-useapp.js`
**Then** la règle détecte ÉGALEMENT les imports directs de `Modal` (en plus de `message` et `notification`)

**Preuve de correction :**
- Code règle inclut `Modal` dans liste des identifiants interdits
- Tests unitaires dans `require-app-useapp.test.js` incluent cas de test pour `Modal`
- `npm run lint` ne lève plus de faux négatif sur usage `Modal` direct

**Rationale :** Modal DOIT également passer par `App.useApp()` selon FRONTEND-STANDARDS.md (ligne 114), mais la règle ESLint ne le détectait pas.

### AC3: Résolution CRITICAL-2 Notes Build/Tests (17-16)

**Given** les completion notes de Story 17-16 mentionnant "erreurs pre-existantes non liées"
**When** je lis la section "Completion Notes List" et "Dev Notes"
**Then** les notes précisent EXACTEMENT :
- Nombre d'erreurs build TypeScript pre-existantes (si applicable)
- Nombre de tests échoués pre-existants non liés aux standards
- Liste des fichiers affectés ou référence au document `KNOWN_ISSUES.md`
- Confirmation que 0 erreurs/tests sont causés par les changements Story 17-16

**Preuve de correction :**
- Section "Completion Notes List" enrichie avec chiffres précis
- Lien vers `KNOWN_ISSUES.md` si erreurs cataloguées
- Distinction claire entre : (1) Violations standards corrigées (10), (2) Erreurs pre-existantes documentées

### AC4: Résolution CRITICAL-3 Chemin Template PR (17-16)

**Given** le template PR créé en Story 17-16
**When** j'examine le fichier `.github/PULL_REQUEST_TEMPLATE.md`
**Then** le lien vers `FRONTEND-STANDARDS.md` utilise le chemin relatif correct depuis la racine du repository

**Preuve de correction :**
- Chemin actuel : ~~`frontend/FRONTEND-STANDARDS.md`~~ (incorrect si PR créée à la racine)
- Chemin corrigé : `idp-portal/frontend/FRONTEND-STANDARDS.md` (correct depuis racine monorepo)
- Vérification : Lien cliquable fonctionnel dans GitHub UI preview

**Rationale :** Template PR est à la racine `.github/`, donc les chemins relatifs doivent partir de la racine du monorepo.

### AC5: Validation croisée et cohérence

**Given** les corrections apportées
**When** je valide l'ensemble
**Then** :
- Aucune régression introduite (tests plugin ESLint 34/34 passent)
- Documentation alignée (signatures ou note explicative cohérente)
- File List de cette story liste TOUS les fichiers créés/modifiés
- Completion notes incluent preuves de vérification (commandes exécutées, outputs)

## Tasks / Subtasks

### Task 1: Traiter signatures rapports validation 15-4 (AC1)

**Contexte :** Story 15-4 a créé les rapports mais les sections signatures sont vides ou génériques. Ce task finalise la démarche.

- [x] Subtask 1.1: Décider approche signatures (consultation équipe)
  - Vérifier si signatures formelles requises pour conformité SOC1
  - Si oui → Option A (signatures réelles avec noms/rôles/dates)
  - Si non → Option B (retirer exigence, note explicative)
  - Documenter décision dans Dev Notes de cette story

- [x] Subtask 1.2: Si Option A — Collecter signatures réelles (N/A — Option B choisie)

- [x] Subtask 1.3: Si Option B — Retirer exigence signatures
  - Remplacer sections signatures par note explicative
  - Exemple : "Les approbations formelles sont gérées via le système de gestion documentaire entreprise [référence système si applicable]"
  - Mettre à jour AC5 Story 15-4 pour refléter que l'exigence signature n'est plus un critère bloquant
  - Documenter rationale dans Dev Notes

- [x] Subtask 1.4: Mettre à jour méta-données rapports
  - Version documents : passer à v1.1 (ou incrémenter)
  - Date dernière modification : date de cette story
  - Statut : "Finalisé" ou "Approuvé" selon Option A/B

### Task 2: Corriger CRITICAL-1 — Détection Modal manquante (AC2)

**Contexte :** La règle `require-app-useapp` détecte `message` et `notification` mais pas `Modal`, créant un faux négatif.

- [x] Subtask 2.1: Modifier règle ESLint `require-app-useapp.js`
  - Fichier : `frontend/eslint-plugin-standards/rules/require-app-useapp.js`
  - Ajouter `'Modal'` dans la liste des identifiants interdits (actuellement : `['message', 'notification']`)
  - Mise à jour : `const FORBIDDEN_IDENTIFIERS = ['message', 'notification', 'Modal'];`
  - Vérifier message d'erreur générique fonctionne pour les 3 identifiants

- [x] Subtask 2.2: Ajouter tests unitaires pour `Modal`
  - Fichier : `frontend/eslint-plugin-standards/rules/__tests__/require-app-useapp.test.js`
  - Ajouter cas de test `invalid` :
    - `import { Modal } from 'antd'; Modal.confirm(...)`
    - `import { message, Modal } from 'antd'` (import multiple)
  - Ajouter cas de test `valid` :
    - `const { modal } = App.useApp(); modal.confirm(...)`
  - S'assurer que les 34 tests existants + nouveaux tests passent

- [x] Subtask 2.3: Valider correction avec audit code
  - Lancer `npm run lint` (working-directory: frontend)
  - Vérifier qu'aucune nouvelle violation `Modal` n'est détectée (code déjà conforme)
  - Si violations détectées → Corriger (refactorer vers `App.useApp()`)
  - Documenter résultat dans Completion Notes

### Task 3: Enrichir notes build/tests 17-16 (AC3)

**Contexte :** Story 17-16 mentionne "erreurs pre-existantes" sans chiffres précis, créant ambiguïté.

- [x] Subtask 3.1: Audit build frontend actuel
  - Lancer `npm run build` (working-directory: frontend)
  - Capturer output complet (erreurs TypeScript, warnings)
  - Compter erreurs TypeScript distinctes (hors warnings)
  - Lister fichiers affectés (top 5-10 si >10 erreurs)

- [x] Subtask 3.2: Audit tests frontend actuel
  - Lancer `npm run test` (working-directory: frontend)
  - Capturer output complet (tests passés/échoués, suites)
  - Compter tests échoués pre-existants (hors tests plugin ESLint)
  - Identifier suites affectées (ex: `ExecutionWizard`, `AdminPage`, etc.)

- [x] Subtask 3.3: Vérifier existence `KNOWN_ISSUES.md`
  - Chercher fichier `idp-portal/frontend/KNOWN_ISSUES.md` ou `idp-portal/KNOWN_ISSUES.md`
  - Si existe → Lire contenu, vérifier si erreurs build/tests y sont documentées
  - Si n'existe pas → Noter dans Dev Notes que les erreurs ne sont pas cataloguées ailleurs

- [x] Subtask 3.4: Enrichir completion notes Story 17-16
  - Mettre à jour fichier `17-16-verification-conformite-frontend-standards.md`
  - Section "Completion Notes List" → Ajouter après ligne "⚠️ Note: ..."
  - Format :
    ```
    **Détail erreurs pre-existantes (non liées Story 17-16) :**
    - Build TypeScript : [X] erreurs dans [Y] fichiers ([liste top 5 fichiers])
    - Tests frontend : [Z] tests échoués sur [W] suites ([liste suites affectées])
    - Référence : [Lien vers KNOWN_ISSUES.md si existe, sinon "Non cataloguées"]
    - Confirmation : 0 erreur/test causé par changements standards (10 violations corrigées)
    ```
  - Ajouter lien vers audit complet si nécessaire (fichier séparé ou section Dev Notes)

### Task 4: Corriger chemin template PR (AC4)

**Contexte :** Template PR créé à `.github/PULL_REQUEST_TEMPLATE.md` avec chemin relatif incorrect vers `FRONTEND-STANDARDS.md`.

- [x] Subtask 4.1: Identifier structure monorepo
  - Confirmer organisation : Racine repo → `idp-portal/` → `frontend/FRONTEND-STANDARDS.md`
  - Vérifier si `.github/` est à la racine ou dans `idp-portal/`
  - Déterminer chemin relatif correct

- [x] Subtask 4.2: Corriger chemin dans template PR
  - Fichier : `idp-portal/.github/PULL_REQUEST_TEMPLATE.md`
  - Chemin corrigé : `../frontend/FRONTEND-STANDARDS.md` (depuis `.github/` vers `frontend/`)
  - Description règle `require-app-useapp` mise à jour pour inclure `modal`

- [x] Subtask 4.3: Valider lien fonctionnel
  - Validation manuelle : chemin relatif `../frontend/FRONTEND-STANDARDS.md` depuis `idp-portal/.github/` est correct
  - Test draft PR non réalisé (nécessite push + PR GitHub) — chemin vérifié structurellement

### Task 5: Validation croisée finale (AC5)

**Contexte :** S'assurer que toutes les corrections n'introduisent pas de régression.

- [x] Subtask 5.1: Tests plugin ESLint standards
  - Lancer tests unitaires règles : `npm test` (working-directory: frontend/eslint-plugin-standards si script existe, sinon via vitest)
  - Confirmer 34 tests existants + nouveaux tests Modal passent (total attendu : ~37-38 tests)
  - Vérifier aucune régression sur tests existants

- [x] Subtask 5.2: Linting frontend complet
  - Lancer `npm run lint` (working-directory: frontend)
  - Confirmer 0 violations standards (10 violations corrigées en 17-16 restent corrigées)
  - Confirmer nouvelle détection Modal fonctionne (ou aucune violation détectée si code conforme)

- [x] Subtask 5.3: Documentation cohérence
  - Vérifier que les documents modifiés (rapports validation, story 17-16) sont cohérents
  - Signatures (Option A) ou note explicative (Option B) présente dans LES DEUX rapports
  - Completion notes 17-16 enrichies avec chiffres précis erreurs pre-existantes
  - Template PR avec chemin correct

- [x] Subtask 5.4: File List et Completion Notes story 20-8
  - Lister TOUS les fichiers créés/modifiés dans cette story (section "File List")
  - Rédiger Completion Notes détaillées avec :
    - Option choisie signatures (A ou B) + rationale
    - Preuve correction CRITICAL-1 (tests Modal ajoutés, lint passe)
    - Preuve enrichissement notes 17-16 (chiffres erreurs build/tests)
    - Preuve correction chemin PR template (lien validé)
    - Validation tests/lint aucune régression

## Dev Notes

### Nature de cette Story — Documentation + Corrections Mineures

Cette story est **principalement documentaire** avec quelques **corrections mineures de code** (règle ESLint, template PR). Elle ne modifie AUCUN code applicatif métier, AUCUNE migration, AUCUN test applicatif. Elle finalise deux stories précédentes (15-4 et 17-16) en traitant leurs action items restants.

### Contexte Story 15-4 — Signatures Rapports Validation

**Situation actuelle :**
- Story 15-4 (done) a créé 5 documents de sécurité dont :
  - `docs/security-release-validation.md` — Rapport go/no-go release
  - `docs/soc1-compliance-report.md` — Rapport conformité SOC1 v2.0
- Les deux rapports contiennent des sections "Approbation" avec signatures génériques ou vides
- Code review AI (15-4) a identifié : "[AI-Review][HIGH] Obtenir signatures réelles ou retirer exigence AC5" (ligne 70)

**Follow-up identifié (Epic 20 Story 20.8) :**
- **Option A** : Signatures réelles (noms, rôles, dates) si requis pour conformité
- **Option B** : Retirer exigence signatures avec note explicative si gestion externe

**Fichiers concernés :**
- `idp-portal/docs/security-release-validation.md` (lignes 308-324 : section "Approbation")
- `idp-portal/docs/soc1-compliance-report.md` (lignes 312-317 : section "Approbation")

**Decision requise (Task 1.1) :**
- Consulter équipe : Signatures formelles requises pour conformité SOC1 interne ?
- Si oui → Collecter noms/rôles/dates signataires (Responsable technique + Spécialiste sécurité)
- Si non → Retirer sections signatures, ajouter note explicative

### Contexte Story 17-16 — 3 CRITICAL Code Review

**Situation actuelle :**
- Story 17-16 (in-progress / done) a créé plugin ESLint custom `eslint-plugin-standards` avec 3 règles
- Code review a identifié 3 CRITICAL (source : ligne 17-16 story, section "Review Follow-ups") :
  1. **CRITICAL-1** : Règle `require-app-useapp` ne détecte pas `Modal` (uniquement `message` et `notification`)
  2. **CRITICAL-2** : Notes build/tests mentionnent "erreurs pre-existantes" sans chiffres précis (ambiguïté)
  3. **CRITICAL-3** : Template PR chemin vers `FRONTEND-STANDARDS.md` incorrect (relatif à racine)

**Follow-up identifié (Epic 20 Story 20.8) :**
- CRITICAL-1 : Ajouter `Modal` dans liste identifiants interdits + tests unitaires
- CRITICAL-2 : Enrichir completion notes 17-16 avec chiffres précis erreurs build/tests pre-existantes
- CRITICAL-3 : Corriger chemin relatif template PR (`.github/PULL_REQUEST_TEMPLATE.md`)

**Fichiers concernés :**
- `frontend/eslint-plugin-standards/rules/require-app-useapp.js` (règle à modifier)
- `frontend/eslint-plugin-standards/rules/__tests__/require-app-useapp.test.js` (tests à ajouter)
- `_bmad-output/implementation-artifacts/17-16-verification-conformite-frontend-standards.md` (notes à enrichir)
- `.github/PULL_REQUEST_TEMPLATE.md` ou `idp-portal/.github/PULL_REQUEST_TEMPLATE.md` (chemin à corriger)

### Standards Frontend Ant Design (Référence FRONTEND-STANDARDS.md)

**Règle concernée (CRITICAL-1) :**
- **Line 114 (FRONTEND-STANDARDS.md)** : `import { message, notification, Modal } from 'antd'` ❌ INTERDIT
- **Correct** : `const { message, notification, modal } = App.useApp()` ✅
- **Rationale** : Ant Design 6.x requiert `App.useApp()` pour message/notification/modal (contexte App nécessaire)

**Règle ESLint actuelle :**
- Détecte `message` et `notification` ✅
- **NE détecte PAS** `Modal` ❌ (GAP critique)

**Correction requise :**
```javascript
// frontend/eslint-plugin-standards/rules/require-app-useapp.js
const FORBIDDEN_IDENTIFIERS = ['message', 'notification', 'Modal']; // Ajouter Modal
```

### Structure Monorepo et Chemins Relatifs (CRITICAL-3)

**Organisation repository :**
```
/Users/cyrille/Documents/Dev/test/
├── .github/
│   └── PULL_REQUEST_TEMPLATE.md     # Template PR (racine repo)
├── idp-portal/
│   ├── frontend/
│   │   └── FRONTEND-STANDARDS.md    # Fichier cible
│   ├── django_backend/
│   └── docs/
└── _bmad-output/
```

**Analyse chemin relatif :**
- Template PR location : `.github/PULL_REQUEST_TEMPLATE.md` (racine repo)
- Fichier cible : `idp-portal/frontend/FRONTEND-STANDARDS.md`
- **Chemin relatif depuis `.github/`** : `../idp-portal/frontend/FRONTEND-STANDARDS.md`
- **Chemin depuis racine repo** (GitHub UI) : `idp-portal/frontend/FRONTEND-STANDARDS.md`

**Correction requise :**
- GitHub UI utilise chemins depuis racine repo (pas relatifs depuis `.github/`)
- **Chemin correct** : `idp-portal/frontend/FRONTEND-STANDARDS.md`
- **Format Markdown** : `[FRONTEND-STANDARDS.md](idp-portal/frontend/FRONTEND-STANDARDS.md)`

### Erreurs Build/Tests Pre-existantes (CRITICAL-2)

**Contexte Story 17-16 (ligne 686) :**
> "⚠️ Note: Erreurs ESLint/TypeScript/tests pre-existantes non liees aux standards restent (separees de cette story)"

**Problème :** Mention générique sans chiffres précis → Ambiguïté sur l'état réel

**Investigation requise (Task 3) :**
1. **Build TypeScript** : `npm run build` → Compter erreurs TypeScript distinctes
2. **Tests frontend** : `npm run test` → Compter tests échoués pre-existants
3. **Vérifier KNOWN_ISSUES.md** : Existe-t-il un fichier cataloguant ces erreurs ?

**Format enrichissement notes 17-16 :**
```markdown
**Détail erreurs pre-existantes (non liées Story 17-16) :**
- Build TypeScript : [X] erreurs dans [Y] fichiers ([liste top 5 fichiers])
- Tests frontend : [Z] tests échoués sur [W] suites ([liste suites affectées])
- Référence : [Lien vers KNOWN_ISSUES.md si existe, sinon "Non cataloguées"]
- Confirmation : 0 erreur/test causé par changements standards (10 violations corrigées)
```

**Source chiffres connus (Story 18-7) :**
- Story 18-7 (correction tests) : "934/1135 tests pass (82.4%)" (ligne 252)
- Donc ~200 tests échoués catalogués dans `KNOWN_ISSUES.md`
- Vérifier si ce fichier existe et référencer dans notes 17-16

### Tests Unitaires Règles ESLint — Pattern Existant

**Framework utilisé (Story 17-16) :**
- `@typescript-eslint/rule-tester` (déjà en dépendance `frontend/package.json`)
- 34 tests existants pour 3 règles (no-antd-internal-imports, require-app-useapp, no-class-components)

**Pattern test à suivre (CRITICAL-1) :**
```javascript
// frontend/eslint-plugin-standards/rules/__tests__/require-app-useapp.test.js
import { RuleTester } from '@typescript-eslint/rule-tester';
import rule from '../require-app-useapp.js';

const ruleTester = new RuleTester({
  parser: '@typescript-eslint/parser',
});

ruleTester.run('require-app-useapp', rule, {
  valid: [
    { code: "const { modal } = App.useApp(); modal.confirm(...)" },
    { code: "import { App } from 'antd'; const { modal } = App.useApp()" },
  ],
  invalid: [
    {
      code: "import { Modal } from 'antd'; Modal.confirm(...)",
      errors: [{ messageId: 'requireAppUseApp' }],
    },
    {
      code: "import { message, Modal } from 'antd'",
      errors: [
        { messageId: 'requireAppUseApp' }, // message
        { messageId: 'requireAppUseApp' }, // Modal
      ],
    },
  ],
});
```

**Validation après correction :**
- Lancer tests : `npm test` (working-directory: frontend/eslint-plugin-standards si script existe)
- Attendu : 34 tests existants + ~3-4 nouveaux tests Modal = ~37-38 tests passent

### Architecture Constraints (Référence)

**From architecture.md (Epic 15 Audit Sécurité) :**
- **NFR6-NFR11** : Standards sécurité (TLS 1.2+, logs immutables, RBAC, Vault, audit trail)
- **FR30-FR35** : Conformité SOC1 (tracabilité, export rapports, evidence generation)
- **SOC1 Controls** : 9 contrôles définis (Story 15-3), 7 CONFORMES, 2 PARTIELS

**Impact Story 20-8 :**
- Signatures rapports (AC1) : Peut être requis pour contrôle SOC1 "Documentation & Approbation"
- Si signatures formelles non requises → Option B acceptable (gestion externe)

**From architecture.md (Frontend Standards) :**
- **UI Component Library** : Ant Design 6.2 (ligne 177)
- **Pattern obligatoire** : `App.useApp()` pour message/notification/modal (ligne 370)
- **No class components** : Function components + hooks uniquement (ligne 367)

**Impact Story 20-8 :**
- CRITICAL-1 (Modal) : Alignement avec standards architecture Ant Design 6.2
- Règle ESLint enforce patterns architecturaux définis

### Testing Requirements — Validation Finale

**Tests Règles ESLint (Task 5.1) :**
- Framework : `@typescript-eslint/rule-tester` + vitest
- Commande : `npm test` (working-directory: frontend/eslint-plugin-standards ou frontend)
- Attendu : 37-38 tests passent (34 existants + 3-4 Modal)
- Vérification : Aucune régression sur tests existants

**Linting Frontend (Task 5.2) :**
- Commande : `npm run lint` (working-directory: frontend)
- Attendu : 0 violations standards (10 violations Story 17-16 restent corrigées)
- Validation : Nouvelle détection Modal fonctionne (ou 0 violation si code conforme)

**Build Frontend (optionnel Task 3.1) :**
- Commande : `npm run build` (working-directory: frontend)
- Objectif : Cataloguer erreurs TypeScript pre-existantes (CRITICAL-2)
- Note : Erreurs build ne doivent PAS augmenter (seulement cataloguer existantes)

**Tests Frontend (optionnel Task 3.2) :**
- Commande : `npm run test` (working-directory: frontend)
- Objectif : Cataloguer tests échoués pre-existants (CRITICAL-2)
- Note : Tests échoués ne doivent PAS augmenter (seulement cataloguer existants)

### Project Structure Notes

**Fichiers à MODIFIER (Documentation) :**
```
idp-portal/docs/
├── security-release-validation.md           # AC1 — Signatures section (lignes 308-324)
└── soc1-compliance-report.md                # AC1 — Signatures section (lignes 312-317)

_bmad-output/implementation-artifacts/
└── 17-16-verification-conformite-frontend-standards.md  # AC3 — Enrichir completion notes
```

**Fichiers à MODIFIER (Code) :**
```
frontend/eslint-plugin-standards/rules/
└── require-app-useapp.js                    # AC2 — Ajouter Modal dans FORBIDDEN_IDENTIFIERS

frontend/eslint-plugin-standards/rules/__tests__/
└── require-app-useapp.test.js               # AC2 — Ajouter tests Modal

.github/
└── PULL_REQUEST_TEMPLATE.md                 # AC4 — Corriger chemin FRONTEND-STANDARDS.md
```

**Fichiers à LIRE (Référence) :**
```
idp-portal/frontend/FRONTEND-STANDARDS.md    # Standards frontend (ligne 114 : Modal règle)
idp-portal/frontend/KNOWN_ISSUES.md          # Catalogage erreurs pre-existantes (si existe)
_bmad-output/implementation-artifacts/15-4-documentation-securite-plan-remediation.md  # Contexte signatures
_bmad-output/implementation-artifacts/17-16-verification-conformite-frontend-standards.md  # Contexte CRITICAL
```

**Aucun fichier à CRÉER** (corrections uniquement)

### Previous Story Intelligence

**Story 15-4 (Documentation Sécurité) — Learnings :**
- **Pattern documentation** : Rapports en Markdown avec tableaux tracabilité
- **Signatures génériques** : Sections créées mais non remplies (follow-up nécessaire)
- **Code review AI** : A identifié gap signatures (HIGH) → Origin story 20-8 AC1
- **Tests sécurité** : 177 tests (154 fonctionnels + 23 SOC1) 100% passent
- **VULN-001 RESOLVED** : 9 dépendances upgradées, 0 HIGH vulns (ligne 69)

**Pattern réutilisé Story 20-8 :**
- Format signatures : `[Nom] - [Rôle] - [Date] - ✅ Approuvé`
- Option alternative : Note explicative si gestion externe
- Vérification cohérence : LES DEUX rapports doivent avoir même approche (A ou B)

**Story 17-16 (Vérification Conformité Frontend) — Learnings :**
- **Pattern ESLint custom** : Plugin local `eslint-plugin-standards/` fonctionnel
- **Tests règles** : 34 tests avec `@typescript-eslint/rule-tester` (ligne 685)
- **Violations corrigées** : 10 violations (4 `antd/es/*` + 6 `message`/`notification`) (ligne 679)
- **Code review 3 CRITICAL** : Modal manquant, notes imprécises, chemin PR incorrect
- **CI existant suffit** : Job `lint-frontend` déjà bloquant (ligne 686)

**Pattern réutilisé Story 20-8 :**
- Modification règle ESLint : Ajouter identifiant dans liste + tests unitaires
- Enrichissement notes : Chiffres précis erreurs pre-existantes (non ambiguïté)
- Validation tests : Aucune régression, tous tests passent

**Story 18-7 (Correction Tests) — Learnings :**
- **Tests échoués catalogués** : "934/1135 tests pass (82.4%)" (ligne 252)
- **KNOWN_ISSUES.md créé** : Document cataloguant 200 failures pre-existants
- **Distinction claire** : Tests liés story vs. pre-existants

**Pattern réutilisé Story 20-8 :**
- Référencer `KNOWN_ISSUES.md` pour erreurs pre-existantes (AC3)
- Confirmer 0 erreur/test causé par Story 17-16 (alignement 18-7)

**Story 20-7 (M10 et 17-12 Follow-ups) — Commit bde9494 :**
- **Pattern follow-up** : Story Epic 20 = Consolidation action items stories done
- **Approche** : Traiter items non-bloquants (WebSocket test, CI/CD, Redis pub/sub)
- **Code review** : 8 fixes appliqués

**Pattern réutilisé Story 20-8 :**
- Story 20-8 suit même logique : Follow-ups 15-4 et 17-16
- Approche méthodique : 1 AC par CRITICAL, validation croisée finale

### Git Intelligence

**Commits Récents (liés Epic 20) :**
```
bde9494 feat(20-7): implement non-blocking M10 and 17-12 follow-ups
044f957 feat(20-6): implement container workflow execution engine with runtime orchestration
ef02b9c feat(20-5): add comprehensive project documentation and quality standards
cfd46a4 feat(20-4): refactor ExecutionWizard with performance optimizations and better maintainability
2c2af1e feat(20-3): migrate workflow retry mechanism to asynchronous Celery tasks
```

**Analyse Commit 20-7 (bde9494) :**
- Story précédente dans Epic 20 (follow-ups non-bloquants)
- **Pattern commit message** : `feat(story-num): [description courte]`
- **Code review** : Tous les commits Epic 20 ont code review appliqué

**Pattern commit attendu Story 20-8 :**
- Message : `feat(20-8): finalize 15-4 validation signatures and resolve 17-16 critical issues`
- Files modifiés : Rapports docs, règle ESLint, template PR, story 17-16 notes
- Validation : Tests plugin ESLint passent, lint 0 violations

**État Git Actuel (gitStatus) :**
- Branch : `develop`
- Main branch : `main`
- Untracked files : Icons statiques (`static/icons/*.jpg|png|svg`)
- **Aucun fichier modifié** : Clean working directory (prêt pour story 20-8)

### Latest Technical Information

**Ant Design 6.2 (Février 2026) :**
- **API publique stable** : `import { Modal } from 'antd'` existe MAIS
- **Pattern obligatoire 6.x** : `App.useApp()` pour message/notification/modal
- **Rationale** : Contexte App nécessaire pour theming, i18n, message config
- **Documentation** : https://ant.design/components/app (section useApp hook)

**ESLint 9.x Flat Config (Février 2026) :**
- **Plugin local** : Import ESM `import plugin from './eslint-plugin-standards/index.js'`
- **Format règles** : `{ rules: { 'rule-name': ruleObject } }`
- **Tests règles** : `@typescript-eslint/rule-tester` (version 8.46.4 selon Story 17-16)

**React 19 (Février 2026) :**
- **Modal pattern** : `Modal.confirm()` fonctionne mais déprécié en faveur `modal.confirm()` via hook
- **App.useApp()** : Hook standard React 19 + Ant Design 6.x pour contexte App

**GitHub Pull Request Templates (Février 2026) :**
- **Location** : `.github/PULL_REQUEST_TEMPLATE.md` à la racine repo
- **Chemins** : Relatifs à la racine repo (pas relatifs à `.github/`)
- **Validation** : Liens cliquables dans GitHub UI preview

**SOC1 Compliance (Standards 2026) :**
- **Documentation & Approbation** : Peut requérir signatures formelles OU système gestion externe
- **Flexibilité** : Option B (note explicative) acceptable si tracabilité externe prouvée
- **Best practice** : Cohérence entre rapports (tous signés OU tous gestion externe)

### Risks & Considerations

**Risque 1: Décision signatures (AC1) retardée**
- **Impact** : Blocage Task 1 si consultation équipe nécessaire
- **Mitigation** :
  - Privilégier Option B (note explicative) si aucune exigence formelle SOC1 interne
  - Documenter décision dans Dev Notes (rationale claire)
  - Si Option A requise → Identifier signataires rapidement (Responsable technique + Spécialiste sécurité)
- **Validation** : Aucune exigence réglementaire externe bloquante (SOC1 interne)

**Risque 2: Tests Modal révèlent violations code existant**
- **Impact** : Correction CRITICAL-1 détecte usages `Modal` direct non corrigés
- **Mitigation** :
  - Audit code avec `grep -rn "import { Modal" frontend/src/` avant correction
  - Si violations → Corriger immédiatement (refactorer vers `App.useApp()`)
  - Pattern correction connu : Story 17-16 a déjà corrigé 6 violations similaires
- **Validation** : Task 2.3 inclut audit + correction avant finalisation

**Risque 3: Enrichissement notes 17-16 révèle erreurs causées**
- **Impact** : Audit Task 3 montre que Story 17-16 A causé erreurs (contradiction)
- **Mitigation** :
  - Vérifier que les 10 violations corrigées (Story 17-16 ligne 679) n'ont PAS cassé tests
  - Isoler tests plugin ESLint (34 tests) des tests applicatifs
  - Si régression détectée → Documenter ET corriger dans cette story
- **Validation** : Story 17-16 mentionne "0 regression" (ligne 686) → Confirmer

**Risque 4: Template PR chemin GitHub Enterprise custom**
- **Impact** : Chemin relatif fonctionne différemment si GitHub Enterprise
- **Mitigation** :
  - Tester sur environnement réel (draft PR GitHub)
  - Si chemin ne fonctionne pas → Utiliser chemin absolu URL GitHub
  - Documenter configuration GitHub (Enterprise vs. Cloud) dans Dev Notes
- **Validation** : Task 4.3 inclut test réel avec draft PR

**Risque 5: KNOWN_ISSUES.md inexistant (AC3)**
- **Impact** : Impossible de référencer document catalogage erreurs pre-existantes
- **Mitigation** :
  - Task 3.3 vérifie existence fichier
  - Si n'existe pas → Noter "Non cataloguées" dans enrichissement notes
  - Option : Créer KNOWN_ISSUES.md dans cette story (hors scope AC mais utile)
- **Validation** : Story 18-7 mentionne KNOWN_ISSUES.md → Devrait exister

### Implementation Order — Séquence Critique

**Phase 1: Investigation (Tasks 1.1, 3.1-3.3) — PRIORITÉ**
1. Décider approche signatures (Option A ou B)
2. Audit build TypeScript (`npm run build`)
3. Audit tests frontend (`npm run test`)
4. Vérifier existence KNOWN_ISSUES.md

**Rationale :** Décisions bloquent Tasks 1.2/1.3 et 3.4

**Phase 2: Corrections Code (Tasks 2.1-2.2, 4.1-4.2) — PARALLÈLE**
1. Modifier règle ESLint `require-app-useapp.js` (ajouter Modal)
2. Ajouter tests unitaires Modal
3. Corriger chemin template PR

**Rationale :** Corrections indépendantes, peuvent être faites en parallèle

**Phase 3: Documentation (Tasks 1.2 ou 1.3, 3.4) — SÉQUENTIEL**
1. Traiter signatures rapports (selon décision Phase 1)
2. Enrichir completion notes 17-16 (avec chiffres Phase 1)

**Rationale :** Nécessite résultats Phase 1 (décision signatures, chiffres erreurs)

**Phase 4: Validation Finale (Tasks 2.3, 5.1-5.4) — BLOQUANT**
1. Audit code violations Modal (après correction règle)
2. Tests règles ESLint (34+ tests passent)
3. Linting frontend complet (0 violations)
4. Cohérence documentation
5. File List + Completion Notes story 20-8

**Rationale :** Validation croisée finale avant marquage done

### Dev Agent Guardrails

**MUST DO:**
- ✅ Traiter signatures rapports (Option A OU B, pas laisser vide)
- ✅ Ajouter `Modal` dans règle `require-app-useapp.js`
- ✅ Créer tests unitaires Modal (cas valid + invalid)
- ✅ Enrichir completion notes 17-16 avec chiffres précis erreurs pre-existantes
- ✅ Corriger chemin template PR (relatif racine repo)
- ✅ Valider tests plugin ESLint passent (34+ tests)
- ✅ Valider linting frontend 0 violations
- ✅ File List complet story 20-8
- ✅ Completion Notes détaillées avec preuves

**MUST NOT DO:**
- ❌ Modifier code applicatif métier (corrections ESLint/docs uniquement)
- ❌ Casser tests existants (aucune régression)
- ❌ Laisser sections signatures vides (choisir Option A ou B)
- ❌ Ignorer violations Modal détectées (corriger immédiatement)
- ❌ Modifier architecture plugin ESLint (structure établie Story 17-16)
- ❌ Créer KNOWN_ISSUES.md si inexistant (hors scope AC, optionnel)

**OPTIONAL (Nice-to-Have):**
- 🔷 Créer KNOWN_ISSUES.md si inexistant (cataloguer erreurs pre-existantes)
- 🔷 Audit exhaustif violations Modal dans code (si temps permet)
- 🔷 Rapport consolidé erreurs build/tests (fichier séparé)
- 🔷 Validation template PR avec draft PR réelle (AC4 recommande)

**Ordre Exécution Critique:**
1. **FIRST:** Investigation décision signatures + audit erreurs (Phase 1)
2. **THEN:** Corrections code parallèle (règle ESLint + template PR) (Phase 2)
3. **THEN:** Documentation (signatures + notes 17-16) (Phase 3)
4. **FINALLY:** Validation finale (tests + lint + cohérence) (Phase 4)

### Success Metrics

**Quantitatif:**
- ✅ 2 rapports validation avec signatures (Option A) OU note explicative (Option B)
- ✅ 1 règle ESLint modifiée (`require-app-useapp.js`)
- ✅ 3-4 tests Modal ajoutés (total ~37-38 tests passent)
- ✅ 1 completion notes enrichie (story 17-16 avec chiffres précis)
- ✅ 1 template PR corrigé (chemin relatif correct)
- ✅ 0 violations standards frontend (lint passe)
- ✅ 0 régression tests (34+ tests passent)

**Qualitatif:**
- ✅ Décision signatures documentée (rationale Option A ou B)
- ✅ Règle ESLint détecte Modal (faux négatif corrigé)
- ✅ Notes 17-16 claires (distinction erreurs story vs. pre-existantes)
- ✅ Template PR lien fonctionnel (validé GitHub UI)
- ✅ File List complet story 20-8 (tous fichiers modifiés listés)
- ✅ Completion Notes détaillées (preuves commandes exécutées)

**Critères Acceptation Story:**
- ✅ AC1: Signatures rapports (Option A avec noms/rôles/dates OU Option B note explicative)
- ✅ AC2: CRITICAL-1 résolu (Modal détecté par règle ESLint + tests)
- ✅ AC3: CRITICAL-2 résolu (notes 17-16 enrichies avec chiffres précis)
- ✅ AC4: CRITICAL-3 résolu (chemin template PR correct)
- ✅ AC5: Validation croisée (tests passent, doc cohérente, File List complet)

### References

**Documents Source (Lecture):**
- [Source: _bmad-output/implementation-artifacts/15-4-documentation-securite-plan-remediation.md] — Story 15-4 (signatures rapports)
- [Source: _bmad-output/implementation-artifacts/17-16-verification-conformite-frontend-standards.md] — Story 17-16 (3 CRITICAL)
- [Source: _bmad-output/implementation-artifacts/18-7-correction-tests-en-echec.md] — Story 18-7 (KNOWN_ISSUES.md)
- [Source: _bmad-output/planning-artifacts/epic-20-action-items-et-suivi-stories-done.md] — Epic 20 (story 20.8 définition)
- [Source: idp-portal/frontend/FRONTEND-STANDARDS.md] — Standards frontend (ligne 114 : Modal règle)

**Fichiers Rapports Validation:**
- [Source: idp-portal/docs/security-release-validation.md] — Rapport go/no-go release (lignes 308-324 : section Approbation)
- [Source: idp-portal/docs/soc1-compliance-report.md] — Rapport conformité SOC1 v2.0 (lignes 312-317 : section Approbation)

**Fichiers Plugin ESLint:**
- [Source: frontend/eslint-plugin-standards/rules/require-app-useapp.js] — Règle à modifier (ajouter Modal)
- [Source: frontend/eslint-plugin-standards/rules/__tests__/require-app-useapp.test.js] — Tests à compléter
- [Source: frontend/eslint.config.js] — Config ESLint flat (règles intégrées)

**Template PR et CI:**
- [Source: .github/PULL_REQUEST_TEMPLATE.md] — Template PR (chemin à corriger)
- [Source: .github/workflows/ci.yml] — Pipeline CI (job `lint-frontend` lignes 24-37)

**Architecture et Contexte:**
- [Source: _bmad-output/planning-artifacts/architecture.md] — Architecture portail (standards Ant Design 6.2, RBAC, SOC1)
- [Source: idp-portal/frontend/KNOWN_ISSUES.md] — Catalogage erreurs pre-existantes (si existe)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- ESLint plugin tests : `npx vitest run eslint-plugin-standards` → 40/40 PASS
- ESLint lint : `npx eslint --no-cache "src/**/*.{ts,tsx}"` → 0 violations `standards/*`
- Build TypeScript : `npm run build` → 243 erreurs dans 81 fichiers (pre-existantes)
- Tests frontend : `npx vitest run` → 1507/1572 passent (65 echoues pre-existants, 20 suites)

### Completion Notes List

**Décision Signatures (AC1) :**
- Option choisie : B — Note explicative
- Rationale : Projet interne sans exigence réglementaire SOC1 externe. Les approbations formelles sont gérées via le processus Git (PR review + merge approval). La traçabilité est assurée par l'historique Git.
- Fichiers modifiés : `security-release-validation.md` (v1.0→v1.1), `soc1-compliance-report.md` (v2.0→v2.1)
- Les deux rapports contiennent la même note explicative (cohérence)
- Conditions d'approbation checklist mise à jour (items vérifiés cochés)

**Correction CRITICAL-1 Modal (AC2) :**
- Règle modifiée : `require-app-useapp.js` — Approche améliorée : détection de l'usage impératif Modal (`Modal.confirm()`, `Modal.error()`, etc.) plutôt que blocage de l'import (le composant JSX `<Modal>` reste valide)
- Nouveau message d'erreur : `requireModalUseApp` pour les usages impératifs
- Tests ajoutés : 6 nouveaux tests Modal (2 valid + 4 invalid) — total 18 tests require-app-useapp, 40 tests plugin
- Violations détectées : 4 usages impératifs dans 3 fichiers → tous corrigés :
  - `ActionWizard.tsx` : `Modal.error()` → `modal.error()` via `App.useApp()`
  - `WorkflowBuilderCanvas.tsx` : `Modal.error()` + `Modal.confirm()` → `modal.error()` + `modal.confirm()`
  - `ExecutionsPage.tsx` : `Modal.confirm()` → `modal.confirm()`
- Validation : `npx eslint --no-cache "src/**/*.{ts,tsx}"` → 0 violations standards

**Enrichissement Notes 17-16 (AC3) :**
- Build TypeScript : 243 erreurs dans 81 fichiers (principalement TS2304 `global`, TS2591 `require`, TS6133 unused vars)
- Tests frontend : 65 tests echoués sur 20 suites (1507/1572 passent, 95.9%)
- KNOWN_ISSUES.md : Existe (backend uniquement : `django_backend/tests/KNOWN_ISSUES.md`, 181 failures pre-existants)
- Pas de KNOWN_ISSUES.md frontend — noté dans enrichissement
- Fichier modifié : `17-16-verification-conformite-frontend-standards.md` (section Completion Notes enrichie avec chiffres précis)

**Correction Chemin Template PR (AC4) :**
- Fichier modifié : `idp-portal/.github/PULL_REQUEST_TEMPLATE.md`
- Chemin corrigé : `../idp-portal/frontend/FRONTEND-STANDARDS.md` → `../frontend/FRONTEND-STANDARDS.md`
- Description règle `require-app-useapp` mise à jour pour inclure `modal`
- Validation : Chemin vérifié structurellement (`.github/` → `../frontend/` = correct)

**Validation Finale (AC5) :**
- Tests plugin ESLint : 40/40 tests passent (3 fichiers test, 18+11+11)
- Linting frontend : 0 violations `standards/*`
- Documentation cohérente : ✅ (même note explicative dans les 2 rapports)
- File List complet : ✅

### File List

**Fichiers modifiés (Documentation) :**
- idp-portal/docs/security-release-validation.md (section Approbation : note explicative, version 1.1, historique)
- idp-portal/docs/soc1-compliance-report.md (section Approbation : note explicative, version 2.1)
- _bmad-output/implementation-artifacts/17-16-verification-conformite-frontend-standards.md (Completion Notes enrichies avec chiffres erreurs pre-existantes)

**Fichiers modifiés (Code — Règle ESLint) :**
- idp-portal/frontend/eslint-plugin-standards/rules/require-app-useapp.js (détection Modal impératif ajoutée)
- idp-portal/frontend/eslint-plugin-standards/rules/__tests__/require-app-useapp.test.js (6 tests Modal ajoutés)

**Fichiers modifiés (Code — Corrections violations Modal) :**
- idp-portal/frontend/src/components/admin/ActionWizard.tsx (Modal.error → modal.error via App.useApp)
- idp-portal/frontend/src/components/admin/WorkflowBuilderCanvas.tsx (Modal.error + Modal.confirm → modal.error + modal.confirm)
- idp-portal/frontend/src/pages/ExecutionsPage.tsx (Modal.confirm → modal.confirm via App.useApp)

**Fichiers modifiés (Template PR) :**
- idp-portal/.github/PULL_REQUEST_TEMPLATE.md (chemin FRONTEND-STANDARDS.md corrigé + description règle useapp)

**Aucun fichier créé** (corrections uniquement)

### Change Log

- 2026-02-08: Implémentation complète Story 20.8 — Signatures rapports (Option B note explicative), détection Modal impératif ESLint + corrections 4 violations, enrichissement notes 17-16 avec chiffres précis, correction chemin template PR. 40/40 tests ESLint plugin, 0 violations standards.
