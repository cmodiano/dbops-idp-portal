# Runbook de Décommissionnement FastAPI

**Version:** 1.0
**Date:** 2026-02-05
**Objectif:** Décommissionner l'infrastructure FastAPI après migration réussie vers Django

---

## Table des Matières

1. [Prérequis](#1-prérequis)
2. [Timeline de Décommissionnement](#2-timeline-de-décommissionnement)
3. [Phase 1: J+7 - Arrêt du Service](#3-phase-1-j7---arrêt-du-service)
4. [Phase 2: J+30 - Désactivation VM](#4-phase-2-j30---désactivation-vm)
5. [Phase 3: J+90 - Suppression Définitive](#5-phase-3-j90---suppression-définitive)
6. [Rollback d'Urgence](#6-rollback-durgence)
7. [Checklist Finale](#7-checklist-finale)

---

## 1. Prérequis

### Conditions pour démarrer le décommissionnement

| Condition | Vérification | Status |
|-----------|--------------|--------|
| Django en production depuis > 7 jours | Dashboard monitoring | [ ] |
| Zéro incident critique lié à Django | JIRA/ServiceNow | [ ] |
| Taux d'erreur Django < 0.1% | Splunk/Dynatrace | [ ] |
| Performance Django = baseline FastAPI | Métriques APM | [ ] |
| Accord Tech Lead | Email/signature | [ ] |

### Inventaire Infrastructure FastAPI

**À documenter avant décommissionnement:**

| Élément | Valeur | Notes |
|---------|--------|-------|
| Serveur/VM | [hostname] | |
| IP interne | [IP] | |
| Port service | 8000 | |
| Service systemd | idp-fastapi | |
| Nginx vhost | /etc/nginx/conf.d/idp-fastapi.conf | |
| Logs path | /var/log/idp-fastapi/ | |
| Pool LB | [pool name] | |
| DNS A record | [si applicable] | |

---

## 2. Timeline de Décommissionnement

```
Jour J      → Bascule production (Django actif)
     |
     ↓
J+7         → PHASE 1: Arrêt service FastAPI (rollback encore possible)
     |
     ↓
J+30        → PHASE 2: Désactivation VM FastAPI
     |
     ↓
J+90        → PHASE 3: Suppression définitive VM + archivage final
```

### Justification des délais

| Phase | Délai | Raison |
|-------|-------|--------|
| J+7 | 7 jours | Période de stabilisation, rollback possible |
| J+30 | 30 jours | Confirmation stabilité long terme |
| J+90 | 90 jours | Conformité audit (90 jours de logs) |

---

## 3. Phase 1: J+7 - Arrêt du Service

### 3.1 Prérequis Phase 1

- [ ] Django stable depuis 7 jours (zéro incident critique)
- [ ] Accord Tech Lead pour arrêter FastAPI
- [ ] Backup final des logs FastAPI effectué

### 3.2 Procédure

```bash
# 1. Connexion au serveur FastAPI
ssh fastapi-prod

# 2. Vérifier qu'aucun trafic n'arrive (devrait être 0)
tail -f /var/log/idp-fastapi/access.log
# Attendu: Aucune nouvelle ligne (trafic sur Django)

# 3. Arrêter le service FastAPI
sudo systemctl stop idp-fastapi

# 4. Désactiver le démarrage automatique
sudo systemctl disable idp-fastapi

# 5. Vérifier le status
sudo systemctl status idp-fastapi
# Attendu: inactive (dead)

# 6. Retirer FastAPI du pool LB (si encore présent)
# HAProxy:
echo "disable server idp-backend/fastapi-prod" | socat stdio /var/lib/haproxy/stats

# 7. Documenter l'heure d'arrêt
echo "FastAPI arrêté: $(date)" >> /var/log/decommissioning.log
```

### 3.3 Vérifications Post-Arrêt

```bash
# 1. Vérifier que Django fonctionne toujours
curl -sf https://api.idp.internal/api/v1/health

# 2. Vérifier les logs Django (pas d'erreurs)
ssh django-prod "tail -50 /var/log/idp-django/error.log"

# 3. Vérifier le dashboard (pas d'alerte)
# → Splunk/Dynatrace
```

### 3.4 Communication

Envoyer email interne équipe :

```
Objet: [INFO] Service FastAPI arrêté (J+7)

Le service FastAPI a été arrêté conformément au plan de décommissionnement.

- Date d'arrêt: [DD/MM/YYYY HH:MM]
- VM FastAPI: En standby (rollback possible jusqu'à J+30)
- Django: Opérationnel

Aucune action requise.
```

---

## 4. Phase 2: J+30 - Désactivation VM

### 4.1 Prérequis Phase 2

- [ ] FastAPI arrêté depuis 23+ jours (Phase 1 complète)
- [ ] Django stable depuis 30 jours
- [ ] Aucune demande de rollback
- [ ] Backup final des logs effectué

### 4.2 Procédure Backup Final

```bash
# 1. Connexion au serveur FastAPI
ssh fastapi-prod

# 2. Archiver tous les logs FastAPI
cd /var/log/idp-fastapi
sudo tar -czvf /backup/idp-fastapi-logs-final-$(date +%Y%m%d).tar.gz .

# 3. Copier l'archive vers stockage long terme
scp /backup/idp-fastapi-logs-final-*.tar.gz backup-server:/archive/idp/

# 4. Vérifier l'archive
tar -tzvf /backup/idp-fastapi-logs-final-*.tar.gz | head -20

# 5. Archiver aussi la configuration
sudo tar -czvf /backup/idp-fastapi-config-final-$(date +%Y%m%d).tar.gz \
    /etc/nginx/conf.d/idp-fastapi.conf \
    /etc/systemd/system/idp-fastapi.service \
    /opt/idp-portal/backend/

# 6. Copier vers stockage long terme
scp /backup/idp-fastapi-config-final-*.tar.gz backup-server:/archive/idp/
```

### 4.3 Procédure Désactivation

```bash
# 1. Désactiver la VM (selon votre infrastructure)

# VMware vSphere:
# PowerCLI: Stop-VM -VM "fastapi-prod" -Confirm:$false

# AWS:
# aws ec2 stop-instances --instance-ids i-xxxxxxxx

# Azure:
# az vm deallocate --resource-group rg-idp --name fastapi-prod

# On-premise:
# Contacter l'équipe infrastructure pour arrêter la VM

# 2. Documenter
echo "VM FastAPI désactivée: $(date)" >> /var/log/decommissioning.log
```

### 4.4 Vérifications

- [ ] VM FastAPI éteinte (vérifier console virtualisation)
- [ ] Aucune alerte monitoring liée à la VM
- [ ] Archives logs accessibles sur stockage long terme

### 4.5 Communication

```
Objet: [INFO] VM FastAPI désactivée (J+30)

La VM FastAPI a été désactivée conformément au plan.

- VM: Arrêtée (pas supprimée)
- Logs: Archivés sur [stockage]
- Configuration: Archivée sur [stockage]

Rollback possible jusqu'à J+90 (réactivation VM).
```

---

## 5. Phase 3: J+90 - Suppression Définitive

### 5.1 Prérequis Phase 3

- [ ] VM FastAPI désactivée depuis 60+ jours
- [ ] Django stable depuis 90 jours
- [ ] Archives vérifiées et accessibles
- [ ] Approbation Tech Lead + Management

### 5.2 Procédure

```bash
# 1. Vérifier une dernière fois les archives
ls -la /archive/idp/idp-fastapi-*
# Confirmer présence des fichiers

# 2. Supprimer la VM définitivement

# VMware:
# PowerCLI: Remove-VM -VM "fastapi-prod" -DeletePermanently -Confirm:$false

# AWS:
# aws ec2 terminate-instances --instance-ids i-xxxxxxxx

# Azure:
# az vm delete --resource-group rg-idp --name fastapi-prod --yes

# 3. Nettoyer les configurations
# - Supprimer entrée DNS (si applicable)
# - Supprimer pool member LB
# - Supprimer config monitoring

# 4. Documenter
echo "VM FastAPI supprimée définitivement: $(date)" >> /var/log/decommissioning.log
```

### 5.3 Nettoyage Git

```bash
# 1. S'assurer que la branche legacy existe
git branch -a | grep legacy/fastapi-final
# Attendu: remotes/origin/legacy/fastapi-final

# 2. Créer le tag final
git tag -a v1.0.0-fastapi -m "Final FastAPI version before Django migration"
git push origin v1.0.0-fastapi

# 3. (Optionnel) Supprimer le code FastAPI du main
# Note: Garder la branche legacy pour référence
# git rm -r backend/
# git commit -m "chore: remove FastAPI backend (archived in legacy/fastapi-final)"
```

### 5.4 Communication Finale

```
Objet: ✅ [COMPLETE] Décommissionnement FastAPI terminé

Le décommissionnement du backend FastAPI est terminé.

Timeline complète:
- J: Bascule vers Django
- J+7: Arrêt service FastAPI
- J+30: Désactivation VM
- J+90: Suppression définitive (aujourd'hui)

Archives:
- Logs: [chemin stockage]
- Configuration: [chemin stockage]
- Code: Branche git legacy/fastapi-final, Tag v1.0.0-fastapi

Le backend Django est le backend officiel.
```

---

## 6. Rollback d'Urgence

### Si rollback nécessaire avant J+30

```bash
# 1. Réactiver la VM (si désactivée)
# [Commande selon infrastructure]

# 2. Démarrer le service FastAPI
ssh fastapi-prod
sudo systemctl start idp-fastapi
sudo systemctl enable idp-fastapi

# 3. Vérifier health check
curl -sf http://localhost:8000/api/v1/health

# 4. Réactiver dans le LB
echo "enable server idp-backend/fastapi-prod" | socat stdio /var/lib/haproxy/stats

# 5. Basculer le trafic vers FastAPI
# [Voir procédure rollback dans migration-switchover-plan.md]

# 6. Documenter l'incident
```

### Si rollback nécessaire après J+30 (VM désactivée)

```bash
# 1. Réactiver la VM
# [Commande selon infrastructure - peut prendre 5-10 min]

# 2. Une fois la VM démarrée, suivre la procédure ci-dessus
```

### Si rollback impossible (J+90, VM supprimée)

**Rollback n'est plus possible.** Actions alternatives:

1. Investiguer le problème Django
2. Fix en urgence sur Django
3. Si vraiment nécessaire: Redéployer FastAPI depuis les archives (temps: plusieurs heures)

---

## 7. Checklist Finale

### Phase 1 (J+7)

- [ ] Django stable 7 jours
- [ ] Accord Tech Lead
- [ ] Service FastAPI arrêté
- [ ] Service FastAPI désactivé (systemctl)
- [ ] FastAPI retiré du LB
- [ ] Email équipe envoyé

### Phase 2 (J+30)

- [ ] Django stable 30 jours
- [ ] Logs FastAPI archivés
- [ ] Config FastAPI archivée
- [ ] VM FastAPI désactivée
- [ ] Archives vérifiées
- [ ] Email équipe envoyé

### Phase 3 (J+90)

- [ ] Django stable 90 jours
- [ ] Approbation Management
- [ ] VM FastAPI supprimée
- [ ] DNS/LB nettoyés
- [ ] Tag git créé
- [ ] Documentation mise à jour
- [ ] Email final envoyé

---

**Document approuvé par:** [Tech Lead]
**Date:** [À compléter lors de l'exécution]
