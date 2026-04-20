# Koala Deployment Guide

This project is split into:

- `frontend`: React + Vite static app
- `backend`: FastAPI API
- MongoDB database
- Groq API for orchestration

## 1. What you need

Backend environment variables:

- `GROQ_API_KEY`
- `MONGO_URI`
- `SECRET_KEY`

Frontend environment variables:

- `VITE_API_BASE_URL`

## 2. Deploy the backend

Recommended platforms:

- Render
- Railway
- Fly.io
- Any VPS with Python installed

Important: deploy the backend from the `backend` directory, because the app imports local modules like `database` and `auth`.

Backend settings:

- Root directory: `backend`
- Install command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Set these backend environment variables in your host:

- `GROQ_API_KEY=...`
- `MONGO_URI=...`
- `SECRET_KEY=...`

For production, use MongoDB Atlas or another hosted MongoDB instance for `MONGO_URI`.

## 3. Deploy the frontend

Recommended platforms:

- Vercel
- Netlify
- Cloudflare Pages

Frontend settings:

- Root directory: `frontend`
- Install command: `npm ci`
- Build command: `npm run build`
- Output directory: `dist`

Set this frontend environment variable:

- `VITE_API_BASE_URL=https://your-backend-domain`

Because this is a React SPA using `BrowserRouter`, add a rewrite so all routes fall back to `index.html`.

Examples:

- Vercel: rewrite `/(.*)` to `/index.html`
- Netlify: `/* /index.html 200`

## 4. Typical production setup

1. Create a hosted MongoDB database.
2. Deploy `backend` and copy its public URL.
3. Set `VITE_API_BASE_URL` in the frontend to that backend URL.
4. Deploy `frontend`.
5. Test signup, signin, session loading, and plan execution.

## 5. Local production build checks

Frontend:

```bash
cd frontend
npm run build
```

Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 4000
```

## 6. Notes

- The frontend previously used a hardcoded localhost API URL; it now supports `VITE_API_BASE_URL`.
- CORS is currently open to all origins in the backend. That works for deployment, but you may want to restrict it later to your frontend domain.
- The frontend production build currently succeeds, but Vite reports a large JS bundle warning. That does not block deployment.
