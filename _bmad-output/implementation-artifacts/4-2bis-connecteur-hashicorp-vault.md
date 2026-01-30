# Story 4.2bis : Connecteur HashiCorp Vault

Status: backlog

<!-- Création story — pas d'implémentation immédiate. Prérequis pour Story 4.3 (moteur d'exécution). -->

## Story

As a **système**,
I want **un connecteur Vault qui se connecte dynamiquement à HashiCorp Vault et récupère les secrets à la demande (par chemin / credential_ref)**,
So that **le moteur d'exécution peut résoudre les credential_ref des intégrations (Story 2.27) et fournir les credentials aux adapters de plateforme sans stocker de secret dans le portail**.

## Acceptance Criteria

1. **AC1 — Config et « secret 0 »**
   **Given** le backend démarre avec une config Vault valide,
   **When** le connecteur Vault est initialisé,
   **Then** il se connecte à Vault en utilisant le « secret 0 » fourni **uniquement par l'environnement** (variables d'env ou secrets montés) : `VAULT_ADDR`, et soit `VAULT_TOKEN`, soit `VAULT_ROLE_ID` + `VAULT_SECRET_ID` (AppRole). Aucun de ces éléments n'est stocké en base ni exposé dans l'admin.

2. **AC2 — Récupération dynamique de secrets**
   **Given** le moteur d'exécution (Story 4.3) ou un service a besoin d'un secret,
   **When** il appelle le connecteur avec un chemin ou `credential_ref` (ex. `secret/data/idp/aap-prod`),
   **Then** le connecteur interroge Vault dynamiquement, retourne le secret (ou les champs nécessaires) et ne le persiste pas.

3. **AC3 — Erreurs et indisponibilité**
   **Given** Vault est indisponible ou le secret 0 est invalide,
   **When** le connecteur tente de se connecter ou de récupérer un secret,
   **Then** une erreur explicite est remontée (ex. `VaultError` ou équivalent) et le caller peut refuser l'exécution (NFR21).

4. **AC4 — Intégration moteur d'exécution**
   **And** le connecteur est exposé comme service injectable (ex. `vault_service` ou `VaultConnector`) utilisé par le moteur d'exécution pour résoudre les `credential_ref` des intégrations avant d'appeler les plateformes (AAP, Terraform, etc.).
   **And** FR17 et FR29 sont satisfaits pour la récupération dynamique des credentials.

## Tasks / Subtasks

- [ ] Task 1 (AC1) — Config et secret 0
  - [ ] 1.1 : Étendre `Settings` (ex. `config.py`) avec `vault_addr`, `vault_token` (ou `vault_role_id` + `vault_secret_id` pour AppRole), lus depuis les variables d'env. Pas de valeur par défaut sensible en prod.
  - [ ] 1.2 : Documenter les variables attendues (`.env.example`, README ou doc déploiement) : `VAULT_ADDR`, `VAULT_TOKEN` ou `VAULT_ROLE_ID` / `VAULT_SECRET_ID`.

- [ ] Task 2 (AC2, AC3) — Connecteur Vault
  - [ ] 2.1 : Créer un module `vault_connector` ou `vault_service` (ex. `backend/app/services/vault_service.py`). Initialisation : connexion au client Vault (ex. `hvac`) avec config lue depuis Settings.
  - [ ] 2.2 : Exposer une méthode `get_secret(path: str) -> dict` (ou équivalent) qui lit le secret à la demande. Gérer les erreurs (secret inexistant, Vault down, token expiré) et remonter une exception dédiée (`VaultError` ou intégrée à la hiérarchie d'erreurs existante).
  - [ ] 2.3 : Ne jamais persister les secrets récupérés ; utilisation uniquement en mémoire pour les appels aux plateformes.

- [ ] Task 3 (AC4) — Injection et usage
  - [ ] 3.1 : Rendre le connecteur injectable (Depends FastAPI ou factory) pour que le moteur d'exécution (Story 4.3) puisse l'utiliser. Prévoir un mode « Vault désactivé » (ex. env `VAULT_ADDR` vide) pour dev/tests si nécessaire.
  - [ ] 3.2 : Documenter comment le moteur résout un `credential_ref` d'intégration (Story 2.27) via le connecteur (mapping chemin / nom logique → `get_secret`).

- [ ] Task 4 — Tests
  - [ ] 4.1 : Tests unitaires avec Vault mocké (ou mode dev) : `get_secret` retourne les données attendues ; erreurs (Vault down, path inexistant) lèvent bien `VaultError` ou équivalent.
  - [ ] 4.2 : Optionnel : test d'intégration contre un Vault de dev (container) si l'équipe le souhaite.

## Dev Notes

- **Secret 0** : Token ou AppRole credentials pour **se connecter à Vault**. Toujours fourni par l'environnement (env, K8s secrets, etc.), jamais en base ni dans l'admin. Voir aussi Story 2.27 Dev Notes.
- **credential_ref** : Référence stockée dans INTEGRATIONS (Story 2.27). Peut être un chemin Vault (ex. `secret/data/idp/aap-prod`) ou un nom logique mappé à un chemin en config ou en code. Le connecteur doit pouvoir résoudre les deux (ou uniquement chemin si on garde la sémantique simple).
- **Librairie** : `hvac` est courante pour Python ; vérifier compatibilité avec la version Vault cible et la politique de deps du projet.
- **NFR21** : Si Vault est indisponible, l'exécution est refusée avec un message explicite ; pas de fallback vers un autre stockage de secrets.

### Project Structure

- Config : `backend/app/core/config.py` (extension Settings).
- Connecteur : `backend/app/services/vault_service.py` (ou `connectors/vault_connector.py` selon structure).
- Erreurs : réutiliser ou étendre la hiérarchie existante (ex. `VaultError` mentionnée dans l'architecture).

### References

- [Source: epics.md] Story 4.2bis — Connecteur HashiCorp Vault ; Story 4.3 (moteur utilise le connecteur).
- [Source: epics.md] FR17, FR29, NFR7, NFR21 — Secrets depuis Vault, zero credential en base, pas de fallback si Vault down.
- [Source: 2-27-backend-integrations-plateformes-distantes] `credential_ref` dans INTEGRATIONS ; secret 0 hors portail.
