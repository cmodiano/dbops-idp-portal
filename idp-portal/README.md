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

## Structure

- `frontend/` : Application React
- `backend/` : API FastAPI
- `database/` : Migrations SQL
- `scripts/` : Scripts utilitaires
