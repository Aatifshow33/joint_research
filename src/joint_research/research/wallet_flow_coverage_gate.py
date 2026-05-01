
"""Wallet-flow backfill coverage gate helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

COVERAGE_GATE_FILENAME = "wallet_flow_coverage_gate.md"


@dataclass(frozen=True)
class WalletFlowCoverageGateThresholds:
    min_covered_markets: int = 25
    min_coverage_ratio: float = 0.20
    min_total_wallet_flow_rows: int = 1000
    min_market_flow_hourly_rows: int = 500
    min_whale_flow_hourly_rows: int = 500


@dataclass(frozen=True)
class WalletFlowCoverageRow:
    market_id: str
    market_slug: str
    asset: str
    is_active: bool
    is_closed: bool
    volume_1mo_usd: float
    volume_total_usd: float
    wallet_flow_rows: int
    trade_rows: int
    copy_rows: int
    market_flow_hourly_rows: int
    whale_flow_hourly_rows: int

    @property
    def has_wallet_flow(self) -> bool:
        return self.wallet_flow_rows > 0

    @property
    def has_hourly_flow(self) -> bool:
        return self.market_flow_hourly_rows > 0 or self.whale_flow_hourly_rows > 0


@dataclass(frozen=True)
class WalletFlowCoverageGate:
    status: str
    coverage_csv: Path
    missing_coverage_csv: bool
    total_markets: int
    active_markets: int
    covered_markets: int
    active_covered_markets: int
    hourly_covered_markets: int
    coverage_ratio: float
    active_coverage_ratio: float
    total_wallet_flow_rows: int
    total_trade_rows: int
    total_copy_rows: int
    total_market_flow_hourly_rows: int
    total_whale_flow_hourly_rows: int
    failure_reasons: list[str]
    top_covered_markets: list[WalletFlowCoverageRow]


def read_wallet_flow_coverage_rows(path: Path) -> list[WalletFlowCoverageRow]:
    if not path.exists():
        return []

    rows: list[WalletFlowCoverageRow] = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                WalletFlowCoverageRow(
                    market_id=row.get("market_id", ""),
                    market_slug=row.get("market_slug", ""),
                    asset=row.get("asset", ""),
                    is_active=_bool_value(row.get("is_active")),
                    is_closed=_bool_value(row.get("is_closed")),
                    volume_1mo_usd=_float_value(row.get("volume_1mo_usd")),
                    volume_total_usd=_float_value(row.get("volume_total_usd")),
                    wallet_flow_rows=_int_value(row.get("wallet_flow_rows")),
                    trade_rows=_int_value(row.get("trade_rows")),
                    copy_rows=_int_value(row.get("copy_rows")),
                    market_flow_hourly_rows=_int_value(row.get("market_flow_hourly_rows")),
                    whale_flow_hourly_rows=_int_value(row.get("whale_flow_hourly_rows")),
                )
            )
    return rows


def build_wallet_flow_coverage_gate(
    *,
    coverage_csv: Path,
    rows: list[WalletFlowCoverageRow],
    thresholds: WalletFlowCoverageGateThresholds,
    top_limit: int = 10,
) -> WalletFlowCoverageGate:
    total_markets = len(rows)
    active_markets = sum(1 for row in rows if row.is_active)
    covered_markets = sum(1 for row in rows if row.has_wallet_flow)
    active_covered_markets = sum(
        1 for row in rows if row.is_active and row.has_wallet_flow
    )
    hourly_covered_markets = sum(1 for row in rows if row.has_hourly_flow)

    coverage_ratio = covered_markets / total_markets if total_markets else 0.0
    active_coverage_ratio = (
        active_covered_markets / active_markets if active_markets else 0.0
    )

    total_wallet_flow_rows = sum(row.wallet_flow_rows for row in rows)
    total_trade_rows = sum(row.trade_rows for row in rows)
    total_copy_rows = sum(row.copy_rows for row in rows)
    total_market_flow_hourly_rows = sum(row.market_flow_hourly_rows for row in rows)
    total_whale_flow_hourly_rows = sum(row.whale_flow_hourly_rows for row in rows)

    failure_reasons: list[str] = []
    if not coverage_csv.exists():
        failure_reasons.append("coverage csv missing")
    if covered_markets < thresholds.min_covered_markets:
        failure_reasons.append("covered markets below minimum")
    if coverage_ratio < thresholds.min_coverage_ratio:
        failure_reasons.append("coverage ratio below minimum")
    if total_wallet_flow_rows < thresholds.min_total_wallet_flow_rows:
        failure_reasons.append("wallet-flow rows below minimum")
    if total_market_flow_hourly_rows < thresholds.min_market_flow_hourly_rows:
        failure_reasons.append("market-flow hourly rows below minimum")
    if total_whale_flow_hourly_rows < thresholds.min_whale_flow_hourly_rows:
        failure_reasons.append("whale-flow hourly rows below minimum")

    top_covered_markets = sorted(
        [row for row in rows if row.has_wallet_flow],
        key=lambda row: (
            -row.wallet_flow_rows,
            -row.market_flow_hourly_rows,
            -row.whale_flow_hourly_rows,
            row.market_slug,
        ),
    )[:top_limit]

    return WalletFlowCoverageGate(
        status="PASS" if not failure_reasons else "FAIL",
        coverage_csv=coverage_csv,
        missing_coverage_csv=not coverage_csv.exists(),
        total_markets=total_markets,
        active_markets=active_markets,
        covered_markets=covered_markets,
        active_covered_markets=active_covered_markets,
        hourly_covered_markets=hourly_covered_markets,
        coverage_ratio=coverage_ratio,
        active_coverage_ratio=active_coverage_ratio,
        total_wallet_flow_rows=total_wallet_flow_rows,
        total_trade_rows=total_trade_rows,
        total_copy_rows=total_copy_rows,
        total_market_flow_hourly_rows=total_market_flow_hourly_rows,
        total_whale_flow_hourly_rows=total_whale_flow_hourly_rows,
        failure_reasons=failure_reasons,
        top_covered_markets=top_covered_markets,
    )


def run_wallet_flow_coverage_gate(
    *,
    coverage_csv: Path,
    thresholds: WalletFlowCoverageGateThresholds,
    top_limit: int = 10,
) -> WalletFlowCoverageGate:
    rows = read_wallet_flow_coverage_rows(coverage_csv)
    return build_wallet_flow_coverage_gate(
        coverage_csv=coverage_csv,
        rows=rows,
        thresholds=thresholds,
        top_limit=top_limit,
    )


def write_wallet_flow_coverage_gate_report(
    *,
    coverage_csv: Path,
    output_dir: Path,
    thresholds: WalletFlowCoverageGateThresholds,
    top_limit: int = 10,
) -> tuple[Path, WalletFlowCoverageGate]:
    output_dir.mkdir(parents=True, exist_ok=True)
    gate = run_wallet_flow_coverage_gate(
        coverage_csv=coverage_csv,
        thresholds=thresholds,
        top_limit=top_limit,
    )
    report_path = output_dir / COVERAGE_GATE_FILENAME
    report_path.write_text(render_wallet_flow_coverage_gate(gate, thresholds))
    return report_path, gate


def render_wallet_flow_coverage_gate(
    gate: WalletFlowCoverageGate,
    thresholds: WalletFlowCoverageGateThresholds,
) -> str:
    lines = [
        "# Wallet Flow Coverage Gate",
        "",
        "EXPLORATORY ONLY - NOT TRADEABLE",
        "",
        "No candidates promoted.",
        "No threshold changes.",
        "No live trading changes.",
        "",
        "## Gate Status",
        "",
        f"- status: {gate.status}",
        f"- coverage_csv: {gate.coverage_csv}",
        f"- missing_coverage_csv: {gate.missing_coverage_csv}",
        "",
        "## Coverage Summary",
        "",
        f"- total_markets: {gate.total_markets}",
        f"- active_markets: {gate.active_markets}",
        f"- covered_markets: {gate.covered_markets}",
        f"- active_covered_markets: {gate.active_covered_markets}",
        f"- hourly_covered_markets: {gate.hourly_covered_markets}",
        f"- coverage_ratio: {gate.coverage_ratio:.4f}",
        f"- active_coverage_ratio: {gate.active_coverage_ratio:.4f}",
        f"- total_wallet_flow_rows: {gate.total_wallet_flow_rows}",
        f"- total_trade_rows: {gate.total_trade_rows}",
        f"- total_copy_rows: {gate.total_copy_rows}",
        f"- total_market_flow_hourly_rows: {gate.total_market_flow_hourly_rows}",
        f"- total_whale_flow_hourly_rows: {gate.total_whale_flow_hourly_rows}",
        "",
        "## Gate Thresholds",
        "",
        f"- min_covered_markets: {thresholds.min_covered_markets}",
        f"- min_coverage_ratio: {thresholds.min_coverage_ratio:.4f}",
        f"- min_total_wallet_flow_rows: {thresholds.min_total_wallet_flow_rows}",
        f"- min_market_flow_hourly_rows: {thresholds.min_market_flow_hourly_rows}",
        f"- min_whale_flow_hourly_rows: {thresholds.min_whale_flow_hourly_rows}",
        "",
        "## Failure Reasons",
        "",
    ]
    if gate.failure_reasons:
        lines.extend(f"- {reason}" for reason in gate.failure_reasons)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Top Covered Markets",
            "",
        ]
    )
    lines.extend(_render_top_covered_markets(gate.top_covered_markets))
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "PASS means coverage is sufficient to justify rerunning wallet-flow research.",
            "FAIL means backfill coverage is still too thin for research reruns.",
            "Neither status approves candidates or changes trading behavior.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _render_top_covered_markets(rows: list[WalletFlowCoverageRow]) -> list[str]:
    if not rows:
        return ["(none)"]
    lines = [
        "| market_id | asset | market_slug | wallet_flow_rows | trade_rows | copy_rows | market_flow_hourly_rows | whale_flow_hourly_rows |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.market_id} | {row.asset} | {row.market_slug} | "
            f"{row.wallet_flow_rows} | {row.trade_rows} | {row.copy_rows} | "
            f"{row.market_flow_hourly_rows} | {row.whale_flow_hourly_rows} |"
        )
    return lines


def _int_value(value: str | None) -> int:
    if value in (None, ""):
        return 0
    return int(float(value))


def _float_value(value: str | None) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def _bool_value(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}
