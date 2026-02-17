# Epic 22 : Amélioration Qualité du Code — Points d'amélioration restants

**En tant que** équipe de développement,  
**je veux** traiter les points d'amélioration identifiés dans l'évaluation de qualité du code du 8 février 2026,  
**afin de** améliorer la maintenabilité, réduire la dette technique, corriger les défauts critiques de conception et atteindre un score de qualité A (actuellement A-).

---

## Contexte

L'évaluation de qualité du code du 8 février 2026 a identifié :
- **Score global : A- (Très Bon)** — en progression depuis B+
- **19 défauts de conception** : 3 critiques, 7 haute sévérité, 9 moyenne sévérité
- **Points d'amélioration** : fichiers volumineux, broad exception catches, Error Boundary manquant, etc.

Cette epic regroupe les actions correctives prioritaires pour atteindre un score A et corriger les défauts critiques.

---

## Portée (scope)

### Catégories identifiées

1. **Défauts CRITIQUES** — Bug RBAC masqué, fail-open permissions, race condition token refresh
2. **Défauts HAUTE sévérité** — Machine à états, pagination, throttling, WebSocket auth, double-submit, closures
3. **Défauts MOYENNE sévérité** — Timezone, cache, localStorage, types manquants, validation, reconnexion WS
4. **Refactoring fichiers volumineux** — Backend (executions/views.py 1914 LOC) et Frontend (types/api.ts 1021 LOC, AdminPage.tsx 845 LOC)
5. **Améliorations qualité** — Error Boundary React, mypy bloquant, containerisation production, API documentation

---

## Stories proposées

### Story 22.1 : Corriger CRIT-1 — Méthode manquante `get_profiles_by_ad_groups` dans RBAC

**En tant que** développeur,  
**je veux** corriger le bug où `DBOPSProfilePermission` appelle une méthode inexistante `get_profiles_by_ad_groups()`,  
**afin de** restaurer l'authentification par groupes AD et éviter le fallback superuser non sécurisé.

**Source :** Section 9.1 CRIT-1 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** un utilisateur avec groupes AD configurés
- **When** `DBOPSProfilePermission.has_permission()` est appelé
- **Then** la méthode `get_profiles_by_ad_groups()` existe dans `ProfileService` ou l'appel est corrigé pour utiliser `Profile.objects.find_by_ad_groups()`
- **And** l'`AttributeError` n'est plus masqué par le broad catch
- **And** les utilisateurs avec groupes AD peuvent accéder aux fonctionnalités protégées
- **And** un test unitaire vérifie que l'authentification par groupes AD fonctionne correctement

**Fichiers concernés :**
- `core/permissions.py:48`
- `profiles/services.py` (ajout méthode si nécessaire)

---

### Story 22.2 : Corriger CRIT-2 — Fallback superuser fail-open dans permissions

**En tant que** développeur,  
**je veux** revoir l'architecture de `DBOPSProfilePermission` pour supprimer ou documenter explicitement le fallback superuser,  
**afin de** respecter le principe du moindre privilège et éviter l'escalade de privilèges.

**Source :** Section 9.1 CRIT-2 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** un superuser Django sans profil DBOPS configuré
- **When** `DBOPSProfilePermission.has_permission()` est appelé
- **Then** l'accès est refusé sauf si explicitement autorisé pour le développement (documenté)
- **And** le check superuser est déplacé avant les checks AD (pour dev) ou supprimé
- **And** un profil DBOPS explicite est requis même pour les superusers en production
- **And** la logique est documentée dans le code avec commentaires explicites

**Fichiers concernés :**
- `core/permissions.py:61-63`

---

### Story 22.3 : Corriger CRIT-3 — Race condition sur token refresh frontend

**En tant que** développeur,  
**je veux** implémenter un mutex sur le token refresh pour éviter les appels multiples concurrents,  
**afin de** éviter l'instabilité d'authentification en charge et la saturation du endpoint de refresh.

**Source :** Section 9.1 CRIT-3 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** plusieurs requêtes reçoivent un 401 simultanément
- **When** `_onRefreshNeeded()` est appelé
- **Then** seule la première requête lance le refresh, les autres attendent la même Promise
- **And** un pattern "refresh promise queue" est implémenté
- **And** les requêtes en attente reprennent automatiquement après le refresh réussi
- **And** un test unitaire vérifie le comportement avec requêtes concurrentes

**Fichiers concernés :**
- `frontend/src/services/api_client.ts:65-71`

---

### Story 22.4 : Corriger HIGH-3 — Gestion HTTP 429 (throttling) côté frontend

**En tant que** développeur,  
**je veux** gérer correctement les réponses HTTP 429 avec retry et backoff,  
**afin de** améliorer l'expérience utilisateur lors du rate limiting et permettre la récupération automatique.

**Source :** Section 9.2 HIGH-3 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** le backend renvoie HTTP 429 avec header `Retry-After`
- **When** une requête API est rate-limited
- **Then** le frontend détecte le 429 et affiche un message utilisateur approprié
- **And** un retry automatique est implémenté avec backoff exponentiel basé sur `Retry-After`
- **And** le message d'erreur indique clairement le rate limiting et le délai avant retry
- **And** un test unitaire vérifie le comportement de retry

**Fichiers concernés :**
- `frontend/src/services/api_client.ts`

---

### Story 22.5 : Corriger HIGH-5 — Protection contre double-submit dans ExecutionWizard

**En tant que** développeur,  
**je veux** ajouter un guard `isSubmitting` dans `ExecutionWizard` pour éviter les exécutions dupliquées,  
**afin de** prévenir la création de multiples exécutions lors d'un double-clic.

**Source :** Section 9.2 HIGH-5 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** un utilisateur dans le wizard d'exécution
- **When** `handleSubmit` ou `handleSubmitScheduled` est appelé
- **Then** un flag `isSubmitting` est vérifié avant soumission
- **And** le bouton de soumission est désactivé pendant le traitement
- **And** une soumission en cours empêche les soumissions supplémentaires
- **And** un test unitaire vérifie qu'un double-clic ne crée qu'une seule exécution

**Fichiers concernés :**
- `frontend/src/components/catalog/ExecutionWizard.tsx:387-440`

---

### Story 22.6 : ✅ RÉSOLU — Corriger HIGH-6 — Standardiser champ pagination `total` vs `total_count`

**En tant que** développeur,  
**je veux** standardiser le champ de pagination entre backend (`total`) et frontend (`total_count`),  
**afin de** corriger l'incohérence qui cause des dysfonctionnements dans les endpoints paginés.

**Source :** Section 9.2 HIGH-6 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** un endpoint paginé renvoie des données
- **When** le frontend consomme la réponse
- **Then** le champ de pagination est cohérent entre backend et frontend (standardiser sur `total`)
- **And** l'interface `PaginationInfo` utilise `total` au lieu de `total_count`
- **And** tous les usages de `total_count` sont mis à jour vers `total`
- **And** un test d'intégration vérifie la cohérence backend/frontend

**Fichiers concernés :**
- `core/pagination.py:33`
- `frontend/src/types/api.ts:210`

---

### Story 22.7 : Refactoriser `executions/views.py` — Extraire helpers (1914 LOC)

**En tant que** développeur,  
**je veux** extraire les 26 fonctions helper de `executions/views.py` dans un module `executions/utils.py`,  
**afin de** réduire la taille du fichier et améliorer la maintenabilité.

**Source :** Section 4.1 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** le fichier `executions/views.py` contient 1914 LOC avec 26 helpers
- **When** le refactoring est effectué
- **Then** les 26 helpers sont extraits dans `executions/utils.py`
- **And** `executions/views.py` importe les helpers depuis `utils.py`
- **And** tous les tests existants passent sans modification
- **And** la taille de `executions/views.py` est réduite à <1000 LOC
- **And** la documentation des helpers est préservée

**Fichiers concernés :**
- `executions/views.py` (réduction à <1000 LOC)
- `executions/utils.py` (nouveau fichier avec helpers)

---

### Story 22.8 : Découper `types/api.ts` — Fichier monolithique (1021 LOC)

**En tant que** développeur,  
**je veux** découper `types/api.ts` en fichiers par domaine,  
**afin de** améliorer la maintenabilité et la navigation dans les types.

**Source :** Section 4.1 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** `types/api.ts` contient 1021 LOC avec tous les types API
- **When** le découpage est effectué
- **Then** les types sont organisés par domaine (ex: `api-actions.ts`, `api-executions.ts`, `api-profiles.ts`, `api-inventory.ts`)
- **And** un fichier `api/index.ts` réexporte tous les types pour compatibilité
- **And** tous les imports existants continuent de fonctionner (via index.ts)
- **And** chaque fichier de types fait <300 LOC
- **And** la documentation TypeScript est préservée

**Fichiers concernés :**
- `frontend/src/types/api.ts` (découpage)
- `frontend/src/types/api-*.ts` (nouveaux fichiers par domaine)
- `frontend/src/types/api/index.ts` (réexport)

---

### Story 22.9 : Découper `AdminPage.tsx` — Composant monolithique (845 LOC)

**En tant que** développeur,  
**je veux** découper `AdminPage.tsx` en sous-composants par onglet,  
**afin de** améliorer la maintenabilité et la testabilité.

**Source :** Section 4.1 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** `AdminPage.tsx` contient 845 LOC avec 5+ features admin
- **When** le découpage est effectué
- **Then** chaque onglet est extrait dans un composant dédié (`ActionAdmin`, `ProfileAdmin`, `TagAdmin`, etc.)
- **And** `AdminPage.tsx` devient un conteneur qui orchestre les onglets
- **And** chaque sous-composant fait <300 LOC
- **And** tous les tests existants passent
- **And** la logique d'état partagée est bien gérée (props/context)

**Fichiers concernés :**
- `frontend/src/pages/AdminPage.tsx` (réduction)
- `frontend/src/pages/admin/*.tsx` (nouveaux sous-composants)

---

### Story 22.10 : Ajouter Error Boundary React au niveau des pages

**En tant que** développeur,  
**je veux** ajouter un composant `ErrorBoundary` au niveau des pages pour capturer les erreurs de rendu,  
**afin de** éviter qu'une erreur JavaScript non gérée crashe toute l'application.

**Source :** Section 4.3 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** une erreur JavaScript non gérée survient dans un composant React
- **When** l'erreur n'est pas catchée localement
- **Then** l'`ErrorBoundary` capture l'erreur et affiche un fallback UI
- **And** un message d'erreur utilisateur-friendly est affiché
- **And** l'erreur est loggée avec le service `logger.ts`
- **And** l'utilisateur peut retourner à la page précédente ou recharger
- **And** un test vérifie que l'ErrorBoundary capture et affiche correctement les erreurs

**Fichiers concernés :**
- `frontend/src/components/ErrorBoundary.tsx` (nouveau)
- `frontend/src/App.tsx` ou `frontend/src/pages/*.tsx` (intégration)

---

### Story 22.11 : Réduire broad exception catches — Remplacer par exceptions spécifiques

**En tant que** développeur,  
**je veux** remplacer les `except Exception` par des exceptions spécifiques quand possible,  
**afin de** éviter de masquer des bugs et améliorer le debugging.

**Source :** Section 4.2 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** 21 occurrences de `except Exception as e` dans le backend
- **When** le refactoring est effectué
- **Then** chaque catch est analysé et remplacé par des exceptions spécifiques quand possible
- **And** les exceptions attendues sont documentées (ex: `OperationalError`, `ConnectionError` pour Redis)
- **And** les `AttributeError` ne sont plus masqués (remontent pour révéler les bugs)
- **And** `core/permissions.py:51` attrape uniquement les exceptions attendues
- **And** tous les tests existants passent
- **And** un test vérifie que les exceptions non attendues remontent correctement

**Fichiers concernés :**
- `executions/views.py` (3 occurrences)
- `core/views.py` (3 occurrences)
- `executions/cancellation_cache.py` (2 occurrences)
- `catalog/views.py` (2 occurrences)
- `core/permissions.py` (1 occurrence — priorité)
- Autres fichiers (9 occurrences)

---

### Story 22.12 : Corriger HIGH-2 — Valider transition PENDING_APPROVAL → SUBMITTED

**En tant que** développeur,  
**je veux** valider et documenter ou supprimer la transition `PENDING_APPROVAL → SUBMITTED`,  
**afin de** éviter le contournement du workflow d'approbation.

**Source :** Section 9.2 HIGH-2 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** une exécution est en état `PENDING_APPROVAL`
- **When** une transition vers `SUBMITTED` est tentée
- **Then** la transition est soit supprimée (si non intentionnelle), soit documentée avec justification métier
- **And** si la transition est conservée, elle nécessite une validation explicite (ex: re-soumission après modification)
- **And** seuls `REJECTED` et les transitions vers l'exécution sont autorisés depuis `PENDING_APPROVAL`
- **And** un test vérifie que le workflow d'approbation ne peut pas être contourné

**Fichiers concernés :**
- `executions/services.py:239`
- `executions/workflow_runtime.py` (machine à états)

---

### Story 22.13 : Corriger HIGH-4 — Token WebSocket hors de l'URL

**En tant que** développeur,  
**je veux** migrer le token WebSocket hors de l'URL (query parameter),  
**afin de** éviter la fuite de token dans les logs et l'historique navigateur.

**Source :** Section 9.2 HIGH-4 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** une connexion WebSocket est établie
- **When** le token d'authentification est envoyé
- **Then** le token est envoyé dans le premier message WebSocket après connexion (pas en query param)
- **And** le serveur WebSocket valide le token depuis le message initial
- **And** le token n'apparaît plus dans les logs serveur ni l'historique navigateur
- **And** un test vérifie que l'authentification WebSocket fonctionne avec le nouveau mécanisme

**Fichiers concernés :**
- `frontend/src/hooks/useWebSocket.ts:77`
- Backend WebSocket handler (validation token depuis message)

---

### Story 22.14 : Corriger HIGH-7 — Stale closure dans ExecutionsPage callbacks

**En tant que** développeur,  
**je veux** corriger les stale closures dans `handleCancelExecution` et `handleApprovalComplete`,  
**afin de** éviter l'affichage de données de la mauvaise page après annulation/approbation.

**Source :** Section 9.2 HIGH-7 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** une pagination change pendant une requête en cours
- **When** `handleCancelExecution` ou `handleApprovalComplete` est exécuté
- **Then** les valeurs courantes (`currentPage`, `activeScope`) sont utilisées au moment de l'exécution
- **And** le refetch utilise les valeurs actuelles, pas celles capturées dans la closure
- **And** la page affiche les bonnes données après annulation/approbation
- **And** un test vérifie le comportement avec changement de pagination pendant requête

**Fichiers concernés :**
- `frontend/src/pages/ExecutionsPage.tsx:354-376, 428-431`

---

### Story 22.15 : Corriger MED-1 — Sérialisation date/timezone asymétrique

**En tant que** développeur,  
**je veux** forcer les datetimes UTC côté backend et valider côté frontend,  
**afin de** éviter les décalages horaires silencieux sur les dates d'exécution.

**Source :** Section 9.3 MED-1 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** une date d'exécution est sérialisée
- **When** le backend sérialise un datetime
- **Then** le datetime est forcé en UTC avant `.isoformat()`
- **And** toutes les dates sérialisées incluent le timezone (`Z` pour UTC)
- **And** le frontend interprète correctement les dates avec timezone
- **And** un test vérifie qu'il n'y a pas de décalage horaire entre backend et frontend

**Fichiers concernés :**
- `executions/serializers.py:29-31`
- `frontend/src/utils/dateFormat.ts:14-35`

---

### Story 22.16 : Corriger MED-3/MED-4 — Cache feature flags (thundering herd + clé source)

**En tant que** développeur,  
**je veux** renforcer le cache des feature flags avec lock anti-thundering herd et clé incluant la source,  
**afin de** éviter les pics de charge DB et les incohérences lors du changement de source.

**Source :** Section 9.3 MED-3 et MED-4 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** le cache des feature flags expire
- **When** plusieurs requêtes concurrentes tentent de charger depuis la DB
- **Then** un lock/mutex empêche les chargements multiples simultanés
- **And** seule la première requête charge depuis la DB, les autres attendent
- **And** la clé de cache inclut la source (`env` ou `database`)
- **And** un changement de `FEATURE_FLAGS_SOURCE` invalide automatiquement le cache
- **And** un test vérifie le comportement avec requêtes concurrentes

**Fichiers concernés :**
- `core/feature_flags.py:67-82`

---

### Story 22.17 : Corriger MED-5 — Migrer cache inventaire de localStorage vers sessionStorage

**En tant que** développeur,  
**je veux** migrer le cache inventaire de `localStorage` vers `sessionStorage` ou mémoire,  
**afin de** réduire l'impact en cas de XSS (les noms d'infrastructure ne persistent pas).

**Source :** Section 9.3 MED-5 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** les données d'inventaire sont cachées
- **When** le cache est utilisé
- **Then** `sessionStorage` ou un cache en mémoire est utilisé au lieu de `localStorage`
- **And** les données ne persistent pas entre sessions (sessionStorage) ou sont en mémoire uniquement
- **And** le TTL de 5 minutes est préservé
- **And** un test vérifie que les données ne sont plus dans localStorage

**Fichiers concernés :**
- `frontend/src/services/execution_service.ts:436-479`

---

### Story 22.18 : Corriger MED-6 — Ajouter champ `requires_target` dans types frontend

**En tant que** développeur,  
**je veux** ajouter le champ `requires_target` dans les types frontend,  
**afin de** permettre au frontend de déterminer si une action nécessite des cibles.

**Source :** Section 9.3 MED-6 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** le backend renvoie `requires_target` dans `ActionResponse` et `ActionDetail`
- **When** le frontend consomme ces types
- **Then** `requires_target?: boolean` est ajouté dans `types/api.ts` (ou fichiers découpés)
- **And** le formulaire d'exécution utilise ce champ pour afficher le bon formulaire
- **And** un test vérifie que le champ est correctement typé et utilisé

**Fichiers concernés :**
- `frontend/src/types/api.ts` (ou fichiers découpés de Story 22.8)

---

### Story 22.19 : Rendre mypy bloquant progressivement (réduire baseline)

**En tant que** développeur,  
**je veux** réduire progressivement la baseline mypy pour rendre le type checking bloquant,  
**afin de** améliorer la qualité du code et détecter les erreurs de type tôt.

**Source :** Section 4.4 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** mypy utilise actuellement un système de baseline (erreurs ignorées)
- **When** la baseline est réduite
- **Then** les erreurs mypy existantes sont corrigées progressivement (par module ou par fichier)
- **And** la baseline est réduite de 20% par sprint jusqu'à 0%
- **And** mypy devient bloquant en CI une fois la baseline à 0%
- **And** un document de suivi liste les erreurs restantes et leur priorité

**Fichiers concernés :**
- Configuration mypy (baseline)
- Fichiers Python avec erreurs de type (correction progressive)

---

### Story 22.20 : Intégrer drf-spectacular pour documentation API automatique

**En tant que** développeur,  
**je veux** intégrer `drf-spectacular` pour générer la documentation OpenAPI/Swagger automatiquement,  
**afin de** améliorer la documentation API et faciliter l'intégration.

**Source :** Section 4.6 du code-quality-assessment-2026-02-08.md

**Acceptance Criteria:**
- **Given** les endpoints DRF sont documentés manuellement
- **When** `drf-spectacular` est intégré
- **Then** la documentation OpenAPI/Swagger est générée automatiquement
- **And** tous les endpoints sont documentés avec schémas, exemples et descriptions
- **And** une interface Swagger UI est accessible (ex: `/api/schema/swagger-ui/`)
- **And** les serializers et viewsets sont annotés avec métadonnées OpenAPI
- **And** un test vérifie que la documentation est générée correctement

**Fichiers concernés :**
- `django_backend/settings.py` (configuration drf-spectacular)
- Serializers et viewsets (annotations OpenAPI)

---

## Priorisation recommandée

### Immédiat (Sprint actuel)
- Story 22.1 : CRIT-1 — Bug RBAC bloquant
- Story 22.2 : CRIT-2 — Fail-open permissions
- Story 22.3 : CRIT-3 — Race condition token refresh

### Court terme (1-2 sprints)
- Story 22.4 : HIGH-3 — Gestion HTTP 429
- Story 22.5 : HIGH-5 — Protection double-submit
- Story 22.6 : HIGH-6 — Standardisation pagination
- Story 22.10 : Error Boundary React
- Story 22.11 : Réduire broad exception catches

### Moyen terme (1-2 mois)
- Story 22.7 : Refactoriser executions/views.py
- Story 22.8 : Découper types/api.ts
- Story 22.9 : Découper AdminPage.tsx
- Story 22.12 à 22.18 : Défauts moyenne/haute sévérité
- Story 22.19 : Mypy bloquant
- Story 22.20 : Documentation API automatique

---

## Métriques de succès

- **Score qualité code :** A- → A
- **Défauts critiques :** 3 → 0
- **Défauts haute sévérité :** 7 → 0
- **Fichiers volumineux :** Réduction de 50%+ des fichiers >800 LOC
- **Broad exception catches :** 21 → <10 (avec exceptions spécifiques)
- **Couverture tests :** Maintien ≥95% avec nouveaux tests pour corrections

---

## Notes

- Cette epic est basée sur l'évaluation de qualité du code du 8 février 2026
- Les stories sont organisées par sévérité et priorité métier
- Certaines stories peuvent être combinées si elles touchent les mêmes fichiers
- Les tests doivent être ajoutés pour chaque correction pour éviter les régressions
