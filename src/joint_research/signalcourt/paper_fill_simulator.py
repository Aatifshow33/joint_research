"""Deterministic non-executing paper fill simulator for SignalCourt previews."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from joint_research.signalcourt.paper_order_preview import (
    PAPER_ORDER_ACTION_NO_TRADE,
    PAPER_ORDER_ACTION_PREVIEW_ONLY,
    PAPER_ORDER_ACTION_WATCH_ONLY,
    SignalCourtPaperOrderPreview,
)

FILL_MODE_REJECT_IF_BLOCKED = "REJECT_IF_BLOCKED"
FILL_MODE_LIMIT_CROSSES_MARK = "LIMIT_CROSSES_MARK"
FILL_MODE_SIMULATED_MID = "SIMULATED_MID"

FILL_STATUS_BLOCKED = "PAPER_FILL_BLOCKED"
FILL_STATUS_REJECTED = "PAPER_FILL_REJECTED"
FILL_STATUS_PREVIEW_ONLY = "PAPER_FILL_PREVIEW_ONLY"
FILL_STATUS_SIMULATED = "PAPER_FILL_SIMULATED"


@dataclass(frozen=True)
class PaperFillMarketSnapshot:
    mark_price: float = 0.0
    bid_price: float = 0.0
    ask_price: float = 0.0
    slippage_bps: float = 0.0
    fee_bps: float = 0.0
    fill_mode: str = FILL_MODE_REJECT_IF_BLOCKED


@dataclass(frozen=True)
class PaperFillSimulationResult:
    run_id: str
    lane: str
    symbol: str
    side: str
    requested_quantity: float
    requested_limit_price: float
    requested_notional_usd: float
    simulated_fill_status: str
    simulated_fill_price: float
    simulated_fill_quantity: float
    simulated_fee_usd: float
    simulated_slippage_bps: float
    paper_fill_allowed: bool
    live_fill_allowed: bool
    blocked_reasons: list[str]
    required_next_gates: list[str]
    source_preview: dict[str, object]
    non_authorization_notice: str
    simulator_safety_metadata: dict[str, bool]


def simulate_paper_fill(
    preview: SignalCourtPaperOrderPreview,
    *,
    ledger_record: dict[str, object] | None = None,
    market_snapshot: PaperFillMarketSnapshot | None = None,
) -> PaperFillSimulationResult:
    snapshot = market_snapshot or PaperFillMarketSnapshot()
    blocked_reasons = list(dict.fromkeys(preview.blocked_reasons or []))
    required_next_gates = list(dict.fromkeys([
        *(preview.required_next_gates or []),
        "Keep golden evaluations passing.",
    ]))

    source_preview = _resolve_source_preview(preview=preview, ledger_record=ledger_record)
    status, fill_price, fill_quantity, fill_allowed = _simulate_status_and_fill(
        preview=preview,
        blocked_reasons=blocked_reasons,
        snapshot=snapshot,
    )
    fee_usd = _compute_fee_usd(
        quantity=fill_quantity,
        fill_price=fill_price,
        fee_bps=snapshot.fee_bps,
    )

    non_auth_notice = (
        f"{preview.non_authorization_notice} "
        "Paper fill simulation is non-executing and does not authorize broker/exchange calls, "
        "paper/live order submission, or execution."
    ).strip()

    return PaperFillSimulationResult(
        run_id=preview.run_id,
        lane=preview.lane,
        symbol=preview.symbol,
        side=preview.side,
        requested_quantity=float(preview.quantity),
        requested_limit_price=float(preview.limit_price),
        requested_notional_usd=float(preview.notional_usd),
        simulated_fill_status=status,
        simulated_fill_price=fill_price,
        simulated_fill_quantity=fill_quantity,
        simulated_fee_usd=fee_usd,
        simulated_slippage_bps=float(snapshot.slippage_bps),
        paper_fill_allowed=fill_allowed,
        live_fill_allowed=False,
        blocked_reasons=blocked_reasons,
        required_next_gates=required_next_gates,
        source_preview=source_preview,
        non_authorization_notice=non_auth_notice,
        simulator_safety_metadata={
            "execution_performed": False,
            "broker_call_performed": False,
            "exchange_call_performed": False,
            "live_order_submitted": False,
            "paper_order_submitted": False,
            "artifact_written": False,
            "ingestion_run": False,
            "simulation_only": True,
        },
    )


def _resolve_source_preview(
    *,
    preview: SignalCourtPaperOrderPreview,
    ledger_record: dict[str, object] | None,
) -> dict[str, object]:
    if not ledger_record:
        return asdict(preview)
    source = ledger_record.get("source_preview")
    if isinstance(source, dict):
        return source
    return asdict(preview)


def _simulate_status_and_fill(
    *,
    preview: SignalCourtPaperOrderPreview,
    blocked_reasons: list[str],
    snapshot: PaperFillMarketSnapshot,
) -> tuple[str, float, float, bool]:
    if not preview.paper_order_allowed:
        if preview.paper_order_action in {PAPER_ORDER_ACTION_WATCH_ONLY, PAPER_ORDER_ACTION_PREVIEW_ONLY}:
            return (FILL_STATUS_REJECTED, 0.0, 0.0, False)
        return (FILL_STATUS_BLOCKED, 0.0, 0.0, False)

    if blocked_reasons and snapshot.fill_mode == FILL_MODE_REJECT_IF_BLOCKED:
        return (FILL_STATUS_REJECTED, 0.0, 0.0, False)

    if preview.paper_order_action == PAPER_ORDER_ACTION_NO_TRADE:
        return (FILL_STATUS_PREVIEW_ONLY, 0.0, 0.0, False)

    fill_price = _resolve_fill_price(preview=preview, snapshot=snapshot)
    if fill_price <= 0.0:
        return (FILL_STATUS_REJECTED, 0.0, 0.0, False)

    fill_quantity = max(float(preview.quantity), 0.0)
    return (FILL_STATUS_SIMULATED, fill_price, fill_quantity, True)


def _resolve_fill_price(
    *,
    preview: SignalCourtPaperOrderPreview,
    snapshot: PaperFillMarketSnapshot,
) -> float:
    side = preview.side.upper()
    limit = float(preview.limit_price)
    bid = float(snapshot.bid_price)
    ask = float(snapshot.ask_price)
    mark = float(snapshot.mark_price)

    if snapshot.fill_mode == FILL_MODE_LIMIT_CROSSES_MARK:
        if side == "BUY":
            if ask > 0 and limit > 0 and limit >= ask:
                return ask
            return 0.0
        if side == "SELL":
            if bid > 0 and limit > 0 and limit <= bid:
                return bid
            return 0.0
        return 0.0

    if snapshot.fill_mode == FILL_MODE_SIMULATED_MID:
        if bid > 0 and ask > 0:
            return round((bid + ask) / 2.0, 8)
        if mark > 0:
            return mark
        if limit > 0:
            return limit
        return 0.0

    # REJECT_IF_BLOCKED mode: only price when explicit paper-order-allowed path exists.
    if mark > 0:
        return mark
    if bid > 0 and ask > 0:
        return round((bid + ask) / 2.0, 8)
    if limit > 0:
        return limit
    return 0.0


def _compute_fee_usd(*, quantity: float, fill_price: float, fee_bps: float) -> float:
    notional = max(quantity, 0.0) * max(fill_price, 0.0)
    return round(notional * max(fee_bps, 0.0) / 10_000.0, 8)
