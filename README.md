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

1. Missing `drone_id` existence check. The endpoint accepted any `drone_id` without verifying the drone exists — an issue the starter test caught but the code did not yet handle. Fixed by adding an existence check in `commands.py`: if the resource does not exist, return 404.

2. Commands accepted for offline drones. A drone may enter an offline state, and an offline drone should not be able to process any command. Fixed by checking the drone's status in `commands.py`: if the drone is offline, return HTTP 409, indicating that the resource's current state conflicts with the command and it cannot be executed. I considered returning HTTP 200 with `body.status = "rejected"` instead, but since commands are in practice forwarded to the edge, and the edge decides whether a command can actually be executed, I reserved the command `status` field for the edge. Separation of concerns: the HTTP status represents the server-side processing result, while the `CommandResponse.status` represents the edge-side processing result.

3. No error logging with command context. Wrapped `command_service.execute` in a `try/except` to log execution errors. Uvicorn's built-in error logging does not include the command parameter details, which makes failures hard to trace and reproduce. The added logging records the command context (`type`, `payload`, `drone_id`) to aid troubleshooting. The exception is then re-raised (a bare `raise`, not converted to `HTTPException(500)`) so that Uvicorn still logs the full traceback at ERROR level.

### Feature 3 — Alert system

#### Design

A dedicated Redux alert slice is the single source of truth. `useWebSocket` is the only producer: on each telemetry frame it detects the alert conditions and dispatches `addAlert` / `delAlert`; the slice's reducers are idempotent, so dismissal sticks. The UI renders one banner per active alert by reading the slice. Because the slice is independent of the connection state, **alert state survives a WebSocket reconnect** (an assignment constraint).

I considered a separate `useAlerts` hook that subscribes to the slice, detects state changes, and dispatches — a cleaner separation of concerns. But a subscribe-and-detect approach likely carries more overhead, and `useWebSocket` is still fairly simple, so I kept detection inside `useWebSocket` directly.

#### State

```
interface Alert {
    key: string; // {droneId}_{type}
    timestamp: number;
    droneId: string;
    type: 'low-battery' | 'lost';
    visible: boolean;
}

interface AlertSliceModel {
    byKey: Record<string, Alert>;
    keys: string[];
}
```

A given drone maps to at most one banner per alert type, so `key` is composed from the drone id and the type. The `keys` array exists because the UI should be ordered: even though each alert carries a `timestamp`, keeping an array preserves insertion order without sorting.

#### Reducers

The reducers are idempotent + no-op, which is what achieves the "do not pop up again once dismissed" behaviour while keeping the logic simple. All take payload `{ droneId, type }`:

- `addAlert`: if the key already exists, skip; otherwise create the Alert with `visible` defaulting to `true`.
- `delAlert`: if no matching alert exists, skip; otherwise remove it.
- `hideAlert`: set the alert's `visible` to `false`; skip if it does not exist.

#### Detection

Both conditions are detected in `useWebSocket`, per frame. The hook only reports conditions; the reducers decide the rest.

- **Low battery:** check the battery on each frame — if sufficient call `delAlert`, if low call `addAlert`.
- **Offline:** `useWebSocket` maintains `offlineTimeouts: Record<string, number>` (droneId → timeout id). When an offline frame arrives and `offlineTimeouts[droneId]` does not exist, the drone just went offline, so set `offlineTimeouts[droneId] = setTimeout(..., 5_000)`; on fire it dispatches `addAlert` and clears the entry. If the timeout already exists, skip and let it fire. When a non-offline frame arrives, dispatch `delAlert` and, if a timeout exists, `clearTimeout` and clear the entry.

#### UI

Each alert renders one banner, and multiple banners stack when several are active. Each banner shows a message based on the droneId and type, with a close button that calls `dispatch(hideAlert(...))`.

### Feature 4 — Command queue

#### Design

`CommandQueueService` (`services/command_queue.py`) holds, per drone:

- a FIFO `deque` of pending commands,
- the currently-executing command,
- one long-lived **worker** task.

It's a producer/consumer model: the `POST` handler enqueues and returns immediately; the per-drone worker pulls one command, `await`s `execute_command` (the simulator's `asyncio.sleep` of a random 2–4s), and only pulls the next once that returns — so **one-at-a-time is guaranteed by the await itself**, with no polling and no locks beyond an `asyncio.Condition` to wake the idle worker. One worker per drone is cheap (an asyncio task is not an OS thread; an idle one costs almost nothing), so this scales to large fleets.

#### Offline drain

The service subscribes to telemetry. On a `status == "offline"` frame it clears that drone's pending `deque` **and cancels the in-flight execution**. I abort the executing command too, not just the pending ones: if the link is down the command never reached the drone, so failing it is the consistent outcome. The worker tells a drain-cancel (swallow, keep serving) from a shutdown-cancel (propagate and exit) by checking which task was cancelled. Submitting to an already-offline drone is still rejected up front with `409` and never enters the queue.

#### `CommandResponse.status` — a shift from Bug 2

Bug 2 framed `status` as the drone's processing result. The queue makes `POST` asynchronous (fire-and-queue): it returns the moment a command is enqueued, before execution, so `status` now means **"received and queued"** (`accepted`). Submit-time failures still use HTTP (`404` unknown drone, `409` offline); execution outcomes are only logged, not returned, and `rejected`/`error` stay reserved for domain verdicts (e.g. backpressure) not yet generated.

#### What comes next

One requirement is only partially met: on offline drain the task asks to "return an appropriate error for any pending commands", but here those commands are dropped and only logged, not surfaced. This is a consequence of the asynchronous (fire-and-queue) design — by the time a command is drained, its `POST` has long since returned `accepted`, so there is no open response to return an error on, and only active state (pending + executing) is tracked.

To close this, terminal outcomes (completed / drained-as-error) would be persisted to a `commands` table, and a new route (e.g. `GET /drones/{id}/commands/{command_id}`) would let a client query a specific command's final status.

---

### Observation beyond scope — Emergency land while offline

While working on the queue I noticed an inconsistency in `DroneCard`: the **Hover** and **RTH** buttons are disabled when a drone is `offline` (`disabled={sending || drone.status === "offline"}`), but **Emergency land** is not (`disabled={sending}` only), so it stays clickable on an offline drone. The backend rejects it with `409` anyway, so it isn't harmful — but an offline drone has no link, so the command can't reach it regardless, and the button should arguably be disabled like the others for consistency. I left it as-is since it's outside the assignment's scope, but flagging it here.
