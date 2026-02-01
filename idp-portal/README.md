# IDP Portal

Internal Developer Platform pour les operations base de donnees.

## Stack

- **Frontend** : React 19 + Vite + Ant Design 6 + TypeScript
- **Backend** : FastAPI + python-oracledb (mode Thin) + Pydantic v2

## Demarrage rapide

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
fastapi dev app/main.py
```

### Backend (API only, sans portail)

Le backend peut tourner sans lancer le frontend. Pour developper/tester l'API sans portail (et sans IdP), activez le bypass d'auth:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

export AUTH_DEV_BYPASS=true
export CORS_ORIGINS=http://localhost:3000
fastapi dev app/main.py
```

Optionnel (flow SAML sans portail): retournez les tokens en JSON au lieu d'un redirect:

```bash
export SAML_CALLBACK_MODE=json
```

## Structure

- `frontend/` : Application React
- `backend/` : API FastAPI
- `database/` : Migrations SQL
- `scripts/` : Scripts utilitaires
