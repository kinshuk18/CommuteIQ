import React, { useState } from "react";
import { Autocomplete } from "./components/Autocomplete";
import { JourneyPanel } from "./components/JourneyPanel";
import { MapView } from "./components/MapView";
import { AssistantChat } from "./components/AssistantChat";
import { SavedCommutes } from "./components/SavedCommutes";
import { PlanResponse, SavedCommute } from "./types";
import "./App.css";

const CURRENT_USER = "user-blr-01";

export const App: React.FC = () => {
  const [origin, setOrigin] = useState<{ id: string; name: string; lat: number; lon: number } | null>(null);
  const [dest, setDest] = useState<{ id: string; name: string; lat: number; lon: number } | null>(null);
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"plan" | "assistant">("plan");

  const handlePlanRoute = async () => {
    if (!origin || !dest) return;
    setLoading(true);
    try {
      const res = await fetch("/api/v1/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          originStopId: origin.id,
          destinationStopId: dest.id,
          departureHour: 9,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setPlan(data);
      }
    } catch (err) {
      console.error("Plan route failed:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveCommute = async () => {
    if (!origin || !dest) return;
    try {
      await fetch("/api/v1/commutes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId: CURRENT_USER,
          originStopId: origin.id,
          destinationOfficeId: dest.id,
          label: `${origin.name.slice(0, 15)} → ${dest.name.slice(0, 15)}`,
          departureTime: "09:00",
        }),
      });
      alert("Commute saved!");
    } catch (err) {
      console.error("Failed to save commute:", err);
    }
  };

  const handleSelectSaved = (saved: SavedCommute) => {
    setOrigin({ id: saved.originStopId, name: saved.originStopId, lat: 12.9716, lon: 77.5946 });
    setDest({ id: saved.destinationOfficeId, name: saved.destinationOfficeId, lat: 12.9352, lon: 77.6245 });
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-brand">
          <h1>CommuteIQ</h1>
          <span className="header-subtitle">Bengaluru Hybrid-Work Multimodal Copilot</span>
        </div>
        <div className="header-tabs">
          <button
            className={`tab-btn ${activeTab === "plan" ? "active" : ""}`}
            onClick={() => setActiveTab("plan")}
          >
            Route Planner
          </button>
          <button
            className={`tab-btn ${activeTab === "assistant" ? "active" : ""}`}
            onClick={() => setActiveTab("assistant")}
          >
            AI Policy Copilot
          </button>
        </div>
      </header>

      <main className="app-main">
        <div className="sidebar">
          {activeTab === "plan" ? (
            <div className="planner-view">
              <div className="card search-card">
                <h3>Find Commute</h3>
                <div className="form-group">
                  <label>Origin (BMTC / Metro Stop)</label>
                  <Autocomplete
                    type="stop"
                    placeholder="Search bus stop or metro station..."
                    onSelect={setOrigin}
                  />
                </div>
                <div className="form-group">
                  <label>Destination (Tech Park / Office)</label>
                  <Autocomplete
                    type="office"
                    placeholder="Search office or tech park..."
                    onSelect={setDest}
                  />
                </div>
                <button
                  className="btn btn-primary full-width"
                  disabled={!origin || !dest || loading}
                  onClick={handlePlanRoute}
                >
                  {loading ? "Planning..." : "Plan Commute"}
                </button>
              </div>

              <JourneyPanel
                plan={plan}
                loading={loading}
                onSave={plan ? handleSaveCommute : undefined}
              />

              <SavedCommutes userId={CURRENT_USER} onSelectCommute={handleSelectSaved} />
            </div>
          ) : (
            <AssistantChat />
          )}
        </div>

        <div className="map-panel">
          <MapView origin={origin} dest={dest} />
        </div>
      </main>
    </div>
  );
};

export default App;
