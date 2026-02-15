# Glossaire — IDP Portal

## Termes clés

| Terme | Définition |
|-------|-----------|
| **Plateforme** | Système externe sur lequel le portail IDP exécute des jobs (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud). Chaque plateforme dispose d'un **adapter** dédié. |
| **Service** | Système externe consommé par le portail pour une fonction transversale (Vault pour les secrets, Splunk pour les logs, ServiceNow pour l'ITSM). Les services ne sont **pas** des plateformes d'exécution. |
| **Adapter (adaptateur de plateforme)** | Classe héritant de `BaseAdapter` dans le package `adapters/`. Responsable de l'exécution de jobs sur une plateforme distante (lancement, monitoring, annulation). Obtenu via la factory `get_platform_adapter()`. |
| **Service client** | Classe dans le package `services/` qui encapsule l'accès à un service externe (ex. `VaultService`, `SplunkService`, `ServiceNowService`). N'hérite **pas** de `BaseAdapter`. Obtenu via la factory `get_service_client()`. |
| **BaseAdapter** | Classe abstraite (`adapters/base_adapter.py`) définissant le contrat commun des adapters de plateforme : `start_job()`, `get_job_status()`, `cancel_job()`, etc. |
| **Factory** | Fonction qui instancie le bon adapter ou service client selon le type d'intégration. `get_platform_adapter()` pour les plateformes, `get_service_client()` pour les services. |
| **credential_ref** | Référence à un secret stocké dans Vault, au format `vault:mount/data/path#key`. Résolu au runtime par `VaultService`. |
| **Circuit breaker** | Mécanisme de résilience qui coupe les appels vers un service indisponible après N échecs consécutifs. Utilisé par `VaultService` et `SplunkService`. |
| **IntegrationTypeCatalogue** | Modèle Django qui référence tous les types d'intégration supportés (plateformes et services) avec leurs actions disponibles. |
| **correlation_id** | Identifiant UUID unique qui relie tous les événements d'une même exécution, de bout en bout (logs, audit, Splunk). |
