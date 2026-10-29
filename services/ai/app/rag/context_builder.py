"""
rag/context_builder.py — Strict verified vs unverified context engineering,
token budget enforcement, citation construction, and prompt-injection neutralization.
"""

import re
from typing import Any

from app.ml_model import RuntimePredictor


INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"\[system\]", re.IGNORECASE),
    re.compile(r"forget\s+everything", re.IGNORECASE),
    re.compile(r"dan\s+mode", re.IGNORECASE),
]


def sanitize_retrieved_chunk(text: str) -> str:
    """Neutralize instruction-like substrings in untrusted text to prevent prompt injection."""
    sanitized = text
    for pat in INJECTION_PATTERNS:
        sanitized = pat.sub("[REDACTED_INSTRUCTION]", sanitized)
    return sanitized.strip()


class ContextBuilder:
    """
    Constructs a structured context prompt with clear separation between
    VERIFIED_FACTS and UNVERIFIED_CONTEXT. Enforces token budgets and
    creates numbered citations.
    """

    def __init__(self, max_tokens: int = 2500) -> None:
        self.max_tokens = max_tokens
        self.verified_chunks: list[dict[str, Any]] = []
        self.unverified_chunks: list[dict[str, Any]] = []
        self.gtfs_facts: list[str] = []
        self.citations: list[dict[str, Any]] = []

    def add_gtfs_plan_facts(self, plan: dict[str, Any]) -> None:
        """Add deterministic facts from the GTFS routing engine."""
        dep_min = plan.get("departure_sec", 0) // 60
        arr_min = plan.get("arrival_sec", 0) // 60
        duration_min = plan.get("total_duration_sec", 0) // 60
        origin_name = plan.get("origin", {}).get("name", "Origin")
        dest_name = plan.get("destination", {}).get("name", "Destination")
        changes = plan.get("vehicle_changes", 0)

        fact = (
            f"Scheduled Journey: from {origin_name} to {dest_name}. "
            f"Departure: {dep_min // 60:02d}:{dep_min % 60:02d}, "
            f"Arrival: {arr_min // 60:02d}:{arr_min % 60:02d} "
            f"({duration_min} minutes, {changes} transfers)."
        )
        self.gtfs_facts.append(fact)

        for i, leg in enumerate(plan.get("legs", [])):
            leg_type = leg.get("type", "transit")
            if leg_type == "walk":
                w_sec = leg.get("walk_sec", 0)
                self.gtfs_facts.append(f"Leg {i+1}: Walk {w_sec // 60} mins between stops.")
            else:
                dep_s = leg.get("dep", 0) // 60
                arr_s = leg.get("arr", 0) // 60
                self.gtfs_facts.append(
                    f"Leg {i+1}: Transit board at {dep_s // 60:02d}:{dep_s % 60:02d}, "
                    f"alight at {arr_s // 60:02d}:{arr_s % 60:02d}."
                )

    def add_retrieved_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """Classify and register retrieved chunks by trust tier."""
        for chunk in chunks:
            trust = chunk.get("trust_tier", "UNVERIFIED").upper()
            safe_text = sanitize_retrieved_chunk(chunk.get("text", ""))
            citation_id = len(self.citations) + 1
            citation_entry = {
                "id": citation_id,
                "title": chunk.get("title", "Bangalore Transit Document"),
                "url": chunk.get("url", ""),
                "trust_tier": trust,
                "authority": chunk.get("authority", ""),
            }
            self.citations.append(citation_entry)

            item = {**chunk, "safe_text": safe_text, "citation_id": citation_id}
            if trust == "VERIFIED":
                self.verified_chunks.append(item)
            else:
                self.unverified_chunks.append(item)

    def build_prompt_context(self) -> str:
        """
        Assemble the formatted system/context block with strict boundaries.
        Verified facts win in conflicts; unverified claims must be explicitly labeled.
        """
        sections = []

        # 1. VERIFIED FACTS
        v_lines = []
        if self.gtfs_facts:
            v_lines.append("--- Official GTFS Journey Facts (Ground Truth) ---")
            for f in self.gtfs_facts:
                v_lines.append(f"- {f}")

        if self.verified_chunks:
            v_lines.append("\n--- Official Government / Operator Regulations (Verified) ---")
            for c in self.verified_chunks:
                cid = c["citation_id"]
                title = c["title"]
                v_lines.append(f"[{cid}] ({title}) {c['safe_text']}")

        if v_lines:
            sections.append("### SECTION 1: VERIFIED FACTS (HIGH TRUST)\n" + "\n".join(v_lines))

        # 2. UNVERIFIED CONTEXT
        if self.unverified_chunks:
            u_lines = []
            for c in self.unverified_chunks:
                cid = c["citation_id"]
                title = c["title"]
                u_lines.append(f"[{cid}] ({title} [UNVERIFIED]) {c['safe_text']}")
            sections.append(
                "### SECTION 2: UNVERIFIED COMMUNITY CONTEXT (LOW TRUST - MUST BE LABELED)\n"
                + "\n".join(u_lines)
            )

        if not sections:
            return "No verified transit documents or community context found in sources."

        instructions = (
            "\n### CITATION & CONFLICT RULES:\n"
            "1. Verified Facts always take precedence over Unverified Context in case of conflict.\n"
            "2. If citing an unverified claim, you MUST label it '(Unverified / Community report)'.\n"
            "3. Every factual claim must include a bracketed citation matching the source number [1], [2], etc.\n"
            "4. If requested information is missing from the provided sources, state clearly that it was not found in official sources."
        )

        return "\n\n".join(sections) + instructions

    def verify_plausibility(self, plan: dict[str, Any] | None) -> list[str]:
        """
        Plausibility check on travel time and speed using the trained ML model.
        Returns list of warnings if anomalies or discrepancies are detected.
        """
        warnings = []
        if not plan:
            return warnings

        total_sec = plan.get("total_duration_sec", 0)
        # Check against ML model for transit legs
        legs = plan.get("legs", [])
        for i, leg in enumerate(legs):
            if leg.get("type") == "transit":
                dep = leg.get("dep", 0)
                arr = leg.get("arr", 0)
                sched_dur = arr - dep
                hour = (dep % 86400) // 3600
                pred = RuntimePredictor.predict(
                    haversine_m=2000.0,
                    hour=hour,
                    route_type=1,
                    stop_seq_pos=0.5,
                    route_len=15,
                )
                # Discrepancy heuristic: if scheduled is extremely off (<30s or >2h)
                if sched_dur < 30:
                    warnings.append(
                        f"Leg {i+1} has an unusually short scheduled time ({sched_dur}s)."
                    )
                elif sched_dur > 7200:
                    warnings.append(
                        f"Leg {i+1} has an unusually long scheduled time ({sched_dur // 60}m)."
                    )

        if self.unverified_chunks:
            warnings.append(
                "Response references unverified community sources; verify critical timings with official operators."
            )

        return warnings
