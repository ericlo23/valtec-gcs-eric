import { createSlice } from "@reduxjs/toolkit";

const alertKey = (droneId, type) => `${droneId}_${type}`;

const initialState = {
  byKey: {},
  keys: [],
};

const alertSlice = createSlice({
  name: "alerts",
  initialState,
  reducers: {
    addAlert(state, action) {
      const { droneId, type } = action.payload;
      const key = alertKey(droneId, type);
      if (state.byKey[key]) return;
      state.byKey[key] = {
        key,
        timestamp: Date.now(),
        droneId,
        type,
        visible: true,
      };
      state.keys.push(key);
    },

    delAlert(state, action) {
      const { droneId, type } = action.payload;
      const key = alertKey(droneId, type);
      if (!state.byKey[key]) return;
      delete state.byKey[key];
      state.keys = state.keys.filter((k) => k !== key);
    },

    hideAlert(state, action) {
      const { droneId, type } = action.payload;
      const key = alertKey(droneId, type);
      const alert = state.byKey[key];
      if (!alert) return;
      alert.visible = false;
    },
  },
});

export const { addAlert, delAlert, hideAlert } = alertSlice.actions;

export const selectVisibleAlerts = (state) =>
  state.alerts.keys
    .map((key) => state.alerts.byKey[key])
    .filter((alert) => alert.visible);

export default alertSlice.reducer;
