# Documentation des actions — clarification : où elle est gérée, où on y accède

**Contexte :** Demande de clarification sur la gestion et l’accès à la documentation des actions (notamment lors de l’exécution). Références : FR12, Story 3.4.

---

## 1. La documentation est déjà maintenue dans l’outil

La documentation détaillée d’une action est **stockée et éditée directement dans le portail** :

| Aspect | Détail |
|--------|--------|
| **Stockage** | Colonne `DOCUMENTATION_MD` (CLOB) de la table `ACTIONS_CATALOG` (migration V022, Story 3.4). |
| **Édition** | Admin > Catalogue (actions) > Création ou modification d’une action > champ **« Documentation (Markdown) »** dans le formulaire (textarea, Markdown, max 100 000 caractères). Présent dans `ActionForm` / `ActionWizard` (étape « Général » ou équivalent). |
| **Format** | Markdown (titres, listes, blocs de code, tableaux). Rendu côté frontend avec `react-markdown` + `remark-gfm` + `rehype-sanitize`. |

Il n’est **pas** nécessaire de maintenir un README externe pour cette documentation contextuelle : tout se fait dans l’outil, par action.

*(Le FR7 « auto-génération de la documentation à partir du readme de l’automatisation via IA » a été retiré / reporté ; la doc actuelle est saisie manuellement par DBOPS dans le formulaire.)*

---

## 2. Où l’utilisateur (DBA) accède à la documentation aujourd’hui

| Contexte | Accès à la documentation |
|----------|---------------------------|
| **Catalogue** | En ouvrant la fiche d’une action dans le **drawer** (clic sur une carte/liste), la section **« Documentation »** affiche le Markdown rendu. Si vide → « Aucune documentation disponible ». Composant : `ActionDrawerPreview`. |
| **Wizard d’exécution** | Aucun lien ni affichage de la documentation. L’utilisateur a déjà choisi l’action (depuis le drawer) ; s’il a fermé le drawer ou changé de vue, la doc n’est plus visible sans rouvrir la fiche au catalogue. |
| **Vue exécution (timeline, logs)** | Aucun lien vers la documentation de l’action exécutée. |

En résumé : **accès = catalogue → ouvrir la fiche de l’action → section Documentation dans le drawer.** Pendant l’exécution (wizard ou page d’exécution), il n’y a pas de « Voir la documentation de l’action » intégré.

---

## 3. Recommandation produit : accès à la doc depuis le flux d’exécution

Pour rendre l’usage plus pratique et cohérent avec « tout le contexte dans l’outil » (UX design) :

- **Wizard d’exécution** : ajouter un lien ou bouton discret du type **« Voir la documentation de l’action »** (ouvre un modal ou un panneau avec le même contenu Markdown que dans le drawer, ou un lien qui rouvre le drawer catalogue sur cette action).
- **Vue exécution (détail d’une exécution)** : dans l’en-tête ou la sidebar, ajouter **« Documentation de l’action »** (même contenu ou lien vers la fiche catalogue).

Cela peut être traité comme une **story d’amélioration UX** (ex. Epic 3 ou backlog) : « Accéder à la documentation de l’action depuis le wizard d’exécution et depuis la vue exécution ».

---

## 4. Synthèse

| Question | Réponse |
|----------|---------|
| Où est maintenue la documentation ? | **Dans l’outil** : champ « Documentation (Markdown) » en édition d’action (Admin), stocké en base dans `ACTIONS_CATALOG.DOCUMENTATION_MD`. |
| Comment y accéder ? | **Catalogue** → ouvrir la fiche de l’action (drawer) → section **Documentation** (Markdown rendu). |
| Référence pendant l’exécution ? | Aujourd’hui **non** : ni dans le wizard, ni dans la vue exécution. Une évolution possible est d’ajouter un accès explicite (lien / modal) à cette même doc depuis ces écrans. |

Si tu valides la direction « accès à la doc depuis le wizard et la vue exécution », on peut rédiger une story courte (titre + AC) pour le backlog.
