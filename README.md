# Valtec GCS

A simplified Ground Control Station for monitoring a simulated drone fleet.

## Stack

- **Frontend:** React 18, Redux Toolkit, Vite
- **Backend:** Python 3.11, FastAPI, WebSockets
- **Infra:** Docker Compose

## Quick start

```bash
docker-compose up
```

Frontend: http://localhost:5173  
Backend API docs: http://localhost:8000/docs

## Running backend tests

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pytest
```

## Project structure

```
valtec-gcs-assignment/
├── frontend/
│   └── src/
│       ├── components/     # React UI components
│       ├── hooks/          # Custom hooks (WebSocket, telemetry)
│       ├── store/          # Redux slices
│       ├── api/            # REST API calls
│       └── utils/          # Helpers
├── backend/
│   ├── app/
│   │   ├── routers/        # FastAPI route handlers
│   │   ├── services/       # Business logic
│   │   └── models/         # Pydantic models
│   └── tests/
└── docker-compose.yml
```

## Architecture

The backend runs a drone simulator that generates telemetry for 3 virtual drones at 2 Hz. Each drone periodically goes offline for a short window — this is simulated automatically and is expected behaviour. A WebSocket endpoint streams this data to connected frontend clients. The frontend maintains a Redux store of drone states and renders a real-time dashboard.

```
Drone Simulator → WebSocket stream → Redux store → Dashboard UI

Frontend → REST POST /command → Command Service → Drone Simulator
```

## Known simplifications

This codebase is intentionally simplified for a single-process, in-memory environment. Not everything here reflects production best practices — that's on purpose.

---

## Your notes (fill this in)

### Bug 1 — Re-render fix

The main cause of the re-renders is that the Dashboard subscribes to the entire `drones` slice. Whenever `useWebSocket` updates a single drone through `upsertTelemetry`, the whole slice gets updated because of how Immer works, which in turn causes the Dashboard to update as well. Once the Dashboard updates, all of the DroneCards inside it get updated too.

A secondary issue is that when the Dashboard re-renders, it also causes unnecessary re-renders of the DroneCards. For example, when the number of drones changes, the DroneCards for drones that already existed re-render as well.

This can be solved with the following approaches:

1. Make DroneCard responsible for obtaining the drone object itself. Change its props to take only the drone id, and have it fetch the drone object from the store and call `sendCommand` on its own, instead of passing these down through the Dashboard. The benefit is that the Dashboard only needs the drone id list and no longer needs to subscribe to the entire slice, reducing the chance of re-renders.
2. Wrap DroneCard with `memo` so it is only affected by changes to the drone id. This avoids re-rendering it just because the Dashboard re-renders.
3. Remove `onCommand` from DroneCard and have it call `sendCommand` itself. `memo` alone is not enough; the inline function also needs to be removed, which can also be done with `useCallback`. Another benefit of pushing this down into DroneCard is improved component cohesion.

### Bug 2 — API error handling

_List each issue you found and how you fixed it._

### Feature 3 — Alert system

_Describe your state design and any decisions you made._

### Feature 4 — Command queue

_Describe your queue design and how you handle the offline drain case._
