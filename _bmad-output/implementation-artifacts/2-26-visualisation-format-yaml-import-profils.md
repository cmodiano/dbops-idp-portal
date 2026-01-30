# Story 2.26 : Visualisation du format YAML pour import de profils

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DBOPS**,
I want **voir un exemple du format YAML attendu et télécharger un template**,
so that **je puisse préparer correctement mon fichier d'import de profils**.

## Acceptance Criteria

1. **AC1 — Exemple YAML visible (collapsible)**
   **Given** un DBOPS accède à l'interface d'import de profils,
   **When** la page (ou le modal d'import) s'affiche,
   **Then** un exemple YAML commenté est visible dans un bloc collapsible, replié par défaut.

2. **AC2 — Déplier l'exemple**
   **Given** un DBOPS veut voir l'exemple,
   **When** il clique sur "Voir le format YAML",
   **Then** le bloc se déplie et affiche un exemple complet avec commentaires explicatifs.

3. **AC3 — Contenu de l'exemple**
   L'exemple doit refléter le format attendu par l'API d'import (Story 2.13), incluant au minimum :
   - `name` (obligatoire), `description`, `ad_group`, `is_admin`, `is_auditor`
   - `action_permissions` : `type` ("all" | "list" | "pattern"), `patterns` ou `action_ids`, `environments`
   - `target_permissions` : `type`, `targets` ou `patterns`
   Avec commentaires en français pour chaque champ.

4. **AC4 — Télécharger template**
   **Given** un DBOPS veut un fichier template,
   **When** il clique sur "Télécharger template",
   **Then** un fichier `profile-template.yaml` est téléchargé avec la structure vide ou exemple prête à remplir.

5. **AC5 — UX**
   **And** le bloc exemple utilise une coloration syntaxique YAML (ou au minimum un style typographique clair pour les commentaires et clés).
   **And** le bouton "Télécharger template" est visible même quand le bloc est replié.

## Tasks / Subtasks

- [x] Task 1 (AC: 1, 2, 5) — Bloc collapsible avec exemple YAML
  - [x] 1.1 : Dans le modal "Importer YAML" (AdminPage) ou dans un composant dédié, ajouter un Collapse (Ant Design) avec un item "Voir le format YAML", replié par défaut (`defaultActiveKey=[]`).
  - [x] 1.2 : Contenu du bloc : exemple YAML complet (voir section Dev Notes) avec commentaires. Utiliser `<pre>` + balisage sémantique ou un composant type Typography.Text en `code` pour une lisibilité correcte.
  - [x] 1.3 : Optionnel : coloration syntaxique YAML (librairie légère type react-syntax-highlighter ou équivalent, ou CSS custom pour commentaires # et clés). Si pas de lib externe, au minimum différencier visuellement commentaires et clés.

- [x] Task 2 (AC: 4, 5) — Bouton Télécharger template
  - [x] 2.1 : Ajouter un bouton "Télécharger template" visible en permanence (au-dessus ou à côté du Collapse). Au clic : déclencher le téléchargement d'un fichier `profile-template.yaml` avec contenu = exemple/structure vide (même contenu que l'exemple affiché dans le bloc, ou version minimale).
  - [x] 2.2 : Implémentation : soit blob client-side (construire le YAML en string, créer Blob, URL.createObjectURL + <a download>), soit endpoint GET `/api/v1/admin/profiles/export-template` qui retourne un fichier template. Préférer client-side pour éviter un nouvel endpoint si le template est statique.

- [x] Task 3 (AC: 3) — Alignement avec format d'import
  - [x] 3.1 : Vérifier que l'exemple et le template correspondent au format accepté par POST `/admin/profiles/import` (backend). Consulter le backend (modèles Pydantic, validation) et le format documenté dans Story 2.13 (epics.md).

- [x] Task 4 — Tests
  - [x] 4.1 : Test d'affichage : ouverture du modal d'import affiche le Collapse replié et le bouton "Télécharger template".
  - [x] 4.2 : Test interaction : clic sur "Voir le format YAML" déplie le bloc et affiche l'exemple.
  - [x] 4.3 : Test téléchargement : clic sur "Télécharger template" déclenche un téléchargement avec nom de fichier `profile-template.yaml` et contenu non vide (snapshot ou assertion sur le blob/texte).

## Dev Notes

- L'interface d'import existante est le **Modal "Importer YAML"** dans `AdminPage.tsx` (lignes ~465–479). C'est là qu'il faut ajouter le bloc exemple + bouton template, sans casser le flux actuel (sélection fichier + Importer).
- Pas de nouvel endpoint obligatoire : le template peut être généré côté client (constante YAML en string ou fichier statique importé).
- Format YAML de référence (épics Story 2.26) :

```yaml
# Format d'import de profil DBOPS Portal
# Tous les champs sont optionnels sauf 'name'

name: "dba_oracle"                    # Obligatoire - Nom unique du profil
description: "DBAs Oracle production"  # Description du profil
ad_group: "GRP-DBA-ORACLE"             # Groupe Active Directory associé
is_admin: false                       # Accès admin (défaut: false)
is_auditor: false                     # Accès audit (défaut: false)

action_permissions:
  type: "pattern"                     # "all" | "list" | "pattern"
  patterns: ["oracle*", "backup*"]     # Si type=pattern
  # action_ids: [1, 2, 3]             # Si type=list
  environments: ["DEV", "STAGING", "PROD"]

target_permissions:
  type: "list"                        # "all" | "list" | "pattern"
  targets: ["srv-ora-01", "srv-ora-02"]
  # patterns: ["srv-ora-*"]           # Si type=pattern
```

- Pour l'import multi-profils (liste), le backend peut attendre `profiles: [ { ... }, { ... } ]`. Vérifier dans l'API existante (Story 2.13) si le format est un seul profil ou une liste et adapter l'exemple/template en conséquence.

### Project Structure Notes

- **Modifier** : `idp-portal/frontend/src/pages/AdminPage.tsx` — modal "Importer YAML" : ajouter Collapse (exemple YAML) + bouton "Télécharger template".
- **Optionnel** : extraire le contenu du modal d'import (exemple + template + file input) dans un composant `ProfileImportModal.tsx` dans `components/admin/` pour alléger AdminPage. Si on reste en inline, documenter l’emplacement dans AdminPage.
- **Optionnel** : `frontend/src/constants/profileYamlTemplate.ts` — constante contenant la chaîne YAML de l’exemple et du template (partagée entre affichage et téléchargement).

### Architecture Compliance

- **Stack** : React 19, TypeScript, Ant Design 6 (Collapse, Button, Typography, Modal existant).
- **Pattern** : Pas de nouveau service API si template généré côté client. Respect du pattern existant : Modal dans AdminPage, appels à `importProfilesYaml` inchangés.
- **API** : Aucun nouvel endpoint requis pour la story (template = client-side). Si l’équipe préfère un endpoint GET `/admin/profiles/export-template`, c’est acceptable mais à documenter.

### Library/Framework Requirements

- **Ant Design 6** : Collapse, Button, Typography (code/pre), Modal — déjà utilisés dans le projet.
- **Optionnel** : librairie de coloration syntaxique (ex. `react-syntax-highlighter`) pour le bloc YAML — à valider avec l’équipe (poids bundle vs confort visuel). Sinon, style CSS/typographie suffisant.

### File Structure Requirements

- Modifier : `frontend/src/pages/AdminPage.tsx` (modal Importer YAML).
- Optionnel : `frontend/src/components/admin/ProfileImportModal.tsx` (extraction du modal).
- Optionnel : `frontend/src/constants/profileYamlTemplate.ts` (exemple + template string).

### Testing Requirements

- **Vitest + React Testing Library** : affichage du modal avec Collapse replié et bouton "Télécharger template" ; clic "Voir le format YAML" déplie le bloc ; clic "Télécharger template" déclenche un download avec le bon nom et contenu.
- **Mock** : pas besoin de mocker `importProfilesYaml` pour les tests d’affichage du bloc et du bouton template (uniquement pour les tests de soumission d’import existants).

### Previous Story Intelligence (Story 2.25 — ProfileWizard)

- **Contexte** : L’onglet Profils utilise déjà `ProfilesTable`, `ProfileWizard`, et le modal d’import YAML dans AdminPage. Les appels `exportProfilesYaml` et `importProfilesYaml` sont en place (Story 2.13).
- **À réutiliser** : Même page AdminPage, même modal d’import ; ajouter uniquement le bloc exemple et le bouton template sans changer le comportement d’import existant.
- **Cohérence** : Boutons et textes en français ; style Ant Design cohérent avec le reste de l’admin (ProfilesTable, ProfileWizard).

### References

- [Source: _bmad-output/planning-artifacts/epics.md] Story 2.26 — Visualisation du format YAML pour import de profils (lignes 619–664).
- [Source: _bmad-output/planning-artifacts/epics.md] Story 2.13 — Import/Export profiles as code (YAML) : format et API.
- [Source: idp-portal/frontend/src/pages/AdminPage.tsx] Modal "Importer YAML" (lignes 465–479).
- [Source: idp-portal/frontend/src/services/profiles_service.ts] `exportProfilesYaml`, `importProfilesYaml`.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- Cree `ProfileImportModal` composant extrait du modal inline AdminPage pour meilleure testabilite
- Cree `profileYamlTemplate.ts` avec constante YAML alignee sur le format backend (`ProfilesYamlImport`)
- Format YAML verifie contre les modeles Pydantic backend : `profiles: [{ name, description, ad_group, is_admin, is_auditor, actions: { type, patterns|list }, targets: { type, patterns|list }, environments }]`
- Collapse Ant Design avec `defaultActiveKey=[]` pour etat replie par defaut
- Telechargement template via Blob client-side (pas de nouvel endpoint)
- 9 tests unitaires couvrant AC1-AC5 (affichage, interaction collapse, telechargement, import)
- Utilise `destroyOnHidden` et `orientation` (nouvelles props Ant Design 6)
- Code review 2026-01-29 : 4 correctifs appliques (defaultActiveKey, notification title, test warning)

### Senior Developer Review (AI)

- **Date:** 2026-01-29
- **Findings:** 4 MEDIUM, 1 LOW. Correctifs appliques : (1) Collapse `defaultActiveKey={[]}` pour repli par defaut (Task 1.1), (2) Notification `message` → `title` (API Ant Design 6), (3) Test « affiche un warning si aucun fichier » complete avec assertion sur `notification.warning`. (4) Space : `orientation` conserve (Ant Design 6 utilise orientation, pas direction).
- **Outcome:** Approve — story done.

### File List

- frontend/src/utils/profileYamlTemplate.ts (NEW)
- frontend/src/components/admin/ProfileImportModal.tsx (NEW)
- frontend/src/components/admin/ProfileImportModal.test.tsx (NEW)
- frontend/src/components/admin/index.ts (MODIFIED)
- frontend/src/pages/AdminPage.tsx (MODIFIED)

### Change Log

- 2026-01-29: Story 2.26 implementation complete — YAML example collapse + template download
- 2026-01-29: Code review — 4 correctifs (defaultActiveKey, notification title, test warning); status → done
