import os

# Prevent premature CUDA initialization by external libraries before spaces loads
os.environ.setdefault("NUMBA_DISABLE_CUDA", "1")

# Must import spaces at the top level for ZeroGPU environment
try:
    import spaces
except ImportError:
    class _DummySpaces:
        def GPU(self, *args, **kwargs):
            if len(args) == 1 and callable(args[0]):
                return args[0]
            def decorator(func):
                return func
            return decorator
    spaces = _DummySpaces()

# Top-level dummy GPU function to satisfy ZeroGPU startup scanner
@spaces.GPU(duration=1)
def dummy_gpu():
    return None

import sys
import json
import logging
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rumi-space")

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import torch
import gradio as gr
from fastapi.middleware.cors import CORSMiddleware

# Import core FastAPI application and startup event
from src.api.main import app as fastapi_app, _startup


# ---------------------------------------------------------------------------
# ZeroGPU-Accelerated Functions
# ---------------------------------------------------------------------------

@spaces.GPU(duration=60)
def zerogpu_diagnostic_tensor_check(n: float = 42.0):
    """Dynamically allocated on ZeroGPU when invoked."""
    is_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if is_cuda else "cpu")
    x = torch.tensor([float(n)], dtype=torch.float32, device=device)
    # Perform sample mathematical tensor transformation
    res = torch.pow(x, 2) + torch.sin(x)
    
    device_name = torch.cuda.get_device_name(0) if is_cuda else "CPU (ZeroGPU not engaged or outside GPU slice)"
    
    output = {
        "status": "ZeroGPU Acceleration Active" if is_cuda else "Standard CPU Execution",
        "device": str(device),
        "device_name": device_name,
        "input": float(n),
        "computed_tensor_result": float(res.item()),
    }
    return json.dumps(output, indent=2)


def get_system_health_report():
    """Check status of all backend subsystems."""
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_firebase = bool(
        os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or
        os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH") or
        os.path.isfile(os.path.join(backend_dir, "firebase-service-account.json")) or
        os.path.isfile(os.path.join(backend_dir, "..", "firebase-service-account.json"))
    )
    is_zerogpu = os.getenv("SPACES_ZERO_GPU") == "1"

    report = f"""
### 🪞 Project Rumi — Core Engine Status

| Component | Status | Details |
|---|---|---|
| **FastAPI REST API** | 🟢 Running | Full API mounted & ready |
| **WebSocket Observer** | 🟢 Listening | `wss://harisawan07-rumi.hf.space/ws/observe` |
| **Google Gemini Live API** | {'🟢 Ready' if has_gemini else '🔴 Missing Key'} | {'GEMINI_API_KEY set' if has_gemini else 'Set GEMINI_API_KEY in Space Secrets'} |
| **Firebase / Firestore** | {'🟢 Connected' if has_firebase else '🟡 Awaiting Credentials'} | {'Credentials found' if has_firebase else 'Set FIREBASE_SERVICE_ACCOUNT_JSON in Space Secrets'} |
| **ZeroGPU Environment** | {'⚡ Active (NVIDIA GPU)' if is_zerogpu else '🖥️ CPU / Ready for GPU allocation'} | Dynamically provisions CUDA via `@spaces.GPU` |
| **PyTorch & CUDA Runtime** | {'🟢 CUDA Ready' if torch.cuda.is_available() else '🟡 Standby'} | Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU (GPU provisioned on request)'} |
"""
    return report


# ---------------------------------------------------------------------------
# Gradio Dashboard UI
# ---------------------------------------------------------------------------

theme = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="purple",
    neutral_hue="slate",
)

with gr.Blocks(theme=theme, title="Project Rumi — AI Core Backend") as demo:
    # Explicitly bind the dummy GPU function so the ZeroGPU event scanner detects it immediately
    dummy_btn = gr.Button(visible=False)
    dummy_btn.click(fn=dummy_gpu)

    gr.Markdown(
        """
        # 🪞 Project Rumi — Backend Control & ZeroGPU Engine
        **Autonomous Empathetic AI Life Mirror** • Hosted on Hugging Face Spaces (Gradio + ZeroGPU)
        """
    )

    with gr.Tabs():
        with gr.TabItem("🛰️ System Diagnostics"):
            status_box = gr.Markdown(value=get_system_health_report())
            refresh_btn = gr.Button("🔄 Refresh System Health", variant="primary")
            refresh_btn.click(fn=get_system_health_report, outputs=[status_box])

        with gr.TabItem("⚡ ZeroGPU Playground"):
            gr.Markdown(
                """
                ### ZeroGPU Dynamic Hardware Check
                Test dynamic NVIDIA GPU allocation on Hugging Face Spaces. When you trigger the calculation,
                `@spaces.GPU` automatically spins up a CUDA tensor runner.
                """
            )
            with gr.Row():
                num_input = gr.Number(value=42.0, label="Input Number for Tensor Calculation")
                run_btn = gr.Button("🚀 Run on ZeroGPU", variant="primary")
            gpu_output = gr.Code(label="GPU Execution Output", language="json")
            run_btn.click(fn=zerogpu_diagnostic_tensor_check, inputs=[num_input], outputs=[gpu_output])

        with gr.TabItem("🌐 Frontend & API Integration"):
            gr.Markdown(
                """
                ### Vercel Frontend Connection Guide

                Your Next.js frontend deployed on Vercel communicates directly with this Space:

                #### 1. Endpoints
                - **HTTP Base URL**: `https://harisawan07-rumi.hf.space`
                - **WebSocket Stream**: `wss://harisawan07-rumi.hf.space/ws/observe`
                - **Health Endpoint**: `https://harisawan07-rumi.hf.space/health`

                #### 2. Vercel Environment Variables
                In your Vercel Project Settings under **Environment Variables**, set:
                ```env
                NEXT_PUBLIC_BACKEND_URL=https://harisawan07-rumi.hf.space
                ```
                *(Plus your standard `NEXT_PUBLIC_FIREBASE_*` variables)*

                #### 3. CORS Policy
                The backend automatically accepts requests from:
                - `https://*.vercel.app` (All production & preview deployments)
                - `http://localhost:3000`
                - Any domain specified in the `FRONTEND_URL` secret
                """
            )

# Enable queueing for Gradio (essential for ZeroGPU event routing)
demo.queue()

# Ensure Gradio's internal FastAPI app is instantiated
if not hasattr(demo, "app") or demo.app is None:
    demo.app = gr.routes.App.create_app(demo)

# Mount all FastAPI endpoints (/health, /auth/verify, /identity, /session/*, /canvas/*, /ws/observe)
# directly onto Gradio's internal FastAPI app
demo.app.include_router(fastapi_app.router)

# Register backend startup event on the Gradio app
demo.app.on_event("startup")(_startup)

# Configure CORS on the Gradio app for Vercel
frontend_origins = ["http://localhost:3000", "http://localhost:3001", "http://localhost:8000", "http://localhost:7860"]
frontend_env = os.getenv("FRONTEND_URL", "")
if frontend_env:
    frontend_origins.extend([origin.strip() for origin in frontend_env.split(",") if origin.strip()])

demo.app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Entrypoint for Hugging Face Spaces (ZeroGPU + Gradio)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting Rumi Core on port 7860 via demo.launch()...")
    # In ZeroGPU, demo.launch() triggers the dynamic GPU broker handshake
    # and exposes both the Gradio UI and all mounted FastAPI routes on 0.0.0.0:7860.
    demo.launch(server_name="0.0.0.0", server_port=7860)
