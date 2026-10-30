import React, { useState, useEffect } from "react";
import { SavedCommute } from "../types";

interface Props {
  userId: string;
  onSelectCommute: (commute: SavedCommute) => void;
}

export const SavedCommutes: React.FC<Props> = ({ userId, onSelectCommute }) => {
  const [commutes, setCommutes] = useState<SavedCommute[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchCommutes = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/commutes?userId=${encodeURIComponent(userId)}`);
      if (res.ok) {
        const data = await res.json();
        setCommutes(data);
      }
    } catch (err) {
      console.error("Failed to load saved commutes:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCommutes();
  }, [userId]);

  if (loading) {
    return <div className="card panel">Loading saved commutes...</div>;
  }

  if (commutes.length === 0) {
    return (
      <div className="card panel empty-saved">
        <h4>Saved Commutes</h4>
        <p>No saved commutes yet. Plan a trip above and click Save!</p>
      </div>
    );
  }

  return (
    <div className="card panel saved-commutes-panel">
      <h4>Saved Commutes</h4>
      <div className="commutes-grid">
        {commutes.map((c) => (
          <div key={c.id} className="commute-card" onClick={() => onSelectCommute(c)}>
            <div className="commute-label">★ {c.label}</div>
            <div className="commute-route">
              {c.originStopId} → {c.destinationOfficeId}
            </div>
            {c.departureTime && <div className="commute-time">⏰ {c.departureTime}</div>}
          </div>
        ))}
      </div>
    </div>
  );
};
