"""Base ``Agent`` class and decision-log primitives.

Every agent in the crew subclasses ``Agent`` and implements ``decide()``,
which takes a typed input artifact and returns a typed output artifact. The
runtime mode (``stub`` / ``live``) controls whether ``decide()`` calls the
LLM or returns a deterministic placeholder. We start in ``stub`` mode so the
orchestration is auditable before any tokens get spent.
"""

from __future__ import annotations

import enum
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


class AgentMode(str, enum.Enum):
    STUB = "stub"
    LIVE = "live"


InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass
class AgentDecisionLog:
    """Append-only log of every ``decide()`` call across the crew.

    Entries are written as one JSON file per call under the run directory and
    rolled up to a Parquet table at end of run for audit.
    """

    run_dir: Path

    def write(
        self,
        *,
        agent_name: str,
        mode: AgentMode,
        input_artifact: BaseModel,
        output_artifact: BaseModel,
        latency_ms: int,
        notes: str | None = None,
    ) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        record = {
            "agent_name": agent_name,
            "mode": mode.value,
            "produced_at_iso": timestamp,
            "latency_ms": latency_ms,
            "input": input_artifact.model_dump(mode="json"),
            "output": output_artifact.model_dump(mode="json"),
            "notes": notes,
        }
        path = self.run_dir / f"{agent_name}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        return path


class Agent(ABC, Generic[InputT, OutputT]):
    """Common scaffolding for every agent in the crew."""

    name: str = "agent"

    def __init__(
        self,
        *,
        mode: AgentMode = AgentMode.STUB,
        decision_log: AgentDecisionLog | None = None,
    ) -> None:
        self.mode = mode
        self.decision_log = decision_log

    def run(self, input_artifact: InputT) -> OutputT:
        start = datetime.now(tz=timezone.utc)
        if self.mode is AgentMode.STUB:
            output = self.decide_stub(input_artifact)
        else:
            output = self.decide_live(input_artifact)
        elapsed_ms = int(
            (datetime.now(tz=timezone.utc) - start).total_seconds() * 1000
        )
        if self.decision_log is not None:
            self.decision_log.write(
                agent_name=self.name,
                mode=self.mode,
                input_artifact=input_artifact,
                output_artifact=output,
                latency_ms=elapsed_ms,
            )
        return output

    @abstractmethod
    def decide_stub(self, input_artifact: InputT) -> OutputT:
        """Deterministic placeholder used in ``stub`` mode for orchestrator tests."""

    def decide_live(self, input_artifact: InputT) -> OutputT:
        """Override in subclasses to call Claude. Default raises until wired."""

        raise NotImplementedError(
            f"{self.name}: live mode not yet wired. Implement decide_live()."
        )
