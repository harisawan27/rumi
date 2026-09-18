# 🚀 Project Rumi — Hugging Face & Vercel Deployment Cheat Sheet

This guide contains the exact secrets, configuration claims, and environment variables needed to get your Rumi backend on **Hugging Face Spaces (Gradio + ZeroGPU)** and frontend on **Vercel** working on the first shot.

---

## 1. Hugging Face Space: Trusted Publishers (CI/CD)

To allow GitHub Actions to build and push your backend automatically on every commit without storing a static token:

1. Open your Space settings:
   🔗 **`https://huggingface.co/spaces/harisawan07/rumi/settings`**
2. Scroll to **Trusted Publishers** -> Click **Add Publisher**.
3. Select **GitHub Actions** and fill in these exact claims:
   - **Repository**: `harisawan27/rumi`
   - **Branch**: `master`
   - **Workflow filename**: `huggingface.yml`
4. Click **Add Publisher**.

*(Optional fallback: If you prefer using a static token, you can also add a secret named `HF_TOKEN` in your GitHub repository secrets at `https://github.com/harisawan27/rumi/settings/secrets/actions` with a Write token from `https://huggingface.co/settings/tokens`).*

---

## 2. Hugging Face Space: Backend Secrets & Variables

In your Space settings at **`https://huggingface.co/spaces/harisawan07/rumi/settings`**, scroll to **Variables and secrets** -> **New secret**:

| Secret Name | Required | Value / Instructions |
|---|---|---|
| `GEMINI_API_KEY` | **Yes** | Your Google Gemini API Key from Google AI Studio. |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | **Yes** | Either paste the base64 string from your `firebase-sa-base64.txt` OR the raw JSON from `firebase-sa.json`. Both formats are supported automatically! |
| `FIREBASE_STORAGE_BUCKET` | Optional | `midyear-acre-322217.firebasestorage.app` |
| `FRONTEND_URL` | Optional | Your Vercel domain (e.g. `https://your-rumi-app.vercel.app`). *Note: All `https://*.vercel.app` domains are automatically allowed by CORS.* |

---

## 3. Vercel: Frontend Deployment & Environment Variables

### How to deploy on Vercel:
1. Go to **[vercel.com/new](https://vercel.com/new)** and import your GitHub repository: `harisawan27/rumi`.
2. Under **Root Directory**, click **Edit** and select:
   👉 **`frontend`**
3. Under **Environment Variables**, add the following:

| Variable Name | Value |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | `https://harisawan07-rumi.hf.space` |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | *(Copy value from your local `frontend/.env.local`)* |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | `midyear-acre-322217.firebaseapp.com` |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | `midyear-acre-322217` |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | `midyear-acre-322217.firebasestorage.app` |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | `906886399946` |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | `1:906886399946:web:0bf53198defa38d2e3b133` |

4. Click **Deploy**.

---

## 4. Verification Checkpoints

Once deployed:
1. **Check Hugging Face Space**:
   - Visit `https://huggingface.co/spaces/harisawan07/rumi`.
   - You will see the Gradio Dashboard:
     - Check the **System Diagnostics** tab to see green status indicators.
     - Open the **ZeroGPU Playground** tab and click **Run on ZeroGPU** to confirm dynamic GPU allocation.
2. **Check Vercel Frontend**:
   - Open your Vercel URL.
   - Open browser developer tools -> Network / Console tab.
   - Start an observation session; you should see WebSocket connecting to `wss://harisawan07-rumi.hf.space/ws/observe`.
