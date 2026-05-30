import { useEffect, useRef } from "react";
import { useDispatch } from "react-redux";
import { upsertTelemetry } from "../store/droneSlice";
import { addAlert, delAlert } from "../store/alertSlice";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000";
const RECONNECT_DELAY_MS = 3000;
const LOW_BATTERY_THRESHOLD = 20;
const OFFLINE_GRACE_MS = 5000;

export function useWebSocket() {
  const dispatch = useDispatch();
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const offlineTimeouts = useRef({});

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(`${WS_URL}/ws/telemetry`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        let frame;
        try {
          frame = JSON.parse(event.data);
        } catch {
          // malformed frame — ignore
          return;
        }
        dispatch(upsertTelemetry(frame));
        detectAlerts(frame);
      };

      ws.onclose = () => {
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    function detectAlerts(frame) {
      const id = frame.drone_id;

      if (frame.battery < LOW_BATTERY_THRESHOLD) {
        dispatch(addAlert({ droneId: id, type: "low-battery" }));
      } else {
        dispatch(delAlert({ droneId: id, type: "low-battery" }));
      }

      if (frame.status === "offline") {
        if (!offlineTimeouts.current[id]) {
          offlineTimeouts.current[id] = setTimeout(() => {
            dispatch(addAlert({ droneId: id, type: "lost" }));
            delete offlineTimeouts.current[id];
          }, OFFLINE_GRACE_MS);
        }
      } else {
        dispatch(delAlert({ droneId: id, type: "lost" }));
        if (offlineTimeouts.current[id]) {
          clearTimeout(offlineTimeouts.current[id]);
          delete offlineTimeouts.current[id];
        }
      }
    }

    connect();

    const timers = offlineTimeouts.current;
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      Object.values(timers).forEach(clearTimeout);
    };
  }, [dispatch]);
}
