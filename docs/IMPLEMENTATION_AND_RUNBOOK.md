# OpenVitality AI — Implementation, Execution, and Operations Runbook

This runbook provides a complete, end-to-end guide to plan, implement, configure, execute, operate, and scale OpenVitality AI. It is written to avoid common pitfalls and future-proof your deployment with security, safety, reliability, and performance best practices.

This document does not run any code. It explains exactly what to do and in what order, with all required commands, configuration, and operational procedures.

---

## 1) System Overview

- API Layer: FastAPI application (src/core/main.py)
- Orchestration: Session, routing, dialog, state
- Safety and Privacy: Safety filters, guardrails, PII/PHI scrubbing (src/safety/*)
- Intelligence: NLU, RAG, Agents, Knowledge retrieval (src/language/*, src/knowledge/*, src/agents/*)
- Voice: STT/TTS pipelines, Telephony (SIP/WebRTC)
- Dynamic API Management: PostgreSQL-backed registry of providers (src/core/api_manager.py + database/schema.sql)
- Observability: Logging, telemetry, metrics

---

## 2) Prerequisites

- OS: Linux (Ubuntu 22.04+ preferred) or macOS; Windows supported for dev
- Python: 3.11+
- System packages:
  - ffmpeg
  - libsndfile1
  - Tesseract OCR (optional; for document parsing)
  - git, curl, unzip
- Datastores:
  - PostgreSQL 13+ (for API registry)
  - Redis 6+ (for sessions/locks) — optional at first
- Optional:
  - Docker and Docker Compose (for containerized deployment)
  - Kubernetes (for production)

---

## 3) Repository Setup

1. Clone the repository
   - git clone <your_repo_url>
   - cd hai

2. Python environment
   - python -m venv .venv
   - source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

3. Install dependencies
   - pip install --upgrade pip
   - pip install -r requirements.txt
   - pip install -r requirements-dev.txt  # For development

4. Verify directories exist (created automatically as needed):
   - config/, database/, src/, docs/

---

## 4) Configuration and Secrets

1. Copy environment template and fill values
   - cp .env.example .env
   - Set the following (examples):
     - DATABASE_URL or API_MANAGER_DB_URL=postgresql://user:password@localhost:5432/openvitality
     - API_ENCRYPTION_KEY=<Fernet_key>  # Optional; if omitted, generated at runtime
     - API_MANAGER_POPULATE_FROM_YAML=1  # Optional; populate API registry from YAML
     - API_DB_YAML_PATH=./config/apis_database.yaml  # Default if not set

2. Feature flags (config/feature_flags.yaml)
   - Enable or disable capabilities safely:
     - enable_guardrails_output_filtering: false
     - enable_api_circuit_breakers: true
     - enable_degraded_mode_without_db: true
     - enable_tts_pre_warm: true
     - enable_rag_fusion: false
     - enable_metrics_endpoint: true

3. Logging configuration (config/logging_config.yaml)
   - Ensure JSON log format in production
   - Adjust log levels for core components and safety

4. Regional settings (config/regions/*.yaml)
   - Validate emergency numbers and locale-specific settings for your deployment

5. Prompts and protocols
   - config/prompts/*: tune personas and cultural nuances
   - config/protocols/*: validate emergency triage and dosage rules

---

## 5) Database Initialization (PostgreSQL)

1. Create database
   - createdb openvitality  # Or use psql/pgAdmin

2. Apply schema
   - psql -U <user> -d openvitality -f database/schema.sql

3. (Optional) Populate API registry from YAML
   - Ensure config/apis_database.yaml is present
   - Set API_MANAGER_POPULATE_FROM_YAML=1 in .env

4. Verify connectivity
   - psql -U <user> -d openvitality -c "SELECT now();"

Notes:
- The application supports degraded mode to keep working if the DB is unavailable (reads providers from YAML into in-memory registry).

---

## 6) Dynamic API Management (How It Works)

- The API Manager (src/core/api_manager.py) does:
  - Initialize asyncpg pool and aiohttp session
  - Populate registry from YAML into PostgreSQL
  - get_best_api(category, language, region) selects the best provider using DB function get_best_api
  - call_api(api_key, endpoint, data) handles headers, retries, rate limits, fallbacks
  - add_api_credential() encrypts API keys via Fernet; get_api_credential() decrypts on-demand
  - check_api_health() records health metrics and updates registry

- Recommended categories: stt, tts, llm, translation, vector_db, audio, telephony, medical_knowledge

- Best practices:
  - Maintain multiple providers for each category
  - Store credentials in api_credentials (encrypted)
  - Schedule health checks and monitor usage reports

---

## 7) Execution (Local Development)

Use either direct or containerized execution.

Option A: Direct (FastAPI + Uvicorn)
- source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
- export $(grep -v '^#' .env | xargs)  # Windows: set variables via PowerShell or setx
- uvicorn src.core.main:app --host 0.0.0.0 --port 8000 --reload

Endpoints:
- GET /health — liveness health with api_manager_initialized
- GET /docs — interactive API docs
- WS /v1/stream — WebSocket for streaming audio (when implemented)

Option B: Docker Compose
- docker compose up --build
- Confirm services (API, PostgreSQL, Redis, ChromaDB if used) are running

---

## 8) Execution (Production)

1. Container build and run
- Create production Dockerfile if not present (base: python:3.11-slim; install system deps; add user; expose port 8000)
- docker build -t openvitality-api:latest .
- docker run -d -p 8000:8000 --env-file .env openvitality-api:latest

2. Kubernetes (optional but recommended)
- Deploy manifests: infra/k8s/base/*
- Set readiness and liveness probes
- Use an Ingress with TLS (cert-manager for Let’s Encrypt)
- Configure resource requests/limits and horizontal autoscaling

3. Secrets
- Use sealed-secrets or external-secrets for API keys
- Never mount raw .env in production Git

---

## 9) Voice Pipeline Configuration

- STT (src/voice/stt/*):
  - Primary Whisper via Groq or other free-tier
  - Fallback: Google SpeechRecognition, Azure (free quota)
  - Configure provider API keys in DB credentials via API Manager

- TTS (src/voice/tts/*):
  - Primary: edge-tts (free)
  - Optional: ElevenLabs, Google Wavenet, Azure Neural, AWS Polly via API Manager
  - AudioCacheManager: ensure cache directory exists; set max size and enable pre-warm via feature flags

- Telephony (src/voice/telephony/*):
  - SIP trunk details from .env
  - WebRTC (aiortc) for browser-based calling

- Audio processing (src/voice/processing/*): noise suppression, echo cancellation, transcoding

---

## 10) Intelligence and RAG

- Embeddings: sentence-transformers/all-MiniLM-L6-v2 (free) or equivalent
- Vector DB: Chroma (local) or Pinecone (cloud)
- Retrieval fusion (optional): Enable if needed to combine vector search and BM25
- Reranking: Cross-Encoder (sentence-transformers) for better relevance
- Self-consistency (advanced): Validate generated answers against sources; abstain if unsupported

---

## 11) Safety, Privacy, and Compliance

- Guardrails and detectors (src/safety/*):
  - Input and output filtering: profanity, topic, jailbreak, violence, self-harm, hate, sexual content
  - PII/PHI scrubbing for logs (privacy/)
  - Compliance validators (HIPAA, GDPR, DPDP) — run and enforce in production

- Recommended defaults:
  - strict_safety_mode: true
  - enable_guardrails_output_filtering: false (log-only) at first, then true after validation

- Logging:
  - Use JSON format and scrub PII/PHI prior to writing logs

- Retention:
  - Follow data_retention_policy: audio 7 days, logs 90 days, transcripts 10 years (local laws may vary)

---

## 12) Observability and Metrics

- Logs: JSON logs with request_id and session_id
- Metrics: Enable /metrics endpoint if built; export Prometheus counters:
  - API selects/calls/failures/fallbacks
  - STT/TTS latencies and errors
  - Guardrails triggers and block counts
  - Queue depth, thread pools, memory usage

- Dashboards: Prometheus + Grafana with latency (p50/p95/p99), error rates, throughput

---

## 13) Testing Strategy

- Unit
  - src/core/*, src/agents/*, src/voice/*, src/knowledge/*
  - pytest, pytest-asyncio, pytest-cov

- Integration
  - STT/TTS to/from sample audio
  - RAG path end-to-end: query -> retrieve -> rerank -> generate -> citations

- End-to-end (e2e)
  - Full voice pipeline: audio in -> STT -> agent -> RAG -> TTS -> audio out

- Load testing
  - Locust: 100–1000 concurrent simulated calls

- Security testing
  - SQL injection tests, auth bypass, PII leakage attempts, jailbreak prompts

---

## 14) Security and Secrets Management

- Secrets are never hardcoded; stored in DB encrypted (Fernet) or in K8s secrets
- Rotate encryption keys periodically
  - Use key IDs; re-encrypt credentials in-place with the new key
- TLS termination at Ingress; HTTPS enforced end-to-end

---

## 15) Backup, DR, and Runbooks

- Database backups
  - Daily pg_dump/gzip; store in encrypted S3 bucket
- Vector store backups
  - Snapshot ChromaDB or Pinecone index periodically
- Disaster recovery drills
  - Restore database and vector store in staging; run smoke tests

- Incident playbooks
  - Provider outage: switch to fallback via API Manager; watch breaker state
  - Elevated latency: degrade gracefully (simpler models, shorter responses)
  - PII leak risk: force enable strict PII scrubber; rotate logs

---

## 16) Scaling and Performance

- Use horizontal scaling (K8s HPA) and multiple API pods
- Concurrency limits and backpressure to avoid overload
- Aggressive caching for TTS and RAG
- Streaming-first for STT and TTS; start generating before user finishes

---

## 17) Common Pitfalls and Avoidance

- API rate limits: rotate keys and cache results; rely on API Manager to select alternatives
- Audio format mismatch: always transcode to target formats; validate sample rate and channels
- Safety regressions: keep strict_safety_mode true; validate with safety test suite
- Dependencies drift: pin versions; rebuild containers regularly
- Secrets leaked: keep .env out of Git; use sealed/external secrets

---

## 18) Production Checklist

- [ ] DATABASE_URL set and reachable; schema applied
- [ ] API credentials stored via API Manager (encrypted)
- [ ] Feature flags set for your environment
- [ ] Safety filters enabled (strict mode) and validated
- [ ] Observability: JSON logs, Prometheus metrics, Grafana dashboards
- [ ] Backups configured and tested restore
- [ ] Health checks: /health and /readiness (if added) confirmed
- [ ] Load test meets SLOs (p95 latency, error rate)

---

## 19) Appendix — Suggested Commands (Non-Interactive)

Environment (Linux/macOS):
- python -m venv .venv
- source .venv/bin/activate
- pip install -r requirements.txt
- export $(grep -v '^#' .env | xargs)
- psql -U <user> -d openvitality -f database/schema.sql
- uvicorn src.core.main:app --host 0.0.0.0 --port 8000 --reload

Environment (Windows PowerShell):
- python -m venv .venv
- .\.venv\Scripts\Activate.ps1
- pip install -r requirements.txt
- $env:DATABASE_URL = "postgresql://user:password@localhost:5432/openvitality"
- uvicorn src.core.main:app --host 0.0.0.0 --port 8000 --reload

Docker (optional):
- docker build -t openvitality-api:latest .
- docker run -d --env-file .env -p 8000:8000 openvitality-api:latest

---

## 20) Final Notes

- This runbook is intentionally exhaustive and conservative for healthcare use. Start in safe mode (strict safety ON, guardrails output filtering OFF), validate, then progressively enable advanced features.
- The application includes degraded mode and fallbacks to maintain service during partial outages. Always monitor metrics and logs to rapidly identify regressions.
- Keep all dependencies pinned, run CI checks on every change, and maintain strict observability to ensure world-class reliability and safety.
