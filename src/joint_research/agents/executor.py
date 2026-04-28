"""Executor agent: routes approved orders to brokers (or paper-fills in stub mode)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict

from joint_research.agents.base import Agent
from joint_research.agents.schemas import (
    ApprovedPlan,
    ExecutionFill,
    ExecutionLog,
)


class ExecutorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    approved_plan: ApprovedPlan
    execution_mode: Literal["paper", "live", "dry_run"] = "dry_run"


class ExecutorAgent(Agent[ExecutorInput, ExecutionLog]):
    name = "executor"

    def decide_stub(self, input_artifact: ExecutorInput) -> ExecutionLog:
        fills: list[ExecutionFill] = []
        errors: list[str] = []

        if input_artifact.execution_mode == "dry_run":
            # Don't generate fills in dry-run; just record what would have run.
            return ExecutionLog(
                run_id=input_artifact.run_id,
                produced_at_iso=datetime.now(tz=timezone.utc).isoformat(),
                approved_plan_run_id=input_artifact.approved_plan.run_id,
                mode=input_artifact.execution_mode,
                fills=[],
                errors=[
                    "dry_run: no broker calls made; "
                    f"would have routed {len(input_artifact.approved_plan.approved_proposals)} proposal(s)"
                ],
            )

        # Paper-fill stub: instant fills at entry_reference (or 1.0 if missing).
        for idx, proposal in enumerate(input_artifact.approved_plan.approved_proposals):
            entry_ref = proposal.entry_reference or 1.0
            qty = proposal.target_notional_usd / max(entry_ref, 1e-9)
            fills.append(
                ExecutionFill(
                    proposal_index=idx,
                    venue=proposal.venue or "stub",
                    symbol=proposal.symbol,
                    side=proposal.side,
                    filled_quantity=qty,
                    fill_price=entry_ref,
                    fill_time_iso=datetime.now(tz=timezone.utc).isoformat(),
                    broker_order_id=f"stub-{input_artifact.run_id}-{idx}",
                    fees_paid=0.0,
                )
            )

        return ExecutionLog(
            run_id=input_artifact.run_id,
            produced_at_iso=datetime.now(tz=timezone.utc).isoformat(),
            approved_plan_run_id=input_artifact.approved_plan.run_id,
            mode=input_artifact.execution_mode,
            fills=fills,
            errors=errors,
        )
