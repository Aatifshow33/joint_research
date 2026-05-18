"""Read-only SignalCourt paper journal reader for JSONL review."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_NON_AUTH_NOTICE = (
    "Read-only SignalCourt paper journal summary. This does not authorize ingestion, "
    "candidate promotion, paper/live trading, order placement, or execution."
)
_REQUIRED_SAFETY_FIELDS = (
    "non_authorization_notice",
    "blocked",
    "paper_order_allowed",
    "live_order_allowed",
    "final_status",
)


@dataclass(frozen=True)
class PaperJournalReadSummary:
    record_count: int
    run_ids: list[str]
    lanes_encountered: list[str]
    final_statuses_encountered: list[str]
    blocked_count: int
    no_trade_count: int
    missing_safety_field_warnings: list[str]
    malformed_jsonl_line_warnings: list[str]
    containment_path_safety_warnings: list[str]
    source_files: list[str]
    non_authorization_notice: str


def read_paper_journal_records(
    *,
    jsonl_file_path: Path | str | None = None,
    output_dir_path: Path | str | None = None,
) -> PaperJournalReadSummary:
    if jsonl_file_path is None and output_dir_path is None:
        raise ValueError("Explicit input required: provide jsonl_file_path or output_dir_path")
    if jsonl_file_path is not None and output_dir_path is not None:
        raise ValueError("Provide only one input: jsonl_file_path or output_dir_path")

    malformed_warnings: list[str] = []
    missing_safety_warnings: list[str] = []
    containment_warnings: list[str] = []

    source_files: list[Path] = []
    if jsonl_file_path is not None:
        _reject_unsafe_input_path(jsonl_file_path)
        resolved = Path(jsonl_file_path).expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"JSONL file does not exist: {resolved}")
        source_files = [resolved]
    else:
        _reject_unsafe_input_path(output_dir_path)
        output_dir = Path(output_dir_path).expanduser().resolve()
        if not output_dir.exists() or not output_dir.is_dir():
            raise ValueError(f"Output directory does not exist: {output_dir}")
        for file_path in sorted(output_dir.glob("*.jsonl")):
            resolved_file = file_path.resolve()
            if not resolved_file.is_relative_to(output_dir):
                containment_warnings.append(
                    "Skipped file outside explicit output directory scope: "
                    + str(resolved_file)
                )
                continue
            source_files.append(resolved_file)

    run_ids: set[str] = set()
    lanes: set[str] = set()
    final_statuses: set[str] = set()
    blocked_count = 0
    no_trade_count = 0
    record_count = 0

    for source in source_files:
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                malformed_warnings.append(
                    f"{source}:{line_number}: malformed JSONL line"
                )
                continue
            if not isinstance(payload, dict):
                malformed_warnings.append(
                    f"{source}:{line_number}: record is not a JSON object"
                )
                continue

            record_count += 1
            _collect_safety_warnings(
                payload=payload,
                source=source,
                line_number=line_number,
                warnings=missing_safety_warnings,
            )

            run_id = payload.get("run_id")
            if isinstance(run_id, str) and run_id:
                run_ids.add(run_id)
            lane = payload.get("lane")
            if isinstance(lane, str) and lane:
                lanes.add(lane)
            final_status = payload.get("final_status")
            if isinstance(final_status, str) and final_status:
                final_statuses.add(final_status)
                if "NO_TRADE" in final_status:
                    no_trade_count += 1

            if payload.get("blocked") is True:
                blocked_count += 1

    return PaperJournalReadSummary(
        record_count=record_count,
        run_ids=sorted(run_ids),
        lanes_encountered=sorted(lanes),
        final_statuses_encountered=sorted(final_statuses),
        blocked_count=blocked_count,
        no_trade_count=no_trade_count,
        missing_safety_field_warnings=missing_safety_warnings,
        malformed_jsonl_line_warnings=malformed_warnings,
        containment_path_safety_warnings=containment_warnings,
        source_files=[str(path) for path in source_files],
        non_authorization_notice=_NON_AUTH_NOTICE,
    )


def _reject_unsafe_input_path(path_value: Path | str | None) -> None:
    if path_value is None:
        return
    raw = str(path_value).strip()
    if not raw:
        raise ValueError("Input path cannot be empty")
    normalized = raw.replace("\\", "/")
    if normalized in {".", ".."}:
        raise ValueError("Unsafe path traversal input")
    if "/../" in f"/{normalized}/" or normalized.startswith("../"):
        raise ValueError("Unsafe path traversal input")
    if ":" in Path(normalized).name:
        raise ValueError("Unsafe path input contains unsupported characters")


def _collect_safety_warnings(
    *,
    payload: dict[str, Any],
    source: Path,
    line_number: int,
    warnings: list[str],
) -> None:
    for field in _REQUIRED_SAFETY_FIELDS:
        if field not in payload:
            warnings.append(f"{source}:{line_number}: missing safety field '{field}'")
