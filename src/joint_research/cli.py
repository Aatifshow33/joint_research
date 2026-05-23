"""``joint-research`` CLI entrypoint."""

from __future__ import annotations

import asyncio
import json
import math
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import typer

from joint_research.signalcourt.dashboard_renderer import (
    render_current_signalcourt_dashboard_summary,
)
from joint_research.research.wallet_flow_backfill_priority import (
    WalletFlowBackfillPriorityThresholds,
    write_wallet_flow_backfill_priority_artifacts,
)
from joint_research.research.wallet_flow_backfill_batches import (
    write_wallet_flow_backfill_batches_artifacts,
)
from joint_research.research.wallet_flow_backfill_manifest import (
    SUPPORTED_COMMAND_TEMPLATE_PRESETS,
    write_wallet_flow_backfill_manifest_artifacts,
)
from joint_research.research.wallet_flow_manifest_review_gate import (
    run_wallet_flow_manifest_review_gate,
)
from joint_research.research.wallet_flow_approved_manifest_packet import (
    write_wallet_flow_approved_manifest_packet,
)
from joint_research.research.wallet_flow_manifest_audit_index import (
    write_wallet_flow_manifest_audit_index,
)
from joint_research.research.wallet_flow_dry_run_execution_planner import (
    write_wallet_flow_dry_run_execution_plan,
)
from joint_research.research.wallet_flow_guarded_operator_handoff import (
    write_wallet_flow_guarded_operator_handoff,
)
from joint_research.research.wallet_flow_operator_approval_ledger import (
    write_wallet_flow_operator_approval_ledger,
)
from joint_research.research.wallet_flow_approval_execution_contract import (
    write_wallet_flow_approval_execution_contract,
)
from joint_research.research.wallet_flow_contract_audit_receipt import (
    write_wallet_flow_contract_audit_receipt,
)
from joint_research.research.wallet_flow_disabled_adapter_interface import (
    write_wallet_flow_disabled_adapter_interface,
)
from joint_research.research.wallet_flow_disabled_adapter_run_receipt import (
    write_wallet_flow_disabled_adapter_run_receipt,
)
from joint_research.research.wallet_flow_disabled_chain_summary import (
    write_wallet_flow_disabled_chain_summary,
)
from joint_research.research.wallet_flow_disabled_policy_guard import (
    write_wallet_flow_disabled_policy_guard,
)
from joint_research.warehouse import WarehousePaths

_DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS = WalletFlowBackfillPriorityThresholds()
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DERIVATIVES_ARTIFACT_DIR = _REPO_ROOT / "artifacts/research/derivatives_regime"
_WALLET_FLOW_ARTIFACT_DIR = _REPO_ROOT / "artifacts/research/wallet_flow_signal"
_DERIVATIVES_RESULTS_CSV = _DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_results.csv"
_DERIVATIVES_CANDIDATES_JSON = _DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_candidates.json"
_DERIVATIVES_SUMMARY_MD = _DERIVATIVES_ARTIFACT_DIR / "derivatives_regime_summary.md"
_WALLET_FLOW_SIGNAL_SUMMARY_MD = _WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_signal_summary.md"
_WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV = (
    _WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_rejection_diagnostics.csv"
)
_WALLET_FLOW_REJECTION_SUMMARY_MD = (
    _WALLET_FLOW_ARTIFACT_DIR / "wallet_flow_rejection_summary.md"
)

app = typer.Typer(no_args_is_help=True, add_completion=False)
ingest_app = typer.Typer(no_args_is_help=True, help="Ingest data into the warehouse.")
research_app = typer.Typer(no_args_is_help=True, help="Run research analyses against the warehouse.")
signalcourt_app = typer.Typer(no_args_is_help=True, help="SignalCourt review utilities.")
app.add_typer(ingest_app, name="ingest")
app.add_typer(research_app, name="research")
app.add_typer(signalcourt_app, name="signalcourt")


def _resolve_paths(warehouse_root: Path | None) -> WarehousePaths:
    if warehouse_root is not None:
        return WarehousePaths(root=warehouse_root.resolve())
    return WarehousePaths.from_env()


def _parse_iso_or_relative_days(value: str) -> datetime:
    """Accept an ISO-8601 datetime, an ISO date, or ``-Nd`` for "N days ago"."""

    if value.startswith("-") and value.endswith("d"):
        try:
            days = int(value[1:-1])
        except ValueError as exc:
            raise typer.BadParameter(f"invalid relative form: {value}") from exc
        return datetime.now(tz=timezone.utc) - timedelta(days=days)
    cleaned = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise typer.BadParameter(f"unparseable timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@signalcourt_app.command("dashboard-summary")
def signalcourt_dashboard_summary(
    wallet_signal_summary_md_path: Path = typer.Option(
        _WALLET_FLOW_SIGNAL_SUMMARY_MD,
        help="Path to wallet-flow summary markdown.",
    ),
    wallet_rejection_diagnostics_csv_path: Path = typer.Option(
        _WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        help="Path to wallet-flow rejection diagnostics CSV.",
    ),
    wallet_rejection_summary_md_path: Path = typer.Option(
        _WALLET_FLOW_REJECTION_SUMMARY_MD,
        help="Path to wallet-flow rejection summary markdown.",
    ),
    derivatives_results_csv_path: Path = typer.Option(
        _DERIVATIVES_RESULTS_CSV,
        help="Path to derivatives-regime results CSV.",
    ),
    derivatives_candidates_json_path: Path = typer.Option(
        _DERIVATIVES_CANDIDATES_JSON,
        help="Path to derivatives-regime candidates JSON.",
    ),
    derivatives_summary_md_path: Path = typer.Option(
        _DERIVATIVES_SUMMARY_MD,
        help="Path to derivatives-regime summary markdown.",
    ),
) -> None:
    """Print the current SignalCourt dashboard summary to stdout."""

    summary = render_current_signalcourt_dashboard_summary(
        wallet_signal_summary_md_path=wallet_signal_summary_md_path,
        wallet_rejection_diagnostics_csv_path=wallet_rejection_diagnostics_csv_path,
        wallet_rejection_summary_md_path=wallet_rejection_summary_md_path,
        derivatives_results_csv_path=derivatives_results_csv_path,
        derivatives_candidates_json_path=derivatives_candidates_json_path,
        derivatives_summary_md_path=derivatives_summary_md_path,
    )
    typer.echo(summary)


@signalcourt_app.command("live-submit-dry-run")
def signalcourt_live_submit_dry_run(
    lane: str = typer.Option(..., help="Signal lane: wallet-flow or derivatives-regime."),
    symbol: str = typer.Option(..., help="Order symbol for dry-run evaluation."),
    side: str = typer.Option(..., help="Order side (BUY/SELL) for dry-run evaluation."),
    quantity: float = typer.Option(..., help="Requested order quantity."),
    limit_price: float = typer.Option(..., help="Requested limit price."),
    notional_usd: float = typer.Option(..., help="Requested notional USD."),
    venue: str = typer.Option(..., help="Requested venue."),
    order_type: str = typer.Option(..., help="Requested order type."),
    manual_approval: bool = typer.Option(
        False,
        "--manual-approval/--no-manual-approval",
        help="Synthetic manual approval flag for dry-run gate evaluation.",
    ),
    operator_acknowledgement: bool = typer.Option(
        False,
        "--operator-acknowledgement/--no-operator-acknowledgement",
        help="Synthetic operator acknowledgement flag for dry-run gate evaluation.",
    ),
    max_micro_live_notional_usd: float = typer.Option(
        5.0,
        help="Synthetic max micro-live notional cap for dry-run gate evaluation.",
    ),
    approval_note: str = typer.Option(
        "",
        help="Optional operator note for approval packet dry-run evaluation.",
    ),
    approval_ttl_minutes: int = typer.Option(
        60,
        help="Optional approval TTL minutes for approval packet dry-run evaluation.",
    ),
    max_approved_notional_usd: float = typer.Option(
        0.0,
        help="Optional max approved notional USD for approval packet dry-run evaluation.",
    ),
    wallet_signal_summary_md_path: Path = typer.Option(
        _WALLET_FLOW_SIGNAL_SUMMARY_MD,
        help="Path to wallet-flow summary markdown.",
    ),
    wallet_rejection_diagnostics_csv_path: Path = typer.Option(
        _WALLET_FLOW_REJECTION_DIAGNOSTICS_CSV,
        help="Path to wallet-flow rejection diagnostics CSV.",
    ),
    wallet_rejection_summary_md_path: Path = typer.Option(
        _WALLET_FLOW_REJECTION_SUMMARY_MD,
        help="Path to wallet-flow rejection summary markdown.",
    ),
    derivatives_results_csv_path: Path = typer.Option(
        _DERIVATIVES_RESULTS_CSV,
        help="Path to derivatives-regime results CSV.",
    ),
    derivatives_candidates_json_path: Path = typer.Option(
        _DERIVATIVES_CANDIDATES_JSON,
        help="Path to derivatives-regime candidates JSON.",
    ),
    derivatives_summary_md_path: Path = typer.Option(
        _DERIVATIVES_SUMMARY_MD,
        help="Path to derivatives-regime summary markdown.",
    ),
) -> None:
    """Run a full SignalCourt live-submit dry run without any execution or network calls."""

    from joint_research.signalcourt.decision_preview import build_decision_preview  # noqa: PLC0415
    from joint_research.signalcourt.execution_adapter import (  # noqa: PLC0415
        ADAPTER_MODE_DRY_RUN,
        ADAPTER_MODE_LIVE_DISABLED,
        ExecutionAdapterPolicy,
        build_execution_request_from_preview,
        evaluate_execution_adapter,
    )
    from joint_research.signalcourt.micro_live_gate import (  # noqa: PLC0415
        MicroLiveGatePolicy,
        build_micro_live_request,
        evaluate_micro_live_gate,
    )
    from joint_research.signalcourt.live_approval_packet import (  # noqa: PLC0415
        LiveApprovalRequest,
        build_live_approval_packet,
    )
    from joint_research.signalcourt.paper_fill_simulator import (  # noqa: PLC0415
        FILL_MODE_REJECT_IF_BLOCKED,
        PaperFillMarketSnapshot,
        simulate_paper_fill,
    )
    from joint_research.signalcourt.paper_order_preview import (  # noqa: PLC0415
        PaperOrderRequest,
        build_paper_order_preview,
    )
    from joint_research.signalcourt.paper_performance_gate import (  # noqa: PLC0415
        review_paper_performance,
    )
    from joint_research.signalcourt.pipeline import (  # noqa: PLC0415
        build_derivatives_regime_pipeline,
        build_wallet_flow_pipeline,
    )
    from joint_research.signalcourt.risk_gate import (  # noqa: PLC0415
        default_decision_preview_risk_policy,
        default_tiny_account_risk_config,
        evaluate_decision_preview_risk_gate,
    )
    from joint_research.signalcourt.readiness_bundle import (  # noqa: PLC0415
        build_readiness_bundle,
    )

    normalized_lane = lane.strip().lower()
    if normalized_lane in {"wallet-flow", "wallet_flow", "wallet_flow_signal"}:
        pipeline = build_wallet_flow_pipeline(
            signal_summary_md_path=wallet_signal_summary_md_path,
            rejection_diagnostics_csv_path=wallet_rejection_diagnostics_csv_path,
            rejection_summary_md_path=wallet_rejection_summary_md_path,
            risk_config=default_tiny_account_risk_config(50.0),
        )
        lane_label = "wallet-flow"
    elif normalized_lane in {"derivatives-regime", "derivatives_regime"}:
        pipeline = build_derivatives_regime_pipeline(
            results_csv_path=derivatives_results_csv_path,
            candidates_json_path=derivatives_candidates_json_path,
            summary_md_path=derivatives_summary_md_path,
            risk_config=default_tiny_account_risk_config(100.0),
        )
        lane_label = "derivatives-regime"
    else:
        raise typer.BadParameter(
            "lane must be one of: wallet-flow, derivatives-regime",
            param_hint="--lane",
        )

    decision_preview = build_decision_preview(pipeline)
    decision_risk = evaluate_decision_preview_risk_gate(
        decision_preview,
        risk_policy=default_decision_preview_risk_policy(),
    )
    paper_order_preview = build_paper_order_preview(
        decision_preview,
        decision_risk,
        order_request=PaperOrderRequest(
            symbol=symbol,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            notional_usd=notional_usd,
            venue=venue,
            order_type=order_type,
        ),
    )
    paper_fill = simulate_paper_fill(
        paper_order_preview,
        market_snapshot=PaperFillMarketSnapshot(
            mark_price=float(limit_price) if float(limit_price) > 0 else 0.0,
            bid_price=float(limit_price) if float(limit_price) > 0 else 0.0,
            ask_price=float(limit_price) if float(limit_price) > 0 else 0.0,
            slippage_bps=0.0,
            fee_bps=0.0,
            fill_mode=FILL_MODE_REJECT_IF_BLOCKED,
        ),
    )
    paper_performance = review_paper_performance([paper_fill])
    execution_request = build_execution_request_from_preview(
        paper_order_preview,
        requested_mode=ADAPTER_MODE_DRY_RUN,
    )
    execution_result = evaluate_execution_adapter(
        preview=paper_order_preview,
        fill_result=paper_fill,
        performance_result=paper_performance,
        request=execution_request,
        policy=ExecutionAdapterPolicy(
            live_trading_enabled=False,
            paper_trading_enabled=False,
            require_manual_approval=True,
            kill_switch_enabled=True,
            max_notional_usd=max_micro_live_notional_usd,
            allowlisted_symbols=(),
            allowlisted_venues=(),
            allow_market_orders=False,
            allow_leverage=False,
            adapter_mode=ADAPTER_MODE_LIVE_DISABLED,
        ),
    )
    micro_live_request = build_micro_live_request(
        performance_result=paper_performance,
        execution_result=execution_result,
        symbol=symbol,
        venue=venue,
        requested_notional_usd=notional_usd,
        order_type=order_type,
    )
    micro_live_result = evaluate_micro_live_gate(
        performance_result=paper_performance,
        execution_result=execution_result,
        request=micro_live_request,
        policy=MicroLiveGatePolicy(
            micro_live_enabled=False,
            require_manual_approval=True,
            manual_approval_granted=manual_approval,
            kill_switch_enabled=True,
            max_micro_live_notional_usd=max_micro_live_notional_usd,
            max_daily_loss_usd=1.0,
            max_session_loss_usd=0.5,
            allowlisted_symbols=(),
            allowlisted_venues=(),
            allow_market_orders=False,
            allow_leverage=False,
            require_paper_candidate=True,
            require_execution_adapter_live_disabled=True,
            require_no_execution_flags=True,
            require_golden_evaluations=True,
            require_operator_acknowledgement=operator_acknowledgement,
        ),
    )
    readiness_bundle = build_readiness_bundle(
        decision_preview=decision_preview,
        decision_risk=decision_risk,
        paper_order_preview=paper_order_preview,
        paper_fill_result=paper_fill,
        paper_performance_result=paper_performance,
        execution_adapter_result=execution_result,
        micro_live_gate_result=micro_live_result,
    )
    approval_packet = build_live_approval_packet(
        readiness_bundle,
        approval_request=LiveApprovalRequest(
            requested_by="signalcourt_live_submit_dry_run_cli",
            operator_acknowledgement=operator_acknowledgement,
            manual_approval_granted=manual_approval,
            approval_note=approval_note,
            approval_ttl_minutes=approval_ttl_minutes,
            max_approved_notional_usd=max_approved_notional_usd,
            requested_notional_usd=notional_usd,
        ),
    )

    payload = {
        "ok": True,
        "source": "signalcourt.live_submit_dry_run",
        "mode": "DRY_RUN_ONLY",
        "lane": lane_label,
        "run_id": decision_preview.run_id,
        "decision_preview": {
            "decision_action": decision_preview.decision_action,
            "paper_eligible": decision_preview.paper_eligible,
            "live_eligible": decision_preview.live_eligible,
            "blocked_reasons": decision_preview.blocked_reasons,
        },
        "decision_preview_summary": {
            "decision_action": decision_preview.decision_action,
            "paper_eligible": decision_preview.paper_eligible,
            "live_eligible": decision_preview.live_eligible,
            "blocked_reasons": decision_preview.blocked_reasons,
        },
        "risk_gate": {
            "risk_verdict": decision_risk.risk_verdict,
            "paper_allowed": decision_risk.paper_allowed,
            "live_allowed": decision_risk.live_allowed,
            "blocked_reasons": decision_risk.blocked_reasons,
        },
        "risk_gate_summary": {
            "risk_verdict": decision_risk.risk_verdict,
            "paper_allowed": decision_risk.paper_allowed,
            "live_allowed": decision_risk.live_allowed,
            "blocked_reasons": decision_risk.blocked_reasons,
        },
        "paper_order_preview": {
            "paper_order_action": paper_order_preview.paper_order_action,
            "paper_order_allowed": paper_order_preview.paper_order_allowed,
            "live_order_allowed": paper_order_preview.live_order_allowed,
            "blocked_reasons": paper_order_preview.blocked_reasons,
        },
        "paper_order_preview_summary": {
            "paper_order_action": paper_order_preview.paper_order_action,
            "paper_order_allowed": paper_order_preview.paper_order_allowed,
            "live_order_allowed": paper_order_preview.live_order_allowed,
            "blocked_reasons": paper_order_preview.blocked_reasons,
        },
        "paper_fill_simulation": {
            "simulated_fill_status": paper_fill.simulated_fill_status,
            "paper_fill_allowed": paper_fill.paper_fill_allowed,
            "live_fill_allowed": paper_fill.live_fill_allowed,
            "blocked_reasons": paper_fill.blocked_reasons,
        },
        "paper_fill_simulation_summary": {
            "simulated_fill_status": paper_fill.simulated_fill_status,
            "paper_fill_allowed": paper_fill.paper_fill_allowed,
            "live_fill_allowed": paper_fill.live_fill_allowed,
            "blocked_reasons": paper_fill.blocked_reasons,
        },
        "paper_performance_gate": {
            "performance_verdict": paper_performance.performance_verdict,
            "paper_review_allowed": paper_performance.paper_review_allowed,
            "live_review_allowed": paper_performance.live_review_allowed,
            "blocked_reasons": paper_performance.blocked_reasons,
        },
        "paper_performance_gate_summary": {
            "performance_verdict": paper_performance.performance_verdict,
            "paper_review_allowed": paper_performance.paper_review_allowed,
            "live_review_allowed": paper_performance.live_review_allowed,
            "blocked_reasons": paper_performance.blocked_reasons,
        },
        "execution_adapter": {
            "execution_verdict": execution_result.execution_verdict,
            "paper_execution_allowed": execution_result.paper_execution_allowed,
            "live_execution_allowed": execution_result.live_execution_allowed,
            "order_submitted": execution_result.order_submitted,
            "broker_call_performed": execution_result.broker_call_performed,
            "exchange_call_performed": execution_result.exchange_call_performed,
            "blocked_reasons": execution_result.blocked_reasons,
        },
        "execution_adapter_summary": {
            "execution_verdict": execution_result.execution_verdict,
            "paper_execution_allowed": execution_result.paper_execution_allowed,
            "live_execution_allowed": execution_result.live_execution_allowed,
            "order_submitted": execution_result.order_submitted,
            "broker_call_performed": execution_result.broker_call_performed,
            "exchange_call_performed": execution_result.exchange_call_performed,
            "blocked_reasons": execution_result.blocked_reasons,
        },
        "micro_live_gate": {
            "micro_live_verdict": micro_live_result.micro_live_verdict,
            "micro_live_review_ready": micro_live_result.micro_live_review_ready,
            "micro_live_execution_allowed": micro_live_result.micro_live_execution_allowed,
            "live_execution_allowed": micro_live_result.live_execution_allowed,
            "blocked_reasons": micro_live_result.blocked_reasons,
            "required_next_gates": micro_live_result.required_next_gates,
        },
        "micro_live_gate_summary": {
            "micro_live_verdict": micro_live_result.micro_live_verdict,
            "micro_live_review_ready": micro_live_result.micro_live_review_ready,
            "micro_live_execution_allowed": micro_live_result.micro_live_execution_allowed,
            "live_execution_allowed": micro_live_result.live_execution_allowed,
            "blocked_reasons": micro_live_result.blocked_reasons,
            "required_next_gates": micro_live_result.required_next_gates,
        },
        "readiness_bundle": asdict(readiness_bundle),
        "approval_packet": asdict(approval_packet),
        "approval_status": approval_packet.approval_status,
        "final_readiness_verdict": readiness_bundle.final_readiness_verdict,
        "final_verdict": micro_live_result.micro_live_verdict,
        "order_submitted": False,
        "broker_call_performed": False,
        "exchange_call_performed": False,
        "micro_live_execution_allowed": False,
        "live_execution_allowed": False,
        "non_authorization_notice": micro_live_result.non_authorization_notice,
    }
    typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))


@ingest_app.command("gamma-events")
def ingest_gamma_events(
    limit: int = typer.Option(500, help="Number of events to fetch in this run."),
    active: bool = typer.Option(True, help="Filter to currently-active events."),
    closed: bool = typer.Option(False, help="Include closed events."),
    archived: bool = typer.Option(False, help="Include archived events."),
    warehouse_root: Path = typer.Option(
        None,
        help="Override warehouse root. Defaults to $JOINT_RESEARCH_WAREHOUSE_ROOT or ./data/warehouse.",
    ),
) -> None:
    """Pull Polymarket /events from the Gamma API and append a Parquet shard."""

    from joint_research.ingest.polymarket_runner import ingest_gamma_events as run  # noqa: PLC0415

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(
        run(paths=paths, limit=limit, active=active, closed=closed, archived=archived)
    )
    if result.rows_written == 0:
        typer.echo("ingested=0 rows. nothing written.")
        raise typer.Exit(code=0)
    typer.echo(f"ingested={result.rows_written} shard={result.shard_path}")


@ingest_app.command("crypto-ohlcv")
def ingest_crypto_ohlcv(
    symbol: str = typer.Option(..., help="Binance symbol, e.g. BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT."),
    interval: str = typer.Option("1h", help="Kline interval: 1m/5m/15m/1h/4h/1d/etc."),
    start: str = typer.Option("-30d", help="Start time. ISO-8601 or '-Nd' for N days ago."),
    end: str = typer.Option(
        None,
        help="End time. ISO-8601 or '-Nd'. Defaults to 'now' (UTC).",
    ),
    warehouse_root: Path = typer.Option(
        None,
        help="Override warehouse root. Defaults to $JOINT_RESEARCH_WAREHOUSE_ROOT or ./data/warehouse.",
    ),
) -> None:
    """Pull Binance klines for [start, end) and append a Parquet shard."""

    from joint_research.ingest.crypto_runner import ingest_binance_ohlcv as run  # noqa: PLC0415

    paths = _resolve_paths(warehouse_root)
    start_dt = _parse_iso_or_relative_days(start)
    end_dt = (
        _parse_iso_or_relative_days(end)
        if end is not None
        else datetime.now(tz=timezone.utc)
    )

    result = asyncio.run(
        run(
            paths=paths,
            symbol=symbol,
            interval=interval,
            start=start_dt,
            end=end_dt,
        )
    )
    if result.rows_written == 0:
        typer.echo(
            f"ingested=0 symbol={result.symbol} interval={result.interval} "
            f"window={result.start_iso}..{result.end_iso}. nothing written."
        )
        raise typer.Exit(code=0)
    typer.echo(
        f"ingested={result.rows_written} symbol={result.symbol} interval={result.interval} "
        f"window={result.start_iso}..{result.end_iso} shard={result.shard_path}"
    )


@ingest_app.command("crypto-derivatives")
def ingest_crypto_derivatives(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT",
        help="Comma-separated Binance symbols.",
    ),
    limit: int = typer.Option(24, help="Funding rows per symbol."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull public/no-auth funding and perp-basis inputs into the warehouse."""

    from joint_research.ingest.crypto_derivatives import fetch_derivatives_rows  # noqa: PLC0415
    from joint_research.warehouse import CRYPTO_DERIVATIVES, ParquetWriter  # noqa: PLC0415

    paths = _resolve_paths(warehouse_root)
    symbol_list = tuple(s.strip().upper() for s in symbols.split(",") if s.strip())
    result = asyncio.run(fetch_derivatives_rows(symbols=symbol_list, limit=limit))
    if not result.rows:
        typer.echo(
            f"ingested=0 symbols={','.join(symbol_list)} errors={len(result.errors)}. "
            "nothing written."
        )
        for attempt in result.source_attempts:
            detail_suffix = f" detail={attempt.detail}" if attempt.detail else ""
            typer.echo(
                f"  source={attempt.source} symbol={attempt.symbol} type={attempt.record_type} "
                f"status={attempt.status} rows={attempt.rows}{detail_suffix}"
            )
        for error in result.errors:
            typer.echo(f"  warning={error}")
        raise typer.Exit(code=0)
    shard = ParquetWriter(table=CRYPTO_DERIVATIVES, paths=paths).write(
        [row.to_warehouse_row() for row in result.rows]
    )
    typer.echo(
        f"ingested={len(result.rows)} symbols={','.join(symbol_list)} "
        f"errors={len(result.errors)} shard={shard}"
    )
    for attempt in result.source_attempts:
        detail_suffix = f" detail={attempt.detail}" if attempt.detail else ""
        typer.echo(
            f"  source={attempt.source} symbol={attempt.symbol} type={attempt.record_type} "
            f"status={attempt.status} rows={attempt.rows}{detail_suffix}"
        )
    for error in result.errors:
        typer.echo(f"  warning={error}")


@ingest_app.command("gamma-crypto-markets")
def ingest_gamma_crypto_markets(
    limit: int = typer.Option(500, help="Max markets to fetch from Gamma."),
    active: bool = typer.Option(True, help="Only currently-active markets."),
    closed: bool = typer.Option(False, help="Include closed markets."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull crypto-tagged Polymarket markets (tag_id=21) into the warehouse."""

    from joint_research.ingest.polymarket_history_runner import (  # noqa: PLC0415
        ingest_gamma_crypto_markets as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(run(paths=paths, limit=limit, active=active, closed=closed))
    if result.rows_written == 0:
        typer.echo("ingested=0 markets. nothing written.")
        raise typer.Exit(code=0)
    typer.echo(f"ingested={result.rows_written} markets shard={result.shard_path}")


@ingest_app.command("polymarket-prices")
def ingest_polymarket_prices(
    top_n: int = typer.Option(10, help="Backfill the top-N crypto markets by 1mo volume."),
    interval: str = typer.Option("1m", help="Polymarket history interval: 1h/6h/1d/1w/1m/max."),
    fidelity_minutes: int = typer.Option(60, help="Bucket size in minutes (60 = hourly)."),
    include_closed: bool = typer.Option(
        False,
        "--include-closed/--active-only",
        help="Include closed/resolved markets — required for survivorship-bias-free analysis.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull /prices-history for top-N crypto YES tokens already in the warehouse."""

    from joint_research.ingest.polymarket_history_runner import (  # noqa: PLC0415
        ingest_top_crypto_market_prices as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(
        run(
            paths=paths,
            top_n=top_n,
            interval=interval,
            fidelity_minutes=fidelity_minutes,
            include_closed=include_closed,
        )
    )
    typer.echo(
        f"tokens_attempted={result.tokens_attempted} "
        f"tokens_with_data={result.tokens_with_data} "
        f"rows_written={result.rows_written} "
        f"shard={result.shard_path or '(none)'}"
    )


@research_app.command("lead-lag")
def research_lead_lag(
    min_observations: int = typer.Option(30, help="Skip tokens with fewer aligned bars than this."),
    frequency: str = typer.Option(
        "hourly",
        help="Sampling frequency: 'hourly' (lags 0/1/4/24 h) or 'daily' (lags 0/1/3/7/14 d).",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/research/lead_lag"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for lead_lag_summary.md, lead_lag_results.csv, "
            "and lead_lag_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N candidates by |t-stat|."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run the exploratory Polymarket→crypto lead-lag report."""

    from joint_research.research.lead_lag import (  # noqa: PLC0415
        rank_signal_candidates,
        run_lead_lag_study,
        write_lead_lag_report,
    )

    paths = _resolve_paths(warehouse_root)
    token_results, bucket_results = run_lead_lag_study(
        paths=paths,
        min_observations_per_token=min_observations,
        frequency=frequency,
    )

    report_paths = write_lead_lag_report(
        output_dir=output_dir.resolve(),
        token_results=token_results,
        bucket_results=bucket_results,
    )

    markets_tested = len({(r.asset, r.market_id, r.token_id) for r in token_results})
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"markets_tested={markets_tested} "
        f"hypothesis_rows={len(token_results)} "
        f"bucket_cells={len(bucket_results)}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")
    if diagnostic_triage_md is not None:
        typer.echo(f"diagnostic_triage={diagnostic_triage_md}")
    if promotion_plan_md is not None:
        typer.echo(f"promotion_plan={promotion_plan_md}")

    if not token_results:
        typer.echo("no tokens met the min_observations threshold. backfill more data.")
        raise typer.Exit(code=0)

    sig = [b for b in bucket_results if b.bh_significant_at_0_05]
    if sig:
        typer.echo(f"BH-significant bucket cells: {len(sig)}")
        for b in sig:
            typer.echo(
                f"  asset={b.asset} bucket={b.days_bucket} lag={b.lag_hours}h "
                f"r={b.pooled_correlation:+.3f} t={b.pooled_tstat:+.2f} "
                f"p={b.pooled_pvalue:.4f} n_obs={b.n_observations}"
            )
    else:
        typer.echo("no BH-significant bucket cells at alpha=0.05 (expected with limited data)")

    typer.echo(f"\ntop {show_top} exploratory candidates by |t|:")
    for c in rank_signal_candidates(token_results, limit=show_top):
        typer.echo(
            f"  rank={c.rank:>2} asset={c.asset:>4} lag={c.lag_hours:>2}h "
            f"r={c.correlation:+.3f} t={c.tstat:+.2f} p={c.pvalue_two_sided:.4f} "
            f"n={c.n} market={c.market_slug or c.market_id}"
        )


@research_app.command("robustness")
def research_robustness(
    min_observations: int = typer.Option(60, help="Minimum aligned bars per market/horizon."),
    min_nonzero_changes: int = typer.Option(
        20,
        help="Minimum non-zero Polymarket probability changes.",
    ),
    max_flat_fraction: float = typer.Option(
        0.90,
        help="Reject markets with a higher fraction of zero probability changes.",
    ),
    min_days_to_resolution: float = typer.Option(
        3.0,
        help="Reject markets whose last aligned sample is this close to resolution.",
    ),
    train_fraction: float = typer.Option(0.60, help="Earlier fraction used as train/discovery."),
    n_permutations: int = typer.Option(200, help="Deterministic shuffles per market/horizon."),
    output_dir: Path = typer.Option(
        Path("artifacts/research/robustness"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for robustness_summary.md, robustness_results.csv, "
            "and robustness_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N robustness candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run paper-only robustness checks over Polymarket→crypto candidates."""

    from joint_research.research.robustness import (  # noqa: PLC0415
        CandidateGrade,
        run_robustness_study,
        write_robustness_report,
    )

    paths = _resolve_paths(warehouse_root)
    results = run_robustness_study(
        paths=paths,
        min_observations=min_observations,
        min_nonzero_changes=min_nonzero_changes,
        max_flat_fraction=max_flat_fraction,
        min_days_to_resolution=min_days_to_resolution,
        train_fraction=train_fraction,
        n_permutations=n_permutations,
    )
    report_paths = write_robustness_report(
        output_dir=output_dir.resolve(),
        results=results,
    )

    counts = {grade.value: sum(1 for r in results if r.grade is grade) for grade in CandidateGrade}
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"hypothesis_rows={len(results)} "
        f"promising={counts['PROMISING']} "
        f"watchlist={counts['WATCHLIST']} "
        f"weak={counts['WEAK']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [r for r in results if r.grade is not CandidateGrade.REJECTED][:show_top]
    if not candidates:
        typer.echo("no robustness candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} robustness candidates:")
    for r in candidates:
        oos_match = (
            r.train_correlation * r.test_correlation > 0
            if not (math.isnan(r.train_correlation) or math.isnan(r.test_correlation))
            else False
        )
        typer.echo(
            f"  rank={r.rank:>2} grade={r.grade.value:<9} asset={r.asset:>4} "
            f"lag={r.lag_hours:>2}h oos_match={oos_match} "
            f"emp_p={r.empirical_pvalue:.4f} stability={r.rolling_stability:.2f} "
            f"n={r.n_observations} market={r.market_slug or r.market_id}"
        )


@research_app.command("composite-signal")
def research_composite_signal(
    min_train_samples: int = typer.Option(30, help="Minimum train samples per rule."),
    min_test_samples: int = typer.Option(20, help="Minimum test samples per rule."),
    output_dir: Path = typer.Option(
        Path("artifacts/research/composite_signal"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for composite_signal_summary.md, composite_signal_results.csv, "
            "and composite_signal_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N composite candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run deterministic composite signal scans over warehouse features."""

    from joint_research.research.composite_signal import (  # noqa: PLC0415
        CompositeCandidateGrade,
        run_composite_signal_study,
        write_composite_signal_report,
    )

    paths = _resolve_paths(warehouse_root)
    results = run_composite_signal_study(
        paths=paths,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
    )
    report_paths = write_composite_signal_report(
        output_dir=output_dir.resolve(),
        results=results,
    )
    counts = {
        grade.value: sum(1 for result in results if result.grade is grade)
        for grade in CompositeCandidateGrade
    }
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"rule_rows={len(results)} "
        f"simulation_ready={counts['SIMULATION_READY']} "
        f"watchlist={counts['WATCHLIST']} "
        f"weak={counts['WEAK']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [
        result for result in results if result.grade is not CompositeCandidateGrade.REJECTED
    ][:show_top]
    if not candidates:
        typer.echo("no composite candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} composite candidates:")
    for result in candidates:
        typer.echo(
            f"  rank={result.rank:>2} grade={result.grade.value:<16} "
            f"asset={result.asset:>4} horizon={result.horizon_hours:>2}h "
            f"test_acc={result.test_accuracy:.2f} "
            f"test_avg={result.test_average_forward_return:+.5f} "
            f"rule={result.rule_family} market={result.market_slug or result.market_id}"
        )


@research_app.command("derivatives-regime")
def research_derivatives_regime(
    min_segment_samples: int = typer.Option(
        24,
        help="Minimum sample count for funding/basis segment analysis.",
    ),
    min_combined_samples: int = typer.Option(
        36,
        help="Minimum sample count for combined regime segments.",
    ),
    train_fraction: float = typer.Option(0.6, help="Temporal train split fraction."),
    output_dir: Path = typer.Option(
        Path("artifacts/research/derivatives_regime"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for derivatives_regime_summary.md, derivatives_regime_results.csv, "
            "and derivatives_regime_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N derivatives-regime candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run derivatives-regime-conditioned Polymarket -> crypto signal analysis."""

    from joint_research.research.derivatives_regime import (  # noqa: PLC0415
        RegimeCandidateGrade,
        run_derivatives_regime_study,
        write_derivatives_regime_report,
    )

    paths = _resolve_paths(warehouse_root)
    results = run_derivatives_regime_study(
        paths=paths,
        min_segment_samples=min_segment_samples,
        min_combined_samples=min_combined_samples,
        train_fraction=train_fraction,
    )
    report_paths = write_derivatives_regime_report(
        output_dir=output_dir.resolve(),
        results=results,
    )
    counts = {
        grade.value: sum(1 for result in results if result.grade is grade)
        for grade in RegimeCandidateGrade
    }
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"segment_rows={len(results)} "
        f"simulation_ready={counts['SIMULATION_READY']} "
        f"watchlist={counts['WATCHLIST']} "
        f"weak={counts['WEAK']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [r for r in results if r.grade is not RegimeCandidateGrade.REJECTED][:show_top]
    if not candidates:
        typer.echo("no regime candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} derivatives-regime candidates:")
    for result in candidates:
        typer.echo(
            f"  rank={result.rank:>2} grade={result.grade.value:<16} "
            f"asset={result.asset:>4} horizon={result.horizon_hours:>2}h "
            f"segment={result.segment_type}:{result.segment_value} "
            f"improvement={result.test_improvement_over_baseline:+.5f} "
            f"win_rate={result.test_win_rate:.2f} "
            f"market={result.market_slug or result.market_id}"
        )


@research_app.command("wallet-flow-coverage-gate")
def research_wallet_flow_coverage_gate(
    coverage_csv: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_coverage.csv"),
        "--coverage-csv",
        help="Wallet-flow coverage CSV produced by the backfill planner.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/research/wallet_flow_signal"),
        "--output-dir",
        "--out-path",
        help="Directory for wallet_flow_coverage_gate.md.",
    ),
    min_covered_markets: int = typer.Option(
        25,
        help="Minimum markets with wallet-flow rows required for PASS.",
    ),
    min_coverage_ratio: float = typer.Option(
        0.20,
        help="Minimum covered_markets / total_markets required for PASS.",
    ),
    min_total_wallet_flow_rows: int = typer.Option(
        1000,
        help="Minimum total wallet-flow rows required for PASS.",
    ),
    min_market_flow_hourly_rows: int = typer.Option(
        500,
        help="Minimum market-flow hourly rows required for PASS.",
    ),
    min_whale_flow_hourly_rows: int = typer.Option(
        500,
        help="Minimum whale-flow hourly rows required for PASS.",
    ),
    show_top: int = typer.Option(10, help="Top covered markets to include in the report."),
) -> None:
    """Run a non-tradeable wallet-flow backfill coverage gate."""

    from joint_research.research.wallet_flow_coverage_gate import (  # noqa: PLC0415
        WalletFlowCoverageGateThresholds,
        write_wallet_flow_coverage_gate_report,
    )

    thresholds = WalletFlowCoverageGateThresholds(
        min_covered_markets=min_covered_markets,
        min_coverage_ratio=min_coverage_ratio,
        min_total_wallet_flow_rows=min_total_wallet_flow_rows,
        min_market_flow_hourly_rows=min_market_flow_hourly_rows,
        min_whale_flow_hourly_rows=min_whale_flow_hourly_rows,
    )
    report_path, gate = write_wallet_flow_coverage_gate_report(
        coverage_csv=coverage_csv.resolve(),
        output_dir=output_dir.resolve(),
        thresholds=thresholds,
        top_limit=show_top,
    )

    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"gate_status={gate.status} "
        f"covered_markets={gate.covered_markets} "
        f"total_markets={gate.total_markets} "
        f"coverage_ratio={gate.coverage_ratio:.4f} "
        f"wallet_flow_rows={gate.total_wallet_flow_rows}"
    )
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo(f"coverage_report={report_path}")
    if gate.failure_reasons:
        typer.echo("failure_reasons=" + ";".join(gate.failure_reasons))


@research_app.command("wallet-flow-backfill-priority")
def research_wallet_flow_backfill_priority(
    coverage_csv: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_coverage.csv"),
        "--coverage-csv",
        help="Wallet-flow coverage CSV produced by the backfill planner.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help="Directory for wallet_flow_backfill_priority.md and wallet_flow_backfill_priority.csv.",
    ),
    min_wallet_flow_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_wallet_flow_rows,
        "--min-wallet-flow-rows",
        help="Minimum wallet-flow rows required per market before it is deprioritized.",
    ),
    min_market_flow_hourly_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_market_flow_hourly_rows,
        "--min-market-flow-hourly-rows",
        help="Minimum market-flow hourly rows required per market before it is deprioritized.",
    ),
    min_whale_flow_hourly_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_whale_flow_hourly_rows,
        "--min-whale-flow-hourly-rows",
        help="Minimum whale-flow hourly rows required per market before it is deprioritized.",
    ),
    show_top: int = typer.Option(25, "--show-top", help="Top-N priorities to render."),
) -> None:
    """Rank wallet-flow data backfill priorities (non-tradeable)."""

    thresholds = WalletFlowBackfillPriorityThresholds(
        min_wallet_flow_rows=min_wallet_flow_rows,
        min_market_flow_hourly_rows=min_market_flow_hourly_rows,
        min_whale_flow_hourly_rows=min_whale_flow_hourly_rows,
    )
    report_path, csv_path, plan = write_wallet_flow_backfill_priority_artifacts(
        coverage_csv=coverage_csv.resolve(),
        output_dir=output_dir.resolve(),
        thresholds=thresholds,
        top_limit=show_top,
    )

    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"backfill_markets={plan.backfill_markets}")
    typer.echo(f"active_backfill_markets={plan.active_backfill_markets}")
    typer.echo(f"total_markets={plan.total_markets}")
    typer.echo(f"priorities_rendered={len(plan.priorities)}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo(f"priority_report={report_path}")
    typer.echo(f"priority_csv={csv_path}")


@research_app.command("wallet-flow-backfill-batches")
def research_wallet_flow_backfill_batches(
    coverage_csv: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_coverage.csv"),
        "--coverage-csv",
        help="Wallet-flow coverage CSV produced by the backfill planner.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help="Directory for wallet_flow_backfill_batches.md and wallet_flow_backfill_batches.csv.",
    ),
    min_wallet_flow_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_wallet_flow_rows,
        "--min-wallet-flow-rows",
        help="Minimum wallet-flow rows required per market before it is deprioritized.",
    ),
    min_market_flow_hourly_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_market_flow_hourly_rows,
        "--min-market-flow-hourly-rows",
        help="Minimum market-flow hourly rows required per market before it is deprioritized.",
    ),
    min_whale_flow_hourly_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_whale_flow_hourly_rows,
        "--min-whale-flow-hourly-rows",
        help="Minimum whale-flow hourly rows required per market before it is deprioritized.",
    ),
    batch_size: int = typer.Option(25, "--batch-size", help="Markets per backfill batch."),
    max_batches: int = typer.Option(5, "--max-batches", help="Maximum number of batches to plan."),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Planning-only mode; this command never executes ingestion.",
    ),
) -> None:
    """Plan deterministic wallet-flow backfill batches (non-tradeable)."""

    thresholds = WalletFlowBackfillPriorityThresholds(
        min_wallet_flow_rows=min_wallet_flow_rows,
        min_market_flow_hourly_rows=min_market_flow_hourly_rows,
        min_whale_flow_hourly_rows=min_whale_flow_hourly_rows,
    )
    report_path, csv_path, plan = write_wallet_flow_backfill_batches_artifacts(
        coverage_csv=coverage_csv.resolve(),
        output_dir=output_dir.resolve(),
        thresholds=thresholds,
        batch_size=batch_size,
        max_batches=max_batches,
        dry_run=dry_run,
    )

    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"dry_run={dry_run}")
    typer.echo(f"batches={len(plan.batches)}")
    typer.echo(f"markets_planned={len(plan.rows)}")
    typer.echo(f"batch_size={batch_size}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo(f"batch_report={report_path}")
    typer.echo(f"batch_csv={csv_path}")


@research_app.command("wallet-flow-backfill-manifest")
def research_wallet_flow_backfill_manifest(
    coverage_csv: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_coverage.csv"),
        "--coverage-csv",
        help="Wallet-flow coverage CSV produced by the backfill planner.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_backfill_execution_manifest.md, "
            "wallet_flow_backfill_execution_manifest.csv, and "
            "wallet_flow_backfill_execution_manifest.json."
        ),
    ),
    min_wallet_flow_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_wallet_flow_rows,
        "--min-wallet-flow-rows",
        help="Minimum wallet-flow rows required per market before it is deprioritized.",
    ),
    min_market_flow_hourly_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_market_flow_hourly_rows,
        "--min-market-flow-hourly-rows",
        help="Minimum market-flow hourly rows required per market before it is deprioritized.",
    ),
    min_whale_flow_hourly_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_whale_flow_hourly_rows,
        "--min-whale-flow-hourly-rows",
        help="Minimum whale-flow hourly rows required per market before it is deprioritized.",
    ),
    batch_size: int = typer.Option(25, "--batch-size", help="Markets per backfill batch."),
    max_batches: int = typer.Option(5, "--max-batches", help="Maximum number of batches to plan."),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Planning-only mode; this command never executes ingestion.",
    ),
    command_template: str | None = typer.Option(
        None,
        "--command-template",
        help="Optional format string using {market_id}, {market_slug}, {asset}, {batch_id}, {rank}.",
    ),
    command_template_preset: str | None = typer.Option(
        None,
        "--command-template-preset",
        help="Built-in template preset: none|default|review_echo.",
    ),
) -> None:
    """Generate a deterministic wallet-flow backfill execution manifest (review-only)."""

    if command_template is not None and command_template_preset is not None:
        raise typer.BadParameter(
            "Provide only one of --command-template or --command-template-preset.",
            param_hint="--command-template-preset",
        )
    if command_template_preset is not None:
        normalized = command_template_preset.strip().lower()
        if normalized not in set(SUPPORTED_COMMAND_TEMPLATE_PRESETS):
            raise typer.BadParameter(
                "command-template-preset must be one of: "
                + ", ".join(SUPPORTED_COMMAND_TEMPLATE_PRESETS),
                param_hint="--command-template-preset",
            )

    thresholds = WalletFlowBackfillPriorityThresholds(
        min_wallet_flow_rows=min_wallet_flow_rows,
        min_market_flow_hourly_rows=min_market_flow_hourly_rows,
        min_whale_flow_hourly_rows=min_whale_flow_hourly_rows,
    )
    report_path, csv_path, json_path, plan = write_wallet_flow_backfill_manifest_artifacts(
        coverage_csv=coverage_csv.resolve(),
        output_dir=output_dir.resolve(),
        thresholds=thresholds,
        batch_size=batch_size,
        max_batches=max_batches,
        dry_run=dry_run,
        command_template=command_template,
        command_template_preset=command_template_preset,
    )

    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"dry_run={dry_run}")
    typer.echo(f"manifest_rows={len(plan.rows)}")
    typer.echo(f"batches={plan.batches}")
    typer.echo(f"batch_size={batch_size}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo(f"manifest_report={report_path}")
    typer.echo(f"manifest_csv={csv_path}")
    typer.echo(f"manifest_json={json_path}")


@research_app.command("wallet-flow-manifest-review-gate")
def research_wallet_flow_manifest_review_gate(
    manifest_json: Path = typer.Option(
        Path(
            "artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_backfill_execution_manifest.json"
        ),
        "--manifest-json",
        help="Execution manifest JSON produced by wallet-flow-backfill-manifest.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help="Directory for wallet_flow_manifest_review_gate.md.",
    ),
    allow_review_required: bool = typer.Option(
        False,
        "--allow-review-required/--no-allow-review-required",
        help="Permit REVIEW_REQUIRED manifest rows to pass the gate.",
    ),
    require_dry_run: bool = typer.Option(
        True,
        "--require-dry-run/--no-require-dry-run",
        help="Fail the gate if manifest dry_run is not true.",
    ),
) -> None:
    """Validate a wallet-flow execution manifest for review safety (no execution)."""

    result = run_wallet_flow_manifest_review_gate(
        manifest_json=manifest_json.resolve(),
        output_dir=output_dir.resolve(),
        allow_review_required=allow_review_required,
        require_dry_run=require_dry_run,
    )

    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"gate_status={result.status}")
    typer.echo(f"manifest_rows={result.manifest_rows}")
    typer.echo(f"failures={len(result.failures)}")
    typer.echo(f"warnings={len(result.warnings)}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo(f"review_gate_report={result.report_path}")


@research_app.command("wallet-flow-approved-manifest-packet")
def research_wallet_flow_approved_manifest_packet(
    manifest_json: Path = typer.Option(
        Path(
            "artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_backfill_execution_manifest.json"
        ),
        "--manifest-json",
        help="Execution manifest JSON produced by wallet-flow-backfill-manifest.",
    ),
    review_gate_report: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_manifest_review_gate.md"),
        "--review-gate-report",
        help="Review gate markdown report path for packet provenance.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_approved_manifest_packet.md and "
            "wallet_flow_approved_manifest_packet.json."
        ),
    ),
) -> None:
    """Export deterministic approved manifest packet for human review (no execution)."""

    artifacts = write_wallet_flow_approved_manifest_packet(
        manifest_json=manifest_json.resolve(),
        review_gate_report=review_gate_report.resolve(),
        output_dir=output_dir.resolve(),
    )
    packet = artifacts.packet
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"export_status={packet.export_status}")
    typer.echo(f"manifest_rows={packet.manifest_rows}")
    typer.echo(f"gate_status={packet.gate_status}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo(f"approved_manifest_packet={artifacts.packet_md}")
    typer.echo(f"approved_manifest_packet_json={artifacts.packet_json}")


@research_app.command("wallet-flow-manifest-audit-index")
def research_wallet_flow_manifest_audit_index(
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_manifest_audit_index.md and "
            "wallet_flow_manifest_audit_index.json."
        ),
    ),
    coverage_gate_report: Path = typer.Option(
        Path("artifacts/research/wallet_flow_signal/wallet_flow_coverage_gate.md"),
        "--coverage-gate-report",
        help="Coverage gate markdown report path.",
    ),
    priority_report: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_backfill_priority.md"),
        "--priority-report",
        help="Backfill priority markdown report path.",
    ),
    batch_report: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_backfill_batches.md"),
        "--batch-report",
        help="Backfill batches markdown report path.",
    ),
    manifest_report: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_backfill_execution_manifest.md"),
        "--manifest-report",
        help="Execution manifest markdown report path.",
    ),
    review_gate_report: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_manifest_review_gate.md"),
        "--review-gate-report",
        help="Manifest review gate markdown report path.",
    ),
    approved_packet_report: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approved_manifest_packet.md"),
        "--approved-packet-report",
        help="Approved manifest packet markdown report path.",
    ),
    manifest_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_backfill_execution_manifest.json"),
        "--manifest-json",
        help="Execution manifest JSON path.",
    ),
    approved_packet_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approved_manifest_packet.json"),
        "--approved-packet-json",
        help="Approved manifest packet JSON path.",
    ),
) -> None:
    """Build deterministic wallet-flow manifest audit index (no execution)."""

    artifacts = write_wallet_flow_manifest_audit_index(
        output_dir=output_dir.resolve(),
        coverage_gate_report=coverage_gate_report.resolve(),
        priority_report=priority_report.resolve(),
        batch_report=batch_report.resolve(),
        manifest_report=manifest_report.resolve(),
        review_gate_report=review_gate_report.resolve(),
        approved_packet_report=approved_packet_report.resolve(),
        manifest_json=manifest_json.resolve(),
        approved_packet_json=approved_packet_json.resolve(),
    )
    index = artifacts.index
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"audit_status={index.audit_status}")
    typer.echo(f"reports_found={index.reports_found}")
    typer.echo(f"reports_missing={index.reports_missing}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo(f"audit_index={artifacts.audit_index_md}")
    typer.echo(f"audit_index_json={artifacts.audit_index_json}")


@research_app.command("wallet-flow-dry-run-execution-planner")
def research_wallet_flow_dry_run_execution_planner(
    manifest_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_backfill_execution_manifest.json"),
        "--manifest-json",
        help="Execution manifest JSON path.",
    ),
    approved_packet_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approved_manifest_packet.json"),
        "--approved-packet-json",
        help="Approved manifest packet JSON path.",
    ),
    audit_index_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_manifest_audit_index.json"),
        "--audit-index-json",
        help="Manifest audit index JSON path.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_dry_run_execution_plan.md and "
            "wallet_flow_dry_run_execution_plan.json."
        ),
    ),
) -> None:
    """Build deterministic preview-only dry-run execution plan (no execution)."""

    artifacts = write_wallet_flow_dry_run_execution_plan(
        manifest_json=manifest_json.resolve(),
        approved_packet_json=approved_packet_json.resolve(),
        audit_index_json=audit_index_json.resolve(),
        output_dir=output_dir.resolve(),
    )
    plan = artifacts.plan
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"plan_status={plan.plan_status}")
    typer.echo(f"manifest_rows={plan.manifest_rows}")
    typer.echo(f"approved_packet_status={plan.approved_packet_status}")
    typer.echo(f"audit_status={plan.audit_status}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo("No manifest commands executed.")
    typer.echo(f"dry_run_execution_plan={artifacts.plan_md}")
    typer.echo(f"dry_run_execution_plan_json={artifacts.plan_json}")


@research_app.command("wallet-flow-guarded-operator-handoff")
def research_wallet_flow_guarded_operator_handoff(
    dry_run_plan_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_dry_run_execution_plan.json"),
        "--dry-run-plan-json",
        help="Dry-run execution plan JSON path.",
    ),
    approved_packet_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approved_manifest_packet.json"),
        "--approved-packet-json",
        help="Approved manifest packet JSON path.",
    ),
    audit_index_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_manifest_audit_index.json"),
        "--audit-index-json",
        help="Manifest audit index JSON path.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_guarded_operator_handoff.md and "
            "wallet_flow_guarded_operator_handoff.json."
        ),
    ),
) -> None:
    """Build deterministic guarded operator handoff for manual approval only."""

    artifacts = write_wallet_flow_guarded_operator_handoff(
        dry_run_plan_json=dry_run_plan_json.resolve(),
        approved_packet_json=approved_packet_json.resolve(),
        audit_index_json=audit_index_json.resolve(),
        output_dir=output_dir.resolve(),
    )
    handoff = artifacts.handoff
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"handoff_status={handoff.handoff_status}")
    typer.echo(f"plan_status={handoff.plan_status}")
    typer.echo(f"approved_packet_status={handoff.approved_packet_status}")
    typer.echo(f"audit_status={handoff.audit_status}")
    typer.echo(f"approval_required={str(handoff.approval_required).lower()}")
    typer.echo(f"manual_operator_only={str(handoff.manual_operator_only).lower()}")
    typer.echo(f"no_execution={str(handoff.no_execution).lower()}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo("No manifest commands executed.")
    typer.echo(f"guarded_operator_handoff={artifacts.handoff_md}")
    typer.echo(f"guarded_operator_handoff_json={artifacts.handoff_json}")


@research_app.command("wallet-flow-operator-approval-ledger")
def research_wallet_flow_operator_approval_ledger(
    guarded_handoff_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_guarded_operator_handoff.json"),
        "--guarded-handoff-json",
        help="Guarded operator handoff JSON path.",
    ),
    decision: str = typer.Option(
        "pending",
        "--decision",
        help="Manual review decision: pending|approve|reject.",
    ),
    reviewer: str = typer.Option(
        "",
        "--reviewer",
        help="Optional reviewer identifier.",
    ),
    review_note: str = typer.Option(
        "",
        "--review-note",
        help="Optional review note.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_operator_approval_ledger.md and "
            "wallet_flow_operator_approval_ledger.json."
        ),
    ),
) -> None:
    """Write a deterministic operator approval ledger (no execution)."""

    normalized_decision = decision.strip().lower()
    if normalized_decision not in {"pending", "approve", "reject"}:
        raise typer.BadParameter(
            "Invalid value for --decision. Expected one of: pending, approve, reject."
        )

    artifacts = write_wallet_flow_operator_approval_ledger(
        guarded_handoff_json=guarded_handoff_json.resolve(),
        decision=normalized_decision,
        reviewer=reviewer,
        review_note=review_note,
        output_dir=output_dir.resolve(),
    )
    ledger = artifacts.ledger
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"ledger_status={ledger.ledger_status}")
    typer.echo(f"decision={ledger.decision}")
    typer.echo(f"handoff_status={ledger.handoff_status}")
    typer.echo(f"approval_required={str(ledger.approval_required).lower()}")
    typer.echo(f"manual_operator_only={str(ledger.manual_operator_only).lower()}")
    typer.echo(f"no_execution={str(ledger.no_execution).lower()}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo("No manifest commands executed.")
    typer.echo(f"operator_approval_ledger={artifacts.ledger_md}")
    typer.echo(f"operator_approval_ledger_json={artifacts.ledger_json}")


@research_app.command("wallet-flow-approval-execution-contract")
def research_wallet_flow_approval_execution_contract(
    approval_ledger_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_operator_approval_ledger.json"),
        "--approval-ledger-json",
        help="Operator approval ledger JSON path.",
    ),
    guarded_handoff_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_guarded_operator_handoff.json"),
        "--guarded-handoff-json",
        help="Guarded operator handoff JSON path.",
    ),
    dry_run_plan_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_dry_run_execution_plan.json"),
        "--dry-run-plan-json",
        help="Dry-run execution plan JSON path.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_approval_execution_contract.md and "
            "wallet_flow_approval_execution_contract.json."
        ),
    ),
) -> None:
    """Write deterministic approval-to-execution contract artifact (no execution)."""

    artifacts = write_wallet_flow_approval_execution_contract(
        approval_ledger_json=approval_ledger_json.resolve(),
        guarded_handoff_json=guarded_handoff_json.resolve(),
        dry_run_plan_json=dry_run_plan_json.resolve(),
        output_dir=output_dir.resolve(),
    )
    contract = artifacts.contract
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"contract_status={contract.contract_status}")
    typer.echo(f"ledger_status={contract.ledger_status}")
    typer.echo(f"decision={contract.decision}")
    typer.echo(f"handoff_status={contract.handoff_status}")
    typer.echo(f"plan_status={contract.plan_status}")
    typer.echo(f"approval_required={str(contract.approval_required).lower()}")
    typer.echo(f"manual_operator_only={str(contract.manual_operator_only).lower()}")
    typer.echo(f"no_execution={str(contract.no_execution).lower()}")
    typer.echo(f"no_ingestion={str(contract.no_ingestion).lower()}")
    typer.echo(f"live_adapter_enabled={str(contract.live_adapter_enabled).lower()}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo("No manifest commands executed.")
    typer.echo(f"approval_execution_contract={artifacts.contract_md}")
    typer.echo(f"approval_execution_contract_json={artifacts.contract_json}")


@research_app.command("wallet-flow-contract-audit-receipt")
def research_wallet_flow_contract_audit_receipt(
    approval_execution_contract_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approval_execution_contract.json"),
        "--approval-execution-contract-json",
        help="Approval execution contract JSON path.",
    ),
    approval_ledger_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_operator_approval_ledger.json"),
        "--approval-ledger-json",
        help="Operator approval ledger JSON path.",
    ),
    guarded_handoff_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_guarded_operator_handoff.json"),
        "--guarded-handoff-json",
        help="Guarded operator handoff JSON path.",
    ),
    dry_run_plan_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_dry_run_execution_plan.json"),
        "--dry-run-plan-json",
        help="Dry-run execution plan JSON path.",
    ),
    approved_packet_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approved_manifest_packet.json"),
        "--approved-packet-json",
        help="Approved manifest packet JSON path.",
    ),
    audit_index_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_manifest_audit_index.json"),
        "--audit-index-json",
        help="Manifest audit index JSON path.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_contract_audit_receipt.md and "
            "wallet_flow_contract_audit_receipt.json."
        ),
    ),
) -> None:
    """Write deterministic wallet-flow contract audit receipt (no execution)."""

    artifacts = write_wallet_flow_contract_audit_receipt(
        approval_execution_contract_json=approval_execution_contract_json.resolve(),
        approval_ledger_json=approval_ledger_json.resolve(),
        guarded_handoff_json=guarded_handoff_json.resolve(),
        dry_run_plan_json=dry_run_plan_json.resolve(),
        approved_packet_json=approved_packet_json.resolve(),
        audit_index_json=audit_index_json.resolve(),
        output_dir=output_dir.resolve(),
    )
    receipt = artifacts.receipt
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"receipt_status={receipt.receipt_status}")
    typer.echo(f"contract_status={receipt.contract_status}")
    typer.echo(f"ledger_status={receipt.ledger_status}")
    typer.echo(f"decision={receipt.decision}")
    typer.echo(f"handoff_status={receipt.handoff_status}")
    typer.echo(f"plan_status={receipt.plan_status}")
    typer.echo(f"approved_packet_status={receipt.approved_packet_status}")
    typer.echo(f"audit_status={receipt.audit_status}")
    typer.echo(f"approval_required={str(receipt.approval_required).lower()}")
    typer.echo(f"manual_operator_only={str(receipt.manual_operator_only).lower()}")
    typer.echo(f"no_execution={str(receipt.no_execution).lower()}")
    typer.echo(f"no_ingestion={str(receipt.no_ingestion).lower()}")
    typer.echo(f"live_adapter_enabled={str(receipt.live_adapter_enabled).lower()}")
    typer.echo(f"no_orders={str(receipt.no_orders).lower()}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo("No manifest commands executed.")
    typer.echo(f"contract_audit_receipt={artifacts.receipt_md}")
    typer.echo(f"contract_audit_receipt_json={artifacts.receipt_json}")


@research_app.command("wallet-flow-disabled-adapter-interface")
def research_wallet_flow_disabled_adapter_interface(
    contract_audit_receipt_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_contract_audit_receipt.json"),
        "--contract-audit-receipt-json",
        help="Contract audit receipt JSON path.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_disabled_adapter_interface.md and "
            "wallet_flow_disabled_adapter_interface.json."
        ),
    ),
) -> None:
    """Write deterministic hard-disabled wallet-flow adapter interface artifact."""

    artifacts = write_wallet_flow_disabled_adapter_interface(
        contract_audit_receipt_json=contract_audit_receipt_json.resolve(),
        output_dir=output_dir.resolve(),
    )
    interface = artifacts.interface
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"adapter_status={interface.adapter_status}")
    typer.echo(f"receipt_status={interface.receipt_status}")
    typer.echo(f"contract_status={interface.contract_status}")
    typer.echo(f"ledger_status={interface.ledger_status}")
    typer.echo(f"decision={interface.decision}")
    typer.echo(f"adapter_enabled={str(interface.adapter_enabled).lower()}")
    typer.echo(f"execution_enabled={str(interface.execution_enabled).lower()}")
    typer.echo(f"network_enabled={str(interface.network_enabled).lower()}")
    typer.echo(f"ingestion_enabled={str(interface.ingestion_enabled).lower()}")
    typer.echo(f"shell_enabled={str(interface.shell_enabled).lower()}")
    typer.echo(f"order_placement_enabled={str(interface.order_placement_enabled).lower()}")
    typer.echo(f"database_mutation_enabled={str(interface.database_mutation_enabled).lower()}")
    typer.echo(f"approval_required={str(interface.approval_required).lower()}")
    typer.echo(f"manual_operator_only={str(interface.manual_operator_only).lower()}")
    typer.echo(f"no_execution={str(interface.no_execution).lower()}")
    typer.echo(f"no_ingestion={str(interface.no_ingestion).lower()}")
    typer.echo(f"no_orders={str(interface.no_orders).lower()}")
    typer.echo(f"disabled_reason={interface.disabled_reason}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo("No manifest commands executed.")
    typer.echo(f"disabled_adapter_interface={artifacts.interface_md}")
    typer.echo(f"disabled_adapter_interface_json={artifacts.interface_json}")


@research_app.command("wallet-flow-disabled-adapter-run-receipt")
def research_wallet_flow_disabled_adapter_run_receipt(
    disabled_adapter_interface_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_adapter_interface.json"),
        "--disabled-adapter-interface-json",
        help="Disabled adapter interface JSON path.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_disabled_adapter_run_receipt.md and "
            "wallet_flow_disabled_adapter_run_receipt.json."
        ),
    ),
) -> None:
    """Write deterministic disabled adapter run receipt (no execution)."""

    artifacts = write_wallet_flow_disabled_adapter_run_receipt(
        disabled_adapter_interface_json=disabled_adapter_interface_json.resolve(),
        output_dir=output_dir.resolve(),
    )
    receipt = artifacts.receipt
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"run_status={receipt.run_status}")
    typer.echo(f"adapter_status={receipt.adapter_status}")
    typer.echo(f"receipt_status={receipt.receipt_status}")
    typer.echo(f"contract_status={receipt.contract_status}")
    typer.echo(f"ledger_status={receipt.ledger_status}")
    typer.echo(f"decision={receipt.decision}")
    typer.echo(f"adapter_enabled={str(receipt.adapter_enabled).lower()}")
    typer.echo(f"execution_enabled={str(receipt.execution_enabled).lower()}")
    typer.echo(f"network_enabled={str(receipt.network_enabled).lower()}")
    typer.echo(f"ingestion_enabled={str(receipt.ingestion_enabled).lower()}")
    typer.echo(f"shell_enabled={str(receipt.shell_enabled).lower()}")
    typer.echo(f"order_placement_enabled={str(receipt.order_placement_enabled).lower()}")
    typer.echo(f"database_mutation_enabled={str(receipt.database_mutation_enabled).lower()}")
    typer.echo(f"approval_required={str(receipt.approval_required).lower()}")
    typer.echo(f"manual_operator_only={str(receipt.manual_operator_only).lower()}")
    typer.echo(f"no_execution={str(receipt.no_execution).lower()}")
    typer.echo(f"no_ingestion={str(receipt.no_ingestion).lower()}")
    typer.echo(f"no_orders={str(receipt.no_orders).lower()}")
    typer.echo(f"disabled_reason={receipt.disabled_reason}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo("No manifest commands executed.")
    typer.echo(f"disabled_adapter_run_receipt={artifacts.receipt_md}")
    typer.echo(f"disabled_adapter_run_receipt_json={artifacts.receipt_json}")


@research_app.command("wallet-flow-disabled-chain-summary")
def research_wallet_flow_disabled_chain_summary(
    approval_execution_contract_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approval_execution_contract.json"),
        "--approval-execution-contract-json",
        help="Approval execution contract JSON path.",
    ),
    contract_audit_receipt_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_contract_audit_receipt.json"),
        "--contract-audit-receipt-json",
        help="Contract audit receipt JSON path.",
    ),
    disabled_adapter_interface_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_adapter_interface.json"),
        "--disabled-adapter-interface-json",
        help="Disabled adapter interface JSON path.",
    ),
    disabled_adapter_run_receipt_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_adapter_run_receipt.json"),
        "--disabled-adapter-run-receipt-json",
        help="Disabled adapter run receipt JSON path.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_disabled_chain_summary.md and "
            "wallet_flow_disabled_chain_summary.json."
        ),
    ),
) -> None:
    """Write deterministic end-to-end disabled chain summary (no execution)."""

    artifacts = write_wallet_flow_disabled_chain_summary(
        approval_execution_contract_json=approval_execution_contract_json.resolve(),
        contract_audit_receipt_json=contract_audit_receipt_json.resolve(),
        disabled_adapter_interface_json=disabled_adapter_interface_json.resolve(),
        disabled_adapter_run_receipt_json=disabled_adapter_run_receipt_json.resolve(),
        output_dir=output_dir.resolve(),
    )
    summary = artifacts.summary
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"chain_status={summary.chain_status}")
    typer.echo(f"contract_status={summary.contract_status}")
    typer.echo(f"receipt_status={summary.receipt_status}")
    typer.echo(f"adapter_status={summary.adapter_status}")
    typer.echo(f"run_status={summary.run_status}")
    typer.echo(f"ledger_status={summary.ledger_status}")
    typer.echo(f"decision={summary.decision}")
    typer.echo(f"adapter_enabled={str(summary.adapter_enabled).lower()}")
    typer.echo(f"execution_enabled={str(summary.execution_enabled).lower()}")
    typer.echo(f"network_enabled={str(summary.network_enabled).lower()}")
    typer.echo(f"ingestion_enabled={str(summary.ingestion_enabled).lower()}")
    typer.echo(f"shell_enabled={str(summary.shell_enabled).lower()}")
    typer.echo(f"order_placement_enabled={str(summary.order_placement_enabled).lower()}")
    typer.echo(f"database_mutation_enabled={str(summary.database_mutation_enabled).lower()}")
    typer.echo(f"approval_required={str(summary.approval_required).lower()}")
    typer.echo(f"manual_operator_only={str(summary.manual_operator_only).lower()}")
    typer.echo(f"no_execution={str(summary.no_execution).lower()}")
    typer.echo(f"no_ingestion={str(summary.no_ingestion).lower()}")
    typer.echo(f"no_orders={str(summary.no_orders).lower()}")
    typer.echo(f"disabled_reason={summary.disabled_reason}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo("No manifest commands executed.")
    typer.echo(f"disabled_chain_summary={artifacts.summary_md}")
    typer.echo(f"disabled_chain_summary_json={artifacts.summary_json}")


@research_app.command("wallet-flow-disabled-policy-guard")
def research_wallet_flow_disabled_policy_guard(
    disabled_chain_summary_json: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_chain_summary.json"),
        "--disabled-chain-summary-json",
        help="Disabled chain summary JSON path.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_disabled_policy_guard.md and "
            "wallet_flow_disabled_policy_guard.json."
        ),
    ),
) -> None:
    """Write deterministic disabled policy regression guard (no execution)."""

    artifacts = write_wallet_flow_disabled_policy_guard(
        disabled_chain_summary_json=disabled_chain_summary_json.resolve(),
        output_dir=output_dir.resolve(),
    )
    guard = artifacts.guard
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"guard_status={guard.guard_status}")
    typer.echo(f"chain_status={guard.chain_status}")
    typer.echo(f"contract_status={guard.contract_status}")
    typer.echo(f"receipt_status={guard.receipt_status}")
    typer.echo(f"adapter_status={guard.adapter_status}")
    typer.echo(f"run_status={guard.run_status}")
    typer.echo(f"ledger_status={guard.ledger_status}")
    typer.echo(f"decision={guard.decision}")
    typer.echo(f"adapter_enabled={str(guard.adapter_enabled).lower()}")
    typer.echo(f"execution_enabled={str(guard.execution_enabled).lower()}")
    typer.echo(f"network_enabled={str(guard.network_enabled).lower()}")
    typer.echo(f"ingestion_enabled={str(guard.ingestion_enabled).lower()}")
    typer.echo(f"shell_enabled={str(guard.shell_enabled).lower()}")
    typer.echo(f"order_placement_enabled={str(guard.order_placement_enabled).lower()}")
    typer.echo(f"database_mutation_enabled={str(guard.database_mutation_enabled).lower()}")
    typer.echo(f"approval_required={str(guard.approval_required).lower()}")
    typer.echo(f"manual_operator_only={str(guard.manual_operator_only).lower()}")
    typer.echo(f"no_execution={str(guard.no_execution).lower()}")
    typer.echo(f"no_ingestion={str(guard.no_ingestion).lower()}")
    typer.echo(f"no_orders={str(guard.no_orders).lower()}")
    typer.echo(f"disabled_reason={guard.disabled_reason}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo("No ingestion executed.")
    typer.echo("No manifest commands executed.")
    typer.echo(f"disabled_policy_guard={artifacts.guard_md}")
    typer.echo(f"disabled_policy_guard_json={artifacts.guard_json}")


@research_app.command("wallet-flow-signal")
def research_wallet_flow_signal(
    min_segment_samples: int = typer.Option(
        24,
        help="Minimum sample count for segmented wallet-flow analysis.",
    ),
    min_feature_samples: int = typer.Option(
        36,
        help="Minimum sample count for all-sample feature rows.",
    ),
    train_fraction: float = typer.Option(0.6, help="Temporal train split fraction."),
    output_dir: Path = typer.Option(
        Path("artifacts/research/wallet_flow_signal"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_signal_summary.md, wallet_flow_signal_results.csv, "
            "and wallet_flow_signal_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N wallet-flow candidates."),
    diagnostic_report: bool = typer.Option(
        False,
        "--diagnostic-report/--no-diagnostic-report",
        help="Also write wallet_flow_diagnostic_triage.md from rejection diagnostics.",
    ),
    promotion_plan: bool = typer.Option(
        False,
        "--promotion-plan/--no-promotion-plan",
        help="Also write wallet_flow_promotion_plan.md as a non-tradeable data/action plan.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run wallet-flow-conditioned Polymarket -> crypto signal analysis."""

    from joint_research.research.wallet_flow_signal import (  # noqa: PLC0415
        WalletFlowCandidateGrade,
        build_wallet_flow_rejection_diagnostics,
        run_wallet_flow_signal_study_with_details,
        write_wallet_flow_signal_report,
    )
    from joint_research.research.wallet_flow_diagnostic_triage import (  # noqa: PLC0415
        write_wallet_flow_diagnostic_triage_report,
    )
    from joint_research.research.wallet_flow_promotion_plan import (  # noqa: PLC0415
        write_wallet_flow_promotion_plan_report,
    )

    paths = _resolve_paths(warehouse_root)
    study_details = run_wallet_flow_signal_study_with_details(
        paths=paths,
        min_segment_samples=min_segment_samples,
        min_feature_samples=min_feature_samples,
        train_fraction=train_fraction,
    )
    results = study_details.results
    resolved_output_dir = output_dir.resolve()
    report_paths = write_wallet_flow_signal_report(
        output_dir=resolved_output_dir,
        results=results,
        study_details=study_details,
    )
    diagnostic_triage_md = None
    promotion_plan_md = None
    diagnostics = None
    if diagnostic_report or promotion_plan:
        diagnostics = build_wallet_flow_rejection_diagnostics(
            raw_results=study_details.raw_results,
            final_results=results,
        )
    if diagnostic_report and diagnostics is not None:
        diagnostic_triage_md = write_wallet_flow_diagnostic_triage_report(
            output_dir=resolved_output_dir,
            diagnostics=diagnostics,
        )
    if promotion_plan and diagnostics is not None:
        promotion_plan_md = write_wallet_flow_promotion_plan_report(
            output_dir=resolved_output_dir,
            diagnostics=diagnostics,
        )
    counts = {
        grade.value: sum(1 for result in results if result.grade is grade)
        for grade in WalletFlowCandidateGrade
    }
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"segment_rows={len(results)} "
        f"simulation_ready={counts['SIMULATION_READY']} "
        f"watchlist={counts['WATCHLIST']} "
        f"weak={counts['WEAK']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [r for r in results if r.grade is not WalletFlowCandidateGrade.REJECTED][:show_top]
    if not candidates:
        typer.echo("no wallet-flow candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} wallet-flow candidates:")
    for result in candidates:
        typer.echo(
            f"  rank={result.rank:>2} grade={result.grade.value:<16} "
            f"asset={result.asset:>4} horizon={result.horizon_hours:>2}h "
            f"feature={result.feature_name} "
            f"segment={result.segment_type}:{result.segment_value} "
            f"improvement={result.test_improvement_over_baseline:+.5f} "
            f"win_rate={result.test_win_rate:.2f} "
            f"market={result.market_slug or result.market_id}"
        )


@research_app.command("simulate")
def research_simulate(
    candidate_source: str = typer.Option(
        "robustness",
        help="Candidate source: robustness|composite-signal|derivatives-regime|wallet-flow-signal.",
    ),
    starting_capital: float = typer.Option(200.0, help="Paper bankroll in USD."),
    fixed_notional: float = typer.Option(10.0, help="Fixed paper notional per trade."),
    max_simultaneous_exposure: float = typer.Option(
        50.0,
        help="Maximum simultaneous simulated exposure in USD.",
    ),
    fee_bps: float = typer.Option(10.0, help="Per-side paper fee in basis points."),
    slippage_bps: float = typer.Option(10.0, help="Per-side paper slippage in basis points."),
    min_samples: int = typer.Option(20, help="Minimum simulation observations per candidate."),
    min_probability_move: float = typer.Option(
        0.001,
        help="Skip signals with smaller absolute probability movement.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/research/simulation"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for simulation_summary.md, simulation_trades.csv, "
            "simulation_results.csv, and simulation_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N simulated candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run paper-only walk-forward simulation for robust candidates."""

    from joint_research.research.simulation import (  # noqa: PLC0415
        SimulationGrade,
        CANDIDATE_SOURCES,
        run_simulation_study,
        write_simulation_report,
    )

    if candidate_source not in CANDIDATE_SOURCES:
        raise typer.BadParameter(
            "candidate_source must be one of: "
            + ",".join(sorted(CANDIDATE_SOURCES))
        )

    paths = _resolve_paths(warehouse_root)
    results = run_simulation_study(
        paths=paths,
        candidate_source=candidate_source,
        starting_capital=starting_capital,
        fixed_notional=fixed_notional,
        max_simultaneous_exposure=max_simultaneous_exposure,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        min_samples=min_samples,
        min_probability_move=min_probability_move,
    )
    resolved_output_dir = output_dir.resolve()
    file_prefix = "simulation"
    if candidate_source == "wallet-flow-signal":
        file_prefix = "simulation_wallet_flow"
        if output_dir == Path("artifacts/research/simulation"):
            resolved_output_dir = Path("artifacts/research/simulation_wallet_flow").resolve()
    report_paths = write_simulation_report(
        output_dir=resolved_output_dir,
        results=results,
        file_prefix=file_prefix,
    )

    counts = {
        grade.value: sum(1 for result in results if result.simulation_grade is grade)
        for grade in SimulationGrade
    }
    total_pnl = sum(result.total_paper_pnl for result in results)
    total_trades = sum(result.trade_count for result in results)
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"candidate_source={candidate_source} "
        f"candidates_simulated={len(results)} "
        f"trades={total_trades} "
        f"paper_pnl=${total_pnl:.2f} "
        f"paper_ready={counts['PAPER_READY']} "
        f"watchlist={counts['WATCHLIST']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"trades_csv={report_paths.trades_csv}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [
        result for result in results if result.simulation_grade is not SimulationGrade.REJECTED
    ][:show_top]
    if not candidates:
        typer.echo("no simulation candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} simulated candidates:")
    for result in candidates:
        typer.echo(
            f"  rank={result.rank:>2} grade={result.simulation_grade.value:<11} "
            f"asset={result.asset:>4} lag={result.lag_hours:>2}h "
            f"trades={result.trade_count} win={result.win_rate:.2f} "
            f"pnl=${result.total_paper_pnl:.2f} dd=${result.max_drawdown:.2f} "
            f"market={result.market_slug or result.market_id}"
        )


@ingest_app.command("wallet-activity")
def ingest_wallet_activity(
    limit: int = typer.Option(50, help="Top-N wallets to discover and pull activity for."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull whale wallet activity (top traders + market top-holders) via DataAPI."""

    from joint_research.ingest.wallet_runner import (  # noqa: PLC0415
        ingest_whale_wallet_activity as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(run(paths=paths, limit=limit))
    typer.echo(
        f"wallets_selected={result.wallets_selected} "
        f"activities_fetched={result.activities_fetched} "
        f"rows_written={result.rows_written} "
        f"shard={result.shard_path or '(none)'}"
    )


@ingest_app.command("polymarket-wallet-flow")
def ingest_polymarket_wallet_flow(
    limit_markets: int = typer.Option(20, help="Top-N crypto-tagged markets to scope ingestion."),
    limit_events: int = typer.Option(500, help="Maximum rows to write for this run."),
    min_volume: float = typer.Option(
        0.0,
        help="Minimum market volume (1mo, fallback total) required for market selection.",
    ),
    asset: str | None = typer.Option(
        None,
        help="Optional asset filter (e.g. BTC, ETH, SOL, XRP).",
    ),
    lookback_hours: int | None = typer.Option(
        None,
        help="Optional lookback window; keep only rows newer than N hours.",
    ),
    large_trade_usdc: float = typer.Option(
        1_000.0,
        help="USDC notional threshold used to tag large trades.",
    ),
    include_copy_signals: bool = typer.Option(
        True,
        "--include-copy-signals/--no-copy-signals",
        help="Include copy-trader relationship evidence rows when available.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull public Polymarket wallet/trader flow into the warehouse."""

    from joint_research.ingest.polymarket_wallet_flow import (  # noqa: PLC0415
        ingest_polymarket_wallet_flow as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(
        run(
            paths=paths,
            limit_markets=limit_markets,
            limit_events=limit_events,
            min_volume=min_volume,
            asset=asset,
            lookback_hours=lookback_hours,
            large_trade_usdc=large_trade_usdc,
            include_copy_signals=include_copy_signals,
        )
    )
    typer.echo(
        f"markets_scanned={result.markets_scanned} "
        f"markets_with_rows={result.markets_with_rows} "
        f"skipped_markets={result.skipped_markets} "
        f"rows_written={result.rows_written} "
        f"trade_rows={result.trade_rows} "
        f"copy_rows={result.copy_rows} "
        f"sources={','.join(result.source_clients) if result.source_clients else '(none)'} "
        f"shard={result.shard_path or '(none)'}"
    )
    for warning in result.warnings:
        typer.echo(f"  warning={warning}")


@ingest_app.command("wallet-flow-backfill-plan")
def ingest_wallet_flow_backfill_plan(
    asset: str = typer.Option(
        "ALL",
        help="Asset scope: BTC|ETH|SOL|XRP|ALL.",
    ),
    stage: str = typer.Option(
        "stage_1_quick",
        help="Stage: stage_1_quick|stage_2_depth|stage_3_breadth.",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Execute the selected stage using the existing polymarket-wallet-flow ingestor.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Dry-run mode (default). Automatically disabled when --execute is passed.",
    ),
    limit_markets: int | None = typer.Option(
        None,
        help="Optional stage market cap override.",
    ),
    limit_events: int = typer.Option(
        2000,
        help="Maximum rows to write when running in --execute mode.",
    ),
    min_volume: float = typer.Option(
        0.0,
        help="Minimum 1mo/total market volume required for plan eligibility.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_backfill_plan.md, wallet_flow_backfill_plan.csv, "
            "and wallet_flow_coverage.csv."
        ),
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Build a safe staged wallet-flow backfill plan, and optionally execute one stage."""

    from joint_research.ingest.wallet_flow_backfill_plan import (  # noqa: PLC0415
        STAGE_ORDER,
        run_wallet_flow_backfill_plan,
    )

    valid_assets = {"BTC", "ETH", "SOL", "XRP", "ALL"}
    normalized_asset = asset.strip().upper()
    if normalized_asset not in valid_assets:
        raise typer.BadParameter("asset must be one of BTC|ETH|SOL|XRP|ALL")
    if stage not in STAGE_ORDER:
        raise typer.BadParameter("stage must be one of stage_1_quick|stage_2_depth|stage_3_breadth")

    paths = _resolve_paths(warehouse_root)
    result = run_wallet_flow_backfill_plan(
        paths=paths,
        output_dir=output_dir.resolve(),
        asset=normalized_asset,
        stage=stage,
        limit_markets=limit_markets,
        limit_events=limit_events,
        min_volume=min_volume,
        execute=execute,
        dry_run=(dry_run and not execute),
    )
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"asset={normalized_asset} stage={result.selected_stage} "
        f"stage_markets={result.selected_stage_markets} "
        f"stage_1={result.stage_counts.get('stage_1_quick', 0)} "
        f"stage_2={result.stage_counts.get('stage_2_depth', 0)} "
        f"stage_3={result.stage_counts.get('stage_3_breadth', 0)} "
        f"dry_run={not execute}"
    )
    typer.echo(f"plan_md={result.artifacts.plan_md}")
    typer.echo(f"plan_csv={result.artifacts.plan_csv}")
    typer.echo(f"coverage_csv={result.artifacts.coverage_csv}")
    typer.echo(
        f"coverage_before wallet_flow_rows={result.before.wallet_flow_rows} "
        f"trade_rows={result.before.trade_rows} "
        f"copy_rows={result.before.copy_rows} "
        f"market_flow_hourly_rows={result.before.market_flow_hourly_rows} "
        f"whale_flow_hourly_rows={result.before.whale_flow_hourly_rows}"
    )

    if result.execution is None:
        return

    execution = result.execution
    typer.echo(
        f"executed stage={execution.stage} "
        f"rows_written={execution.rows_written} "
        f"trade_rows={execution.trade_rows_written} "
        f"copy_rows={execution.copy_rows_written} "
        f"markets_scanned={execution.markets_scanned} "
        f"markets_with_rows={execution.markets_with_rows} "
        f"skipped_markets={execution.skipped_markets} "
        f"sources={','.join(execution.source_clients) if execution.source_clients else '(none)'}"
    )
    typer.echo(
        f"coverage_after wallet_flow_rows={execution.after.wallet_flow_rows} "
        f"trade_rows={execution.after.trade_rows} "
        f"copy_rows={execution.after.copy_rows} "
        f"market_flow_hourly_rows={execution.after.market_flow_hourly_rows} "
        f"whale_flow_hourly_rows={execution.after.whale_flow_hourly_rows}"
    )
    for warning in execution.warnings:
        typer.echo(f"  warning={warning}")


@research_app.command("event-study")
def research_event_study(
    min_trade_size_usdc: float = typer.Option(
        100.0, help="Skip trades smaller than this notional in USDC."
    ),
    out_path: Path = typer.Option(
        Path("data/research/event_study_catalog.parquet"),
        help="Output Parquet path for the event-study cells.",
    ),
    show_top: int = typer.Option(20, help="Print the top-N cells by |t-stat|."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run the whale-trade → crypto-return event study."""

    from joint_research.research.event_study import (  # noqa: PLC0415
        run_event_study,
        write_event_study_catalog,
    )

    paths = _resolve_paths(warehouse_root)
    result = run_event_study(
        paths=paths,
        min_trade_size_usdc=min_trade_size_usdc,
    )
    write_event_study_catalog(out_path=out_path.resolve(), result=result)

    typer.echo(
        f"trades_total={result.n_trades_total} "
        f"wallets={result.n_wallets} assets={result.n_assets} "
        f"cells={len(result.cells)}"
    )

    sig = [c for c in result.cells if c.bh_significant_at_0_05]
    if sig:
        typer.echo(f"BH-significant cells: {len(sig)}")
        for c in sig:
            typer.echo(
                f"  asset={c.asset} dir={c.direction} lag={c.lag_hours}h "
                f"mean={c.mean_log_return*1e4:+.2f}bps "
                f"t={c.tstat_vs_zero:+.2f} p={c.pvalue_vs_zero:.4f} n={c.n_trades}"
            )
    else:
        typer.echo("no BH-significant cells at alpha=0.05")

    typer.echo(f"\ntop {show_top} cells by |t|:")
    ordered = sorted(
        (c for c in result.cells if not math.isnan(c.tstat_vs_zero)),
        key=lambda c: -abs(c.tstat_vs_zero),
    )[:show_top]
    for c in ordered:
        typer.echo(
            f"  asset={c.asset:>4} dir={c.direction:>8} lag={c.lag_hours:>2}h "
            f"mean={c.mean_log_return*1e4:+7.2f}bps t={c.tstat_vs_zero:+.2f} "
            f"p={c.pvalue_vs_zero:.4f} n={c.n_trades}"
        )


@research_app.command("cryp-backtest")
def research_cryp_backtest(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT",
        help="Comma-separated symbol list to backtest.",
    ),
    feature_lookback: int = typer.Option(14, help="Hours of history fed to feature pipeline."),
    max_holding_hours: int = typer.Option(24, help="Max bars to hold a trade if neither stop nor TP hits."),
    round_trip_cost_bps: float = typer.Option(
        14.0,
        help="Combined entry+exit fee + slippage in bps. Bybit perp taker is ~11 bps round-trip; 14 leaves buffer.",
    ),
    out_path: Path = typer.Option(
        Path("data/research/cryp_backtest_trades.parquet"),
        help="Output Parquet path for the per-trade ledger.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Backtest cryp's deterministic breakout/mean-reversion on warehouse OHLCV."""

    from joint_research.research.cryp_backtest import (  # noqa: PLC0415
        run_cryp_backtest,
        write_backtest_catalog,
    )

    paths = _resolve_paths(warehouse_root)
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = []
    for symbol in symbol_list:
        res = run_cryp_backtest(
            paths=paths,
            symbol=symbol,
            feature_lookback=feature_lookback,
            max_holding_hours=max_holding_hours,
            round_trip_cost_bps=round_trip_cost_bps,
        )
        results.append(res)
        s = res.summary()
        typer.echo(
            f"symbol={res.symbol:<10} candles={res.n_candles:>5} "
            f"breakout_props={res.n_proposals_breakout:>4} "
            f"mr_props={res.n_proposals_mean_reversion:>4} "
            f"trades={s['n_trades']:>4} "
            f"hit_rate={s['hit_rate']:.2f} "
            f"mean_bps={s['mean_net_bps']:+7.2f} "
            f"total_bps={s['total_net_bps']:+8.1f} "
            f"max_dd_bps={s['max_drawdown_bps']:7.1f} "
            f"sharpe={s['sharpe_per_trade']:+5.2f}"
        )

    write_backtest_catalog(out_path=out_path.resolve(), results=results)
    typer.echo(f"\ntrades catalog: {out_path.resolve()}")


if __name__ == "__main__":
    app()
