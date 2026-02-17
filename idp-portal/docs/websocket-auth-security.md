# Authentification WebSocket — Sécurité

> Story 22.13 — Correction HIGH-4 : Token WebSocket hors de l'URL

## Pourquoi le token dans l'URL est risqué

Le passage du JWT en query parameter (`?token=eyJ...`) expose le token dans :

1. **Logs serveur** — nginx, Apache et load balancers loggent les URLs complètes par défaut
2. **Historique navigateur** — L'URL complète est stockée dans l'historique
3. **Headers Referer** — Le token peut fuir via le header Referer
4. **Proxies réseau** — Les proxies d'entreprise peuvent logger les URLs

## Solution : Authentification message-based

Le token JWT est envoyé dans le **premier message** après connexion WebSocket, conformément aux recommandations OAuth 2.0 / RFC 6749.

## Séquence d'authentification

```
1. Client → Serveur : ws.connect("wss://host/ws/executions/123")   # Pas de token dans l'URL
2. Serveur : accept()                                                # Accepte sans auth
3. Client → Serveur : {"type": "auth", "token": "eyJ..."}           # Token dans le corps du message
4. Serveur : verify_token(token, expected_type='access')             # Validation JWT
5. Serveur → Client : {"type": "auth_success", "user_id": "..."}    # Confirmation
6. Client ↔ Serveur : Messages métier                                # Après auth uniquement
```

## Codes d'erreur WebSocket

| Code | Raison | Reconnexion |
|------|--------|-------------|
| 4001 | Authentification invalide ou manquante | Non (erreur définitive) |
| 4002 | JSON invalide | Non |
| 1000 | Fermeture normale | Oui |

## Sécurité des logs

Le consumer backend (`core/consumers.py`) ne logge **jamais** le token JWT. Seuls les événements suivants sont loggés :

- `websocket_auth_success` — avec `user_id` uniquement
- `websocket_auth_failed` — avec `reason` uniquement (pas le token)

## Références

- [OWASP A02:2021 — Cryptographic Failures](https://owasp.org/Top10/A02_2021-Cryptographic_Failures/)
- [RFC 6455 — WebSocket Protocol](https://datatracker.ietf.org/doc/html/rfc6455)
- [Django Channels](https://channels.readthedocs.io/en/stable/)
