# CIVIS-CORE Operator Dashboard & Console

The **CIVIS-CORE Operator Dashboard** is a mission-critical web application built with **React + TypeScript + Vite** for security operators, system administrators, and forensic analysts.

## Key Features

1. **System Health Bar**: Live operational status, active cameras count, uptime, and aggregated health diagnosis from `civis.observability`.
2. **Multi-Camera Grid**: Real-time tile view of all configured video feeds showing FPS, processed frames, drop counts, and status indicators.
3. **Live Risk & Alert Feed**: Priority-sorted explainable risk assessments with severity badges and detailed breakdown of contributing factors.
4. **WebSocket Event Timeline**: Real-time event streaming (`/ws/events`) with automatic exponential backoff reconnection and memory-safe ring-buffering.
5. **Cross-Camera Entity Inspection**: Modal viewer showing global person Re-ID matches, track history, and behavioral context.
6. **Forensic Evidence Verification**: Cryptographic SHA-256 verification of tamper-evident immutable evidence records and investigation timelines.
7. **Runtime & Stream Controls**: Start, pause, resume, and stop cameras or the whole pipeline with safe operator confirmation dialogs.
8. **Configuration & Policy Overview**: Read-only inspection of active configuration parameters, policy rules, and snapshot checksums.

## Architecture

```text
┌───────────────────────────┐         HTTP REST (FastAPI)         ┌──────────────────────────┐
│   React Operator Console  │ ◄─────────────────────────────────► │      civis.api           │
│   (Vite + TypeScript)     │         WebSocket (/ws/events)      │   (FastAPI Gateway)      │
└───────────────────────────┘ ◄────────────────────────────────── └──────────────────────────┘
```

## Running the Dashboard

```bash
cd frontend/civis-dashboard
npm install
npm run dev
```
