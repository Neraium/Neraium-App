# Neraium Demo Setup

## Quick Start (Docker)

If you have Docker installed:

```bash
docker-compose up
```

Then open: **http://localhost:3006**

That's it. Everything runs in containers.

## Local Development (Manual)

If you don't have Docker:

**Terminal 1 (Backend):**
```bash
cd backend
source ../.venv/Scripts/activate  # Windows Git Bash
# or: ..\.venv\Scripts\activate  # Windows CMD
uvicorn server:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 (Frontend):**
```bash
cd frontend
npm install
npm start
```

Then open: **http://localhost:3006**

## What You Need

### For Docker:
- Docker Desktop (https://www.docker.com/products/docker-desktop)

### For Local:
- Python 3.10+
- Node.js 18+
- MongoDB Atlas account (free tier at https://www.mongodb.com/cloud/atlas)

## Features

- **Status**: Real-time system state (STABLE / TRANSITION / UNSTABLE / LOCK_IN)
- **Time to Action**: Cycles until critical window
- **Consequence Messaging**: "If ignored..." stakes for each state
- **Audit Trail**: All state transitions logged with timestamps
- **Multi-system**: View multiple systems side-by-side

## Demo Flow

1. Click **START** button (top right)
2. Watch **sys-DEMO** progress through states over 4+ minutes
3. Go to **Audit Trail** tab to see state transitions logged
4. Click on **sys-DEMO** row to see detailed decision information

## Architecture

- **Backend**: FastAPI + MongoDB (uvicorn)
- **Frontend**: React + Tailwind CSS (localhost:3000)
- **Intelligence**: SII Engine (structural instability detection)

## Deployment

To deploy to cloud (Heroku, Railway, Render):
1. Set `MONGO_URL` environment variable
2. Set `REACT_APP_BACKEND_URL` to your backend URL
3. Push Docker image to container registry

## Questions?

Check `/backend/routers/` for API endpoints
Check `/frontend/src/` for UI components
