# Story 4.9 : Intégrations — type libre, flow d’auth et upload d’icône

Status: backlog

<!-- Story ajoutée hors Epic 2 (terminé). Positionnée dans Epic 4 (Exécution & suivi) car les intégrations alimentent les connecteurs d’exécution. -->

## Story

As a **DBOPS**,
I want **définir une intégration avec un type libre (nom de plateforme), un flow d’authentification, une icône uploadée, l’URL et la référence Vault**,
So that **je peux ajouter demain une nouvelle plateforme sans changer le code : je choisis le nom, j’uploade l’icône, je définis l’URL, le flow de connexion et le secret Vault**.

## Contexte / Problème

Aujourd’hui, le type d’intégration est un enum fixe (aap, servicenow, terraform, etc.). Pour ajouter une nouvelle plateforme, il faut modifier le code. De plus, le flow d’authentification (token seul, username/password, username/password → token, PAT) n’est pas défini par intégration : l’exécuteur ne sait pas comment utiliser le secret récupéré depuis Vault. Enfin, l’icône est soit un preset par type, soit une URL saisie à la main — pas d’upload.

## Acceptance Criteria

1. **AC1 — Type libre**
   **Given** un DBOPS crée ou modifie une intégration,
   **When** il renseigne le type (ou « nom de plateforme »),
   **Then** le type est une chaîne libre (saisie texte, 1–100 caractères), pas une liste figée ; aucune modification de code n’est requise pour ajouter une nouvelle plateforme.

2. **AC2 — Flow d’authentification**
   **Given** un DBOPS crée ou modifie une intégration,
   **When** il configure l’authentification,
   **Then** il peut choisir un flow parmi : token (Bearer), basic (username/password), basic_then_token (user/pass puis échange pour token), pat (Personal Access Token). Ce flow est persisté et utilisé par le moteur d’exécution pour savoir comment utiliser le secret Vault (clés attendues, méthode d’auth).

3. **AC3 — Upload d’icône**
   **Given** un DBOPS crée ou modifie une intégration,
   **When** il souhaite associer une icône,
   **Then** il peut uploader un fichier image (PNG, JPEG, SVG ou équivalent) ; le backend stocke l’icône (ou une référence/URL) et l’affichage dans la liste et le formulaire utilise cette icône. L’option « URL d’icône » (saisie manuelle) reste possible.

4. **AC4 — Champs existants conservés**
   **Given** une intégration,
   **Then** les champs nom (unique), URL de base, référence credentials (Vault) restent tels quels ; le formulaire inclut : nom, type (libre), URL, flow (select), référence Vault, icône (upload ou URL).

5. **AC5 — Rétrocompatibilité**
   **Given** des intégrations existantes avec type enum (aap, servicenow, etc.),
   **When** la migration est appliquée,
   **Then** les types existants restent valides (chaîne) ; les intégrations sans flow ont une valeur par défaut ou nullable selon le design ; l’affichage et l’API restent cohérents.

6. **AC6 — Backend**
   **Given** le modèle et l’API intégrations,
   **Then** la base de données permet un type VARCHAR libre et une colonne auth_flow (ou équivalent) ; l’API CRUD expose type (string) et flow ; un endpoint d’upload d’icône (ex. POST /admin/integrations/upload-icon) accepte un fichier et retourne une URL ou un chemin à enregistrer dans le champ icon.

7. **AC7 — Frontend**
   **Given** le formulaire d’intégration,
   **Then** le champ type est un Input texte (avec suggestions optionnelles) ; le champ flow est un Select (token, basic, basic_then_token, pat) ; le champ icône propose Upload (fichier) et/ou URL ; la liste des intégrations affiche l’icône uploadée ou l’URL.

## Tasks / Subtasks (à détailler en ready-for-dev)

- [ ] Task 1 — Migration DB : type libre + auth_flow
  - Colonne TYPE : passer en VARCHAR(100) sans CHECK (ou étendre la contrainte), colonne AUTH_FLOW VARCHAR(50) avec valeurs (token, basic, basic_then_token, pat).

- [ ] Task 2 — Backend : modèles et repository
  - Modèles Pydantic : type (str), auth_flow (enum ou str), garder credential_ref, icon ; repository et API CRUD mis à jour.

- [ ] Task 3 — Backend : endpoint upload icône
  - POST /api/v1/admin/integrations/upload-icon (multipart), stockage configurable (fichier local ou futur S3), retour { icon_url } ou équivalent.

- [ ] Task 4 — Frontend : types et formulaire
  - Types API : type string, auth_flow ; formulaire : type Input libre, flow Select, icône Upload + URL ; liste : afficher icône uploadée.

- [ ] Task 5 — Tests et rétrocompatibilité
  - Tests unitaires backend/frontend ; migration des données existantes si nécessaire.

## Dev Notes

- **Contexte** : Les intégrations (Story 2.27, 2.28) alimentent le moteur d’exécution (Epic 4). Le flow d’auth permet à l’exécuteur de savoir comment utiliser le secret Vault (Bearer, Basic, échange token, PAT) sans coder en dur par type.
- **Position** : Epic 4 (Exécution & suivi) — story 4.9 ; Epic 2 est considéré terminé.
- **Références** : Story 2.27 (backend intégrations), Story 2.28 (frontend admin intégrations), discussion PM — type libre, flow par intégration, upload icône.

## Change Log

- **2026-01-29** : Création de la story (4.9) ; positionnée dans Epic 4 ; pas d’implémentation.
