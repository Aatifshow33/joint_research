"""Orchestrator: runs the crew end-to-end and persists every artifact."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from joint_research.agents.base import AgentDecisionLog, AgentMode
from joint_research.agents.executor import ExecutorAgent, ExecutorInput
from joint_research.agents.memory import AgentMemory
from joint_research.agents.planner import PlannerAgent, PlannerInput
from joint_research.agents.researcher import ResearcherAgent, ResearcherInput
from joint_research.agents.reviewer import ReviewerAgent, ReviewerInput
from joint_research.agents.schemas import (
    ApprovedPlan,
    CandidatePlan,
    ExecutionLog,
    Postmortem,
    ResearchBrief,
)
from joint_research.agents.supervisor import SupervisorAgent, SupervisorInput
from joint_research.warehouse.paths import WarehousePaths


@dataclass
class CrewRunResult:
    run_id: str
    run_dir: Path
    research_brief: ResearchBrief
    candidate_plan: CandidatePlan
    approved_plan: ApprovedPlan
    execution_log: ExecutionLog
    postmortem: Postmortem | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class CrewOrchestrator:
    paths: WarehousePaths
    runs_root: Path
    memory: AgentMemory
    mode: AgentMode = AgentMode.STUB

    def run(
        self,
        *,
        as_of_date: str,
        portfolio_equity_usd: float = 200.0,
        execution_mode: Literal["paper", "live", "dry_run"] = "dry_run",
        kill_switch_active: bool = False,
        run_reviewer: bool = True,
    ) -> CrewRunResult:
        run_id = _new_run_id()
        run_dir = self.runs_root / run_id
        log = AgentDecisionLog(run_dir=run_dir)

        researcher = ResearcherAgent(paths=self.paths, mode=self.mode, decision_log=log)
        planner = PlannerAgent(mode=self.mode, decision_log=log)
        supervisor = SupervisorAgent(mode=self.mode, decision_log=log)
        executor = ExecutorAgent(mode=self.mode, decision_log=log)

        brief = researcher.run(ResearcherInput(run_id=run_id, as_of_date=as_of_date))
        candidate = planner.run(
            PlannerInput(
                run_id=run_id,
                research_brief=brief,
                portfolio_equity_usd=portfolio_equity_usd,
            )
        )
        approved = supervisor.run(
            SupervisorInput(
                run_id=run_id,
                candidate_plan=candidate,
                portfolio_equity_usd=portfolio_equity_usd,
                kill_switch_active=kill_switch_active,
            )
        )
        execution = executor.run(
            ExecutorInput(
                run_id=run_id,
                approved_plan=approved,
                execution_mode=execution_mode,
            )
        )

        postmortem: Postmortem | None = None
        if run_reviewer:
            reviewer = ReviewerAgent(mode=self.mode, decision_log=log)
            postmortem = reviewer.run(
                ReviewerInput(
                    run_id=run_id,
                    research_brief=brief,
                    approved_plan=approved,
                    execution_log=execution,
                )
            )
            self.memory.append(
                kind="postmortem",
                run_id=run_id,
                payload=postmortem.model_dump(mode="json"),
            )

        return CrewRunResult(
            run_id=run_id,
            run_dir=run_dir,
            research_brief=brief,
            candidate_plan=candidate,
            approved_plan=approved,
            execution_log=execution,
            postmortem=postmortem,
        )


def _new_run_id() -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{secrets.token_hex(3)}"
