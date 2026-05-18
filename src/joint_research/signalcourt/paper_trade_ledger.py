"""Local non-executing paper trade ledger writer for paper order previews."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from joint_research.signalcourt.paper_order_preview import SignalCourtPaperOrderPreview

_DEFAULT_SESSION_ID = "default"
_SCHEMA_VERSION = "1.0"
_LEDGER_RECORD_TYPE = "signalcourt_paper_trade_preview"


@dataclass(frozen=True)
class PaperTradeLedgerWriteResult:
    ledger_path: Path
    session_id: str
    records_written: int
    run_id: str
    lane: str
    paper_order_action: str
    paper_order_allowed: bool
    live_order_allowed: bool
    non_authorization_notice: str


def write_paper_trade_ledger_record(
    preview: SignalCourtPaperOrderPreview,
    ledger_dir: Path | str,
    *,
    session_id: str | None = None,
) -> PaperTradeLedgerWriteResult:
    if ledger_dir is None:
        raise ValueError("ledger_dir must be explicitly provided")

    safe_session_id = _sanitize_identifier(
        _DEFAULT_SESSION_ID if session_id is None else session_id,
        field_name="session_id",
    )
    safe_run_id = _sanitize_identifier(preview.run_id, field_name="run_id")

    ledger_dir_path = Path(ledger_dir).expanduser().resolve()
    ledger_dir_path.mkdir(parents=True, exist_ok=True)

    ledger_path = (ledger_dir_path / f"signalcourt_paper_trade_ledger_{safe_session_id}.jsonl").resolve()
    if ledger_path.parent != ledger_dir_path:
        raise ValueError("ledger output path must remain inside ledger_dir")

    payload = _build_payload(preview=preview, session_id=safe_session_id, safe_run_id=safe_run_id)
    line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(line)

    return PaperTradeLedgerWriteResult(
        ledger_path=ledger_path,
        session_id=safe_session_id,
        records_written=1,
        run_id=preview.run_id,
        lane=preview.lane,
        paper_order_action=preview.paper_order_action,
        paper_order_allowed=preview.paper_order_allowed,
        live_order_allowed=preview.live_order_allowed,
        non_authorization_notice=preview.non_authorization_notice,
    )


def _build_payload(
    *,
    preview: SignalCourtPaperOrderPreview,
    session_id: str,
    safe_run_id: str,
) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "ledger_record_type": _LEDGER_RECORD_TYPE,
        "session_id": session_id,
        "run_id": safe_run_id,
        "lane": preview.lane,
        "symbol": preview.symbol,
        "side": preview.side,
        "quantity": preview.quantity,
        "limit_price": preview.limit_price,
        "notional_usd": preview.notional_usd,
        "venue": preview.venue,
        "order_type": preview.order_type,
        "paper_order_action": preview.paper_order_action,
        "paper_order_allowed": preview.paper_order_allowed,
        "live_order_allowed": preview.live_order_allowed,
        "blocked_reasons": list(preview.blocked_reasons),
        "required_next_gates": list(preview.required_next_gates),
        "source_preview": asdict(preview),
        "non_authorization_notice": preview.non_authorization_notice,
        "writer_safety_metadata": {
            "execution_performed": False,
            "broker_call_performed": False,
            "exchange_call_performed": False,
            "live_order_submitted": False,
            "paper_order_submitted": False,
            "artifacts_refreshed": False,
            "ingestion_run": False,
            "explicit_ledger_dir_only": True,
        },
    }


def _sanitize_identifier(value: str, *, field_name: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError(f"{field_name} cannot be empty")
    if candidate in {".", ".."}:
        raise ValueError(f"{field_name} cannot be traversal-style")
    if "/" in candidate or "\\" in candidate or "\x00" in candidate:
        raise ValueError(f"{field_name} contains unsafe path characters")
    if ".." in candidate:
        raise ValueError(f"{field_name} cannot include traversal segments")
    return candidate
