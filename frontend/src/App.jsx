import { useWebSocket } from "./hooks/useWebSocket";
import FleetDashboard from "./components/FleetDashboard";
import AlertBanner from "./components/AlertBanner";

function App() {
  useWebSocket();
  return (
    <>
      <AlertBanner />
      <FleetDashboard />
    </>
  );
}

export default App;
