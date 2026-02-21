# Epic 32 : Résilience Data Guard (failover / switchover)

**En tant que** opérateur ou consommateur de l’API (portail ou système externe),  
**je veux** que le backend gère correctement une coupure de connexion à la base (failover/switchover Data Guard) en se reconnectant et en reprenant ou retentant l’opération,  
**afin de** bénéficier d’une haute disponibilité transparente sans erreur utilisateur ni échec côté API pendant la fenêtre de bascule (< 1 min).

---

## Contexte

- En production, la base de données est en **Oracle Data Guard** avec FSFO : 2 serveurs sur un site, 2 bases sur un autre site, F5 pointant vers l’instance active.
- Lors d’un **failover** ou **switchover**, la connexion DB peut être perdue pendant typiquement **moins d’une minute**.
- Le backend doit : **détecter** la perte de connexion, **reconnecter** une fois la base disponible, et **reprendre la transaction** ou retenter l’opération métier de façon bornée et idempotente quand possible.
- Cela s’applique aux **flux portail** (utilisateurs) et aux **flux API** (consommateurs externes).

---

## Stories

### Story 32.1 : Détection et reconnexion automatique à la base après failover/switchover

**En tant que** backend,  
**je veux** détecter la perte de connexion à la base (erreurs driver/DB) et me reconnecter automatiquement une fois la base à nouveau disponible,  
**afin de** ne pas laisser des requêtes en échec définitif pendant la fenêtre de bascule Data Guard.

**Acceptance Criteria:**

- **Given** une connexion DB active
- **When** la connexion est perdue (failover/switchover, erreur réseau, etc.)
- **Then** le backend détecte l’erreur (ex. exceptions Oracle / driver)
- **And** après reconnexion possible (base à nouveau disponible), les nouvelles requêtes utilisent une connexion valide
- **And** la stratégie de reconnexion est configurable (nombre de tentatives, délai/backoff) et documentée
- **And** des tests (unitaires ou intégration) simulent une coupure et vérifient la reconnexion

**Fichiers / zones :** couche d’accès données (pool de connexions, Django DB backend ou équivalent), configuration (retry, timeouts), logging des événements de reconnexion.

---

### Story 32.2 : Retry et rejeu de transaction après reconnexion

**En tant que** backend,  
**je veux** après une reconnexion DB, retenter l’opération métier (ou rejouer la transaction) de manière bornée,  
**afin de** que l’appelant (portail ou API) obtienne un succès sans avoir à rejouer la requête manuellement.

**Acceptance Criteria:**

- **Given** une requête métier en cours (transaction ou opération service)
- **When** la connexion DB est perdue puis rétablie
- **Then** le backend retente l’opération (ou la transaction) selon une politique configurée (nombre max de retries, fenêtre temporelle)
- **And** les opérations rejouées sont conçues pour être **idempotentes** lorsque c’est possible (éviter double écriture si la même requête est retentée)
- **And** après épuisement des retries, une erreur explicite est retournée (code HTTP / message clair) sans laisser l’appel en attente indéfinie
- **And** des tests valident : succès après retry, échec après N retries, comportement en cas d’idempotence

**Fichiers / zones :** couche service/transaction, middleware ou décorateur retry, gestion des exceptions DB, réponses d’erreur standardisées.

---

### Story 32.3 : Résilience pour le portail et les consommateurs API

**En tant que** utilisateur du portail ou consommateur de l’API,  
**je veux** que la résilience (détection, reconnexion, retry) s’applique à tous les flux : requêtes issues du portail et appels API externes,  
**afin de** ne pas subir d’échecs évitables pendant un failover/switchover.

**Acceptance Criteria:**

- **Given** la résilience implémentée en 32.1 et 32.2
- **When** une requête provient du **portail** (utilisateur humain) ou d’un **consommateur API** (système externe)
- **Then** la même logique de détection, reconnexion et retry s’applique
- **And** au moins un scénario portail (ex. chargement catalogue, soumission exécution) et un scénario API (ex. POST /api/v1/...) sont couverts par des tests ou validés manuellement lors d’un test de bascule simulée
- **And** la documentation (NFR ou runbook) précise le comportement attendu pendant et après un failover (< 1 min)

**Fichiers / zones :** endpoints API, vues/controllers utilisés par le portail, tests E2E ou d’intégration, documentation.

---

### Story 32.4 : Bornes retry, observabilité et codes d’erreur explicites

**En tant que** opérateur ou développeur,  
**je veux** que les retries soient bornés (nombre max, fenêtre temporelle), que les erreurs soient explicites et que les événements soient tracés (logs / métriques),  
**afin de** éviter des attentes infinies et pouvoir diagnostiquer les incidents liés à la base.

**Acceptance Criteria:**

- **Given** la politique de retry (32.1 / 32.2)
- **Then** le **nombre maximum de retries** et une **fenêtre temporelle** (ex. 2 min) sont configurables et documentés
- **And** après épuisement, l’API retourne un **code d’erreur explicite** (ex. 503 Service Unavailable ou code métier dédié) avec un message clair (ex. « Base temporairement indisponible après bascule ; veuillez réessayer »)
- **And** les événements (perte connexion, reconnexion, retry, échec après N retries) sont **loggés** (structlog ou équivalent) avec correlation_id si disponible
- **And** optionnel : métriques (compteur reconnexions, retries, échecs) pour surveillance
- **And** des tests vérifient les bornes et le format de réponse d’erreur

**Fichiers / zones :** configuration retry, gestion d’erreurs API, logging, optionnel : métriques (Prometheus/StatsD ou équivalent).

---

## Références

- NFR discutée en session PM (résilience Data Guard, backend transaction retry, portail + API).
- Fenêtre de bascule typique : **< 1 minute** (failover/switchover Data Guard avec FSFO).
