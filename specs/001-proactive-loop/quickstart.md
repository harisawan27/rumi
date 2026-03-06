# Quickstart: Identity-Aware Proactive Loop

**Feature**: `001-proactive-loop`
**Date**: 2026-03-06

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- A webcam connected to your machine
- Firebase project with:
  - Google Auth enabled
  - Firestore database (Native mode)
  - Service account key downloaded
- Google Cloud project with:
  - Gemini API enabled
  - Cloud Build + Cloud Run APIs enabled

## 1. Clone & Configure

```bash
git clone <repo-url>
cd mirrat
git checkout 001-proactive-loop

# Copy env template and fill in your values
cp .env.example .env
```

Required `.env` values:

```
# Gemini
GEMINI_API_KEY=<your_gemini_api_key>

# Firebase Admin (backend)
FIREBASE_SERVICE_ACCOUNT_PATH=./backend/firebase-service-account.json

# Firebase Client (frontend)
NEXT_PUBLIC_FIREBASE_API_KEY=<from Firebase console>
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=<project-id>

# App config
AUTHORISED_USER_UID=uid_haris_001
SESSION_SUMMARY_DEPTH=3
IDLE_TIMEOUT_MINUTES=30
BACKEND_URL=http://localhost:8000
```

Place your Firebase service account JSON at `backend/firebase-service-account.json`
(this file is gitignored).

## 2. Seed Firestore (First Run Only)

```bash
cd backend
pip install -r requirements.txt
python src/identity/seed_identity.py
```

This creates the Haris Core Identity document in Firestore.

## 3. Run Locally with Docker Compose

```bash
docker-compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

## 4. Run Without Docker (Development)

**Backend**:
```bash
cd backend
pip install -r requirements.txt
uvicorn src.api.main:app --reload --port 8000
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```

## 5. Verify the Setup

1. Open `http://localhost:3000`
2. Click "Sign in with Google" — use the authorised Haris account
3. Verify: system displays "Haris" and enters observation mode (camera indicator turns green)
4. Check Firestore console: a new `sessions` document should appear under `users/{uid}`
5. Wait 45 seconds: backend logs should show "Watchman cycle: state=focused confidence=0.XX"

## 6. Run Tests

```bash
# Backend
cd backend
pytest tests/ -v

# Frontend
cd frontend
npm test
```

## 7. Deploy to Google Cloud Run

```bash
# Ensure gcloud CLI is configured
gcloud auth login
gcloud config set project <your-project-id>

# Manual deploy (CI/CD does this automatically on push to main)
cd backend
gcloud builds submit --config ../cloudbuild.yaml
```

After deployment, update `BACKEND_URL` in the frontend `.env.production` to the Cloud Run URL.

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| Camera not detected | Check `cv2.VideoCapture(0)` index; try index 1 for external webcam |
| Gemini WebSocket disconnects | Check `GEMINI_API_KEY` validity; increase reconnect backoff |
| Firebase 403 on Firestore | Verify service account has Firestore read/write role; check security rules |
| Session not starting | Confirm `AUTHORISED_USER_UID` matches the UID of the Google account used to sign in |
| Auto-Summarizer not running | Check backend logs for `auto_summarizer` task; Firestore write permissions |
