# CIVIS-CORE: Production Deployment & Operations Guide

## 1. Overview
CIVIS-CORE is packaged as a lightweight, non-root, multi-stage Docker container exposing REST API endpoints, WebSocket event streaming, and Prometheus metrics.

```text
┌────────────────────────────────────────────────────────┐
│               Client / Operator Console                │
└───────────────────────────┬────────────────────────────┘
                            │  HTTPS / WSS (Port 443)
┌───────────────────────────▼────────────────────────────┐
│          Reverse Proxy (Nginx / Traefik / Envoy)       │
└───────────────────────────┬────────────────────────────┘
                            │  HTTP (Port 8000)
┌───────────────────────────▼────────────────────────────┐
│             CIVIS-CORE Pipeline Container              │
│  - FastAPI Gateway        - Risk & Event Intelligence  │
│  - Runtime Orchestrator   - Observability Engine       │
│  - Forensic Evidence      - Re-ID Subsystem            │
└───────────────────────────┬────────────────────────────┘
                            │ Mounted Volumes
         ┌──────────────────┴──────────────────┐
         ▼                                     ▼
/var/lib/civis/evidence                 /var/log/civis
(Immutable Evidence Ledger)             (Container Logs)
```

---

## 2. Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `CIVIS_ENVIRONMENT` | `production` | Environment mode (`development`, `staging`, `production`) |
| `CIVIS_API_KEY` | *(Generated)* | Secret API authentication key (Header: `X-API-Key`) |
| `CIVIS_API_AUTH_ENABLED` | `true` | Enforce API key verification on HTTP & WS endpoints |
| `CIVIS_STORAGE_ROOT` | `/var/lib/civis` | Base persistent storage root |
| `CIVIS_EVIDENCE_DIR` | `/var/lib/civis/evidence`| WORM ledger & BagIt forensic export directory |
| `CIVIS_LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `ENABLE_OPENTELEMETRY` | `false` | Optional non-blocking OpenTelemetry instrumentation |

---

## 3. Quick Start (Docker Compose)

```bash
# 1. Start the stack
docker compose up -d

# 2. Verify container liveness & readiness
curl -f http://127.0.0.1:8000/health/liveness
curl -f http://127.0.0.1:8000/health/readiness

# 3. View live Prometheus metrics
curl -s http://127.0.0.1:8000/health/metrics
```

---

## 4. Health & Orchestration Probes

- **Liveness Probe**: `GET /health/liveness` (Returns 200 OK if process is responding).
- **Readiness Probe**: `GET /health/readiness` (Verifies core runtime, config, and observability engines are operational).
- **Metrics Probe**: `GET /health/metrics` (Prometheus-formatted plaintext stream).
