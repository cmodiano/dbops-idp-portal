# Plan de Bascule FastAPI → Django

**Version:** 1.0
**Date:** 2026-02-05
**Statut:** Approuvé
**Auteur:** Équipe IDP Backend

---

## Table des Matières

1. [Contexte](#1-contexte)
2. [Options de Bascule Analysées](#2-options-de-bascule-analysées)
3. [Stratégie Retenue](#3-stratégie-retenue)
4. [Chronologie de Bascule](#4-chronologie-de-bascule)
5. [Rôles et Responsabilités](#5-rôles-et-responsabilités)
6. [Procédure de Bascule](#6-procédure-de-bascule)
7. [Procédure de Rollback](#7-procédure-de-rollback)
8. [Checklists](#8-checklists)
9. [Surveillance et Alertes](#9-surveillance-et-alertes)
10. [Communication](#10-communication)
11. [Annexes](#11-annexes)

---

## 1. Contexte

### 1.1 Objectif de la Migration

Migration du backend du portail IDP de **FastAPI + SQL brut** vers **Django + Django REST Framework** afin de :
- Faciliter l'arrimage à la plateforme hébergeuse (même stack, mêmes conventions)
- Permettre une maintenance mutualisable avec les autres applications de la plateforme
- Bénéficier de l'écosystème Django (admin, ORM, middleware)

### 1.2 État Actuel

| Composant | Technologie | Statut |
|-----------|-------------|--------|
| **Backend Production** | FastAPI 0.115+ | ✅ Opérationnel |
| **Backend Migration** | Django 5.1+ / DRF 3.15+ | ✅ Prêt production |
| **Base de données** | Oracle 19c+ | ✅ Partagée (même schéma) |
| **Frontend** | React + Vite | ✅ Inchangé (même API) |

### 1.3 Prérequis Validés (Epic M Stories M.1-M.9)

- ✅ **M.1** - Bootstrap Django + DRF (structure projet, health check)
- ✅ **M.2** - Modèles Django mappés au schéma Oracle
- ✅ **M.3** - Couche données migrée vers ORM Django
- ✅ **M.4** - API Catalogue/Admin (CRUD actions, tags)
- ✅ **M.5** - API Profils/Permissions (RBAC)
- ✅ **M.6** - API Auth/Health/Intégrations
- ✅ **M.7** - Authentification SAML et sécurité
- ✅ **M.8** - Middleware et observabilité (structlog, correlation_id)
- ✅ **M.9** - Tests unitaires et intégration (80%+ coverage)

**Conclusion:** Le backend Django est **PRODUCTION-READY**.

---

## 2. Options de Bascule Analysées

### 2.1 Option A : Bascule DNS/Load Balancer (Switch Instantané)

| Aspect | Description |
|--------|-------------|
| **Principe** | Modification du A record DNS ou du pool member LB de FastAPI vers Django |
| **Temps de bascule** | < 5 minutes (TTL DNS = 60s) |
| **Rollback** | Instantané (revert DNS/LB) |
| **Infrastructure** | Minimale (2 backends sur même LB) |
| **Complexité** | Faible |

**Avantages:**
- Simple à exécuter et comprendre
- Rollback instantané et testé
- Pattern utilisé par la plateforme hébergeuse

**Inconvénients:**
- Pas de rollout progressif (tout ou rien)
- Nécessite fenêtre de maintenance pour minimiser risque

### 2.2 Option B : Feature Flag Backend (Déploiement Dual)

| Aspect | Description |
|--------|-------------|
| **Principe** | Feature flag routant le trafic vers FastAPI ou Django |
| **Temps de bascule** | Progressif (10% → 50% → 100%) |
| **Rollback** | Flag toggle (instantané) |
| **Infrastructure** | Double (2 backends en parallèle) |
| **Complexité** | Élevée |

**Avantages:**
- Rollout progressif, A/B testing possible
- Monitoring détaillé par version

**Inconvénients:**
- ❌ Complexité (infrastructure feature flag, routing, monitoring dual)
- ❌ Durée de migration prolongée
- ❌ Double maintenance pendant la période de transition

### 2.3 Option C : Fenêtre de Maintenance (Arrêt Complet)

| Aspect | Description |
|--------|-------------|
| **Principe** | Arrêt FastAPI → Démarrage Django → Validation |
| **Temps de bascule** | 30-60 minutes |
| **Rollback** | Redémarrer FastAPI (5-10 min) |
| **Infrastructure** | Minimale |
| **Complexité** | Faible |

**Avantages:**
- Simplicité, contrôle total

**Inconvénients:**
- ❌ Downtime utilisateur (30-60 min)
- ❌ Impact sur SLA 99.9%

---

## 3. Stratégie Retenue

### Décision : **Option A - Bascule DNS/Load Balancer**

**Justification:**
1. **Simplicité** - Moins de risque d'erreur humaine
2. **Rollback rapide** - < 5 minutes si problème détecté
3. **Pattern éprouvé** - Utilisé par la plateforme hébergeuse
4. **Pas de downtime** - Switch transparent pour les utilisateurs
5. **Infrastructure existante** - LB déjà en place

### Paramètres de la Bascule

| Paramètre | Valeur | Justification |
|-----------|--------|---------------|
| **Fenêtre** | Vendredi 18h-20h | Trafic faible, équipe disponible week-end si besoin |
| **Durée estimée** | 30 min bascule + 2h monitoring | Validation complète |
| **DNS TTL** | 60s (réduit J-1) | Propagation rapide |
| **Méthode** | Pool member LB | Plus rapide que DNS |
| **Validation** | Smoke tests automatisés + checklist manuelle | Couverture complète |

---

## 4. Chronologie de Bascule

### J-7 : Validation Complète en Staging

| Action | Responsable | Durée |
|--------|-------------|-------|
| Déployer Django staging | DevOps | 30 min |
| Exécuter tous les tests M.9 | Dev backend | 1h |
| Valider frontend avec Django staging | Dev frontend | 2h |
| Documenter résultats validation | Tech lead | 30 min |

**Gate:** Tous les tests passent (80%+ coverage) ✓

### J-3 : Communication Stakeholders

| Action | Responsable | Durée |
|--------|-------------|-------|
| Envoyer email notification migration | Support | 15 min |
| Publier dans canal Slack/Teams | Tech lead | 5 min |
| Briefing équipe support | Tech lead | 30 min |

**Gate:** Accusé de réception stakeholders clés ✓

### J-1 : Préparation Finale

| Heure | Action | Responsable |
|-------|--------|-------------|
| 10h | Code freeze (pas de nouveaux commits) | Tech lead |
| 11h | Réduire DNS TTL à 60s | DevOps |
| 14h | Déployer Django production (non exposé) | DevOps |
| 15h | Test health check Django local | Dev backend |
| 16h | Valider accès SSH/console | DevOps |
| 17h | Imprimer runbook rollback | Tech lead |

**Gate:** Checklist pré-bascule complète ✓

### J : Jour de la Bascule

| Heure | Action | Responsable | Durée |
|-------|--------|-------------|-------|
| 18h00 | Début fenêtre de bascule | Tech lead | - |
| 18h05 | Envoi notification début | Support | 2 min |
| 18h10 | Bascule pool member LB vers Django | DevOps | 5 min |
| 18h15 | Exécuter smoke tests automatisés | Dev backend | 5 min |
| 18h20 | Validation checklist manuelle | Dev frontend | 15 min |
| 18h35 | Décision Go/No-Go | Tech lead | 5 min |
| 18h40 | Si Go: Monitoring intensif (2h) | Toute l'équipe | 2h |
| 18h40 | Si No-Go: Rollback immédiat | DevOps | 5 min |
| 20h40 | Fin monitoring intensif | - | - |
| 20h45 | Envoi communication succès | Support | 5 min |

### J+1 : Monitoring Normal

| Action | Responsable |
|--------|-------------|
| Review alertes Splunk (erreurs 500, latence) | Dev backend |
| Vérifier tickets support | Support |
| Communication succès finale | Tech lead |

### J+7 : Arrêt Service FastAPI

| Action | Responsable |
|--------|-------------|
| Arrêter `idp-fastapi.service` | DevOps |
| Retirer FastAPI du pool LB | DevOps |
| Garder VM en standby (rollback possible) | DevOps |

### J+30 : Désactivation VM FastAPI

| Action | Responsable |
|--------|-------------|
| Backup final logs FastAPI | DevOps |
| Désactiver VM FastAPI | DevOps |
| Mise à jour documentation | Tech lead |

### J+90 : Suppression Définitive

| Action | Responsable |
|--------|-------------|
| Supprimer VM FastAPI | DevOps |
| Archiver code FastAPI (branche legacy) | Dev backend |
| Rapport final migration | Tech lead |

---

## 5. Rôles et Responsabilités

### RACI Matrix

| Rôle | Responsabilité |
|------|----------------|
| **Tech Lead** | Coordination générale, décision Go/No-Go, communication management |
| **DevOps** | Bascule DNS/LB, déploiement Django, surveillance infrastructure, rollback |
| **Dev Backend** | Surveillance logs/erreurs Django, support technique, smoke tests |
| **Dev Frontend** | Validation fonctionnelle post-bascule, checklist UI |
| **DBA** | Surveillance base de données Oracle (connexions, performance, locks) |
| **Support** | Communication clients, escalation incidents, tickets |

### Contacts d'Urgence

| Rôle | Nom | Téléphone | Disponibilité J |
|------|-----|-----------|-----------------|
| Tech Lead | [À compléter] | [À compléter] | 18h-22h |
| DevOps | [À compléter] | [À compléter] | 18h-22h |
| DBA | [À compléter] | [À compléter] | Sur appel |

---

## 6. Procédure de Bascule

### 6.1 Pré-Bascule (J-1)

```bash
# 1. Créer le répertoire de logs Django (requis par systemd service)
ssh django-prod "sudo mkdir -p /var/log/idp-django && sudo chown idp:idp /var/log/idp-django"

# 2. Vérifier que Django est déployé et opérationnel
ssh django-prod "systemctl status idp-django"
ssh django-prod "curl -sf http://localhost:8000/api/v1/health"

# 3. Vérifier que FastAPI est toujours opérationnel
ssh fastapi-prod "systemctl status idp-fastapi"
ssh fastapi-prod "curl -sf http://localhost:8000/api/v1/health"

# 4. Réduire DNS TTL (si DNS direct, pas LB)
# Exemples par type de DNS:
# - AWS Route53: aws route53 change-resource-record-sets --hosted-zone-id ZXXXX --change-batch '{"Changes":[{"Action":"UPSERT","ResourceRecordSet":{"Name":"api.idp.internal","Type":"A","TTL":60,"ResourceRecords":[{"Value":"IP_FASTAPI"}]}}]}'
# - Cloudflare: curl -X PATCH https://api.cloudflare.com/client/v4/zones/ZONE_ID/dns_records/RECORD_ID -H "Authorization: Bearer TOKEN" -d '{"ttl":60}'
# - Bind: Modifier /etc/bind/zones/idp.internal (TTL 60), reload bind
# - PowerDNS: pdnsutil set-meta idp.internal SOA-EDIT INCEPTION-INCREMENT && pdnsutil increase-serial idp.internal

# 5. Confirmer checklist pré-bascule complète
```

### 6.2 Exécution de la Bascule (J 18h)

```bash
# 1. Notification début (via Slack/Teams/Email)
echo "🚀 Début de la bascule FastAPI → Django - $(date)"

# 2. Bascule Load Balancer (méthode recommandée)
# Option A: Si F5 BigIP
# tmsh modify ltm pool idp-api-pool members modify { django-prod:8000 { state enabled } fastapi-prod:8000 { state disabled } }

# Option B: Si HAProxy
# echo "disable server idp-backend/fastapi-prod" | socat stdio /var/lib/haproxy/stats
# echo "enable server idp-backend/django-prod" | socat stdio /var/lib/haproxy/stats

# Option C: Si Nginx upstream
# mv /etc/nginx/conf.d/idp-upstream-fastapi.conf /etc/nginx/conf.d/idp-upstream-fastapi.conf.disabled
# mv /etc/nginx/conf.d/idp-upstream-django.conf.ready /etc/nginx/conf.d/idp-upstream-django.conf
# nginx -t && systemctl reload nginx

# 3. Vérifier que le trafic arrive sur Django
ssh django-prod "tail -f /var/log/idp-django/access.log" &

# 4. Exécuter smoke tests automatisés
./scripts/post-switchover-validation.sh

# 5. Si smoke tests OK: Continuer monitoring
# 6. Si smoke tests KO: Déclencher rollback (voir section 7)
```

### 6.3 Post-Bascule Immédiate

```bash
# 1. Vérifier health check public
curl -sf https://api.idp.internal/api/v1/health

# 2. Vérifier logs Django (pas d'erreurs 500)
ssh django-prod "grep -c '\"status_code\": 500' /var/log/idp-django/access.log"
# Attendu: 0

# 3. Vérifier latence API
curl -w "@curl-format.txt" -o /dev/null -s https://api.idp.internal/api/v1/catalog/actions
# Attendu: < 500ms

# 4. Valider checklist manuelle (dev frontend)
# Voir section 8.2
```

---

## 7. Procédure de Rollback

### 7.1 Critères de Déclenchement Rollback

| Critère | Seuil | Action |
|---------|-------|--------|
| Health check failed | 3 échecs consécutifs | Rollback immédiat |
| Erreurs 500 | > 10 en 10 minutes | Rollback immédiat |
| Latence API | > 2s p95 pendant 5 min | Rollback après analyse |
| Auth SAML failed | Tout échec login | Rollback immédiat |
| Base de données | Connection pool exhausted | Rollback après analyse |

### 7.2 Exécution du Rollback

```bash
# 1. Notification rollback
echo "⚠️ ROLLBACK en cours - FastAPI → Django annulé - $(date)"

# 2. Revert Load Balancer OU DNS
# Option A: Si F5 BigIP
# tmsh modify ltm pool idp-api-pool members modify { fastapi-prod:8000 { state enabled } django-prod:8000 { state disabled } }

# Option B: Si HAProxy
# echo "enable server idp-backend/fastapi-prod" | socat stdio /var/lib/haproxy/stats
# echo "disable server idp-backend/django-prod" | socat stdio /var/lib/haproxy/stats

# Option C: Si Nginx upstream
# mv /etc/nginx/conf.d/idp-upstream-django.conf /etc/nginx/conf.d/idp-upstream-django.conf.disabled
# mv /etc/nginx/conf.d/idp-upstream-fastapi.conf.disabled /etc/nginx/conf.d/idp-upstream-fastapi.conf
# nginx -t && systemctl reload nginx

# Option D: Si DNS A record direct (rollback plus lent - 60s+ propagation)
# AWS Route53: aws route53 change-resource-record-sets --hosted-zone-id ZXXXX --change-batch '{"Changes":[{"Action":"UPSERT","ResourceRecordSet":{"Name":"api.idp.internal","Type":"A","TTL":60,"ResourceRecords":[{"Value":"IP_FASTAPI"}]}}]}'
# Cloudflare: curl -X PATCH https://api.cloudflare.com/client/v4/zones/ZONE_ID/dns_records/RECORD_ID -H "Authorization: Bearer TOKEN" -d '{"content":"IP_FASTAPI"}'
# Bind: Modifier zone, reload named
# PowerDNS: pdnsutil edit-rrset idp.internal api.idp.internal A "IP_FASTAPI" && pdnsutil increase-serial idp.internal

# 3. Vérifier que FastAPI répond
curl -sf https://api.idp.internal/api/v1/health

# IMPORTANT: Si DNS modifié, attendre 60-120s pour propagation complète

# 4. Notification rollback terminé
echo "✅ ROLLBACK terminé - FastAPI opérationnel - $(date)"
```

### 7.3 Post-Rollback

1. **Analyse root cause** (obligatoire avant nouvelle tentative)
2. **Documentation incident** dans JIRA/ServiceNow
3. **Communication stakeholders** : "Migration reportée - Nouvelle date à confirmer"
4. **Fix issues Django** avant prochaine tentative
5. **Rejouer tests M.9** après fix

---

## 8. Checklists

### 8.1 Checklist Pré-Bascule (J-1)

```markdown
- [ ] Tous les tests M.9 passent (80%+ coverage)
- [ ] Backend Django déployé en staging et validé
- [ ] Frontend configuré pour Django staging et testé
- [ ] Runbook rollback imprimé et accessible
- [ ] Accès SSH/console aux serveurs Django et FastAPI confirmés
- [ ] Surveillance Splunk/Dynatrace configurée
- [ ] Communication stakeholders envoyée (J-3)
- [ ] DNS TTL réduit à 60s (si applicable)
- [ ] Équipe disponible pendant fenêtre de bascule
- [ ] Contacts d'urgence à jour
```

### 8.2 Checklist Post-Bascule (J)

```markdown
- [ ] Health check Django retourne 200 OK
- [ ] Login SAML fonctionne (1 utilisateur test)
- [ ] Catalogue chargé (action visible dans UI)
- [ ] Exécution d'action test réussit (AAP job lancé)
- [ ] Dashboard analytics affiche données
- [ ] Logs structurés visibles dans Splunk
- [ ] Aucune erreur 500 dans logs Django (30 min)
- [ ] Latence API < 500ms p95 (baseline FastAPI)
```

### 8.3 Checklist Validation Frontend Complète

```markdown
- [ ] Page login charge (SAML redirect fonctionne)
- [ ] Après login, dashboard charge (stats visibles)
- [ ] Catalogue actions charge (liste + filtres + recherche)
- [ ] Fiche action ouvre en drawer (métadonnées + documentation)
- [ ] Wizard execution 3 étapes fonctionne (paramètres + cible + confirm)
- [ ] Execution démarre (timeline temps réel affiche steps)
- [ ] Historique exécutions charge (liste paginée)
- [ ] Admin actions CRUD fonctionne (création, édition, suppression)
- [ ] Admin profils fonctionne (création, permissions)
- [ ] Export CSV/PDF fonctionne (analytics + audit)
- [ ] Dark mode toggle fonctionne (UX)
- [ ] Favoris actions fonctionne (toggle + filtre "Mes actions")
```

---

## 9. Surveillance et Alertes

### 9.1 Métriques Critiques (Splunk Dashboards)

| Métrique | Seuil Normal | Seuil Alerte | Action si Alerte |
|----------|--------------|--------------|------------------|
| Health check status | 200 | != 200 | Page immédiate |
| Erreurs 500/min | 0-2 | > 5 | Alerte + analyse |
| Latence API p95 | < 500ms | > 1s | Alerte |
| Connexions Oracle | < 8 | > 9 | Analyse pool |
| Logins/min | Normal | -50% | Vérifier SAML |

### 9.2 Configuration Alertes Splunk

```spl
# Alerte erreurs 500
index=idp-django sourcetype=django-json status_code=500
| stats count as errors by _time span=5m
| where errors > 5

# Alerte latence élevée
index=idp-django sourcetype=django-json
| stats p95(response_time_ms) as latency_p95 by _time span=5m
| where latency_p95 > 1000

# Alerte health check failed
index=idp-django sourcetype=django-json endpoint="/api/v1/health" status_code!=200
| stats count as failures by _time span=1m
| where failures > 0
```

### 9.3 Configuration Dynatrace

- **Service:** `idp-django-backend`
- **SLO:** 99.9% availability, < 500ms response time
- **Alerting Profile:** `IDP-Migration-Critical`
- **Notification:** Email + Slack + PagerDuty

---

## 10. Communication

### 10.1 Template Email J-7

**Objet:** Migration backend FastAPI → Django - Date de bascule confirmée

```
Bonjour,

Dans le cadre de l'alignement avec la plateforme hébergeuse, le backend du portail IDP
sera migré de FastAPI vers Django REST Framework.

**Date de bascule:** [Vendredi DD/MM/YYYY à 18h00]
**Durée estimée:** 30 minutes
**Impact utilisateurs:** Aucune interruption de service attendue

Cette migration apporte :
- Meilleure maintenabilité (stack mutualisée avec la plateforme)
- Performances équivalentes ou supérieures
- Même interface utilisateur (aucun changement visible)

En cas de question, contactez [email support].

Cordialement,
L'équipe IDP
```

### 10.2 Template Email J-1

**Objet:** REMINDER: Migration backend demain 18h

```
Bonjour,

Rappel : la migration du backend IDP est prévue demain.

**Date:** [Vendredi DD/MM/YYYY à 18h00]
**Fenêtre:** 18h00 - 20h00 (monitoring)
**Impact:** Aucune interruption de service prévue

En cas de problème post-migration, contactez [téléphone urgence].

Cordialement,
L'équipe IDP
```

### 10.3 Template Communication Succès

**Objet:** ✅ Migration Django réussie - Backend IDP opérationnel

```
Bonjour,

La migration du backend IDP vers Django REST Framework a été effectuée avec succès.

**Statut:** Opérationnel
**Date de bascule:** [Vendredi DD/MM/YYYY à 18h15]
**Incidents:** Aucun

Toutes les fonctionnalités sont disponibles. N'hésitez pas à nous signaler
tout comportement anormal via [canal support].

Cordialement,
L'équipe IDP
```

### 10.4 Template Communication Rollback

**Objet:** ⚠️ Migration Django reportée - Backend FastAPI maintenu

```
Bonjour,

Suite à un incident technique lors de la migration, nous avons décidé de
reporter la bascule vers Django.

**Statut actuel:** Backend FastAPI opérationnel (aucun impact utilisateur)
**Cause:** [Description courte de l'incident]
**Nouvelle date:** À confirmer

Nous vous tiendrons informés de la nouvelle date de migration.

Cordialement,
L'équipe IDP
```

---

## 11. Annexes

### 11.1 Architecture Cible Post-Migration

```
                                    ┌─────────────────────────┐
                                    │   Frontend React/Vite   │
                                    │   (Inchangé)            │
                                    └───────────┬─────────────┘
                                                │
                                                │ HTTPS
                                                ▼
                                    ┌─────────────────────────┐
                                    │   Nginx Reverse Proxy   │
                                    │   - TLS Termination     │
                                    │   - /api/v1/* routing   │
                                    └───────────┬─────────────┘
                                                │
                                                │ HTTP :8000
                                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                     Django REST Framework                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ Catalog API │  │ Profiles    │  │ Executions  │  │ Analytics   │  │
│  │ /actions    │  │ /profiles   │  │ /executions │  │ /stats      │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ Middleware: CORS, Auth JWT, Logging (structlog), Correlation ID  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
                                                │
                        ┌───────────────────────┼───────────────────────┐
                        │                       │                       │
                        ▼                       ▼                       ▼
              ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
              │   Oracle 19c    │    │ HashiCorp Vault │    │   ServiceNow    │
              │   (Partagée)    │    │   Credentials   │    │   Change Mgmt   │
              └─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 11.2 Commandes Utiles

```bash
# Vérifier statut services
systemctl status idp-django
systemctl status idp-fastapi

# Logs Django temps réel
journalctl -u idp-django -f

# Health check local
curl -sf http://localhost:8000/api/v1/health | jq

# Pool connexions Oracle
SELECT username, status, COUNT(*)
FROM v$session
WHERE username = 'IDP_USER'
GROUP BY username, status;

# Latence API
curl -w "time_total: %{time_total}s\n" -o /dev/null -s https://api.idp.internal/api/v1/health
```

### 11.3 Contacts

| Rôle | Nom | Email | Téléphone |
|------|-----|-------|-----------|
| Tech Lead | [À compléter] | [À compléter] | [À compléter] |
| DevOps | [À compléter] | [À compléter] | [À compléter] |
| DBA | [À compléter] | [À compléter] | [À compléter] |
| Support | [À compléter] | [À compléter] | [À compléter] |

### 11.4 Références

- [Epic M - Migration FastAPI → Django](_bmad-output/planning-artifacts/epic-migration-fastapi-django.md)
- [Architecture IDP](_bmad-output/planning-artifacts/architecture.md)
- [M.9 Tests et Coverage](m-9-tests-unitaires-et-integration-parite.md)
- [Backend Best Practices](docs/backend-best-practices.md)

---

**Document approuvé par:** [À compléter]
**Date d'approbation:** [À compléter]
**Prochaine révision:** Après bascule production
