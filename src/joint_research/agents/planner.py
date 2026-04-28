"""Planner agent: builds a candidate trade plan from a research brief.

Stub mode produces a deterministic plan that defers all real decisions
('flat — awaiting strategy menu and live agent wiring'). This lets the
orchestrator pipeline be testable end-to-end before Claude is wired in.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from joint_research.agents.base import Agent
from joint_research.agents.schemas import (
    CandidatePlan,
    ResearchBrief,
)


class PlannerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    research_brief: ResearchBrief
    portfolio_equity_usd: float = Field(gt=0, default=200.0)
    open_positions: list[dict[str, Any]] = Field(default_factory=list)


class PlannerAgent(Agent[PlannerInput, CandidatePlan]):
    name = "planner"

    def decide_stub(self, input_artifact: PlannerInput) -> CandidatePlan:
        return CandidatePlan(
            run_id=input_artifact.run_id,
            produced_at_iso=datetime.now(tz=timezone.utc).isoformat(),
            research_brief_run_id=input_artifact.research_brief.run_id,
            proposals=[],
            rationale=(
                "Stub mode: no validated strategies in menu yet. Stay flat. "
                "Live agent wiring + strategy backtests required before any "
                "proposal is emitted."
            ),
        )
