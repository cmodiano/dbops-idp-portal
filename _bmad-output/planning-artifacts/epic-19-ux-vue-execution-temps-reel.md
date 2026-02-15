# Epic 19 : UX — Vue d'exécution temps réel

**En tant que** DBA ou utilisateur du portail,  
**je veux** une vue d'exécution riche au lieu d'un simple popup « action démarrée »,  
**afin de** suivre la progression en temps réel, consulter les logs détaillés et identifier l'étape active immédiatement.

---

## Contexte

Actuellement, une fois toutes les étapes du wizard d'exécution remplies et l'action lancée, le portail affiche un simple popup indiquant que l'exécution est démarrée. L'utilisateur doit naviguer manuellement vers la liste des exécutions pour suivre la progression et consulter les logs.

Cet epic vise à remplacer ce flux par une **vue d'exécution immersive** qui s'affiche automatiquement après le lancement, offrant une expérience de suivi en temps réel adaptée au type d'exécution (action simple ou workflow).

---

## Portée (scope)

### Actions simples (une étape)

- **Timeline verticale** avec les étapes d'exécution (prérequis, exécution, vérification, etc.)
- **Indicateur visuel** de l'étape active (badge, couleur, icône animée)
- **Logs détaillés** en temps réel par étape (streaming WebSocket ou polling)
- **Statut global** visible (soumis, en cours, terminé, erreur)

### Workflows (multi-étapes)

- **Aperçu visuel du workflow** : graphe des étapes avec nœuds Départ → Actions → Fin
- **Étape active mise en évidence** dans le graphe (bordure, couleur, pulsation)
- **Clic sur une étape** : ouverture d'un panneau latéral ou modal avec la même vue que pour une action simple :
  - Timeline des sous-étapes de cette action
  - Logs en direct pour cette action
- **Vue d'ensemble** du chemin parcouru (étapes complétées vs en cours vs à venir)

### Comportement commun

- **Remplacement du popup** : après confirmation du wizard, redirection ou ouverture automatique vers la vue d'exécution (drawer, page dédiée ou modal plein écran)
- **Rafraîchissement temps réel** : WebSocket existant (`/ws/executions/{id}`) ou polling pour les mises à jour
- **Bouton « Fermer »** : retour au catalogue ou à la liste des exécutions ; l'exécution continue en arrière-plan

---

## Definition of Done

- [ ] Le popup « action démarrée » est remplacé par une vue d'exécution dédiée
- [ ] Pour une **action simple** : timeline verticale avec étape active et logs en direct
- [ ] Pour un **workflow** : aperçu visuel du graphe avec étape active mise en évidence
- [ ] Clic sur une étape de workflow ouvre la timeline + logs détaillés de cette action
- [ ] Les mises à jour sont visibles en temps réel (WebSocket ou polling < 5 s)
- [ ] L'utilisateur peut fermer la vue et revenir au catalogue ; l'exécution continue

---

## Stories proposées

### Story 19.0 : Simulation exécution en mode dev (sans intégrations réelles)

**En tant que** développeur,  
**je veux** pouvoir simuler visuellement les exécutions et le streaming des logs en environnement de développement sans AAP/ServiceNow configurés,  
**afin de** tester et valider l'UX de la vue d'exécution temps réel sans dépendre des plateformes distantes.

**Contexte :** En dev, les intégrations sont en `pass` ; les exécutions restent en SUBMITTED et les ExecutionSteps en PENDING. Le WebSocket Django n'est pas déployé. Cette story permet de débloquer le développement de l'Epic 19.

**Acceptance Criteria:**

**Given** le backend est en mode dev (`SIMULATE_EXECUTION_DEV=true` ou `DEBUG=True`)  
**When** une exécution est créée via POST `/api/v1/executions`  
**Then** une tâche de simulation s'exécute en arrière-plan  
**And** des ExecutionSteps sont créés/mis à jour avec progression simulée (PENDING → RUNNING → COMPLETED)  
**And** le champ `output` contient des logs fictifs (ex. `[INFO] Connexion Vault...`, `[INFO] Déclenchement AAP...`)  
**And** l'exécution passe en statut COMPLETED ou FAILED (selon config)

**Given** le frontend détecte l'absence de WebSocket ou `VITE_SIMULATE_EXECUTION=true`  
**When** la vue d'exécution est affichée  
**Then** un fallback en polling appelle `getExecution(id)` et `getExecutionSteps(id)` toutes les 2–3 secondes  
**And** la timeline et les logs se mettent à jour à mesure que le backend simule la progression

**Given** une exécution de workflow simulée  
**When** WorkflowRuntime est invoqué en mode simulation  
**Then** les étapes du workflow sont créées avec progression simulée  
**And** les logs par étape sont visibles dans la vue d'exécution

---

### Story 19.1 : Vue d'exécution pour action simple — Timeline et logs

**En tant que** DBA,  
**je veux** qu'après avoir lancé une action simple, une vue timeline s'affiche avec l'étape active et les logs en direct,  
**afin de** suivre la progression sans quitter le contexte.

**Acceptance Criteria:**

**Given** je viens de confirmer l'exécution d'une action simple (non-workflow) dans le wizard  
**When** l'exécution est créée avec succès  
**Then** le wizard se ferme et une vue d'exécution s'ouvre (drawer, modal ou page dédiée)  
**And** je ne vois plus le simple popup « action démarrée »

**Given** la vue d'exécution d'une action simple  
**When** j'affiche la progression  
**Then** une timeline verticale affiche les étapes (prérequis, exécution, vérification, etc.)  
**And** l'étape en cours est visuellement distinguée (badge actif, couleur, icône)  
**And** les étapes terminées affichent un indicateur de succès ou erreur

**Given** la vue d'exécution  
**When** une étape produit des logs  
**Then** les logs s'affichent en direct dans une zone dédiée (streaming ou polling)  
**And** je peux faire défiler les logs si nécessaire  
**And** les logs sont associés à l'étape correspondante

**Given** l'exécution se termine (succès ou erreur)  
**When** le statut final est reçu  
**Then** la timeline reflète l'état final  
**And** un message de succès ou d'erreur est affiché clairement

---

### Story 19.2 : Vue d'exécution pour workflow — Aperçu visuel et étape active

**En tant que** DBA,  
**je veux** qu'après avoir lancé un workflow, un aperçu visuel du graphe s'affiche avec l'étape active mise en évidence,  
**afin de** comprendre rapidement où en est l'exécution dans le flux.

**Acceptance Criteria:**

**Given** je viens de confirmer l'exécution d'un workflow dans le wizard  
**When** l'exécution est créée avec succès  
**Then** le wizard se ferme et une vue d'exécution workflow s'ouvre  
**And** un graphe visuel affiche Départ → étapes (actions) → Fin

**Given** la vue d'exécution d'un workflow  
**When** une étape est en cours  
**Then** cette étape est visuellement mise en évidence (bordure, couleur, animation légère)  
**And** les étapes terminées ont un indicateur de succès ou erreur  
**And** les étapes à venir sont grisées ou en attente

**Given** le graphe du workflow  
**When** l'exécution progresse  
**Then** les mises à jour sont reflétées en temps réel (WebSocket ou polling)  
**And** le chemin parcouru (étapes complétées) est clairement distingué

---

### Story 19.3 : Détail d'une étape de workflow — Timeline et logs au clic

**En tant que** DBA,  
**je veux** cliquer sur une étape du workflow pour afficher la timeline et les logs détaillés de cette action,  
**afin de** diagnostiquer ou suivre le détail d'une étape précise.

**Acceptance Criteria:**

**Given** la vue d'exécution d'un workflow avec plusieurs étapes  
**When** je clique sur une étape (terminée ou en cours)  
**Then** un panneau latéral ou une section s'ouvre avec le détail de cette action  
**And** la même vue que pour une action simple s'affiche : timeline des sous-étapes + logs en direct

**Given** le panneau détail d'une étape ouverte  
**When** l'étape produit des logs ou change de statut  
**Then** les logs et la timeline se mettent à jour en temps réel  
**And** je peux fermer le panneau et revenir à l'aperçu du workflow

**Given** je consulte une étape terminée  
**When** j'ouvre le détail  
**Then** la timeline complète et les logs historiques sont affichés  
**And** je peux naviguer entre les étapes du workflow sans perdre le contexte

---

### Story 19.4 : Intégration et remplacement du popup

**En tant que** équipe produit,  
**je veux** que le flux actuel (popup « action démarrée ») soit remplacé par l'ouverture automatique de la vue d'exécution,  
**afin de** offrir une expérience cohérente et immersive dès le lancement.

**Acceptance Criteria:**

**Given** le wizard d'exécution (ExecutionWizard)  
**When** l'utilisateur confirme l'exécution et que POST /api/v1/executions retourne 201  
**Then** le wizard se ferme  
**And** la vue d'exécution (drawer, modal ou route) s'ouvre automatiquement avec l'execution_id retourné  
**And** le popup « action démarrée » n'est plus affiché

**Given** la vue d'exécution ouverte  
**When** l'utilisateur clique sur « Fermer » ou « Retour »  
**Then** la vue se ferme  
**And** l'utilisateur est redirigé vers le catalogue, la liste des exécutions ou la page précédente  
**And** l'exécution continue en arrière-plan ; l'utilisateur peut la retrouver dans l'historique

**Given** l'utilisateur est sur la vue d'exécution  
**When** une erreur réseau ou une déconnexion survient  
**Then** un message approprié s'affiche  
**And** l'utilisateur peut réessayer ou fermer la vue

---

### Story 19.5 : Différenciation action vs workflow dans la page d'exécution

**En tant que** DBA,  
**je veux** que la page d'exécution indique clairement si je suis face à une **action simple** ou à un **workflow**,  
**afin de** comprendre immédiatement le type d'exécution et m'attendre au bon mode d'affichage (timeline simple vs graphe multi-étapes).

**Acceptance Criteria:**

**Given** je consulte la vue d'exécution d'une **action simple**  
**When** la page se charge  
**Then** un indicateur visuel distingue le type : badge, icône ou libellé « Action » (cohérent avec Story 18.2)  
**And** le nom de l'action et son type sont visibles (ex. titre ou en-tête)

**Given** je consulte la vue d'exécution d'un **workflow**  
**When** la page se charge  
**Then** un indicateur visuel distingue le type : badge, icône ou libellé « Workflow »  
**And** le nom du workflow est affiché  
**And** la distinction action vs workflow est immédiatement reconnaissable (icône dédiée, couleur, ou libellé)

**Given** je navigue depuis la liste des exécutions vers une exécution  
**When** j'arrive sur la page d'exécution  
**Then** le type (action ou workflow) est visible dès l'ouverture, avant de parcourir le détail

---

### Story 19.6 : Logs étape workflow dans le drawer — Analyse et correction

**En tant que** DBA,  
**je veux** accéder aux **logs détaillés de l'action exécutée** lorsqu'une étape de workflow est cliquée (drawer),  
**afin de** diagnostiquer le déroulement réel (timeline, sortie, erreurs) et non uniquement un résumé JSON.

**Contexte :** Actuellement, pour les workflows conteneur, chaque étape crée une exécution enfant ; le drawer charge cette exécution mais l'enfant n'a **aucune étape** en base, donc « Aucune étape à afficher » + résumé JSON uniquement. Les vrais logs ne sont pas accessibles.

**Acceptance Criteria:** Voir `_bmad-output/implementation-artifacts/19-6-logs-etape-workflow-drawer-analyse-correction.md`.

---

## Dépendances techniques

- **WebSocket** : `/ws/executions/{id}` (ou équivalent) pour les mises à jour temps réel — à vérifier dans l'architecture actuelle
- **API REST** : GET `/api/v1/executions/{id}/` et GET `/api/v1/executions/{id}/steps/` pour les données d'exécution et de logs
- **WorkflowBuilderCanvas** : réutilisation possible des composants visuels (nœuds, arêtes) pour l'aperçu workflow en lecture seule
- **ExecutionTimeline** : composant UX existant (mentionné dans l'UX spec) — à étendre ou réutiliser

---

## FRs couvertes

- **FR19** : Suivi statut exécution temps réel  
- **FR20** : Consultation logs plateforme  
- **FR21** : Logs techniques détaillés (DBA)

---

## Phase

Growth (Phase 2) — Amélioration UX post-MVP
