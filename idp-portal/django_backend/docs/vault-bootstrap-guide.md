# Guide de Bootstrap Vault (Secret 0) — Story 27.11

## 1. Introduction au problème œuf/poule

Le portail IDP utilise HashiCorp Vault comme **service de secrets principal** :
tous les credentials des intégrations (AAP, Tower, ServiceNow, Azure DevOps, GitHub Actions,
Terraform Cloud, Jira, Splunk) sont résolus via Vault au moment de l'exécution.
**Aucun secret n'est stocké en base de données** (NFR7, NFR21).

**Le problème :** Comment le portail s'authentifie-t-il à Vault sans stocker de secret en base ?

**La réponse :** Le « secret 0 » (token ou AppRole credentials) est fourni par
l'environnement d'exécution — variables d'environnement, secrets manager externe,
ou injection au déploiement. Il n'est jamais persisté dans le portail.

## 2. Options de bootstrap

### 2.1 Option A — Variables d'environnement (Recommandé Phase 2)

Le secret 0 est fourni via les variables d'environnement standard Vault.

| Variable | Rôle | Requis |
|----------|------|--------|
| `VAULT_ADDR` | URL du serveur Vault | Oui |
| `VAULT_TOKEN` | Token auth (prioritaire sur AppRole) | Oui* |
| `VAULT_ROLE_ID` | AppRole role_id | Oui* |
| `VAULT_SECRET_ID` | AppRole secret_id | Oui* |

*Il faut soit `VAULT_TOKEN`, soit `VAULT_ROLE_ID` + `VAULT_SECRET_ID`.

**Avantages :**
- Simple, standard 12-factor app
- Déjà supporté par le `VaultService` existant
- Compatible avec tous les environnements (Docker, Kubernetes, bare metal)

**Inconvénients :**
- Token statique peut expirer (si non-renewable)
- AppRole nécessite rotation du `secret_id`
- Variables visibles dans les process listings (atténué par Docker/K8s)

**Cas d'usage :** Environnements conteneurisés, CI/CD pipelines, développement local.

### 2.2 Option B — Secret 0 fourni par mécanisme externe (Recommandé Phase 3)

Le secret 0 est injecté par un service externe au moment du déploiement.

**Mécanismes d'injection :**
- **Kubernetes Secrets** : Montés comme variables d'environnement dans le pod
- **Azure Key Vault** : Injecté via CSI driver ou Azure Identity
- **AWS Secrets Manager** : Injecté via AWS SDK ou IAM roles
- **HashiCorp Vault Agent** : Sidecar qui renouvelle et injecte le token automatiquement

**Avantages :**
- Séparation des concerns (l'application ne gère pas l'injection)
- Gestion centralisée des secrets
- Rotation automatique possible (Vault Agent, K8s External Secrets Operator)

**Inconvénients :**
- Complexité supplémentaire d'infrastructure
- Dépendance à un service externe pour le bootstrap

**Cas d'usage :** Plateformes cloud natives, environnements hautement sécurisés.

### 2.3 Option C — Autres variantes

| Variante | Description | Cas d'usage |
|----------|-------------|-------------|
| **Vault Agent Sidecar** | Container companion qui renouvelle le token et le stocke dans un fichier partagé | Kubernetes, Docker Compose |
| **Kubernetes Service Account** | Auth native K8s → Vault via `auth/kubernetes/login` | Clusters Kubernetes avec Vault intégré |
| **AppRole + Wrapped Secret ID** | Secret ID jetable, une seule utilisation (response wrapping) | Pipelines CI/CD avec sécurité renforcée |

### Tableau comparatif

| Critère | Option A (env vars) | Option B (injection externe) | Option C (variantes) |
|---------|-------------------|---------------------------|---------------------|
| **Simplicité** | Haute | Moyenne | Variable |
| **Sécurité** | Bonne | Très bonne | Très bonne |
| **Maintenabilité** | Haute | Moyenne | Moyenne |
| **Cloud-readiness** | Bonne | Excellente | Excellente |
| **Rotation** | Manuelle | Automatique possible | Automatique |

### Recommandation

**Phase 2 (MVP) : Option A** — Variables d'environnement avec AppRole auth.
Justification : Équilibre entre time-to-market et sécurité, path de migration clair.

**Phase 3 : Migration vers Option B** — Injection externe (Vault Agent ou K8s Secrets).
Justification : Rotation automatique, séparation des concerns.

## 3. Configuration recommandée (Variables d'environnement)

### 3.1 Token authentication (développement)

```bash
export VAULT_ADDR=https://vault.company.com
export VAULT_TOKEN=s.xxxxxxxxxxxxxxxx
```

### 3.2 AppRole authentication (production — recommandé)

```bash
export VAULT_ADDR=https://vault.company.com
export VAULT_ROLE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
export VAULT_SECRET_ID=yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
```

### 3.3 Procédure d'obtention du role_id et secret_id

```bash
# 1. Créer une policy pour l'application
vault policy write idp-portal - <<EOF
path "secret/data/*" {
  capabilities = ["read"]
}
EOF

# 2. Créer un AppRole
vault auth enable approle
vault write auth/approle/role/idp-portal \
  token_policies="idp-portal" \
  token_ttl=1h \
  token_max_ttl=4h \
  secret_id_num_uses=0

# 3. Récupérer le role_id (stable)
vault read auth/approle/role/idp-portal/role-id

# 4. Générer un secret_id (jetable, regénérer à chaque déploiement)
vault write -f auth/approle/role/idp-portal/secret-id
```

### 3.4 Exemple .env.production

```ini
# Vault — Secret 0 (Bootstrap)
# NE JAMAIS COMMITER CE FICHIER
VAULT_ADDR=https://vault.company.com
VAULT_ROLE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
VAULT_SECRET_ID=yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy

# Vault Enterprise (optionnel)
VAULT_NAMESPACE=team-dbops

# Performance
VAULT_CACHE_TTL=300
VAULT_TIMEOUT=10
VAULT_MAX_RETRIES=3
```

**Sécurité :** Ne jamais commiter `.env.production`. Utiliser l'injection CI/CD ou un secrets manager.

## 4. Configuration alternative (Injection externe)

### 4.1 Kubernetes Secrets

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: vault-credentials
  namespace: idp-portal
stringData:
  VAULT_ADDR: "https://vault.company.com"
  VAULT_ROLE_ID: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  VAULT_SECRET_ID: "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: idp-portal
spec:
  template:
    spec:
      containers:
        - name: django
          envFrom:
            - secretRef:
                name: vault-credentials
```

### 4.2 Vault Agent Sidecar (Kubernetes)

```yaml
annotations:
  vault.hashicorp.com/agent-inject: "true"
  vault.hashicorp.com/role: "idp-portal"
  vault.hashicorp.com/agent-inject-secret-vault-token: "auth/token/lookup-self"
```

### 4.3 Azure Key Vault (CSI Driver)

```yaml
volumeMounts:
  - name: vault-secrets
    mountPath: /mnt/secrets
volumes:
  - name: vault-secrets
    csi:
      driver: secrets-store.csi.k8s.io
      readOnly: true
      volumeAttributes:
        secretProviderClass: "vault-credentials"
```

## 5. Spécification du service de secrets par intégration (secret_service_id)

### 5.1 Cas d'usage multi-Vault

Dans certains environnements, plusieurs instances Vault coexistent :
- **Vault Production** : `https://vault-prod.company.com` — secrets des intégrations production
- **Vault Dev** : `https://vault-dev.company.com` — secrets des intégrations développement
- **Vault multi-tenant** : Même instance Vault avec des namespaces différents par équipe

Le champ `secret_service_id` (migration V077) permet de spécifier quelle instance Vault
utiliser pour résoudre les secrets d'une intégration donnée.

### 5.2 Configuration dans l'Admin UI

1. **Créer les intégrations Vault** : Admin > Intégrations > Type "Vault"
   - Vault Production : `base_url=https://vault-prod.company.com`
   - Vault Dev : `base_url=https://vault-dev.company.com`

2. **Associer aux intégrations** : Lors de la création/édition d'une intégration (AAP, Tower, etc.),
   le champ "Service de secrets" permet de sélectionner l'instance Vault à utiliser.

### 5.3 Comportement par défaut

- Si `secret_service_id` est **NULL** : Le `VaultService` singleton est utilisé
  (configuré via les variables d'environnement VAULT_*)
- Si `secret_service_id` pointe vers une intégration Vault : Une instance `VaultService`
  dédiée est créée avec le `base_url` et la configuration de cette intégration

### 5.4 Cache multi-instance

Le cache est isolé par instance Vault via un `instance_id` dans la clé de cache :
```
vault:{instance_id}:{namespace}/{mount}/data/{path}#key
```

Cela évite les collisions entre les secrets de différentes instances Vault.

## 6. Troubleshooting et FAQ

**Q : Que se passe-t-il si le secret 0 est invalide ?**
R : Le `VaultService` ne peut pas s'authentifier. Les appels à `get_secret()` échouent
avec `VaultAuthError`. Le circuit breaker s'ouvre après 5 échecs.
Vérifier les logs du VaultService et les variables d'environnement.

**Q : Comment rotationner le secret 0 ?**
R : Avec AppRole, générer un nouveau `secret_id` :
```bash
vault write -f auth/approle/role/idp-portal/secret-id
```
Mettre à jour la variable d'environnement et redémarrer le portail.

**Q : Peut-on stocker le secret 0 dans Vault lui-même ?**
R : Non, c'est le problème œuf/poule. Le secret 0 doit provenir d'une source **externe** à Vault.

**Q : Que se passe-t-il si l'instance Vault référencée par `secret_service_id` est down ?**
R : Le circuit breaker de cette instance s'ouvre. Les exécutions utilisant cette intégration
échouent avec `VaultUnavailableError`. Les autres intégrations (utilisant le Vault par défaut)
ne sont pas impactées.

**Q : Comment migrer d'une instance Vault à une autre ?**
R : 1) Créer la nouvelle intégration Vault dans l'Admin
2) Copier les secrets dans la nouvelle instance Vault
3) Mettre à jour le `secret_service_id` des intégrations concernées
4) Vérifier que les `credential_ref` sont valides sur la nouvelle instance
