# Staging Dry Run Checklist - Répétition Générale

> **📦 Document d'archivage — Migration terminée**  
> Ce document est conservé pour référence historique. La migration FastAPI→Django est complète (février 2026).  
> Voir [MIGRATION_ARCHIVE.md](MIGRATION_ARCHIVE.md) pour accéder au code FastAPI archivé.

**Date de préparation:** 2026-02-05
**Objectif:** Valider le plan de bascule dans un environnement staging avant la production
**Statut:** Migration terminée — Checklist historique conservée

---

## Prérequis de l'Environnement Staging

### Infrastructure

- [ ] Django backend déployé sur serveur staging
- [ ] Frontend staging configuré avec `.env.staging`
- [ ] DNS staging ou `/etc/hosts` configuré pour simuler bascule
- [ ] FastAPI staging toujours opérationnel (état initial)

### Accès

- [ ] SSH vers serveur Django staging vérifié
- [ ] SSH vers serveur FastAPI staging vérifié
- [ ] Accès console LB/DNS staging vérifié
- [ ] Splunk/Dynatrace staging accessible

---

## Étape 1: Préparation (J-1 Staging)

### 1.1 Vérification Django Staging

```bash
# Vérifier service Django
ssh staging-django "systemctl status idp-django"

# Vérifier health check
ssh staging-django "curl -sf http://localhost:8000/api/v1/health | jq"
```

- [ ] Service Django `idp-django` running
- [ ] Health check retourne 200 OK
- [ ] Logs sans erreurs (`journalctl -u idp-django -n 50`)

### 1.2 Vérification FastAPI Staging

```bash
# Vérifier service FastAPI
ssh staging-fastapi "systemctl status idp-fastapi"

# Vérifier health check
ssh staging-fastapi "curl -sf http://localhost:8000/api/v1/health | jq"
```

- [ ] Service FastAPI `idp-fastapi` running
- [ ] Health check retourne 200 OK

### 1.3 Vérification Frontend Staging

```bash
# Build frontend avec config staging
cd frontend
cp .env.staging .env
npm run build
```

- [ ] Build frontend réussi
- [ ] Variables d'environnement staging correctes

---

## Étape 2: Exécution du Dry Run

### 2.1 Chronométrage

| Étape | Temps estimé | Temps réel | Responsable |
|-------|--------------|------------|-------------|
| Notification début | 2 min | | |
| Bascule LB/DNS | 5 min | | |
| Smoke tests | 5 min | | |
| Validation manuelle | 15 min | | |
| Décision Go/No-Go | 5 min | | |
| **Total** | **32 min** | | |

### 2.2 Bascule Staging

```bash
# Étape 1: Noter l'heure de début
echo "Début bascule: $(date)"

# Étape 2: Bascule LB (adapter selon votre LB)
# HAProxy exemple:
echo "disable server idp-backend/fastapi-staging" | socat stdio /var/lib/haproxy/stats
echo "enable server idp-backend/django-staging" | socat stdio /var/lib/haproxy/stats

# Étape 3: Vérifier trafic arrive sur Django
ssh staging-django "tail -f /var/log/idp-django/access.log"
```

- [ ] Bascule LB exécutée
- [ ] Trafic redirigé vers Django (logs confirment)
- [ ] FastAPI ne reçoit plus de requêtes

### 2.3 Smoke Tests Automatisés

```bash
# Exécuter smoke tests
./scripts/post-switchover-validation.sh --api-url https://staging-api.idp.internal
```

- [ ] Health check: PASS
- [ ] SAML redirect: PASS
- [ ] Catalog list: PASS (si JWT disponible)
- [ ] Profiles list: PASS (si JWT disponible)
- [ ] Executions list: PASS (si JWT disponible)
- [ ] Response time < 500ms: PASS

### 2.4 Validation Manuelle

Utiliser la checklist complète du frontend:

- [ ] Page login charge (SAML redirect fonctionne)
- [ ] Après login, dashboard charge (stats visibles)
- [ ] Catalogue actions charge (liste + filtres + recherche)
- [ ] Fiche action ouvre en drawer (métadonnées + documentation)
- [ ] Wizard execution 3 étapes fonctionne (paramètres + cible + confirm)
- [ ] Execution démarre (timeline temps réel affiche steps)
- [ ] Historique executions charge (liste paginée)
- [ ] Admin actions CRUD fonctionne (création, édition, suppression)
- [ ] Admin profils fonctionne (création, permissions)
- [ ] Export CSV/PDF fonctionne (analytics + audit)
- [ ] Dark mode toggle fonctionne (UX)
- [ ] Favoris actions fonctionne (toggle + filtre "Mes actions")

---

## Étape 3: Test du Rollback

### 3.1 Simulation Incident

```bash
# Simuler incident: arrêter Django
ssh staging-django "sudo systemctl stop idp-django"

# Vérifier que health check échoue
curl -sf https://staging-api.idp.internal/api/v1/health
# Expected: Connection refused ou timeout
```

### 3.2 Exécution Rollback

```bash
# Étape 1: Noter l'heure de début rollback
echo "Début rollback: $(date)"

# Étape 2: Revert LB
echo "enable server idp-backend/fastapi-staging" | socat stdio /var/lib/haproxy/stats
echo "disable server idp-backend/django-staging" | socat stdio /var/lib/haproxy/stats

# Étape 3: Vérifier FastAPI répond
curl -sf https://staging-api.idp.internal/api/v1/health

# Étape 4: Noter l'heure de fin
echo "Fin rollback: $(date)"
```

- [ ] Rollback exécuté
- [ ] Temps de rollback: ___ minutes (cible: < 5 min)
- [ ] FastAPI opérationnel après rollback
- [ ] Health check retourne 200 OK

### 3.3 Restauration Post-Rollback

```bash
# Redémarrer Django (pour prochains tests)
ssh staging-django "sudo systemctl start idp-django"

# Vérifier Django opérationnel
ssh staging-django "curl -sf http://localhost:8000/api/v1/health"
```

---

## Étape 4: Documentation des Learnings

### Problèmes Rencontrés

| # | Problème | Impact | Solution | Status |
|---|----------|--------|----------|--------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

### Améliorations du Plan de Bascule

| # | Amélioration | Priorité | Appliquée |
|---|-------------|----------|-----------|
| 1 | | | |
| 2 | | | |

### Métriques Collectées

| Métrique | Valeur Staging | Cible Production |
|----------|----------------|------------------|
| Temps total bascule | min | < 30 min |
| Temps rollback | min | < 5 min |
| Latence API p95 | ms | < 500 ms |
| Erreurs pendant bascule | | 0 |

---

## Conclusion Dry Run

**Date d'exécution:** ____________________
**Résultat:** [ ] SUCCÈS / [ ] ÉCHEC

### Validation Finale

- [ ] Plan de bascule validé en staging
- [ ] Rollback testé et fonctionnel
- [ ] Équipe formée sur la procédure
- [ ] Documentation mise à jour si nécessaire
- [ ] Prêt pour production

### Signatures

| Rôle | Nom | Signature | Date |
|------|-----|-----------|------|
| Tech Lead | | | |
| DevOps | | | |
| Dev Backend | | | |

---

**Note:** Ce document doit être complété lors de l'exécution réelle du dry run en staging.
