"""
routes/ask.py — POST /ask endpoint running the LangGraph multimodal commute agent.
"""

from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent.graph import get_agent_graph

router = APIRouter()


class AskRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    departure_sec: int | None = Field(None, ge=0, description="Optional seconds since midnight")


class Citation(BaseModel):
    id: int
    title: str
    url: str
    trust_tier: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    plan: dict[str, Any] | None
    warnings: list[str]


@router.post("", response_model=AskResponse)
async def ask_assistant(req: AskRequest):
    """
    Query the CommuteIQ assistant for Bengaluru transit routes, policies, and fare rules.
    Runs a 6-node LangGraph pipeline with strict verified vs unverified context separation.
    """
    initial_state = {
        "query": req.query,
        "intent": "commute_query",
        "origin_name": None,
        "dest_name": None,
        "origin_coords": None,
        "dest_coords": None,
        "departure_sec": req.departure_sec if req.departure_sec is not None else 32400,
        "plan": None,
        "retrieved_chunks": [],
        "citations": [],
        "warnings": [],
        "context_text": "",
        "answer": "",
        "clarification": None,
        "confidence": 1.0,
        "retry_count": 0,
    }

    graph = get_agent_graph()
    final_state = graph.invoke(initial_state)

    formatted_citations = [
        Citation(
            id=c["id"],
            title=c["title"],
            url=c["url"],
            trust_tier=c["trust_tier"],
        )
        for c in final_state.get("citations", [])
    ]

    return AskResponse(
        answer=final_state.get("answer", "No answer could be generated."),
        citations=formatted_citations,
        plan=final_state.get("plan"),
        warnings=final_state.get("warnings", []),
    )
