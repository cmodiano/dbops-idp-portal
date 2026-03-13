# Epic 79 : Notifications enrichies — Variables, CC, pièces jointes, webhook Teams par step

**Date :** 2026-03-13  
**Statut :** Draft  
**Périmètre :** `services/notification_service.py`, `executions/step_handlers/service_call_handler.py`, `frontend/.../NotificationTemplateEditor.tsx`, `frontend/.../ServiceCallStepConfig.tsx`

---

## 1. Contexte et problème

Les steps de notification (`send_email`, `send_teams`) dans les workflows permettent d'envoyer des messages après une action. Plusieurs limitations empêchent des cas d'usage courants :

| Besoin | Comportement actuel | Attendu |
|--------|---------------------|---------|
| **Variables dans le message** | VariablePicker existe (Story 63.4) mais le flux input_mapping → outputs d'étapes précédentes n'est pas pleinement exploité pour les notifications | Utiliser `{{ steps.<step_id>.<field> }}` dans titre, corps, destinataire — ex. : envoyer le rapport de patch généré par l'étape précédente |
| **CC email** | Non supporté | Champ CC avec support des variables |
| **Pièces jointes email** | Non supporté | Attacher des fichiers issus des outputs (artifacts, chemins) |
| **Webhook Teams par step** | Webhook global ou par intégration | Chaque step de notification peut envoyer vers un channel Teams différent (webhook spécifique par step) |

---

## 2. Cas d'usage principal

**Exemple :** Workflow appliquant un patch sur une machine, puis envoi du rapport par email.

1. Step `patch` (platform) : exécute un playbook, génère un output avec `report_path` ou `artifacts`
2. Step `notify` (service_call, send_email) : `input_mapping` récupère `steps.patch.output.report_path` → variable dans le corps du mail ; optionnellement attache le fichier

---

## 3. Objectifs de l'Epic

1. **Variables dans les steps notification** : Titre, corps, destinataire, CC — tous les champs supportent `{{ steps.<step_id>.<field> }}` via input_mapping (réutiliser le moteur existant Story 63-11).
2. **CC email** : champ CC avec support des variables (liste d'adresses séparées par virgule).
3. **Pièces jointes email** : sources depuis outputs d'étapes (artifacts, chemins) ; limite de taille configurable.
4. **Webhook Teams par step** : chaque step `send_teams` peut spécifier son propre webhook (URL ou référence Vault).

---

## 4. Stories

### Story 79.1 — Variables {{ steps.* }} dans les steps notification

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
S'assurer que les steps de notification (send_email, send_teams) utilisent pleinement le flux output_mapping → input_mapping. Les champs titre, corps, destinataire doivent accepter des variables `{{ steps.<step_id>.<field> }}` résolues au runtime via `_step_outputs`.

**Acceptance criteria :**
- AC1 : Step notification avec input_mapping référençant `steps.<step_id>.output.<field>` → résolution correcte au runtime (même moteur que les autres steps).
- AC2 : VariablePicker dans NotificationTemplateEditor suggère les outputs des steps disponibles (availableStepIds déjà passé).
- AC3 : Champ destinataire email supporte les variables (ex. `{{ steps.patch.output.contact_email }}`).
- AC4 : Tests : step send_email avec input_mapping vers output d’un step précédent → email reçu avec contenu résolu.

**Fichiers impactés :** `executions/step_handlers/service_call_handler.py`, `frontend/.../NotificationTemplateEditor.tsx`, `frontend/.../ServiceCallStepConfig.tsx`, tests.

---

### Story 79.2 — Champ CC pour les notifications email

**Priorité :** Moyenne  
**Effort estimé :** S

**Description :**  
Ajouter un champ CC optionnel dans les steps send_email. Le CC accepte des variables (ex. `{{ steps.patch.output.contact_email }}`) et une liste d'adresses séparées par virgule.

**Acceptance criteria :**
- AC1 : NotificationService.send_email accepte un paramètre `cc` optionnel (liste d'adresses).
- AC2 : Step config send_email : champ `cc` dans le template config (input_mapping).
- AC3 : NotificationTemplateEditor : champ CC avec VariablePicker.
- AC4 : Tests : send_email avec cc → django send_mail appelé avec cc.

**Fichiers impactés :** `services/notification_service.py`, `executions/step_handlers/service_call_handler.py`, `frontend/.../NotificationTemplateEditor.tsx`, output schema send_email.

---

### Story 79.3 — Pièces jointes pour les notifications email

**Priorité :** Moyenne  
**Effort estimé :** M

**Description :**  
Permettre d'attacher des fichiers aux emails. Les sources possibles : outputs d'étapes (artifacts, chemins de fichiers). Limite de taille configurable (ex. 10 Mo par mail).

**Acceptance criteria :**
- AC1 : NotificationService.send_email accepte un paramètre `attachments` optionnel (liste de tuples (filename, content) ou chemins).
- AC2 : Step config : champ `attachments` (liste de références) — ex. `steps.patch.output.artifacts[0].path` ou `steps.patch.output.report_path`.
- AC3 : Résolution des chemins/artifacts depuis le runtime (OutputExtractor, artifacts).
- AC4 : Limite de taille configurable (settings) ; dépassement → log + skip ou erreur.
- AC5 : Tests : send_email avec attachment → fichier joint correctement.

**Fichiers impactés :** `services/notification_service.py`, `executions/step_handlers/service_call_handler.py`, `frontend/.../NotificationTemplateEditor.tsx`, output schema.

---

### Story 79.4 — Webhook Teams spécifique par step de notification

**Priorité :** Haute  
**Effort estimé :** S

**Description :**  
Chaque step send_teams peut spécifier son propre webhook (URL ou référence Vault). Un workflow peut ainsi envoyer un message à un channel et un autre à un channel différent.

**Acceptance criteria :**
- AC1 : Step config send_teams : champ `webhook_url` (ou `webhook_url_ref`) dans le template config — pas de webhook global par défaut si non fourni.
- AC2 : Le webhook est résolu au runtime (variable ou valeur statique) ; support des variables `{{ steps.* }}` si pertinent.
- AC3 : NotificationTemplateEditor : champ webhook_url avec support VariablePicker ou saisie directe.
- AC4 : Tests : deux steps send_teams avec webhooks différents → deux messages envoyés vers les bons channels.

**Fichiers impactés :** `executions/step_handlers/service_call_handler.py`, `frontend/.../NotificationTemplateEditor.tsx`, output schema send_teams.

---

## 5. Dépendances et ordre de réalisation

| Story | Dépendances | Ordre suggéré |
|-------|-------------|---------------|
| 79.1 | Story 63-11 (syntaxe variables), 63-12 (input_mapping platform) | 1 |
| 79.2 | 79.1 (contexte variables) | 2 |
| 79.4 | 79.1 (contexte step config) | 2 (en parallèle avec 79.2) |
| 79.3 | 79.1 (contexte outputs/artifacts) | 3 |

---

## 6. Références

- `services/notification_service.py` — send_email, send_teams
- `executions/step_handlers/service_call_handler.py` — résolution params, appel notification
- `frontend/.../NotificationTemplateEditor.tsx` — UI templates send_email, send_teams
- `frontend/.../ServiceCallStepConfig.tsx` — intégration NotificationTemplateEditor
- Story 63-11 — doc syntaxe `{{ steps.<step_id>.<field> }}`
- Story 63-12 — input/output mapping platform steps
- Story 77-4 — extraction outputs/artifacts child executions
