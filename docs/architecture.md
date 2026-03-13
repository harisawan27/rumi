# Project Rumi — System Architecture

```mermaid
graph TB
    subgraph User["User (Desktop)"]
        CAM[Webcam]
        SCREEN[Screen]
    end

    subgraph Frontend["Next.js Frontend (Firebase Hosting)"]
        SIGNIN[Sign-In Page<br/>page.tsx]
        DASH[Dashboard<br/>dashboard/page.tsx]
        OI[ObservationIndicator]
        IC[InterventionCard]
        PB[PauseButton]
    end

    subgraph Backend["Python Backend (Cloud Run)"]
        API[FastAPI<br/>api/main.py]
        SM[SessionManager<br/>session_manager.py]
        WM[StateMonitor<br/>state_monitor.py]
        TA[FrustrationTracker<br/>trigger_a.py]
        TB[CodingBlockTracker<br/>trigger_b.py]
        GLC[GeminiLiveClient<br/>live_client.py]
        PB2[PromptBuilder<br/>prompt_builder.py]
        IL[interaction_log.py]
        AS[AutoSummarizer<br/>auto_summarizer.py]
        AUTH[firebase_auth.py]
        FS[firestore_client.py]
        ID[identity_loader.py]
    end

    subgraph GCP["Google Cloud Platform"]
        GEMINI_LIVE[Gemini Multimodal<br/>Live API<br/>WebSocket]
        GEMINI_FLASH[Gemini 2.0 Flash<br/>REST]
        FIRESTORE[(Firebase Firestore)]
        CB[Cloud Build CI/CD]
        CR[Cloud Run]
        FH[Firebase Hosting]
    end

    %% User → Frontend
    CAM -->|15fps JPEG| DASH
    SCREEN --> User

    %% Frontend ↔ Backend
    SIGNIN -->|POST /auth/verify| API
    DASH -->|GET /identity| API
    DASH -->|WS /ws/observe<br/>frames + messages| API
    API -->|intervention events| IC
    PB -->|PUT /session/pause-resume| API

    %% Backend internal
    API --> SM
    SM --> WM
    WM --> TA
    WM --> TB
    SM --> GLC
    SM --> PB2
    SM --> IL
    SM --> AS
    API --> AUTH
    AUTH --> FS
    SM --> FS
    IL --> FS
    AS --> FS
    ID --> FS

    %% Backend → Gemini
    GLC -->|"JPEG frames (ephemeral)<br/>PRIVACY: never persisted"| GEMINI_LIVE
    GEMINI_LIVE -->|state JSON + text| GLC
    AS -->|interaction log JSON| GEMINI_FLASH
    GEMINI_FLASH -->|2-sentence summary| AS

    %% Backend → Firestore
    FS <-->|Core Identity<br/>Sessions<br/>Interactions<br/>Session Summaries| FIRESTORE

    %% CI/CD
    CB -->|docker build + push| CR
    CB -->|firebase deploy| FH

    style GEMINI_LIVE fill:#4285F4,color:#fff
    style GEMINI_FLASH fill:#4285F4,color:#fff
    style FIRESTORE fill:#FF6D00,color:#fff
    style CB fill:#34A853,color:#fff
    style CR fill:#34A853,color:#fff
    style FH fill:#FF6D00,color:#fff
```

## Data Flow: Ephemeral vs Persisted

| Data | Path | Persisted? |
|------|------|-----------|
| Video frames | Webcam → Frontend → Backend → Gemini WebSocket | **Never** — ephemeral only |
| State analysis | Gemini → StateMonitor (in-memory) | **Never** |
| Intervention text | Gemini → InterventionCard | Only the text, in Firestore |
| Interaction Summary | Backend → Firestore `interactions/` | ✅ Text only |
| Session Summary | AutoSummarizer → Firestore `session_summaries/` | ✅ 2 sentences |
| Core Identity | Firestore `users/` | ✅ Seeded once |

## Key Architectural Decisions

1. **Single Gemini Live WebSocket** per session — avoids reconnect latency; preserves context
2. **Ephemeral frame processing** — OpenCV → base64 → WebSocket → discarded; zero disk/DB writes
3. **Firestore sub-collection hierarchy** — `users/{uid}/sessions/{sid}/interactions/{iid}` + `users/{uid}/session_summaries/{sum}`
4. **AutoSummarizer uses Gemini 2.0 Flash** (non-streaming) — Live API session closed at end; Flash is cheaper and sufficient
5. **Trigger A priority** over Trigger B when both fire simultaneously — Trigger B deferred to next 45s cycle
