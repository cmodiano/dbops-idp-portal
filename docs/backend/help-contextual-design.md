# Aide contextuelle — Tooltip (court) + Popover Markdown (sections complexes)

## Objectif

Offrir dans les fenêtres de configuration (formulaires action, intégrations, gates, etc.) :
- un **tooltip** pour un texte court (contexte rapide au survol) ;
- un **popover** avec rendu **Markdown** pour les sections plus complexes (doc détaillée au clic).

La documentation est stockée côté **backend** (fichiers MD dans le repo), maintenable dans git, et exposée via une API.

---

## Backend

### Stockage des fichiers MD

- **Répertoire :** `docs/backend/help/` (ou dédié type `help/content/` dans une app `help`).
- **Un fichier par sujet** (topic), nommé par `topic_id` : ex. `action-form-integration.md`, `action-form-changement-servicenow.md`, `gates-config.md`.
- **Format recommandé :** Markdown avec **frontmatter YAML** optionnel pour le texte court (tooltip) :

```yaml
---
short: "Choisissez l'intégration qui exécutera cette action. Seules les intégrations configurées dans Admin > Intégrations sont proposées."
---
# Intégration d'exécution

Cette section permet d'associer l'action à une **intégration** (instance de plateforme)...
```

- Si pas de frontmatter : le backend peut utiliser la première ligne ou les N premiers caractères du corps comme `short`, le reste comme `markdown`.

### Mapping topic_id → fichier

- **Config Python** (ex. dans l’app `help` ou `core`) : dictionnaire ou liste de topics autorisés qui mappe `topic_id` → nom de fichier (sans chemin), ex. `action-form-integration` → `action-form-integration.md`.
- Sécurité : n’autoriser que des `topic_id` figurant dans cette config (pas de path traversal). Fichiers lus depuis le répertoire dédié uniquement.

### API

- **GET** `/api/v1/help/<topic_id>/`
- **Réponse 200 :** JSON
  - `topic_id`: str
  - `short`: str — texte court pour tooltip (une phrase ou courte phrase, pas de MD)
  - `markdown`: str — contenu Markdown complet pour le popover
- **404** si topic inconnu ou fichier absent.
- **Authentification :** même politique que le reste de l’API (ex. `IsAuthenticated`). Pas besoin d’exposer l’aide en public si les configs sont réservées aux utilisateurs connectés.

### Implémentation backend (résumé)

- Vue (DRF APIView ou équivalent) qui :
  1. Valide `topic_id` contre la liste autorisée ;
  2. Construit le chemin vers le fichier `docs/help/<topic_id>.md` (ou depuis le mapping) ;
  3. Lit le fichier, parse le frontmatter (ex. avec `python-frontmatter` ou regex simple) ;
  4. Retourne `{ "topic_id": "...", "short": "...", "markdown": "..." }`.
- Enregistrement de la route sous `api/v1/help/<topic_id>/` (nouvelle app `help` ou sous `core`).

---

## Frontend

### Récupération du contenu

- **Service :** `getHelpContent(topicId: string): Promise<{ short: string; markdown: string }>` qui appelle `GET /api/v1/help/<topicId>/`.
- **Cache optionnel :** mémoriser par `topicId` en mémoire (ou React Query) pour éviter des appels répétés dans la même session.

### Affichage

- **Tooltip (contexte court) :**
  - À côté du label de section (ou d’un champ), une icône **InfoCircleOutlined** (ou **QuestionCircleOutlined**) avec un **Tooltip** Ant Design dont le contenu est `short`.
  - Au survol : affichage du texte court uniquement (pas de rendu Markdown dans le tooltip).

- **Popover (doc complète) :**
  - Même icône (ou un lien « Aide » / « En savoir plus ») qui, **au clic**, ouvre un **Popover** Ant Design.
  - Contenu du Popover : rendu du champ `markdown` avec une librairie **Markdown** (ex. `react-markdown`) pour afficher titres, listes, gras, etc.
  - Dimensions : largeur max raisonnable (ex. 400px), hauteur max avec scroll si nécessaire.

### Composant réutilisable

- **SectionHelp** (ou **HelpIcon**) : prend en props `topicId`, `mode?: 'tooltip' | 'popover' | 'both'`.
  - `tooltip` : uniquement icône + Tooltip (short).
  - `popover` : icône + au clic Popover (markdown).
  - `both` (défaut suggéré) : Tooltip au survol (short) + Popover au clic (markdown).
- Accessibilité : `aria-label` sur l’icône (ex. « Aide pour cette section »), et le Popover focusable / fermable au Escape.

### Intégration dans les écrans

- Dans **ActionForm** / **ActionWizard** : à côté des labels « Intégration », « Changement ServiceNow par environnement », « Règles métier », etc., ajouter `<SectionHelp topicId="action-form-integration" />` (ou mode adapté).
- Topic IDs à définir en cohérence avec les fichiers MD et le mapping backend (ex. `action-form-integration`, `action-form-changement-servicenow`, `action-form-gates`, `integration-form`).

---

## Récapitulatif

| Élément            | Rôle |
|--------------------|------|
| **Fichiers MD**    | Dans `docs/backend/help/*.md`, un par topic, avec frontmatter `short` optionnel. |
| **API**            | `GET /api/v1/help/<topic_id>/` → `{ short, markdown }`. |
| **Tooltip**        | Texte court (`short`) au survol de l’icône. |
| **Popover**        | Markdown rendu (`markdown`) au clic sur l’icône (ou lien « Aide »). |
| **Mapping**       | Côté backend : liste des topic_id autorisés → nom de fichier. Côté frontend : même topic_id passé aux composants. |

Cela permet de maintenir la doc en **git** (fichiers MD), de la servir de façon **centralisée** par le backend, et d’afficher soit un **contexte court** (tooltip) soit une **doc structurée** (popover Markdown) selon le besoin de chaque section.
