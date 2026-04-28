"""Reviewer agent: end-of-day postmortem + memory updates."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from joint_research.agents.base import Agent
from joint_research.agents.schemas import (
    ApprovedPlan,
    ExecutionLog,
    Postmortem,
    ResearchBrief,
)


class ReviewerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    research_brief: ResearchBrief
    approved_plan: ApprovedPlan
    execution_log: ExecutionLog
    realized_pnl_usd: float = 0.0
    expected_pnl_usd: float = 0.0


class ReviewerAgent(Agent[ReviewerInput, Postmortem]):
    name = "reviewer"

    def decide_stub(self, input_artifact: ReviewerInput) -> Postmortem:
        hits: list[str] = []
        misses: list[str] = []
        next_actions: list[str] = []

        if not input_artifact.approved_plan.approved_proposals:
            hits.append("no trades placed; capital preserved")
        else:
            n_fills = len(input_artifact.execution_log.fills)
            n_approved = len(input_artifact.approved_plan.approved_proposals)
            if n_fills == n_approved:
                hits.append(f"all {n_approved} approved proposals filled")
            else:
                misses.append(f"{n_approved - n_fills} proposals failed to fill")

        if input_artifact.realized_pnl_usd < input_artifact.expected_pnl_usd - 1.0:
            misses.append(
                f"realized pnl {input_artifact.realized_pnl_usd:.2f} below expected "
                f"{input_artifact.expected_pnl_usd:.2f}"
            )
            next_actions.append("review slippage assumption; may need recalibration")

        return Postmortem(
            run_id=input_artifact.run_id,
            produced_at_iso=datetime.now(tz=timezone.utc).isoformat(),
            covers_run_id=input_artifact.approved_plan.run_id,
            realized_pnl_usd=input_artifact.realized_pnl_usd,
            expected_pnl_usd=input_artifact.expected_pnl_usd,
            hits=hits,
            misses=misses,
            calibration_deltas=[],
            next_actions=next_actions,
        )
