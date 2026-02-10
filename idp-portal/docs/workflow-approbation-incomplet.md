# Workflow d'Approbation — État Actuel (Incomplet)

## Contexte

Le workflow d'approbation pour les exécutions à fort impact en production a été défini dans la **Story 7.4**. Il permet aux DBA de valider ou refuser les exécutions avant leur lancement sur les environnements de production.

## Flux Attendu

```
1. Utilisateur soumet une exécution en production (impact_level=high/critical)
2. Statut → PENDING_APPROVAL (en attente de validation DBA)
3a. DBA approuve → PENDING_APPROVAL → RUNNING → COMPLETED/FAILED
3b. DBA refuse  → PENDING_APPROVAL → REJECTED (état terminal)
```

## État d'Implémentation

### Implémenté

| Composant | Détail | Story |
|-----------|--------|-------|
| Frontend — UI approbation | `PendingApprovalsList`, `usePendingApprovalsCount` | 7.4 |
| Backend — Modèle de données | Colonnes `approved_by`, `approved_at`, `approval_comment` (migration V030) | 7.4 |
| Backend — Machine à états | Transitions `PENDING_APPROVAL → RUNNING` et `PENDING_APPROVAL → REJECTED` autorisées | 7.4, 22.12 |
| Backend — Sécurité | Transition `PENDING_APPROVAL → SUBMITTED` **bloquée** (risque de contournement) | 22.12 |

### Manquant (Bloquant)

| Composant | Détail | Story cible |
|-----------|--------|-------------|
| Backend — Endpoint approbation | `POST /api/v1/executions/{id}/approve` | 7.4 (Task 3.1) |
| Backend — Endpoint rejet | `POST /api/v1/executions/{id}/reject` | 7.4 (Task 3.2) |

## Impact

Sans les endpoints `/approve` et `/reject`, le workflow d'approbation **n'est pas fonctionnel en production**. Les transitions `PENDING_APPROVAL → RUNNING` et `PENDING_APPROVAL → REJECTED` ne peuvent être déclenchées que par manipulation directe de la base de données ou via `update_status()` au niveau du code.

## Correction de Sécurité (Story 22.12)

La **Story 22.12** a corrigé un défaut de sécurité **HIGH-2** : la machine à états autorisait la transition `PENDING_APPROVAL → SUBMITTED`, ce qui permettait théoriquement de contourner le workflow d'approbation DBA. Cette transition est désormais **interdite**.

## Référence

- Story 7.4 : `_bmad-output/implementation-artifacts/7-4-workflow-approbation-pour-la-production.md`
- Story 22.12 : `_bmad-output/implementation-artifacts/22-12-corriger-high-2-transition-pending-approval-submitted.md`
- Code : `django_backend/executions/services.py` — méthode `update_status()`
