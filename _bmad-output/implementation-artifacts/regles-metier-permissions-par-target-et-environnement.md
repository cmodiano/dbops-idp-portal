# Règles métier : Permissions par target et environnement

**Statut** : Spécification produit (backlog)  
**Contexte** : Refonte du modèle de privilèges — l'environnement est une propriété du **target** (inventaire), pas de l'action.

---

## 1. Principe

- **Une action** = un type d’opération (ex. « Exécuter playbook », « Créer PDB »). Il n’existe qu’**une seule** définition d’action par type, sans duplication par environnement.
- **L’environnement** est porté par l’élément d’**inventaire** (serveur, base, groupe Ansible, etc.) : chaque target est associé à un environnement (dev, certif, prod).
- **Les privilèges** ne lient pas « action ↔ environnement », mais « utilisateur/profil ↔ environnements autorisés » et, optionnellement, « utilisateur/profil ↔ restriction sur les targets » (pattern ou liste). Au moment de l’exécution, l’utilisateur ne peut choisir que des **targets** pour lesquels il a le droit (dérivé de l’env + restriction éventuelle).

---

## 2. Règles métier

### RM1 — Source de l’environnement

- L’environnement (dev, certif, prod, etc.) est une propriété des **targets** dans l’inventaire.
- Une action n’est pas associée à un environnement : c’est le **target** ciblé qui détermine l’environnement de l’exécution.

### RM2 — Droits par environnement

- Un profil (ou l’utilisateur via ses profils) dispose de **droits par environnement** (ex. droit en dev, en certif).
- Un utilisateur ayant le droit sur un environnement donné peut, par défaut, **sélectionner tous les targets de cet environnement** (tous les serveurs de l’inventaire rattachés à cet env).

### RM3 — Restriction optionnelle par target (pattern ou liste)

- Le profil peut définir une **restriction cible** optionnelle :
  - **Pattern** : ex. `web-*`, `*-dev` → l’utilisateur ne voit que les targets dont l’identifiant (ou le nom) matche le pattern, **dans les environnements où il a le droit**.
  - **Liste explicite** : ex. `[srv-app-01, srv-app-02]` → l’utilisateur ne voit que ces targets, **s’ils appartiennent à un environnement autorisé**.
- Si aucune restriction n’est définie (ni pattern ni liste), l’utilisateur voit **tous les targets** des environnements auxquels il a droit.

### RM4 — Filtrage des targets proposés

- Les targets proposés à l’utilisateur dans le wizard d’exécution sont l’**intersection** :
  1. Targets appartenant à un **environnement** pour lequel l’utilisateur a le droit ;
  2. Et, si une restriction target est définie (pattern ou liste), targets qui **respectent** cette restriction.
- Un target d’un environnement non autorisé ne doit **jamais** apparaître, même s’il matche un pattern ou figure dans une liste.

### RM5 — Une action, plusieurs environnements

- Une même action peut être exécutée sur des targets de différents environnements selon les droits du profil (ex. dev + certif). L’utilisateur choisit **une** action, puis sélectionne un ou plusieurs **targets** parmi ceux qui lui sont autorisés (tous envs confondus, selon RM4).

### RM6 — Cumul multi‑profils

- Si l’utilisateur a plusieurs profils, les droits (environnements + restrictions targets) sont **cumulés** : il voit l’union des targets autorisés par chaque profil (sans dépasser les règles ci‑dessus).

---

## 3. Cas d’usage résumés

| Profil | Droits env | Restriction target | Résultat |
|--------|------------|--------------------|----------|
| A | dev | Aucune | Tous les serveurs de l’env dev |
| B | dev | Pattern `web-*` | Serveurs dev dont l’id/name matche `web-*` |
| C | dev | Liste [srv1, srv2] | Uniquement srv1 et srv2 (s’ils sont en dev) |
| D | dev + certif | Liste [srv1] | srv1 s’il est en dev ou certif |
| E | prod | Aucune | Tous les serveurs prod |

---

## 4. Critères d’acceptation (pour implémentation)

### AC1 — Inventaire et environnement

- **Given** l’inventaire (serveurs / targets), **when** chaque target est associé à un environnement (dev, certif, prod), **then** cette association est la source de vérité pour déterminer l’environnement d’une exécution ciblant ce target.

### AC2 — Permissions par environnement (profil)

- **Given** un DBOPS configure un profil, **when** il définit les environnements autorisés (ex. [DEV, CERTIF]), **then** l’utilisateur ayant ce profil ne peut sélectionner que des targets dont l’environnement est dans cette liste.

### AC3 — Restriction par pattern (profil)

- **Given** un profil a une restriction target de type **pattern** (ex. `web-*`), **when** l’utilisateur ouvre le wizard d’exécution pour une action, **then** seuls les targets des environnements autorisés **et** dont l’identifiant matche le pattern sont proposés.

### AC4 — Restriction par liste explicite (profil)

- **Given** un profil a une restriction target de type **liste** (ex. [srv1, srv2]), **when** l’utilisateur ouvre le wizard d’exécution, **then** seuls les targets de cette liste qui appartiennent à un environnement autorisé sont proposés.

### AC5 — Pas de duplication d’actions par environnement

- **Given** le catalogue d’actions, **then** une action n’existe qu’une seule fois (pas d’instance « action X – dev », « action X – prod »). L’utilisateur sélectionne l’action puis les targets autorisés.

### AC6 — Validation backend

- **Given** une requête d’exécution (action + target(s)), **when** le backend valide les permissions, **then** il vérifie que le target appartient à l’inventaire, qu’il est dans un environnement autorisé pour l’utilisateur, et qu’il respecte les restrictions target (pattern/liste) du profil. Sinon → 403.

### AC7 — Cumul multi‑profils

- **Given** un utilisateur a plusieurs profils avec des environnements et/ou restrictions targets différents, **when** les targets autorisés sont calculés, **then** sont proposés tous les targets autorisés par au moins un de ses profils (union), en respectant RM4.

---

## 5. Source inventaire : intégration et mode dev

- **Inventaire comme intégration** : La source des targets (serveurs, bases, groupes) est une **intégration** (table INTEGRATIONS). Types prévus : **`inventory`** (API externe, base_url + credential_ref) ou **`inventory_db`** (lecture depuis schéma BD, ex. DBOPS_INVENTORY ; config JSON possible).
- **Fallback dev** : Si aucune intégration de type inventaire n'est configurée (ex. dev sans API), le backend utilise le schéma **DBOPS_INVENTORY** (accès via synonyme Oracle).
- **Contrat** : Chaque target expose au minimum : identifiant (ou nom), environnement (dev, certif, prod).

---

## 6. Impacts / dépendances

- **Inventaire** : Les targets doivent exposer au minimum : identifiant (ou nom), environnement. Les APIs d’inventaire et de liste des targets pour le wizard doivent être filtrées selon les règles ci‑dessus.
- **Profils** : Les permissions « environnements autorisés » et « restriction targets » (pattern / liste) sont portées par le **profil** (tables / champs existants ou à adapter : PROFILE_ACTION_PERMISSIONS, PROFILE_TARGET_PERMISSIONS).
- **RBAC / exécution** : Le service RBAC et le flux d’exécution doivent utiliser l’environnement **dérivé du target** (et non plus d’une association action–environnement) pour l’évaluation des droits et l’audit.
- **Refactoring** : Si aujourd’hui des « actions par environnement » existent (duplication), une story de refactoring devra les remplacer par une action unique + filtrage des targets par env + permissions profil.

---

## 7. Références

- Stories existantes : 2.10 (permissions actions par profil), 2.11 (permissions targets par profil), 2.14 (refactoring ancien RBAC), 7.3 (RBAC granulaire).
- Ce document formalise le **modèle cible** à atteindre pour aligner implémentation et produit.
