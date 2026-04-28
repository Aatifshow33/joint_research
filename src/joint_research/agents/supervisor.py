"""Supervisor agent: vetoes / modifies / approves the candidate plan.

The Supervisor has *final veto power*. Even in stub mode it enforces the
hard risk-cap rules deterministically — no proposal larger than the
configured per-trade risk fraction is approved.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from joint_research.agents.base import Agent
from joint_research.agents.schemas import (
    ApprovedPlan,
    CandidatePlan,
    SupervisorDecision,
)


class SupervisorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    candidate_plan: CandidatePlan
    portfolio_equity_usd: float = Field(gt=0, default=200.0)
    max_risk_per_trade: float = Field(default=0.005, ge=0, le=0.05)
    max_daily_drawdown: float = Field(default=0.03, ge=0, le=0.5)
    daily_drawdown_so_far: float = Field(default=0.0, ge=-1.0, le=1.0)
    kill_switch_active: bool = False


class SupervisorAgent(Agent[SupervisorInput, ApprovedPlan]):
    name = "supervisor"

    def decide_stub(self, input_artifact: SupervisorInput) -> ApprovedPlan:
        decisions: list[SupervisorDecision] = []
        approved = []

        if input_artifact.kill_switch_active:
            for i, _p in enumerate(input_artifact.candidate_plan.proposals):
                decisions.append(
                    SupervisorDecision(
                        proposal_index=i,
                        status="rejected",
                        reason="kill_switch_active",
                    )
                )
            return ApprovedPlan(
                run_id=input_artifact.run_id,
                produced_at_iso=datetime.now(tz=timezone.utc).isoformat(),
                candidate_plan_run_id=input_artifact.candidate_plan.run_id,
                decisions=decisions,
                approved_proposals=[],
                overall_status="all_rejected",
                risk_notes="kill switch is active; no orders permitted.",
            )

        if input_artifact.daily_drawdown_so_far <= -input_artifact.max_daily_drawdown:
            for i, _p in enumerate(input_artifact.candidate_plan.proposals):
                decisions.append(
                    SupervisorDecision(
                        proposal_index=i,
                        status="rejected",
                        reason="daily_drawdown_limit_reached",
                    )
                )
            return ApprovedPlan(
                run_id=input_artifact.run_id,
                produced_at_iso=datetime.now(tz=timezone.utc).isoformat(),
                candidate_plan_run_id=input_artifact.candidate_plan.run_id,
                decisions=decisions,
                approved_proposals=[],
                overall_status="all_rejected",
                risk_notes=(
                    f"daily drawdown {input_artifact.daily_drawdown_so_far:.2%} "
                    f"already at/below limit {input_artifact.max_daily_drawdown:.2%}"
                ),
            )

        max_notional = input_artifact.portfolio_equity_usd * 1.0  # 1× equity gross cap

        for i, prop in enumerate(input_artifact.candidate_plan.proposals):
            if prop.risk_pct_of_equity > input_artifact.max_risk_per_trade:
                decisions.append(
                    SupervisorDecision(
                        proposal_index=i,
                        status="rejected",
                        reason=(
                            f"risk_pct_of_equity={prop.risk_pct_of_equity:.4f} exceeds cap "
                            f"{input_artifact.max_risk_per_trade:.4f}"
                        ),
                    )
                )
                continue
            if prop.target_notional_usd > max_notional:
                decisions.append(
                    SupervisorDecision(
                        proposal_index=i,
                        status="rejected",
                        reason=(
                            f"target_notional_usd={prop.target_notional_usd:.2f} exceeds "
                            f"gross-equity cap {max_notional:.2f}"
                        ),
                    )
                )
                continue
            decisions.append(
                SupervisorDecision(
                    proposal_index=i,
                    status="approved",
                    reason="within risk caps",
                )
            )
            approved.append(prop)

        if not input_artifact.candidate_plan.proposals:
            overall = "approved"  # nothing to gate
        elif not approved:
            overall = "all_rejected"
        elif len(approved) < len(input_artifact.candidate_plan.proposals):
            overall = "partial"
        else:
            overall = "approved"

        return ApprovedPlan(
            run_id=input_artifact.run_id,
            produced_at_iso=datetime.now(tz=timezone.utc).isoformat(),
            candidate_plan_run_id=input_artifact.candidate_plan.run_id,
            decisions=decisions,
            approved_proposals=approved,
            overall_status=overall,
            risk_notes=(
                f"equity={input_artifact.portfolio_equity_usd}, "
                f"max_risk_per_trade={input_artifact.max_risk_per_trade}, "
                f"daily_dd_so_far={input_artifact.daily_drawdown_so_far}"
            ),
        )
