"""Researcher agent: turns warehouse state into a daily ResearchBrief."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict

import duckdb

from joint_research.agents.base import Agent
from joint_research.agents.schemas import FactorObservation, ResearchBrief
from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.views import register_views


class ResearcherInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    as_of_date: str  # YYYY-MM-DD; the most recent macro_state row at or before this is used


class ResearcherAgent(Agent[ResearcherInput, ResearchBrief]):
    name = "researcher"

    def __init__(self, *, paths: WarehousePaths, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._paths = paths

    def decide_stub(self, input_artifact: ResearcherInput) -> ResearchBrief:
        """Read the latest ``macro_state_daily`` row and shape it into a brief.

        This is fully deterministic — no LLM. The structure mirrors what the
        live (Claude-powered) version will emit, so the orchestrator and
        downstream agents are testable today.
        """

        con = duckdb.connect()
        register_views(con, self._paths)
        row = _latest_macro_state(con, input_artifact.as_of_date)

        produced_at = datetime.now(tz=timezone.utc).isoformat()
        if row is None:
            return ResearchBrief(
                run_id=input_artifact.run_id,
                produced_at_iso=produced_at,
                as_of_date=input_artifact.as_of_date,
                regime="unknown",
                headline="No macro_state row available; backfill is empty or stale.",
                factors=[],
                notable_moves=[],
                open_questions=["macro_state_daily is empty — run ingest first"],
            )

        factors = _factor_observations(row)
        notable = _notable_moves(row)
        regime = row.get("regime") or "unknown"
        headline = (
            f"Regime={regime}. "
            f"VIX={_fmt(row.get('vix'))} (1y pct_rank={_pct(row.get('vix_pct_1y'))}). "
            f"2s10s={_fmt(row.get('curve_2s10s'))}. "
            f"NFCI={_fmt(row.get('nfci'))} (1y pct_rank={_pct(row.get('nfci_pct_1y'))})."
        )

        return ResearchBrief(
            run_id=input_artifact.run_id,
            produced_at_iso=produced_at,
            as_of_date=input_artifact.as_of_date,
            regime=regime,
            headline=headline,
            factors=factors,
            notable_moves=notable,
            open_questions=_open_questions(row),
        )


def _latest_macro_state(con: duckdb.DuckDBPyConnection, as_of_date: str) -> dict | None:
    try:
        cutoff_ns = int(
            datetime.fromisoformat(as_of_date)
            .replace(tzinfo=timezone.utc, hour=23, minute=59, second=59)
            .timestamp() * 1_000_000_000
        )
    except ValueError:
        return None
    rows = con.execute(
        """
        SELECT *
        FROM macro_state_daily
        WHERE open_time_ns <= ?
        ORDER BY open_time_ns DESC
        LIMIT 1
        """,
        [cutoff_ns],
    ).fetchall()
    if not rows:
        return None
    columns = [desc[0] for desc in con.description]
    return dict(zip(columns, rows[0]))


def _factor_observations(row: dict) -> list[FactorObservation]:
    spec = [
        ("fed_funds", "fed_funds", None, None, None),
        ("yield_2y", "yield_2y", None, None, None),
        ("yield_10y", "yield_10y", None, None, None),
        ("real_10y", "real_10y", None, None, None),
        ("curve_2s10s", "curve_2s10s", None, None, None),
        ("dxy_broad", "dxy_broad", None, None, None),
        ("vix", "vix", "vix_pct_1y", None, None),
        ("nfci", "nfci", "nfci_pct_1y", None, None),
        ("unrate", "unrate", None, None, None),
        ("cpi_change_1m", "cpi_change_1m", None, None, None),
    ]
    out: list[FactorObservation] = []
    for name, value_col, pct_1y_col, pct_5y_col, change_col in spec:
        out.append(
            FactorObservation(
                name=name,
                value=_optional_float(row.get(value_col)),
                pct_rank_1y=_optional_float(row.get(pct_1y_col)) if pct_1y_col else None,
                pct_rank_5y=_optional_float(row.get(pct_5y_col)) if pct_5y_col else None,
                change_1d=_optional_float(row.get(change_col)) if change_col else None,
            )
        )
    return out


def _notable_moves(row: dict) -> list[str]:
    notes: list[str] = []
    vix_pct = row.get("vix_pct_1y")
    if vix_pct is not None and vix_pct >= 0.85:
        notes.append(f"VIX in 1y top 15% (pct_rank={_pct(vix_pct)}) — risk-off flag.")
    if vix_pct is not None and vix_pct <= 0.15:
        notes.append(f"VIX in 1y bottom 15% (pct_rank={_pct(vix_pct)}) — complacency flag.")
    curve = row.get("curve_2s10s")
    if curve is not None and curve < 0:
        notes.append(f"2s10s inverted ({_fmt(curve)}) — recession-watch indicator.")
    nfci_pct = row.get("nfci_pct_1y")
    if nfci_pct is not None and nfci_pct >= 0.80:
        notes.append(
            f"Financial conditions tight (NFCI 1y pct_rank={_pct(nfci_pct)}) — credit stress."
        )
    return notes


def _open_questions(row: dict) -> list[str]:
    questions: list[str] = []
    if row.get("nfci") is None:
        questions.append("NFCI missing — backfill incomplete?")
    if row.get("breakeven_10y") is None:
        questions.append("10y breakeven missing — T10YIE backfill?")
    return questions


def _fmt(v: Any) -> str:
    if v is None:
        return "?"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


def _pct(v: Any) -> str:
    if v is None:
        return "?"
    try:
        return f"{float(v) * 100:.0f}%"
    except (TypeError, ValueError):
        return str(v)


def _optional_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
