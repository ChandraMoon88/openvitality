# OpenVitality AI — Visual Architecture (No Code)

This document presents visual, text-based (ASCII) architecture diagrams that you can read in any Markdown viewer without rendering code or Mermaid. It also maps each major file/folder to its purpose directly inside the visuals.

Tip: View with a monospace font for best alignment.

-------------------------------------------------------------------------------
OVERVIEW — END‑TO‑END DATA FLOW
-------------------------------------------------------------------------------

 [Caller / Patient]                      [Web User]
        |                                      |
        v                                      v
  +----------------+                     +--------------+
  |   SIP / PBX    |<------------------->|  WebRTC Peer |
  +----------------+         (audio)     +--------------+
           | RTP (PCMU/Opus)                     |
           v                                      v
  +-----------------------+                +------------------------+
  |  SIP Audio Bridge     |<-------------->| FastAPI (HTTP/WebSocket)|
  |  (src/voice/telephony/|   PCM frames   |  src/core/main.py       |
  |   sip_audio_bridge.py)|                +------------------------+
  +----------+------------+                           |
             |                                       (Middleware)
             v                                        |
  +-----------------------+      +--------------------+-------------------+
  | VAD / Streaming STT   |----->|  Guardrails (Safety & Privacy)         |
  | src/voice/stt/*.py    | text |  src/safety/* (pre/post filters)       |
  +-----------------------+      +--------------------+-------------------+
                                                      |
                                                      v
                                           +----------+-----------+
                                           |   Orchestrator       |
                                           |   src/core/          |
                                           |   orchestrator.py    |
                                           +----------+-----------+
                                                      |
                                  +-------------------+-------------------+
                                  |                                       |
                                  v                                       v
                       +--------------------+                   +----------------------+
                       | Dialogue/Context   |                   |  Intent/Language     |
                       | src/core/dialogue_ |                   |  src/language/*      |
                       | manager.py, router |                   |  + core/intent_*     |
                       +---------+----------+                   +----------+-----------+
                                 |                                         |
                                 v                                         v
                         +-------+-------------------+         +----------+------------+
                         |            AGENTS         |<--------|  RAG (Knowledge)     |
                         | src/agents/*              |  ctx    |  src/knowledge/*     |
                         | (medical/admin/emergency) |  docs   +----------+-----------+
                         +---------------+-----------+                    |
                                         |                                 |  (Embeddings, Vector DB,
                                         | response text                    |   Reranker, Sources)
                                         v                                 v
                                 +-------+--------------------+   +--------+----------------+
                                 |    TTS (Audio Synthesis)  |   |  Telemetry/Logs/Metrics |
                                 |    src/voice/tts/*        |   |  src/core/telemetry_*   |
                                 +---------------+-----------+   +-------------------------+
                                                 |
                                       audio     v
                                 +---------------+-----------+
                                 |      SIP Audio Bridge    |
                                 |      (encode/stream)     |
                                 +---------------+-----------+
                                                 |
                                                 v
                                          +------+------+
                                          |  Caller     |
                                          +-------------+

-------------------------------------------------------------------------------
CORE PLATFORM — FILES BY SUBSYSTEM (WHY USED)
-------------------------------------------------------------------------------

FASTAPI API LAYER (entrypoints, lifecycle)
- src/core/main.py ........... Application entrypoint (startup/shutdown, /health, chat/voice/ws). Initializes providers (e.g., API Manager).
- src/core/error_handler_global.py ... Global exception handling with safe responses (no stack traces to user).
- src/core/system_health_monitor.py ... Periodic health checks and readiness signals.

ORCHESTRATION & CONVERSATION
- src/core/orchestrator.py .... Brain/dispatcher: routes requests, applies timeouts, manages workflows.
- src/core/dialogue_manager.py . Multi-turn state, slot filling, confirmations.
- src/core/context_router.py ... Sticky routing; maps intents to the right agent.
- src/core/state_machine.py .... Formal states for robust conversation flows.
- src/core/session_manager.py .. Sessions in cache (e.g., Redis), TTL, context memory.
- src/core/priority_queue.py ... Emergency-first prioritization and fairness.
- src/core/thread_pool_manager.py Parallel I/O or CPU-bound processing.
- src/core/task_scheduler.py ... Reminders and delayed tasks.
- src/core/memory_manager.py ... Short/long-term memory consolidation.

SAFETY, PRIVACY, COMPLIANCE (defense‑in‑depth)
- src/safety/guardrails_core.py ........... Master gate for input/output filtering decisions.
- src/safety/filters/* .................... Specialized detectors (violence, self-harm, hate, sexual content).
- src/safety/profanity_filter.py .......... Professional language enforcement.
- src/safety/topic_blacklist.py ........... Keep on medical topics (no politics, etc.).
- src/safety/jailbreak_defense.py ......... Detect prompt injection attempts.
- src/safety/hallucination_detector.py .... Validate claims against RAG evidence.
- src/safety/human_handoff_trigger.py ..... Escalate to human when needed.
- src/safety/privacy/pii_scrubber.py ...... Remove PII from logs.
- src/safety/privacy/phi_masker.py ........ HIPAA safe‑harbor masking (PHI).
- src/safety/privacy/consent_manager.py ... Track user consent states.
- src/safety/privacy/right_to_be_forgotten.py ... Data deletion workflow.
- src/safety/privacy/data_retention_policy.py ... Retention rules for audio/logs/records.
- src/safety/compliance/* ................. HIPAA/GDPR/DPDP validators (startup/ops checks).

LANGUAGE UNDERSTANDING (NLU)
- src/language/nlu_engine.py ........... Full pipeline: detect -> tokenize -> normalize -> entities -> sentiment -> intent.
- src/language/tokenizer_multilingual.py Tokenization per language.
- src/language/code_mixer_normalizer.py  Normalize code‑mixed text (e.g., Hinglish/Spanglish).
- src/language/code_mix/spanglish_processor.py ..... Spanish+English support.
- src/language/entity_extractor_medical.py Medical entities (symptom, drug, dosage, duration).
- src/language/sentiment_analyzer.py ..... Emotional state detection.
- src/language/intent_parser.py .......... Intent rules/zero‑shot fallback.
- src/language/translator_api.py ........ Translation manager.
- src/language/locales/en_handler.py ..... Locale‑specific formatting for English.

KNOWLEDGE & RAG (accuracy, citations)
- src/knowledge/rag_orchestrator.py ..... Orchestrates retrieval -> rerank -> LLM -> answer with citations.
- src/knowledge/retrieval_ranker.py ..... Cross‑encoder reranking for precision.
- src/knowledge/embedding_openai.py ..... Free embedding alternative (HuggingFace models).
- src/knowledge/vector_db_chroma.py ..... Local vector store (ChromaDB) for low‑cost RAG.
- src/knowledge/vector_db_pinecone.py ... Cloud vector store (Pinecone) for scaling.
- src/knowledge/chunking_strategy.py ..... Chunking strategy to preserve semantics.
- src/knowledge/document_loader_pdf.py ... PDF/OCR loader for medical documents.
- src/knowledge/sources/* ............... Data connectors: FDA, CDSCO, WHO, ICD‑10, SNOMED, RxNorm.

AGENTS (medical, admin, emergency, engagement)
- src/agents/base_agent.py ............... Standard interface (process_input, memory, persona, safety hook).
- src/agents/agent_factory.py ............ Registry/pool for agent creation and reuse.
- src/agents/medical/* ................... GP, cardiology, pediatrics, psychiatry, lab results, chronic care.
- src/agents/admin/* ..................... Booking, rescheduling, cancelations, billing, insurance verification.
- src/agents/emergency/* ................. Emergency detection and ambulance dispatch.
- src/agents/engagement/* ................ Wellness coach and feedback collection.

VOICE (real‑time STT/TTS/audio)
- src/voice/stt/* ........................ Whisper/Google/Azure STT + streaming + VAD + language ID.
- src/voice/tts/* ........................ Edge TTS (free), ElevenLabs (selective), SSML control, audio cache.
- src/voice/telephony/* .................. SIP trunk, audio bridge, IVR, codec negotiation, WebRTC server.
- src/voice/processing/* ................. Noise suppression, echo cancellation, codec transcoding, bandwidth adaptation.

DYNAMIC PROVIDER MANAGEMENT (free‑tier first)
- src/core/api_manager.py ................. PostgreSQL‑backed API registry; selects best provider per category; handles rate limits, retries, failover; stores encrypted credentials.
- database/schema.sql ..................... Tables for registry, endpoints, credentials, usage logs, health checks, rate limits, rules.

CONFIGURATION
- config/settings.yaml .................... App settings (LLM model, audio params, timeouts).
- config/feature_flags.yaml ............... Toggle advanced features (guardrails output filtering, circuit breakers, degraded mode, metrics, etc.).
- config/logging_config.yaml .............. JSON logging, filters, handlers.
- config/prompts/* ........................ Personas and cultural nuances.
- config/regions/* ........................ Locale/regulatory details.
- config/protocols/* ...................... Triage and dosage safety protocols.

-------------------------------------------------------------------------------
SUBSYSTEM VISUALS — DEEPER DIVE
-------------------------------------------------------------------------------

VOICE PIPELINE (Real‑Time)

 [Mic/Caller] --> [SIP / WebRTC] --> [SIP Audio Bridge] --> [VAD] --> [Streaming STT]
         |                                                    (segments)
         |                                                     |
         |                                                     v
         |<------------------------- [TTS + Audio Cache] <-----|
         |                           (PCM/PCMU/Opus)           |
         v                                                     v
     [Playout] <---------[Codec Transcoder + Jitter Buffer]-----> [Network]

- Why: Ensures robust capture, transcription, synthesis, and playback under varying network conditions with minimal latency.

SAFETY & PRIVACY GUARDRAILS

 [User Text/Audio] -> [PII/PHI Scrub] -> [Topic/Profanity] -> [Jailbreak/Abuse] -> [Hallucination Check] -> [Output Filter]

- Why: Medical safety through layered checks (input and output), ensuring lawful, respectful, and correct responses.

DYNAMIC API SELECTION

 [Agent/Component] -> [API Manager] -> [PostgreSQL Registry] -> [Best Provider + Credentials]
                                         |               \
                                         |                -> [Health, Rate Limits, Usage]
                                         -> [Endpoints]

- Why: Vendor‑agnostic, budget‑aware, fault‑tolerant selection of external APIs (STT, TTS, LLM, translation, etc.).

RAG ANSWERING

 [Question] -> [Embedding] -> [Vector Search] -> [Rerank] -> [LLM Synthesis w/ Citations] -> [Confidence]

- Why: Evidence‑grounded answers with traceable sources to prevent unsafe hallucinations.

-------------------------------------------------------------------------------
HOW TO EXTEND SAFELY (VISUAL GUIDE)
-------------------------------------------------------------------------------

Add a new Agent
- Create file in src/agents/<domain>/*.py
- Register in src/agents/agent_factory.py and route in src/core/context_router.py

Add a new Provider (STT/TTS/LLM)
- Update config/apis_database.yaml
- Populate into PostgreSQL (database/schema.sql and app init)
- Optionally add fallback endpoints in api_manager

Add a new Safety Rule
- Implement detector in src/safety/filters/*
- Register in src/safety/guardrails_core.py

Add a new Knowledge Source
- Implement under src/knowledge/sources/*
- Ingest via document_loader_pdf + chunking + vector_db + indexing

-------------------------------------------------------------------------------
LEGEND
-------------------------------------------------------------------------------
- Rectangles = components/services
- Brackets [ ] = runtime artifacts or user endpoints
- Files/paths shown inline point to the primary implementation location
- Arrows indicate the direction of request/response data flow

-------------------------------------------------------------------------------
TIP
-------------------------------------------------------------------------------
- Keep this document updated when adding new files to maintain a single‑source visual reference for onboarding, audits, and architecture reviews.
