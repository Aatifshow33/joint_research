"""Trading agent crew.

Composed of:

- ``Researcher`` — produces the daily macro brief.
- ``Planner`` — turns the brief + portfolio + strategy menu into a candidate plan.
- ``Supervisor`` — vetoes/modifies the plan against risk constraints.
- ``Executor`` — routes approved orders to brokers (Alpaca, Bybit).
- ``Reviewer`` — end-of-day postmortem + memory updates.

Agents communicate exclusively via Pydantic-typed JSON artifacts. Each run
is logged to ``data/agent_runs/{run_id}/`` for audit.
"""

from joint_research.agents.base import Agent, AgentDecisionLog, AgentMode
from joint_research.agents.executor import ExecutorAgent
from joint_research.agents.memory import AgentMemory
from joint_research.agents.orchestrator import CrewOrchestrator, CrewRunResult
from joint_research.agents.planner import PlannerAgent
from joint_research.agents.researcher import ResearcherAgent
from joint_research.agents.reviewer import ReviewerAgent
from joint_research.agents.schemas import (
    ApprovedPlan,
    CandidatePlan,
    ExecutionLog,
    Postmortem,
    ResearchBrief,
    SupervisorDecision,
    TradeProposal,
)
from joint_research.agents.supervisor import SupervisorAgent

__all__ = [
    "Agent",
    "AgentDecisionLog",
    "AgentMemory",
    "AgentMode",
    "ApprovedPlan",
    "CandidatePlan",
    "CrewOrchestrator",
    "CrewRunResult",
    "ExecutionLog",
    "ExecutorAgent",
    "PlannerAgent",
    "Postmortem",
    "ResearchBrief",
    "ResearcherAgent",
    "ReviewerAgent",
    "SupervisorAgent",
    "SupervisorDecision",
    "TradeProposal",
]
