# Epic 36 : Vue Exécutions partagée et mise à jour du statut

**En tant que** utilisateur du portail (DBA ou autre),  
**je veux** une vue « Exécutions » partagée où je vois les exécutions auxquelles j’ai accès (y compris lancées par d’autres) et où la liste se met à jour quand un statut change,  
**afin de** suivre l’activité collective et voir immédiatement le résultat de mes propres lancements.

---

## Contexte

La vue « Exécutions » doit être **partagée** : une action lancée par l’utilisateur A doit être visible par l’utilisateur B (sous réserve des droits RBAC). La liste doit **se mettre à jour** lorsque le statut d’une exécution change, avec une expérience différenciée :

- **Pour l’utilisateur qui a lancé l’action** : mise à jour **immédiate** du statut (temps réel ou quasi).
- **Pour les autres** : mise à jour via **polling régulier** (quelques secondes).

**Spec détaillée :** `_bmad-output/planning-artifacts/spec-vue-executions-partagee-mise-a-jour-statut.md`

---

## Portée (scope)

- Onglet **« Toutes les exécutions »** : liste filtrée par droits RBAC (actions / cibles / environnements), avec colonne **« Utilisateur »** (initiateur).
- **Mise à jour immédiate** pour l’acteur (celui qui a lancé) : WebSocket, SSE ou polling court dédié à *son* exécution en cours.
- **Mise à jour par polling** pour la vue partagée (tous les utilisateurs) : intervalle régulier (ex. 5–10 s) pour rafraîchir les statuts.

---

## Definition of Done (epic)

- [ ] La liste « Toutes les exécutions » affiche toutes les exécutions auxquelles l’utilisateur a accès (RBAC), y compris celles lancées par d’autres.
- [ ] La colonne « Utilisateur » (ou équivalent) identifie qui a lancé chaque exécution.
- [ ] L’utilisateur qui a lancé une exécution voit son statut se mettre à jour immédiatement (sans rechargement manuel).
- [ ] Les autres utilisateurs voient la liste se mettre à jour via un rafraîchissement automatique régulier (ordre de grandeur : quelques secondes).

---

## Stories

| # | Story | Objectif |
|---|-------|----------|
| 36.1 | Vue partagée — Liste et droits RBAC | S’assurer que « Toutes les exécutions » est filtrée par RBAC et affiche l’initiateur |
| 36.2 | Mise à jour immédiate pour l’acteur | L’utilisateur qui lance voit le statut en temps réel |
| 36.3 | Polling pour les observateurs | Les autres voient la liste se rafraîchir régulièrement |

---

## Détail des stories

### Story 36.1 : Vue partagée — Liste et droits RBAC

**En tant que** utilisateur du portail,  
**je veux** que l’onglet « Toutes les exécutions » affiche toutes les exécutions auxquelles j’ai accès (y compris lancées par d’autres utilisateurs),  
**afin de** voir l’activité collective sur les actions et environnements que je suis autorisé à consulter.

**Contexte :** La règle d’accès est la même que pour lancer une action (RBAC : actions, cibles, environnements). La liste ne doit pas se limiter aux exécutions de l’utilisateur connecté.

**Critères d’acceptation :**

- **Given** je suis connecté et j’ai accès à certaines actions / cibles / environnements  
**When** j’ouvre l’onglet « Toutes les exécutions »  
**Then** je vois toutes les exécutions éligibles selon mes droits (y compris celles lancées par d’autres utilisateurs)  
**And** je ne vois pas les exécutions sur des actions / cibles / environnements auxquels je n’ai pas accès

- **Given** la liste des exécutions  
**When** j’affiche le tableau  
**Then** une colonne « Utilisateur » (ou équivalent) indique qui a lancé chaque exécution  
**And** je peux distinguer « Mes exécutions » (onglet dédié ou filtre) de « Toutes les exécutions »

- **Given** l’API ou le backend qui fournit la liste  
**When** un utilisateur B interroge la liste  
**Then** le filtre appliqué est cohérent avec les permissions RBAC (même logique que pour le catalogue / lancement d’action)  
**And** les exécutions lancées par A sont incluses si B a les droits sur l’action / cible / environnement concerné

---

### Story 36.2 : Mise à jour immédiate pour l’acteur

**En tant qu’**utilisateur qui viens de lancer une exécution,  
**je veux** voir le statut de cette exécution se mettre à jour **immédiatement** (soumis → en cours → terminé / échec),  
**afin de** savoir sans attendre si mon action a démarré et quel est son résultat.

**Contexte :** Pas de rechargement manuel. Mise à jour par push (WebSocket, SSE) ou par polling très court tant que *mon* exécution est en cours. L’objectif est un feedback immédiat pour l’acteur.

**Critères d’acceptation :**

- **Given** je viens de lancer une exécution (wizard ou catalogue)  
**When** je reste sur la vue Exécutions (liste ou détail)  
**Then** le statut de *mon* exécution se met à jour sans que j’aie à recharger la page  
**And** le délai perçu est immédiat (ordre de grandeur : &lt; 2–3 s après réception du callback côté backend, ou équivalent)

- **Given** mon exécution est « en cours »  
**When** le backend reçoit un changement de statut (étape, terminé, échec)  
**Then** l’UI reflète ce changement dès que le canal temps réel (WebSocket/SSE) ou le prochain poll dédié est reçu  
**And** si une vue détail existe (ex. Epic 19), elle se met à jour aussi pour cette exécution

- **Given** je n’ai pas lancé l’exécution affichée  
**When** je consulte la liste  
**Then** la mise à jour pour cette exécution peut suivre le mécanisme « observateur » (Story 36.3), pas obligatoirement temps réel

**Notes techniques :** Réutilisation du WebSocket existant `/ws/executions/{id}` ou équivalent pour l’exécution en cours de l’utilisateur connecté, ou polling court (ex. 2–3 s) limité à cette exécution tant qu’elle est en cours.

---

### Story 36.3 : Polling pour les observateurs

**En tant qu’**utilisateur consultant la liste « Toutes les exécutions » (sans avoir lancé une exécution en cours),  
**je veux** que la liste se rafraîchisse **régulièrement** pour refléter les changements de statut (ex. terminé, échec),  
**afin de** voir l’activité des autres et l’état à jour sans recharger la page.

**Contexte :** Un délai de quelques secondes est acceptable. Pas besoin de temps réel strict pour les observateurs ; un polling à intervalle fixe (ex. 5–10 s) suffit.

**Critères d’acceptation :**

- **Given** je suis sur la vue « Toutes les exécutions » (ou « Mes exécutions »)  
**When** une exécution (lancée par moi ou par un autre) change de statut côté backend  
**Then** la liste se met à jour automatiquement après au plus un intervalle de polling (ex. 5–10 s)  
**And** je n’ai pas besoin de recharger la page manuellement

- **Given** le polling est actif  
**When** la page est visible (onglet actif ou visible)  
**Then** les requêtes de rafraîchissement sont envoyées à l’intervalle défini  
**And** (optionnel) le polling peut être ralenti ou suspendu quand l’onglet est en arrière-plan pour limiter la charge

- **Given** des exécutions « en cours » sont présentes dans la liste  
**When** je suis observateur (je n’ai pas lancé ces exécutions)  
**Then** je vois leur statut passer à « terminé » ou « échec » après le prochain cycle de polling  
**And** la colonne Statut et les indicateurs visuels (badge, couleur) reflètent l’état à jour

**Notes techniques :** Endpoint existant type GET `/api/v1/executions` (avec filtres) ; intervalle configurable (ex. 5 s ou 10 s). Éviter de cumuler un polling global trop agressif avec le mécanisme temps réel de la Story 36.2 (ex. ne pas poller la liste entière à 2 s pour tout le monde).

---

## Dépendances et liens

- **Epic 19** (Vue d’exécution temps réel) : vue détail d’une exécution ; la Story 36.2 peut s’appuyer sur le même canal temps réel pour l’acteur.
- **RBAC / Profils** : même modèle de droits que pour le catalogue et le lancement d’action (FR26, FR25x).
- **NFR3** : « La mise à jour du statut d’exécution en temps réel se rafraîchit avec un délai maximum de 5 secondes » — ici on renforce pour l’acteur (immédiat) et on accepte quelques secondes pour les observateurs.

---

## Références

- `_bmad-output/planning-artifacts/spec-vue-executions-partagee-mise-a-jour-statut.md`
- Epic 19 : UX — Vue d’exécution temps réel
