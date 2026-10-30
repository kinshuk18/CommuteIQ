import React, { useState, useEffect } from "react";
import { Stop, Office } from "../types";

interface Props {
  placeholder: string;
  onSelect: (item: { id: string; name: string; lat: number; lon: number }) => void;
  type: "stop" | "office";
}

export const Autocomplete: React.FC<Props> = ({ placeholder, onSelect, type }) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const endpoint = type === "stop" ? `/api/v1/stops?q=${encodeURIComponent(query)}` : `/api/v1/offices?q=${encodeURIComponent(query)}`;
        const res = await fetch(endpoint);
        if (res.ok) {
          const data = await res.json();
          setResults(data.slice(0, 8));
          setIsOpen(true);
        }
      } catch (err) {
        console.error("Autocomplete fetch failed:", err);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query, type]);

  return (
    <div className="autocomplete-container">
      <input
        type="text"
        className="autocomplete-input"
        placeholder={placeholder}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setIsOpen(true)}
      />
      {isOpen && results.length > 0 && (
        <ul className="autocomplete-dropdown">
          {results.map((item) => {
            const id = type === "stop" ? item.stopId : item.id;
            const name = type === "stop" ? item.stopName : item.name;
            const lat = type === "stop" ? item.stopLat : item.lat;
            const lon = type === "stop" ? item.stopLon : item.lon;
            const badge = type === "stop" ? item.agencyId : "OFFICE";

            return (
              <li
                key={id}
                className="autocomplete-item"
                onClick={() => {
                  setQuery(name);
                  setIsOpen(false);
                  onSelect({ id, name, lat, lon });
                }}
              >
                <span className="item-name">{name}</span>
                <span className={`item-badge badge-${badge.toLowerCase()}`}>{badge}</span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
