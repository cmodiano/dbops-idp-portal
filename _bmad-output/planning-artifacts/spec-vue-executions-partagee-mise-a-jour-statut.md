# Spec : Vue Exécutions partagée et mise à jour du statut

**Contexte :** Vue « Exécutions » du portail DBOPS (liste des exécutions avec onglets « Toutes les exécutions » / « Mes exécutions »).

**Date :** 2026-02-23  
**Référence :** Discussion produit — Epic 36

---

## 1. Exigences utilisateur

### 1.1 Vue partagée (visibilité)

- **Tous les utilisateurs** voient les exécutions **auxquelles ils ont accès** (même règle que pour lancer une action : RBAC par action, cible, environnement).
- Une exécution lancée par **l’utilisateur A** doit être **visible par l’utilisateur B** dès lors que B a les droits sur cette action / cible / environnement.
- La liste « **Toutes les exécutions** » affiche donc l’ensemble des exécutions éligibles (pas seulement celles de l’utilisateur connecté).
- La colonne **« Utilisateur »** identifie qui a lancé chaque exécution.

### 1.2 Mise à jour de la liste lorsque le statut change

- La liste des exécutions doit **se mettre à jour** quand une action change de statut (soumis → en cours → terminé / échec), **sans rechargement manuel** de la page.
- Comportement différencié selon le rôle par rapport à l’exécution :
  - **Utilisateur qui a lancé l’action (acteur)** : il doit voir le changement de statut **immédiatement** (feedback temps réel).
  - **Autres utilisateurs (observateurs)** : mise à jour via un **polling régulier** (quelques secondes) ; un délai de quelques secondes est acceptable.

---

## 2. Critères d’acceptation (résumé)

| Contexte | Comportement attendu |
|----------|----------------------|
| **Vue partagée** | Chaque utilisateur voit toutes les exécutions auxquelles il a accès (RBAC), y compris celles lancées par d’autres ; la colonne « Utilisateur » affiche l’initiateur. |
| **Acteur (celui qui lance)** | Voit le statut de *son* exécution se mettre à jour **immédiatement** (push / WebSocket / SSE ou polling très court tant que l’exécution est en cours). |
| **Observateurs** | Voient la liste (et les changements de statut) se mettre à jour via un **polling régulier** (ex. intervalle de l’ordre de 5–10 s). |

---

## 3. Référence

- **Epic 36** : Vue Exécutions partagée et mise à jour du statut (stories 36.1–36.3).
- **Epic 19** : UX Vue d’exécution temps réel (vue détail d’une exécution ; complémentaire).
