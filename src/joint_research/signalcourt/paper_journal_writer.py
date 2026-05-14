"""Deterministic non-executing paper journal writer skeleton."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from joint_research.signalcourt.paper_journal import PaperJournalEntry
from joint_research.signalcourt.trace import SignalCourtTrace

_SAFE_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_DEFAULT_RUN_ID = "default"


@dataclass(frozen=True)
class PaperJournalWriteResult:
    output_path: Path
    run_id: str
    records_written: int
    lane: str
    signal_id: str
    final_status: str
    blocked: bool
    paper_order_allowed: bool
    live_order_allowed: bool
    non_authorization_notice: str
    safety_metadata: dict[str, str]


def write_paper_journal_entry(
    entry: PaperJournalEntry,
    trace: SignalCourtTrace,
    output_dir: Path | str,
    *,
    run_id: str | None = None,
) -> PaperJournalWriteResult:
    if output_dir is None:
        raise ValueError("output_dir must be explicitly provided")

    safe_run_id = _sanitize_run_id(run_id)
    output_dir_path = Path(output_dir).expanduser().resolve()
    output_dir_path.mkdir(parents=True, exist_ok=True)

    filename = f"signalcourt_paper_journal_{safe_run_id}.jsonl"
    output_path = (output_dir_path / filename).resolve()
    if output_path.parent != output_dir_path:
        raise ValueError("output path must remain inside output_dir")

    payload = _build_payload(entry=entry, trace=trace, run_id=safe_run_id)
    line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    output_path.write_text(line, encoding="utf-8")

    return PaperJournalWriteResult(
        output_path=output_path,
        run_id=safe_run_id,
        records_written=1,
        lane=entry.lane,
        signal_id=entry.signal_id,
        final_status=entry.final_status,
        blocked=entry.blocked,
        paper_order_allowed=entry.paper_order_allowed,
        live_order_allowed=entry.live_order_allowed,
        non_authorization_notice=entry.non_authorization_notice,
        safety_metadata={
            "execution_enabled": "false",
            "network_calls_enabled": "false",
            "exchange_calls_enabled": "false",
            "artifact_mutation_enabled": "false",
            "journal_scope": "explicit_output_dir_only",
        },
    )


def _sanitize_run_id(run_id: str | None) -> str:
    candidate = _DEFAULT_RUN_ID if run_id is None else run_id.strip()
    if not candidate:
        raise ValueError("run_id cannot be empty")
    if candidate in {".", ".."} or "/" in candidate or "\\" in candidate:
        raise ValueError("run_id contains path traversal characters")
    if not _SAFE_RUN_ID_PATTERN.fullmatch(candidate):
        raise ValueError("run_id contains unsupported characters")
    return candidate


def _build_payload(
    *,
    entry: PaperJournalEntry,
    trace: SignalCourtTrace,
    run_id: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "run_id": run_id,
        "trace_id": trace.trace_id,
        "lane": entry.lane,
        "signal_id": entry.signal_id,
        "final_status": entry.final_status,
        "blocked": entry.blocked,
        "paper_order_allowed": entry.paper_order_allowed,
        "live_order_allowed": entry.live_order_allowed,
        "non_authorization_notice": entry.non_authorization_notice,
        "trace_summary": {
            "final_status": trace.final_status,
            "blocked": trace.blocked,
            "paper_order_allowed": trace.paper_order_allowed,
            "live_order_allowed": trace.live_order_allowed,
            "step_names": [step.step_name for step in trace.steps],
            "warnings": list(trace.warnings),
        },
        "writer_safety_metadata": {
            "execution_enabled": False,
            "network_calls_enabled": False,
            "exchange_calls_enabled": False,
            "artifact_mutation_enabled": False,
        },
        "paper_journal_entry": asdict(entry),
    }
    return payload
