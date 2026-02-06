# Epic 16: Builder de Workflow Visuel avec Branches Conditionnelles et Retry

Status: backlog

## Epic Goal

En tant que **DBOPS créant des workflows complexes**,
je veux **un éditeur visuel de workflow avec branches conditionnelles (succès/erreur) et options de retry configurables**,
afin que **je puisse créer des workflows robustes avec gestion d'erreurs et réessais automatiques sans avoir à écrire du code complexe**.

## Contexte

**État actuel (Post-Story 9.5):**

Les workflows actuels sont des séquences linéaires d'actions :
- Un seul bouton "Nouvelle action" ouvre un wizard où l'utilisateur doit choisir entre "action" et "workflow"
- Chaque workflow contient une liste ordonnée d'actions (`workflow_steps`)
- Les actions s'exécutent séquentiellement dans l'ordre défini
- Aucune gestion d'erreur conditionnelle : si une action échoue, le workflow entier échoue
- Aucun mécanisme de retry : si une action échoue, elle n'est pas réessayée
- Pas de branches conditionnelles : impossible de définir des chemins différents selon le résultat d'une action

**Limitations identifiées :**

1. **UX de création peu intuitive** : Un seul bouton nécessite de choisir le type dans le wizard, ce qui ajoute une étape inutile
2. **Pas de gestion d'erreur fine** : Un workflow ne peut pas avoir des comportements différents selon qu'une action réussit ou échoue
3. **Pas de retry** : Les actions qui échouent temporairement (ex: timeout réseau) ne peuvent pas être réessayées automatiquement
4. **Workflows linéaires uniquement** : Impossible de créer des workflows avec des chemins parallèles ou conditionnels
5. **Expérience utilisateur limitée** : Création de workflow via liste textuelle, pas de visualisation du flux

**Objectif de cet épic :**

Améliorer l'expérience de création et transformer les workflows en une expérience visuelle avec :
- **Séparation des boutons** : Accès direct à "Nouvelle action" ou "Nouveau workflow" sans étape de sélection
- **Éditeur graphique** : Visualisation du workflow comme un diagramme de flux
- **Branches conditionnelles** : Définir des chemins différents selon le résultat (succès/erreur) de chaque étape
- **Options de retry** : Configurer le nombre de tentatives et l'intervalle entre les tentatives pour chaque action
- **Validation visuelle** : Détecter les erreurs de configuration (chemins orphelins, boucles infinies, etc.)

**Bénéfices attendus :**

- **UX améliorée** : Accès direct aux formulaires de création sans étape de sélection intermédiaire
- **Workflows plus robustes** : Gestion d'erreurs fine avec chemins de récupération
- **Fiabilité accrue** : Retry automatique pour les erreurs temporaires
- **Productivité DBOPS** : Création de workflows complexes sans code
- **Visualisation claire** : Compréhension immédiate du flux d'exécution
- **Maintenance facilitée** : Modification et débogage de workflows plus simples

## Stories

### Story 16.1: Séparation des boutons "Nouvelle action" et "Nouveau workflow"

En tant que **DBOPS créant des éléments du catalogue**,
je veux **avoir deux boutons distincts "Nouvelle action" et "Nouveau workflow" au lieu d'un seul bouton avec sélection de type**,
afin que **je puisse accéder directement au bon formulaire sans avoir à choisir le type dans un wizard**.

**Acceptance Criteria:**

**Given** je suis sur la page Administration (onglet Actions)
**When** je consulte la section Actions
**Then** deux boutons distincts sont affichés côte à côte :
  - "Nouvelle action" (bouton primary avec icône PlusOutlined)
  - "Nouveau workflow" (bouton primary avec icône BranchesOutlined ou similaire)

**Given** je suis sur la page Administration
**When** je clique sur le bouton "Nouvelle action"
**Then** le wizard ActionWizard s'ouvre avec `item_type` pré-sélectionné à "action"
**And** le champ Radio.Group pour le type est masqué ou désactivé (valeur fixée à "action")
**And** les champs Moteur et Plateforme sont visibles et obligatoires

**Given** je suis sur la page Administration
**When** je clique sur le bouton "Nouveau workflow"
**Then** le wizard ActionWizard s'ouvre avec `item_type` pré-sélectionné à "workflow"
**And** le champ Radio.Group pour le type est masqué ou désactivé (valeur fixée à "workflow")
**And** les champs Moteur et Plateforme sont masqués (workflows n'ont pas de connecteur)

**Given** je suis en mode édition d'une action existante
**When** le wizard ActionWizard s'ouvre
**Then** le champ Radio.Group pour le type reste désactivé (on ne peut pas changer le type après création)
**And** le comportement actuel est préservé

**Given** je suis sur la page Administration
**When** je consulte la liste des actions/workflows
**Then** la colonne "Type" affiche clairement "Action" ou "Workflow" pour chaque élément
**And** les filtres permettent de filtrer par type si nécessaire

**Given** je suis sur la page Administration
**When** je crée une nouvelle action via le bouton "Nouvelle action"
**Then** le workflow de création est simplifié (pas de sélection de type)
**And** l'expérience utilisateur est plus directe et intuitive

**Given** je suis sur la page Administration
**When** je crée un nouveau workflow via le bouton "Nouveau workflow"
**Then** le workflow de création est simplifié (pas de sélection de type)
**And** l'éditeur d'étapes workflow s'affiche directement au Step 2

### Story 16.2: Modèle de données pour workflows avec branches et retry

En tant que **développeur backend**,
je veux **étendre le modèle de données des workflows pour supporter les branches conditionnelles et les options de retry**,
afin que **le système puisse stocker et exécuter des workflows complexes avec gestion d'erreurs**.

**Acceptance Criteria:**

**Given** le modèle de données actuel des workflows (Story 9.5)
**When** j'étends le schéma pour supporter les branches et retry
**Then** la table `WORKFLOW_STEPS` inclut les nouveaux champs :
  - `on_success_step_id` : ID de l'étape suivante en cas de succès (nullable)
  - `on_error_step_id` : ID de l'étape suivante en cas d'erreur (nullable)
  - `retry_enabled` : Boolean indiquant si le retry est activé pour cette étape
  - `retry_max_attempts` : Nombre maximum de tentatives (nullable, défaut: 3)
  - `retry_interval_seconds` : Intervalle en secondes entre les tentatives (nullable, défaut: 60)
  - `retry_backoff_multiplier` : Multiplicateur pour backoff exponentiel (nullable, défaut: 2.0)

**And** une migration SQL est créée pour ajouter ces colonnes à `WORKFLOW_STEPS`
**And** les contraintes de clé étrangère sont ajoutées pour `on_success_step_id` et `on_error_step_id` référençant `WORKFLOW_STEPS.ID`
**And** une contrainte CHECK garantit que `retry_max_attempts >= 1` si `retry_enabled = true`
**And** une contrainte CHECK garantit que `retry_interval_seconds >= 1` si `retry_enabled = true`

**And** le modèle Pydantic `WorkflowStep` est mis à jour avec ces nouveaux champs
**And** le modèle TypeScript `WorkflowStep` est mis à jour en conséquence

**Given** un workflow avec des branches conditionnelles
**When** je sauvegarde le workflow
**Then** le système valide que :
  - Toutes les références `on_success_step_id` et `on_error_step_id` pointent vers des étapes du même workflow
  - Il n'y a pas de boucles infinies dans les chemins d'erreur
  - Au moins une étape a `on_success_step_id = NULL` (point de sortie du workflow)

### Story 16.3: Moteur d'exécution avec support des branches conditionnelles

En tant que **système d'exécution**,
je veux **exécuter des workflows avec branches conditionnelles en suivant les chemins succès/erreur**,
afin que **les workflows puissent gérer les erreurs et prendre des chemins différents selon le résultat**.

**Acceptance Criteria:**

**Given** un workflow avec des branches conditionnelles configurées
**When** une étape s'exécute avec succès
**Then** le système passe à l'étape définie dans `on_success_step_id`
**And** si `on_success_step_id` est NULL, le workflow se termine avec succès

**Given** un workflow avec des branches conditionnelles configurées
**When** une étape s'exécute et échoue
**Then** le système passe à l'étape définie dans `on_error_step_id`
**And** si `on_error_step_id` est NULL, le workflow se termine avec erreur
**And** l'erreur de l'étape est propagée dans le contexte d'exécution

**Given** un workflow avec plusieurs chemins parallèles
**When** plusieurs étapes peuvent être exécutées en parallèle (pas de dépendances)
**Then** le système exécute ces étapes en parallèle
**And** le workflow attend que toutes les branches parallèles se terminent avant de continuer

**Given** un workflow avec une étape qui a `on_success_step_id` et `on_error_step_id` pointant vers la même étape
**When** l'étape s'exécute (succès ou erreur)
**Then** le système passe toujours à cette étape commune
**And** le contexte d'exécution indique le chemin emprunté (succès ou erreur)

**Given** un workflow avec une boucle (étape A → étape B → étape A)
**When** le workflow s'exécute
**Then** le système détecte la boucle et limite le nombre d'itérations
**And** après un nombre maximum d'itérations (ex: 100), le workflow échoue avec une erreur "Boucle infinie détectée"

### Story 16.4: Moteur de retry avec backoff exponentiel

En tant que **système d'exécution**,
je veux **réessayer automatiquement les actions qui échouent avec un intervalle configurable et un backoff exponentiel**,
afin que **les erreurs temporaires (timeout réseau, service indisponible) soient gérées automatiquement**.

**Acceptance Criteria:**

**Given** une étape de workflow avec `retry_enabled = true` et `retry_max_attempts = 3`
**When** l'étape échoue lors de la première tentative
**Then** le système attend `retry_interval_seconds` secondes
**And** réessaye l'étape (tentative 2)
**And** si la tentative 2 échoue, attend `retry_interval_seconds * retry_backoff_multiplier` secondes
**And** réessaye l'étape (tentative 3)
**And** si toutes les tentatives échouent, passe à `on_error_step_id` ou termine avec erreur

**Given** une étape avec `retry_enabled = true` et `retry_max_attempts = 5`
**When** l'étape réussit lors de la tentative 2
**Then** le système arrête les retries
**And** passe à `on_success_step_id` avec le résultat de la tentative réussie
**And** les logs indiquent le nombre de tentatives effectuées

**Given** une étape avec retry activé
**When** l'étape échoue avec une erreur permanente (ex: validation échouée, action non trouvée)
**Then** le système détecte que c'est une erreur non-réessayable
**And** arrête immédiatement les retries
**And** passe à `on_error_step_id` sans attendre

**Given** une étape avec retry activé
**When** l'utilisateur annule manuellement l'exécution du workflow
**Then** le système arrête immédiatement les retries en cours
**And** marque le workflow comme annulé

**Given** une étape avec retry activé
**When** le système effectue des retries
**Then** chaque tentative est loggée dans l'audit log avec :
  - Numéro de tentative
  - Résultat (succès/échec)
  - Erreur si échec
  - Temps d'attente avant la tentative suivante

### Story 16.5: Interface de builder visuel de workflow

En tant que **DBOPS créant un workflow**,
je veux **une interface graphique pour créer et modifier des workflows avec drag-and-drop**,
afin que **je puisse visualiser et configurer facilement les branches conditionnelles et les chemins d'exécution**.

**Acceptance Criteria:**

**Given** je suis sur la page de création/édition de workflow
**When** je sélectionne l'onglet "Builder visuel"
**Then** un canvas graphique s'affiche avec :
  - Une zone de travail zoomable et pannable
  - Une palette d'actions disponibles (liste des actions publiées)
  - Des outils de connexion pour créer des liens entre les étapes

**Given** je suis dans le builder visuel
**When** je fais glisser une action depuis la palette vers le canvas
**Then** un nouveau nœud d'étape apparaît sur le canvas
**And** le nœud affiche :
  - Le nom de l'action
  - L'icône de la technologie (Oracle, SQL Server, etc.)
  - Des ports de connexion (entrée, sortie succès, sortie erreur)

**Given** je suis dans le builder visuel avec des étapes créées
**When** je clique sur le port "succès" d'une étape et le connecte au port "entrée" d'une autre étape
**Then** une flèche verte apparaît entre les deux étapes
**And** le système met à jour `on_success_step_id` de la première étape

**Given** je suis dans le builder visuel avec des étapes créées
**When** je clique sur le port "erreur" d'une étape et le connecte au port "entrée" d'une autre étape
**Then** une flèche rouge apparaît entre les deux étapes
**And** le système met à jour `on_error_step_id` de la première étape

**Given** je suis dans le builder visuel
**When** je double-clique sur un nœud d'étape
**Then** un panneau latéral s'ouvre avec :
  - Les détails de l'action (nom, description, paramètres)
  - Les options de retry (activé/désactivé, nombre de tentatives, intervalle)
  - Les options de branchement (étape suivante en succès, étape suivante en erreur)

**Given** je suis dans le builder visuel
**When** je supprime une connexion entre deux étapes
**Then** la flèche disparaît
**And** le champ correspondant (`on_success_step_id` ou `on_error_step_id`) est mis à NULL

**Given** je suis dans le builder visuel
**When** je supprime un nœud d'étape
**Then** le nœud disparaît du canvas
**And** toutes les connexions vers/depuis ce nœud sont supprimées
**And** le système valide que le workflow reste valide (au moins une étape de départ)

**Given** je suis dans le builder visuel
**When** je sauvegarde le workflow
**Then** le système valide :
  - Toutes les étapes ont au moins une connexion de sortie (succès ou erreur)
  - Il n'y a pas de chemins orphelins (étapes non atteignables depuis le début)
  - Il n'y a pas de boucles infinies
**And** affiche les erreurs de validation directement sur le canvas (nœuds en rouge)

### Story 16.6: Configuration des options de retry dans le builder visuel

En tant que **DBOPS configurant un workflow**,
je veux **configurer les options de retry pour chaque étape directement dans le builder visuel**,
afin que **je puisse définir facilement le comportement de retry pour chaque action**.

**Acceptance Criteria:**

**Given** je suis dans le builder visuel avec un nœud d'étape sélectionné
**When** j'ouvre le panneau de configuration de l'étape
**Then** une section "Options de retry" s'affiche avec :
  - Un toggle "Activer le retry automatique"
  - Un champ "Nombre maximum de tentatives" (défaut: 3, min: 1, max: 10)
  - Un champ "Intervalle entre tentatives (secondes)" (défaut: 60, min: 1)
  - Un champ "Multiplicateur de backoff" (défaut: 2.0, min: 1.0, max: 10.0)
  - Une explication textuelle : "L'intervalle sera multiplié par ce facteur à chaque tentative (backoff exponentiel)"

**Given** je suis dans le panneau de configuration d'une étape
**When** je désactive le toggle "Activer le retry automatique"
**Then** les champs de configuration de retry deviennent désactivés (grisés)
**And** les valeurs sont conservées mais non appliquées

**Given** je suis dans le panneau de configuration d'une étape avec retry activé
**When** je modifie le "Nombre maximum de tentatives" à 5
**Then** le champ se met à jour
**And** un indicateur visuel apparaît sur le nœud montrant "Retry: 5x"

**Given** je suis dans le panneau de configuration d'une étape avec retry activé
**When** je modifie l'intervalle à 30 secondes et le multiplicateur à 1.5
**Then** un aperçu s'affiche montrant :
  - Tentative 1: immédiate
  - Tentative 2: après 30s
  - Tentative 3: après 45s (30 * 1.5)
  - Tentative 4: après 67.5s (45 * 1.5)
  - etc.

**Given** je suis dans le builder visuel
**When** je survole un nœud avec retry activé
**Then** un tooltip s'affiche avec :
  - "Retry: X tentatives max"
  - "Intervalle: Y secondes"
  - "Backoff: Zx"

**Given** je suis dans le builder visuel
**When** je sauvegarde un workflow avec des étapes ayant retry activé
**Then** les configurations de retry sont validées :
  - Nombre de tentatives >= 1
  - Intervalle >= 1 seconde
  - Multiplicateur >= 1.0
**And** les valeurs sont sauvegardées dans la base de données

### Story 16.7: Visualisation et validation des chemins dans le builder visuel

En tant que **DBOPS créant un workflow**,
je veux **voir visuellement les chemins d'exécution et être alerté des erreurs de configuration**,
afin que **je puisse créer des workflows valides et compréhensibles**.

**Acceptance Criteria:**

**Given** je suis dans le builder visuel
**When** le workflow contient des chemins conditionnels
**Then** les flèches vertes représentent les chemins de succès
**And** les flèches rouges représentent les chemins d'erreur
**And** un nœud de départ (vert) et un nœud de fin (gris) sont affichés automatiquement

**Given** je suis dans le builder visuel
**When** une étape n'a pas de connexion de sortie (ni succès ni erreur)
**Then** le nœud est affiché avec un bordure orange (avertissement)
**And** un message d'erreur apparaît : "Cette étape n'a pas de chemin de sortie"

**Given** je suis dans le builder visuel
**When** une étape n'est pas atteignable depuis le nœud de départ
**Then** le nœud est affiché avec un bordure rouge (erreur)
**And** un message d'erreur apparaît : "Cette étape n'est pas atteignable"

**Given** je suis dans le builder visuel
**When** le workflow contient une boucle infinie (ex: A → B → A sans condition de sortie)
**Then** les nœuds de la boucle sont affichés avec un bordure rouge
**And** un message d'erreur apparaît : "Boucle infinie détectée : [liste des nœuds]"
**And** le workflow ne peut pas être sauvegardé

**Given** je suis dans le builder visuel
**When** je clique sur un chemin (flèche) entre deux étapes
**Then** la flèche est mise en surbrillance
**And** un menu contextuel apparaît avec l'option "Supprimer la connexion"

**Given** je suis dans le builder visuel
**When** je survole un nœud d'étape
**Then** un aperçu s'affiche montrant :
  - Le nom de l'action
  - Les chemins de sortie (succès → étape X, erreur → étape Y)
  - Les options de retry si activées

**Given** je suis dans le builder visuel
**When** je clique sur le bouton "Valider le workflow"
**Then** le système vérifie :
  - Toutes les étapes ont au moins une connexion de sortie
  - Toutes les étapes sont atteignables depuis le début
  - Il n'y a pas de boucles infinies
  - Au moins une étape mène à une fin (succès ou erreur)
**And** affiche un rapport de validation avec les erreurs trouvées
**And** met en surbrillance les nœuds problématiques sur le canvas

**Given** je suis dans le builder visuel
**When** je sauvegarde un workflow avec des erreurs de validation
**Then** le système empêche la sauvegarde
**And** affiche un message : "Le workflow contient des erreurs. Veuillez les corriger avant de sauvegarder."
**And** liste toutes les erreurs trouvées

### Story 16.8: Export/Import de workflows depuis le builder visuel

En tant que **DBOPS gérant des workflows**,
je veux **exporter et importer des workflows depuis le builder visuel**,
afin que **je puisse partager, versionner et réutiliser des workflows complexes**.

**Acceptance Criteria:**

**Given** je suis dans le builder visuel avec un workflow créé
**When** je clique sur le bouton "Exporter"
**Then** un menu s'affiche avec les options :
  - "Exporter en JSON" (format technique)
  - "Exporter en YAML" (format lisible)
  - "Exporter l'image" (capture du canvas)

**Given** je suis dans le builder visuel
**When** je sélectionne "Exporter en JSON"
**Then** un fichier JSON est téléchargé contenant :
  - La structure complète du workflow (étapes, connexions, retry)
  - Les métadonnées (nom, description, tags)
  - La version du format d'export

**Given** je suis dans le builder visuel
**When** je sélectionne "Exporter l'image"
**Then** une image PNG du canvas est générée et téléchargée
**And** l'image contient :
  - Tous les nœuds et connexions visibles
  - Les légendes (vert = succès, rouge = erreur)
  - Le nom du workflow en en-tête

**Given** je suis dans le builder visuel
**When** je clique sur le bouton "Importer"
**Then** un dialogue de sélection de fichier s'ouvre
**And** j'ai la possibilité de sélectionner un fichier JSON ou YAML

**Given** je suis dans le builder visuel
**When** je sélectionne un fichier JSON/YAML valide pour import
**Then** le workflow est chargé dans le canvas
**And** tous les nœuds et connexions sont restaurés
**And** les options de retry sont restaurées
**And** un message de confirmation s'affiche : "Workflow importé avec succès"

**Given** je suis dans le builder visuel
**When** je sélectionne un fichier JSON/YAML invalide pour import
**Then** un message d'erreur s'affiche : "Format de fichier invalide"
**And** les détails de l'erreur sont affichés
**And** le workflow actuel n'est pas modifié

**Given** je suis dans le builder visuel avec un workflow existant
**When** j'importe un nouveau workflow
**Then** un dialogue de confirmation s'affiche : "Voulez-vous remplacer le workflow actuel ?"
**And** si je confirme, le workflow actuel est remplacé
**And** si j'annule, l'import est annulé

## Dependencies

- **Story 9.5** : Interface admin création workflows (prérequis - workflows de base doivent exister)
- **Story 4.3** : Moteur d'exécution (prérequis - le moteur doit exister pour exécuter les workflows avec branches)

**Note Story 16.1** : Cette story peut être implémentée indépendamment et avant les autres stories de cet épic. Elle améliore l'UX de base de création d'actions/workflows.

## Technical Notes

- **Bibliothèque de graphiques** : Utiliser React Flow ou une bibliothèque similaire pour le canvas graphique
- **Validation de graphe** : Implémenter des algorithmes de détection de cycles (DFS) et de chemins orphelins
- **Performance** : Le builder visuel doit supporter des workflows avec 50+ étapes sans lag
- **Accessibilité** : Le builder doit être navigable au clavier (WCAG 2.1 AA)
- **Responsive** : Le builder fonctionne sur écrans larges (min 1280px) comme défini dans l'UX Design

## FR Coverage

Cet épic ne couvre pas de FRs existants du PRD initial, mais ajoute de nouvelles fonctionnalités avancées pour les workflows.

## Phase

**Phase 2** (Post-MVP) - Fonctionnalité avancée pour workflows complexes
