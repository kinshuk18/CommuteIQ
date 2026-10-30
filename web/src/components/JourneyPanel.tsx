import React from "react";
import { PlanResponse } from "../types";

interface Props {
  plan: PlanResponse | null;
  loading: boolean;
  onSave?: () => void;
}

export const JourneyPanel: React.FC<Props> = ({ plan, loading, onSave }) => {
  if (loading) {
    return <div className="panel card">Calculating optimal multimodal route...</div>;
  }

  if (!plan) {
    return (
      <div className="panel card empty-state">
        <p>Select origin and destination to plan your multimodal commute.</p>
      </div>
    );
  }

  return (
    <div className="panel card journey-panel">
      <div className="journey-header">
        <h3>Trip Plan</h3>
        {plan.cached && <span className="cache-badge">Redis Cached</span>}
      </div>

      <div className="journey-metrics">
        <div className="metric">
          <span className="metric-label">Estimated Time</span>
          <span className="metric-val">{plan.estimatedMinutes} min</span>
        </div>
        <div className="metric">
          <span className="metric-label">Distance</span>
          <span className="metric-val">{plan.distanceKm?.toFixed(1) || "—"} km</span>
        </div>
      </div>

      <div className="itinerary-list">
        <h4>Itinerary</h4>
        <ul>
          {plan.itinerary?.map((step, idx) => (
            <li key={idx} className="itinerary-step">
              <span className="step-idx">{idx + 1}</span>
              <span className="step-desc">{step}</span>
            </li>
          ))}
        </ul>
      </div>

      {onSave && (
        <button className="btn btn-secondary save-btn" onClick={onSave}>
          ★ Save this Commute
        </button>
      )}
    </div>
  );
};
