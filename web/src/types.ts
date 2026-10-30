export interface Stop {
  stopId: string;
  stopName: string;
  stopLat: number;
  stopLon: number;
  agencyId: string;
}

export interface Office {
  id: string;
  name: string;
  lat: number;
  lon: number;
}

export interface PlanResponse {
  originStopId: string;
  destinationStopId: string;
  estimatedMinutes: number;
  distanceKm: number;
  itinerary: string[];
  breakdown: Record<string, any>;
  cached: boolean;
  coordinates?: [number, number][];
}

export interface Citation {
  id: number;
  title: string;
  url: string;
  trust_tier: "VERIFIED" | "UNVERIFIED" | string;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  plan?: any;
  warnings: string[];
}

export interface SavedCommute {
  id: number;
  userId: string;
  originStopId: string;
  destinationOfficeId: string;
  label: string;
  departureTime?: string;
}
