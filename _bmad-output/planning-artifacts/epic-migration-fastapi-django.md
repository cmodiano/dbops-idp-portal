---
type: epic
title: Migration FastAPI vers Django REST
status: draft
createdAt: '2026-01-29'
project_name: test
user_name: Cyrille
context: Arrimage à la plateforme interne (hébergeur) — stack cible Django + DRF. Réduction de la dette d'arrimage et alignement stack.
scope: Backend IDP Portal uniquement. Frontend React inchangé (cohabitation ou même API contract).
---

# Epic M : Migration FastAPI vers Django REST

## Objectif

Migrer le backend du portail IDP de **FastAPI + SQL brut (python-oracledb)** vers **Django + Django REST Framework** afin de faciliter l'arrimage à la plateforme hébergeuse (même stack, même conventions, maintenance mutualisable). Le frontend React consomme la même API (contrat préservé).

## Périmètre

- **In scope :** Backend uniquement (API, couche données, auth, config, middleware, tests).
- **Out of scope :** Changement de frontend ; changement de schéma métier (les FR restent couverts).
- **Contrainte :** Parité fonctionnelle et contractuelle avec l'API actuelle (OpenAPI / contrats frontend).

## Risques et hypothèses

- **Hypothèse :** Oracle reste la BDD cible (Django Oracle backend) ou bascule PostgreSQL décidée avec l'hébergeur.
- **Risque :** Dette de migration (repositories ~SQL brut, CLOB/JSON) → estimer en sprints avant engagement.
- **Critère de succès :** Tous les tests actuels (ou équivalents) passent sur le backend Django ; le frontend fonctionne sans modification des appels API (ou avec adaptation minimale documentée).

---

## Story M.1 : Bootstrap projet Django et Django REST Framework

As a développeur de l'équipe IDP,
I want un projet Django initial avec DRF, structure d'apps et configuration de base,
So that nous avons une base saine pour migrer les endpoints et la logique métier.

**Acceptance Criteria:**

**Given** un environnement Python dédié à la migration (venv ou équivalent)
**When** on installe Django, djangorestframework, djangocorsheaders, et les dépendances Oracle (cx_Oracle ou oracledb)
**Then** un projet Django `idp_backend` est créé avec une structure d'apps : `catalog`, `profiles`, `auth`, `integrations`, `core`

**Given** le projet Django
**When** on configure `settings.py` (DEBUG, ALLOWED_HOSTS, DATABASES Oracle, INSTALLED_APPS avec rest_framework, CORS)
**Then** `python manage.py runserver` démarre sans erreur
**And** la structure respecte les conventions du projet hébergeur si documentées (nommage, place des configs)
**And** un fichier `requirements.txt` ou `pyproject.toml` liste toutes les dépendances avec versions

**Given** DRF est installé
**When** on configure REST_FRAMEWORK dans settings (auth, pagination, format JSON, throttle si requis)
**Then** une route de test GET /api/v1/health (ou équivalent) renvoie 200 avec un payload minimal
**And** le format de réponse (enveloppe data/error, snake_case) est aligné avec l'API actuelle pour compatibilité frontend

---

## Story M.2 : Modèles Django et migrations (schéma Oracle existant)

As a développeur,
I want les modèles Django mappés sur le schéma Oracle actuel (USERS, ACTIONS_CATALOG, PROFILES, etc.),
So that la couche ORM remplace le SQL brut sans changer le schéma en production.

**Acceptance Criteria:**

**Given** le schéma Oracle actuel (tables V001–V020+ : users, actions_catalog, execution_steps, profiles, profile_*_permissions, integrations, audit, etc.)
**When** on crée les modèles Django correspondants (Meta.db_table, champs CLOB/JSONField, relations ForeignKey, enums)
**Then** chaque table existante a un modèle Django avec les mêmes noms de colonnes et types compatibles
**And** les champs JSON (parameters_schema, impact_rules, execution_steps, change_type_config) utilisent JSONField ou TextField + sérialisation documentée
**And** les migrations Django initiales sont générées (makemigrations) et documentées pour exécution sur un schéma existant (--fake initial si tables déjà présentes)

**Given** un schéma Oracle de dev (ou fixture)
**When** on exécute migrate (ou migrate --fake puis vérification)
**Then** aucune régression sur le schéma ; les contraintes et index existants sont respectés ou explicitement décidés (nommage Django)
**And** un README ou ADR décide : migrations Django prennent le relais de Flyway à partir de la version X, ou cohabitation temporaire

---

## Story M.3 : Couche données — conversion des repositories vers l'ORM Django

As a développeur,
I want la logique des repositories FastAPI (catalog, profiles, integrations, audit, user) réécrite avec l'ORM Django,
So que les vues DRF s'appuient sur des QuerySet et services Django au lieu de SQL brut.

**Acceptance Criteria:**

**Given** les repositories actuels (catalog_repository, profile_repository, profile_action_permission_repository, profile_target_permission_repository, integration_repository, user_repository, audit_repository)
**When** on crée l'équivalent en couche Django (managers personnalisés, services dans chaque app, ou repositories encapsulant l'ORM)
**Then** chaque opération CRUD et requête métier actuelle a un équivalent testé (parité fonctionnelle)
**And** la gestion des CLOB/JSON (lecture/écriture) est centralisée et couverte par des tests unitaires
**And** les transactions et l'audit (écriture dans audit_log) sont gérés (signals Django ou appels explicites) conformément aux NFR d'audit
**And** aucune requête SQL brute dans les vues DRF (sauf exception documentée et justifiée)

**Given** les tests unitaires existants des repositories (pytest)
**When** on les réécrit ou duplique pour la couche Django (pytest-django ou unittest)
**Then** le taux de couverture et les cas limites (pagination, filtres, champs optionnels) sont au moins équivalents

---

## Story M.4 : API REST — endpoints catalogue et admin (actions, tags)

As a développeur,
I want les endpoints admin et catalogue (actions, tags) exposés en DRF avec le même contrat que l'API FastAPI actuelle,
So que le frontend Admin et Catalogue continue de fonctionner sans changement (ou avec adaptation minimale documentée).

**Acceptance Criteria:**

**Given** les routes FastAPI actuelles : admin (create/list/get/update action, steps, metadata, tags, status), catalog (list catalog actions), tags (list)
**When** on implémente les ViewSet ou APIView DRF correspondants avec serializers
**Then** les URLs et verbes HTTP sont identiques (ex. GET /api/v1/catalog/actions, POST /api/v1/admin/actions, etc.)
**And** le format des corps de requête et de réponse (champs, types, enveloppe data) est inchangé pour le client
**And** la pagination, filtres et tri du catalogue sont supportés (paramètres query et format de réponse alignés)
**And** les permissions (RBAC) sont appliquées (DRF permissions ou middleware) : seuls les rôles autorisés accèdent aux endpoints admin

**Given** les tests d'intégration ou E2E du frontend (Admin, Catalogue)
**When** on pointe le frontend vers le backend Django
**Then** les scénarios critiques (liste actions, création action, édition, tags, statut) passent ; les régressions sont documentées et tracées

---

## Story M.5 : API REST — endpoints profils et permissions

As a développeur,
I want les endpoints profils (list, get, create, update, delete, profile_actions, profile_targets) migrés en DRF,
So que la gestion des profils et des permissions par le frontend reste fonctionnelle.

**Acceptance Criteria:**

**Given** les routes FastAPI profiles (list_profiles, get_profile, create_profile, update_profile, delete_profile, get_profile_actions, get_profile_targets)
**When** on implémente les vues DRF et serializers correspondants
**Then** le contrat (query params, body, response shape) est préservé
**And** les règles métier (cumul multi-profils, résolution AD, validation des permissions) sont respectées (délégation aux services Django)
**And** l'import/export YAML (si exposé via API) reste supporté ou est documenté comme évolution séparée

**Given** les tests unitaires et d'intégration des profils
**When** on les exécute contre le backend Django
**Then** les cas de succès et d'erreur (validation, 404, 403) sont couverts

---

## Story M.6 : API REST — auth, health, intégrations

As a développeur,
I want les endpoints auth (current user, refresh), health et integrations migrés en DRF,
So que l'authentification, le monitoring et la gestion des intégrations fonctionnent sur Django.

**Acceptance Criteria:**

**Given** les routes FastAPI : auth (get_current_user_profile), health (GET /api/v1/health), integrations (CRUD)
**When** on implémente les équivalents DRF
**Then** GET /api/v1/health renvoie le statut des dépendances (DB, optionnellement Vault/ServiceNow) avec codes HTTP 200/503
**And** les endpoints d'intégrations (list, get, create, update, delete) respectent le contrat actuel
**And** l'endpoint de profil utilisateur courant renvoie le même format (user, permissions, profils) pour le frontend
**And** la documentation OpenAPI (schema) est générée (drf-spectacular ou équivalent) et comparée à l'actuelle pour écarts documentés

---

## Story M.7 : Authentification SAML et sécurité (alignement plateforme cible)

As a responsable technique,
I want l'authentification SAML 2.0 et la gestion des sessions (JWT ou session Django) alignées avec la plateforme hébergeuse,
So que le portail IDP s'intègre à leur infra SSO et politique de sécurité.

**Acceptance Criteria:**

**Given** la plateforme hébergeuse utilise Django + SSO (SAML ou autre)
**When** on intègre le mécanisme d'auth (django-saml2, python3-saml, ou proxy SSO côté hébergeur)
**Then** un utilisateur non authentifié est redirigé vers l'IdP et revient avec une session valide
**And** les attributs utilisateur (nom, groupes AD, etc.) sont disponibles pour la résolution des profils IDP (FR25, FR25a-d)
**And** les tokens ou cookies de session respectent la politique de sécurité (httpOnly, durée, renouvellement)
**And** NFR6 (TLS), NFR9 (expiration session), NFR10 (accès non autorisé journalisé) sont satisfaits
**And** un document d'architecture ou runbook décrit l'interaction SSO entre le portail IDP et l'infra hébergeur

**Given** des tests d'auth (login, refresh, 401, 403)
**When** on les exécute contre le backend Django
**Then** les scénarios de succès et d'échec sont couverts

---

## Story M.8 : Middleware, logging, observabilité

As a DBOPS,
I want le middleware (CORS, correlation ID, erreurs), le logging structuré et l'observabilité alignés sur la plateforme et les NFR,
So que le portail Django soit monitorable et cohérent avec le reste de l'infra.

**Acceptance Criteria:**

**Given** le backend Django
**When** une requête entre et sort
**Then** un correlation ID (X-Idp-Request-Id ou équivalent) est généré et propagé dans les logs et réponses si applicable
**And** les logs sont structurés (JSON) avec timestamp, level, event, correlation_id, user_id (NFR, convention hébergeur)
**And** les exceptions sont catchées et renvoyées au client dans le format d'erreur actuel (enveloppe error, codes HTTP)
**And** CORS est configuré pour les origines autorisées (frontend)
**And** le health check reflète l'état DB (et optionnellement Vault, ServiceNow) pour le monitoring

---

## Story M.9 : Tests unitaires et d'intégration (parité avec FastAPI)

As a développeur,
I want une suite de tests (unitaires + intégration) au moins équivalente à celle du backend FastAPI,
So que la migration n'introduise pas de régressions et que les futures évolutions restent couvertes.

**Acceptance Criteria:**

**Given** la liste des tests pytest actuels (repositories, API, auth, middleware)
**When** on migre ou réécrit les tests pour Django (pytest-django, client DRF, factories)
**Then** chaque module critique (catalog, profiles, integrations, auth, health) a des tests unitaires et, si pertinent, des tests d'intégration (DB réelle ou test DB)
**And** les tests d'API (endpoints) valident statut HTTP, corps de réponse et cas d'erreur (400, 403, 404)
**And** la couverture de code est mesurée et documentée ; objectif : au moins égal à la couverture actuelle
**And** les tests s'exécutent dans le CI (GitHub Actions ou équivalent) à chaque push

---

## Story M.10 : Stratégie de bascule et décommissionnement FastAPI

As a chef de projet ou tech lead,
I want une stratégie de bascule (double run, feature flag, ou bascule unique) et un plan de décommissionnement du backend FastAPI,
So que la mise en production du backend Django soit maîtrisée et sans perte de service.

**Acceptance Criteria:**

**Given** le backend Django est fonctionnel et testé (parité avec FastAPI)
**When** on définit la stratégie de bascule (bascule DNS/route, feature flag backend, ou fenêtre de maintenance)
**Then** un document "Plan de bascule FastAPI → Django" décrit les étapes, les rôles, le rollback et la vérification post-bascule
**And** les données (Oracle) sont partagées : pas de migration de données si même schéma ; si changement de BDD, un script de migration est prévu et testé
**And** le frontend est configuré pour pointer vers le backend Django (env, config) et une checklist de validation (catalogue, admin, profils, auth, health) est exécutée
**And** après validation en production, le code et les déploiements FastAPI sont désactivés ou archivés ; le dépôt/documentation indique Django comme backend officiel

**Given** la bascule est effectuée
**When** on surveille les erreurs et les métriques (logs, health, temps de réponse)
**Then** les incidents sont traités selon le runbook ; un retour arrière vers FastAPI est possible si documenté (snapshot config, rollback DNS/deploy)

---

## Résumé des stories

| Story | Titre | Ordre suggéré |
|-------|--------|----------------|
| M.1 | Bootstrap projet Django et DRF | 1 |
| M.2 | Modèles Django et migrations (schéma Oracle) | 2 |
| M.3 | Couche données — repositories → ORM Django | 3 |
| M.4 | API REST — catalogue et admin (actions, tags) | 4 |
| M.5 | API REST — profils et permissions | 5 |
| M.6 | API REST — auth, health, intégrations | 6 |
| M.7 | Authentification SAML et sécurité | 7 |
| M.8 | Middleware, logging, observabilité | 8 |
| M.9 | Tests unitaires et d'intégration | 9 (en parallèle 4–8) |
| M.10 | Stratégie de bascule et décommissionnement FastAPI | 10 |

## Estimation indicative (à affiner par l'équipe)

- **M.1** : 1–2 j
- **M.2** : 3–5 j (volume schéma, CLOB/JSON)
- **M.3** : 8–15 j (gros bloc : tous les repositories)
- **M.4** : 3–5 j
- **M.5** : 2–4 j
- **M.6** : 1–2 j
- **M.7** : 3–5 j (dépend de l'offre SSO hébergeur)
- **M.8** : 1–2 j
- **M.9** : 5–8 j (en parallèle)
- **M.10** : 2–3 j (rédaction + exécution)

**Total indicatif :** ~30–50 j (6–10 sprints selon vélocité). À faire estimer par un dev/archi Django.

---

*Epic rédigé dans le cadre du positionnement arrimage plateforme interne (hébergeur). Décision produit : migrer vers Django pour faciliter l'arrimage ; cet epic en formalise le périmètre.*
