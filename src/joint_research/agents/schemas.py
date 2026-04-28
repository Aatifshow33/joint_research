"""Typed JSON artifacts the agent crew exchanges.

Pydantic models so every step has a contract; nothing flows through the crew
unless it validates. ``schema_version`` on each artifact lets us evolve the
contracts without silently corrupting the decision log.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ArtifactBase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    run_id: str
    produced_at_iso: str


class FactorObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    value: float | None
    pct_rank_1y: float | None = None
    pct_rank_5y: float | None = None
    change_1d: float | None = None


class ResearchBrief(_ArtifactBase):
    """Researcher → Planner."""

    as_of_date: str
    regime: Literal["risk_off", "recession_risk", "goldilocks", "neutral", "unknown"]
    headline: str
    factors: list[FactorObservation] = Field(default_factory=list)
    notable_moves: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class TradeProposal(BaseModel):
    """One proposed trade. The Planner emits these; the Supervisor approves them."""

    model_config = ConfigDict(extra="forbid")
    strategy_id: str
    asset_class: Literal["equity", "crypto"]
    venue: Literal["alpaca", "bybit"] | None = None
    symbol: str
    side: Literal["buy", "sell", "long", "short"]
    target_notional_usd: float = Field(gt=0)
    entry_reference: float | None = None
    stop_price: float | None = None
    take_profit_price: float | None = None
    expected_holding_days: int = Field(ge=1, le=365)
    thesis: str = Field(min_length=1)
    risk_pct_of_equity: float = Field(ge=0, le=0.05)


class CandidatePlan(_ArtifactBase):
    """Planner → Supervisor."""

    research_brief_run_id: str
    proposals: list[TradeProposal] = Field(default_factory=list)
    rationale: str = Field(min_length=1)


class SupervisorDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_index: int
    status: Literal["approved", "rejected", "modified"]
    reason: str = Field(min_length=1)
    modifications: dict[str, float] = Field(default_factory=dict)


class ApprovedPlan(_ArtifactBase):
    """Supervisor → Executor. ``approved_proposals`` is the trimmed set that may execute."""

    candidate_plan_run_id: str
    decisions: list[SupervisorDecision] = Field(default_factory=list)
    approved_proposals: list[TradeProposal] = Field(default_factory=list)
    overall_status: Literal["approved", "all_rejected", "partial"]
    risk_notes: str = Field(default="")


class ExecutionFill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_index: int
    venue: str
    symbol: str
    side: str
    filled_quantity: float
    fill_price: float
    fill_time_iso: str
    broker_order_id: str
    fees_paid: float = 0.0


class ExecutionLog(_ArtifactBase):
    """Executor → Reviewer. ``mode`` is one of paper / live / dry-run."""

    approved_plan_run_id: str
    mode: Literal["paper", "live", "dry_run"]
    fills: list[ExecutionFill] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CalibrationDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    prior_value: float | None = None
    posterior_value: float | None = None
    note: str = ""


class Postmortem(_ArtifactBase):
    """Reviewer → Memory."""

    covers_run_id: str
    realized_pnl_usd: float
    expected_pnl_usd: float
    hits: list[str] = Field(default_factory=list)
    misses: list[str] = Field(default_factory=list)
    calibration_deltas: list[CalibrationDelta] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
