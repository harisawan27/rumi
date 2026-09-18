---
name: Hugging Face Spaces Gradio ZeroGPU and Vercel Migration
description: Migrated backend to Hugging Face Spaces free Gradio SDK with ZeroGPU and frontend to Vercel, with GitHub Actions Trusted Publishers CI/CD.
type: general
stage: green
date: 2026-09-18
surface: agent
model: gemini-3.8-flash
feature: general
branch: master
user: Haris
---

## Summary

Migrated Project Rumi backend from Google Cloud Platform to Hugging Face Spaces (free Gradio SDK + ZeroGPU) and configured the frontend for Vercel deployment with automated CI/CD via Hugging Face Trusted Publishers.

### 1. Hugging Face Spaces Backend Entrypoint (`backend/app.py`)
- Created `app.py` combining Gradio Blocks UI and the existing FastAPI server.
- Safe ZeroGPU loader with `import spaces` and `@spaces.GPU` decorator.
- ZeroGPU diagnostic playground function for dynamic CUDA allocation testing.
- Interactive Gradio dashboard with System Diagnostics, ZeroGPU Playground, and Frontend integration guide.
- Preserved all REST API and WebSocket routes using `gr.mount_gradio_app(fastapi_app, demo, path="/")`.
- Default server port configured for 7860.

### 2. Hugging Face Space Metadata & Dependencies
- `backend/README.md`: YAML frontmatter metadata specifying `sdk: gradio`, `sdk_version: 5.20.0`, `app_file: app.py`.
- `backend/packages.txt`: Added Debian dependencies `ffmpeg`, `libgl1`, `libglib2.0-0` required by OpenCV/MediaPipe/FER.
- `backend/requirements.txt`: Added `gradio>=5.0.0` and `torch>=2.2.0`.

### 3. Backend Resiliency & CORS
- `backend/src/api/main.py`: Enhanced CORS middleware to allow all `https://*.vercel.app` domains dynamically and parse comma-separated `FRONTEND_URL`.
- `backend/src/memory/firestore_client.py`: Made `FIREBASE_SERVICE_ACCOUNT_JSON` parse both raw JSON and base64 strings cleanly, with auto-discovery fallback for local service account files.

### 4. Automated CI/CD (`.github/workflows/huggingface.yml`)
- Configured GitHub Actions workflow for automatic keyless deployment using Hugging Face Trusted Publishers (OIDC).
- Granted `permissions: id-token: write, contents: read`.
- Automatically uploads `./backend` to `harisawan07/rumi` Space using `hf upload`.
- Scoped to `HF_OIDC_RESOURCE: spaces/harisawan07/rumi` with fallback for `HF_TOKEN`.
- Updated `deploy.yml` to manual trigger (`workflow_dispatch`) to avoid conflicts.

### 5. Vercel Configuration & Secrets Guide
- Created `frontend/vercel.json` and root `vercel.json` for Next.js detection.
- Created `docs/DEPLOYMENT_SECRETS_GUIDE.md` containing all exact secrets, variables, and setup steps.

## Files Modified / Created
- `backend/app.py` (New)
- `backend/README.md` (New)
- `backend/packages.txt` (New)
- `backend/requirements.txt` (Modified)
- `backend/src/api/main.py` (Modified)
- `backend/src/memory/firestore_client.py` (Modified)
- `.github/workflows/huggingface.yml` (New)
- `.github/workflows/deploy.yml` (Modified)
- `frontend/vercel.json` (New)
- `vercel.json` (New)
- `docs/DEPLOYMENT_SECRETS_GUIDE.md` (New)
