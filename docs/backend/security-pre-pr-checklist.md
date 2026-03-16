# Self-Checklist Sécurité — Pré-PR

> **Objectif :** Vérifier les points de sécurité critiques avant de soumettre une PR.
> **Usage :** Parcourir cette liste pour chaque PR contenant du code backend Django.

## Validation des Inputs

- [ ] Tous les paramètres utilisateur passent par un serializer DRF
- [ ] Les enums utilisent `ChoiceField` (pas de strings libres)
- [ ] Les IDs sont validés (entier positif, existence en BD)
- [ ] Les champs JSON sont validés avec un schéma si critique
- [ ] Les uploads sont validés (MIME type, taille, contenu)

## Authentification & Autorisation

- [ ] Endpoint protégé par `IsAuthenticated` (minimum)
- [ ] Permission RBAC appropriée (`DBOPSProfilePermission` pour admin)
- [ ] Tests 401 et 403 présents
- [ ] Cache RBAC invalidé si modification permissions/profils
- [ ] Pas de contournement possible de l'authentification

## Données Sensibles

- [ ] Pas de secrets dans les logs (tokens, passwords, clés API)
- [ ] Pas de données personnelles dans les logs (sauf user_id)
- [ ] Pas de credentials dans le code source (utiliser Vault)
- [ ] Réponses 500 ne révèlent pas de détails internes

## Requêtes Base de Données

- [ ] Pas de SQL brut avec interpolation de strings
- [ ] Bind variables (`:param`) si SQL brut nécessaire
- [ ] Pas de N+1 queries (`select_related` / `prefetch_related`)
- [ ] Types audit via `AuditActionType` enum (pas de strings)

## Audit Trail

- [ ] Opérations CRUD logguées via `AuditService`
- [ ] `correlation_id` propagé
- [ ] `entity_type` et `entity_id` corrects

---

**Références :**
- [Patterns sécurité détaillés](common-pitfalls.md)
- [Checklist endpoint DRF](../standards/endpoint-checklist.md)
