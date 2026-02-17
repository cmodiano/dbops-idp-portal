# Builder Visuel de Workflows

Documentation du mode visuel du builder de workflows (React Flow).

## Utilisation du mode visuel

### Taille du canvas

- **Modale** : 1400px de largeur en mode visuel (640px en mode liste ou action)
- **Canvas** : 700px de hauteur minimum pour visualiser des workflows avec 5+ actions
- La modale est centrée et responsive (adapte si l'écran est < 1440px)

### Blocs Départ et Fin

- Les blocs **Départ** (Start) et **Fin** (End) sont **déplaçables** sur le canvas
- Ils peuvent être repositionnés librement pour organiser la disposition
- **Suppression impossible** : les blocs Départ/Fin ne peuvent pas être supprimés
- **Visuels uniquement** : les blocs Start/End ne sont **pas sauvegardés** dans les `WorkflowStep[]` du backend

### Connexions manuelles

- Les connexions entre blocs sont **créées manuellement** par l'utilisateur
- Il n'y a **pas de connexion automatique** de Départ vers la première action ou d'une action vers Fin
- L'utilisateur connecte les blocs en glissant depuis les handles de sortie (succès vert, erreur rouge) vers les handles d'entrée
- La validation du workflow accepte un bloc Départ sans connexion sortante et un bloc Fin sans connexion entrante

### Nom d'action dans les blocs

- Chaque bloc workflow affiche le **vrai nom de l'action** référencée (ex. "Apply Oracle Patch")
- Le nom est récupéré depuis le backend via le champ `action_name` dans `workflow_steps`
- Si l'action référencée est supprimée ou inaccessible, le fallback affiche "Action #ID"
- Si un nom custom est défini (`name`), il est affiché en priorité avec le nom d'action en sous-titre
- Les noms longs sont tronqués avec ellipsis (max ~200px)

## Architecture technique

### Composants

| Composant | Rôle |
|-----------|------|
| `WorkflowBuilderCanvas.tsx` | Canvas React Flow avec palette, toolbar, validation |
| `WorkflowStepNode.tsx` | Node custom affichant nom, engine, retry, validation |
| `StartNode.tsx` | Bloc visuel Départ (draggable, non supprimable) |
| `EndNode.tsx` | Bloc visuel Fin (draggable, non supprimable) |
| `ActionWizard.tsx` | Modale conteneur (1400px en mode visuel) |

### Fonctions de conversion

- `workflowStepsToReactFlow(steps)` : Convertit `WorkflowStep[]` en nodes/edges React Flow
- `reactFlowToWorkflowSteps(nodes, edges)` : Convertit nodes/edges en `WorkflowStep[]` (exclut Start/End)
- `validateWorkflowGraph(nodes, edges)` : Valide le graphe (orphelins, cycles, sorties manquantes)

### Backend

Le champ `action_name` est fourni par le serializer Django (`ActionSerializer.get_workflow_steps()`) qui résout les noms des actions référencées en une seule requête batch (pas de N+1).
