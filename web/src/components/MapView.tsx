import React from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

// Fix Leaflet's default marker icons in React
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

interface Props {
  origin?: { lat: number; lon: number; name: string } | null;
  dest?: { lat: number; lon: number; name: string } | null;
  routeCoords?: [number, number][];
}

const BENGALURU_CENTER: [number, number] = [12.9716, 77.5946];

export const MapView: React.FC<Props> = ({ origin, dest, routeCoords }) => {
  const center = origin ? [origin.lat, origin.lon] as [number, number] : BENGALURU_CENTER;

  // If routeCoords is provided, use it; otherwise draw line between origin and dest if both exist
  const polylinePositions: [number, number][] =
    routeCoords && routeCoords.length > 0
      ? routeCoords
      : origin && dest
      ? [[origin.lat, origin.lon], [dest.lat, dest.lon]]
      : [];

  return (
    <div className="map-wrapper">
      <MapContainer center={center} zoom={12} style={{ height: "100%", width: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {origin && (
          <Marker position={[origin.lat, origin.lon]}>
            <Popup>
              <strong>Origin:</strong> {origin.name}
            </Popup>
          </Marker>
        )}

        {dest && (
          <Marker position={[dest.lat, dest.lon]}>
            <Popup>
              <strong>Destination:</strong> {dest.name}
            </Popup>
          </Marker>
        )}

        {polylinePositions.length > 1 && (
          <Polyline positions={polylinePositions} color="#2563eb" weight={4} opacity={0.8} />
        )}
      </MapContainer>
    </div>
  );
};
