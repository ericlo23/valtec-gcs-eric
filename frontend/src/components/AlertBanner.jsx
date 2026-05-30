import { useSelector, useDispatch } from "react-redux";
import { selectVisibleAlerts, hideAlert } from "../store/alertSlice";

const ALERT_STYLES = {
  "low-battery": {
    background: "#fff8e1",
    color: "#856404",
    border: "1px solid #ffd54f",
  },
  lost: {
    background: "#fdecea",
    color: "#b71c1c",
    border: "1px solid #f5a0a0",
  },
};

const MESSAGES = {
  "low-battery": (id) => `${id} — battery below 20%`,
  lost: (id) => `${id} — connection lost`,
};

const formatTime = (ts) =>
  new Date(ts).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

function AlertBanner() {
  const alerts = useSelector(selectVisibleAlerts);
  const dispatch = useDispatch();

  if (alerts.length === 0) return null;

  return (
    <div style={styles.container}>
      {alerts.map((alert) => (
        <div
          key={alert.key}
          style={{ ...styles.banner, ...ALERT_STYLES[alert.type] }}
        >
          <span style={styles.message}>
            <span style={styles.time}>{formatTime(alert.timestamp)}</span>
            {MESSAGES[alert.type](alert.droneId)}
          </span>
          <button
            style={styles.dismiss}
            aria-label="Dismiss alert"
            onClick={() =>
              dispatch(hideAlert({ droneId: alert.droneId, type: alert.type }))
            }
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

const styles = {
  container: {
    position: "fixed",
    top: 16,
    left: "50%",
    transform: "translateX(-50%)",
    zIndex: 1000,
    display: "flex",
    flexDirection: "column",
    gap: 8,
    width: 360,
    maxWidth: "calc(100vw - 32px)",
    pointerEvents: "none",
  },
  banner: {
    pointerEvents: "auto",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    padding: "10px 16px",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 500,
    boxShadow: "0 4px 12px rgba(0, 0, 0, 0.15)",
  },
  message: { display: "flex", alignItems: "baseline", gap: 8 },
  time: { fontSize: 12, fontWeight: 400, opacity: 0.7, fontVariantNumeric: "tabular-nums" },
  dismiss: {
    background: "none",
    border: "none",
    color: "inherit",
    fontSize: 20,
    lineHeight: 1,
    cursor: "pointer",
    padding: "0 4px",
  },
};

export default AlertBanner;
