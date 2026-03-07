# Recherche par Correlation ID dans l'Audit

> Story 27.8 — Guide auditeur pour la recherche par correlation_id dans le portail et Splunk.

## Qu'est-ce qu'un Correlation ID ?

Chaque requête entrante dans le portail IDP reçoit un identifiant unique (UUID v4) appelé **Correlation ID**. Cet identifiant est propagé dans :
- Tous les logs structurés (structlog)
- Les appels vers les plateformes externes (AAP, Azure DevOps, GitHub, Terraform, Vault)
- Les entrées d'audit en base de données
- Les événements envoyés vers Splunk HEC

Le Correlation ID permet de **tracer l'intégralité d'une opération** à travers tous les systèmes.

## Recherche dans le portail Audit

### Accès

Menu **Audit** > Page **Audit des exécutions**

### Utilisation du filtre

1. Localiser le champ **Correlation ID** dans la barre de filtres
2. Saisir le Correlation ID complet (ex: `550e8400-e29b-41d4-a716-446655440000`)
3. La liste se met à jour automatiquement avec les entrées correspondantes
4. Un **badge bleu** `Correlation: <valeur>` confirme le filtre actif
5. Cliquer sur le **X** du badge pour supprimer le filtre

### Combinaison avec d'autres filtres

Le filtre Correlation ID fonctionne en combinaison (AND logique) avec :
- **Période** (date début / date fin)
- **Environnement** (DEV, STAGING, PROD)
- **Statut** (Succès, Échec, En cours)

### Copier le Correlation ID

Dans le **détail d'une entrée** (clic sur une ligne) :
- Le champ **Correlation ID** est affiché avec une icône **copier**
- Cliquer sur l'icône pour copier la valeur dans le presse-papier

## Lien Portail → Splunk

Pour des analyses plus approfondies (logs complets, output des steps, appels externes) :

1. Copier le Correlation ID depuis le portail (détail de l'entrée audit)
2. Ouvrir Splunk et exécuter la recherche :

```spl
index="prod-idp" correlation_id="<valeur copiée>"
| sort timestamp
| table timestamp, event, level, user_id, execution_id, platform, details
```

Cette recherche retourne la **timeline complète** de l'opération : démarrage, steps, appels adapter, résultat final.

## API Backend

Le filtre est aussi disponible via l'API REST :

```bash
curl -H "Authorization: Bearer <token>" \
  "https://idp-portal.example.com/api/v1/audit/executions/?correlation_id=550e8400-e29b-41d4-a716-446655440000"
```

Export CSV avec filtre :

```bash
curl -H "Authorization: Bearer <token>" \
  "https://idp-portal.example.com/api/v1/audit/export/?fmt=csv&correlation_id=550e8400-e29b-41d4-a716-446655440000"
```
