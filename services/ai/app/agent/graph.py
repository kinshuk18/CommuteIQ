"""
agent/graph.py — LangGraph 6-node state machine for commuter query handling:
parse_query → resolve_places → plan_route → retrieve → verify → compose.
"""

import json
import logging
import re
from typing import Any, TypedDict

import psycopg
from langgraph.graph import END, StateGraph

from app.config import settings
from app.llm.client import get_llm_client
from app.rag.context_builder import ContextBuilder
from app.rag.vector_store import get_vector_backend
from app.router import get_router

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    query: str
    intent: str
    origin_name: str | None
    dest_name: str | None
    origin_coords: tuple[float, float] | None
    dest_coords: tuple[float, float] | None
    departure_sec: int
    plan: dict[str, Any] | None
    retrieved_chunks: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    warnings: list[str]
    context_text: str
    answer: str
    clarification: str | None
    confidence: float
    retry_count: int


def _resolve_place_in_db(name: str) -> tuple[float, float] | None:
    """Find coordinates for a place/office/stop name via Postgres fuzzy match."""
    if not name or len(name.strip()) < 2:
        return None
    try:
        with psycopg.connect(settings.db_url) as conn:
            with conn.cursor() as cur:
                # 1. Search offices
                cur.execute(
                    "SELECT lat, lon FROM office WHERE name ILIKE %s LIMIT 1",
                    (f"%{name}%",),
                )
                row = cur.fetchone()
                if row:
                    return float(row[0]), float(row[1])

                # 2. Search stops
                cur.execute(
                    "SELECT stop_lat, stop_lon FROM stop WHERE stop_name ILIKE %s LIMIT 1",
                    (f"%{name}%",),
                )
                row = cur.fetchone()
                if row:
                    return float(row[0]), float(row[1])
    except Exception as exc:
        logger.warning("DB place resolution failed for '%s': %s", name, exc)
    return None


def parse_query_node(state: AgentState) -> dict[str, Any]:
    """Parse commuter query, extract places and intent, assess confidence."""
    query = state["query"].strip()
    if len(query) < 4:
        return {
            "clarification": "Could you provide more details about your starting point, destination, or question?",
            "confidence": 0.1,
            "intent": "unknown",
        }

    # Extract origin/destination patterns like "from X to Y" or "to Y from X"
    from_to = re.search(r"from\s+([a-zA-Z0-9\s]+?)\s+to\s+([a-zA-Z0-9\s]+)", query, re.I)
    to_from = re.search(r"to\s+([a-zA-Z0-9\s]+?)\s+from\s+([a-zA-Z0-9\s]+)", query, re.I)

    origin = None
    dest = None
    if from_to:
        origin = from_to.group(1).strip()
        dest = from_to.group(2).strip()
    elif to_from:
        dest = to_from.group(1).strip()
        origin = to_from.group(2).strip()

    # Time detection (default to 09:00 AM = 32400 seconds)
    dep_sec = 32400
    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", query, re.I)
    if time_match:
        hr = int(time_match.group(1))
        mn = int(time_match.group(2) or 0)
        meridiem = (time_match.group(3) or "").lower()
        if meridiem == "pm" and hr < 12:
            hr += 12
        elif meridiem == "am" and hr == 12:
            hr = 0
        if 0 <= hr <= 23 and 0 <= mn <= 59:
            dep_sec = hr * 3600 + mn * 60

    confidence = 0.85 if (origin or dest) else 0.7
    intent = "commute_plan" if (origin and dest) else "transit_faq"

    return {
        "intent": intent,
        "origin_name": origin,
        "dest_name": dest,
        "departure_sec": dep_sec,
        "confidence": confidence,
    }


def resolve_places_node(state: AgentState) -> dict[str, Any]:
    """Resolve extracted origin/dest place names to geographic coordinates."""
    origin_coords = None
    dest_coords = None

    if state.get("origin_name"):
        origin_coords = _resolve_place_in_db(state["origin_name"])
    if state.get("dest_name"):
        dest_coords = _resolve_place_in_db(state["dest_name"])

    return {
        "origin_coords": origin_coords,
        "dest_coords": dest_coords,
    }


def plan_route_node(state: AgentState) -> dict[str, Any]:
    """Generate multimodal route via GTFSRouter if origin and destination coordinates exist."""
    orig_coords = state.get("origin_coords")
    dest_coords = state.get("dest_coords")
    dep_sec = state.get("departure_sec", 32400)

    if not orig_coords or not dest_coords:
        return {"plan": None}

    try:
        rt = get_router()
        nearby_o = rt.graph.nearby_stops(orig_coords[0], orig_coords[1], radius_m=1200)
        nearby_d = rt.graph.nearby_stops(dest_coords[0], dest_coords[1], radius_m=1200)

        if not nearby_o or not nearby_d:
            return {"plan": None}

        best = None
        for o in nearby_o[:3]:
            for d in nearby_d[:3]:
                res = rt.route(o["id"], d["id"], (dep_sec // 60) * 60)
                if res and (best is None or res["arrival_sec"] < best["arrival_sec"]):
                    best = res

        return {"plan": best}
    except Exception as exc:
        logger.warning("Routing failed in agent: %s", exc)
        return {"plan": None}


def retrieve_node(state: AgentState) -> dict[str, Any]:
    """Retrieve top policy, fare, and regulation document chunks from vector store."""
    backend = get_vector_backend()
    chunks = backend.search(state["query"], top_k=4, min_score=0.25)
    return {"retrieved_chunks": chunks}


def verify_node(state: AgentState) -> dict[str, Any]:
    """Cross-check journey plan and retrieved context for plausibility and trust."""
    builder = ContextBuilder()
    if state.get("plan"):
        builder.add_gtfs_plan_facts(state["plan"])
    builder.add_retrieved_chunks(state.get("retrieved_chunks", []))

    warnings = builder.verify_plausibility(state.get("plan"))
    context_text = builder.build_prompt_context()

    return {
        "warnings": warnings,
        "context_text": context_text,
        "citations": builder.citations,
    }


def compose_node(state: AgentState) -> dict[str, Any]:
    """Synthesize final response using LLM with structured citations and warnings."""
    if state.get("clarification"):
        return {
            "answer": state["clarification"],
            "citations": [],
            "warnings": [],
        }

    system_prompt = (
        "You are CommuteIQ, an expert transit copilot for Bengaluru commuters. "
        "Your task is to provide concise, accurate transit advice based STRICTLY on provided context.\n\n"
        "Guidelines:\n"
        "1. Prioritize Section 1 (VERIFIED FACTS) over Section 2 (UNVERIFIED CONTEXT).\n"
        "2. If citing an unverified claim, label it clearly with '(Unverified / Community report)'.\n"
        "3. Include bracketed citations [1], [2] for every claim made.\n"
        "4. If information is not in the context, explicitly state 'Not found in official sources'."
    )

    user_prompt = f"User Question: {state['query']}\n\nContext:\n{state['context_text']}"

    try:
        llm = get_llm_client()
        answer = llm.complete(user_prompt, system=system_prompt, temperature=0.2)
    except Exception as exc:
        logger.warning("Remote LLM unavailable (%s), synthesizing directly from verified facts", exc)
        v_chunks = [c for c in state.get("retrieved_chunks", []) if c.get("trust_tier") == "VERIFIED"]
        if v_chunks:
            primary = v_chunks[0]
            answer = (
                f"Based on official regulations from {primary.get('authority', 'Bangalore Transit')} "
                f"([{primary.get('citation_id', 1)}]): {primary.get('text', '')[:250]}..."
            )
        elif state.get("plan"):
            p = state["plan"]
            dur = p.get("total_duration_sec", 0) // 60
            answer = (
                f"Official GTFS route: {p.get('origin', {}).get('name')} to "
                f"{p.get('destination', {}).get('name')}, duration {dur} minutes "
                f"with {p.get('vehicle_changes', 0)} vehicle transfers. Ground truth from GTFS schedule."
            )
        else:
            answer = "Information retrieved from official Bangalore transit documents cited in references."

    return {"answer": answer}


def should_clarify(state: AgentState) -> str:
    """Route decision: clarify if confidence is low, else proceed to places."""
    if state.get("confidence", 1.0) < 0.3:
        return "compose"
    return "resolve_places"


def build_commute_graph() -> StateGraph:
    """Construct the compiled LangGraph workflow."""
    builder = StateGraph(AgentState)

    builder.add_node("parse_query", parse_query_node)
    builder.add_node("resolve_places", resolve_places_node)
    builder.add_node("plan_route", plan_route_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("verify", verify_node)
    builder.add_node("compose", compose_node)

    builder.set_entry_point("parse_query")
    builder.add_conditional_edges("parse_query", should_clarify)
    builder.add_edge("resolve_places", "plan_route")
    builder.add_edge("plan_route", "retrieve")
    builder.add_edge("retrieve", "verify")
    builder.add_edge("verify", "compose")
    builder.add_edge("compose", END)

    return builder.compile()


_agent_graph = None


def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_commute_graph()
    return _agent_graph
