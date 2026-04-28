"""Walk-forward paper simulation for robust Polymarket -> crypto candidates."""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

import duckdb

from joint_research.research.robustness import (
    CandidateGrade,
    RobustnessResult,
    run_robustness_study,
)
from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.views import register_views

HOUR_NS = 3_600_000_000_000
SIMULATION_GRADES = {"REJECTED", "WATCHLIST", "PAPER_READY"}


class SimulationGrade(str, Enum):
    REJECTED = "REJECTED"
    WATCHLIST = "WATCHLIST"
    PAPER_READY = "PAPER_READY"


@dataclass(frozen=True)
class SimulationCandidate:
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    lag_hours: int
    signal_correlation: float
    robustness_grade: str


@dataclass(frozen=True)
class SimulationObservation:
    open_time_ns: int
    poly_price_change: float
    crypto_close: float
    forward_log_return: float


@dataclass(frozen=True)
class SimulatedTrade:
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    lag_hours: int
    signal_time_ns: int
    entry_time_ns: int
    exit_time_ns: int
    side: int
    notional_usd: float
    probability_change: float
    gross_return: float
    net_return: float
    pnl_usd: float


@dataclass(frozen=True)
class SimulationResult:
    rank: int
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    lag_hours: int
    robustness_grade: str
    simulation_grade: SimulationGrade
    trade_count: int
    win_rate: float
    average_gross_return: float
    average_net_return: float
    total_paper_pnl: float
    max_drawdown: float
    sharpe_like_hourly: float
    exposure_utilization: float
    best_trade_pnl: float
    worst_trade_pnl: float
    skipped_tiny_signal: int
    skipped_exposure_cap: int
    trades: list[SimulatedTrade]


@dataclass(frozen=True)
class SimulationReportPaths:
    summary_md: Path
    trades_csv: Path
    results_csv: Path
    candidates_json: Path


def determine_side(*, signal_correlation: float, probability_change: float) -> int:
    """Return +1 long, -1 short, 0 no trade."""

    if abs(probability_change) <= 0.0 or not _is_finite(signal_correlation):
        return 0
    if signal_correlation > 0:
        return 1 if probability_change > 0 else -1
    if signal_correlation < 0:
        return -1 if probability_change > 0 else 1
    return 0


def simulate_candidate(
    candidate: SimulationCandidate,
    observations: Sequence[SimulationObservation],
    *,
    starting_capital: float = 200.0,
    fixed_notional: float = 10.0,
    max_simultaneous_exposure: float = 50.0,
    fee_bps: float = 10.0,
    slippage_bps: float = 10.0,
    min_samples: int = 20,
    min_probability_move: float = 0.001,
) -> SimulationResult:
    ordered = sorted(observations, key=lambda obs: obs.open_time_ns)
    if len(ordered) < min_samples:
        return _empty_result(candidate, "insufficient_samples")

    trades: list[SimulatedTrade] = []
    active: list[SimulatedTrade] = []
    skipped_tiny = 0
    skipped_cap = 0
    round_trip_cost = 2.0 * (fee_bps + slippage_bps) / 10_000.0

    for obs in ordered:
        active = [trade for trade in active if trade.exit_time_ns > obs.open_time_ns + HOUR_NS]
        if abs(obs.poly_price_change) < min_probability_move:
            skipped_tiny += 1
            continue
        side = determine_side(
            signal_correlation=candidate.signal_correlation,
            probability_change=obs.poly_price_change,
        )
        if side == 0:
            skipped_tiny += 1
            continue
        current_exposure = sum(trade.notional_usd for trade in active)
        if current_exposure + fixed_notional > max_simultaneous_exposure:
            skipped_cap += 1
            continue
        gross_return = side * (math.exp(obs.forward_log_return) - 1.0)
        net_return = gross_return - round_trip_cost
        entry_time_ns = obs.open_time_ns + HOUR_NS
        trade = SimulatedTrade(
            asset=candidate.asset,
            market_id=candidate.market_id,
            market_slug=candidate.market_slug,
            token_id=candidate.token_id,
            lag_hours=candidate.lag_hours,
            signal_time_ns=obs.open_time_ns,
            entry_time_ns=entry_time_ns,
            exit_time_ns=entry_time_ns + candidate.lag_hours * HOUR_NS,
            side=side,
            notional_usd=fixed_notional,
            probability_change=obs.poly_price_change,
            gross_return=gross_return,
            net_return=net_return,
            pnl_usd=fixed_notional * net_return,
        )
        trades.append(trade)
        active.append(trade)

    return _result_from_trades(
        candidate,
        trades,
        skipped_tiny_signal=skipped_tiny,
        skipped_exposure_cap=skipped_cap,
        starting_capital=starting_capital,
        max_simultaneous_exposure=max_simultaneous_exposure,
    )


def run_simulation_study(
    *,
    paths: WarehousePaths,
    starting_capital: float = 200.0,
    fixed_notional: float = 10.0,
    max_simultaneous_exposure: float = 50.0,
    fee_bps: float = 10.0,
    slippage_bps: float = 10.0,
    min_samples: int = 20,
    min_probability_move: float = 0.001,
) -> list[SimulationResult]:
    robust_results = run_robustness_study(paths=paths)
    candidates = [_candidate_from_robustness(r) for r in robust_results if _is_simulatable(r)]
    con = duckdb.connect()
    register_views(con, paths)
    results = [
        simulate_candidate(
            candidate,
            _load_simulation_observations(con, candidate),
            starting_capital=starting_capital,
            fixed_notional=fixed_notional,
            max_simultaneous_exposure=max_simultaneous_exposure,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            min_samples=min_samples,
            min_probability_move=min_probability_move,
        )
        for candidate in candidates
    ]
    return rank_simulation_results(results)


def rank_simulation_results(results: Sequence[SimulationResult]) -> list[SimulationResult]:
    grade_rank = {
        SimulationGrade.PAPER_READY: 0,
        SimulationGrade.WATCHLIST: 1,
        SimulationGrade.REJECTED: 2,
    }
    ordered = sorted(
        results,
        key=lambda r: (
            grade_rank[r.simulation_grade],
            -_simulation_score(r),
            -r.total_paper_pnl,
            r.max_drawdown,
            -r.trade_count,
            r.asset,
            r.market_slug or "",
            r.market_id,
            r.token_id,
            r.lag_hours,
        ),
    )
    return [_with_rank(result, rank) for rank, result in enumerate(ordered, start=1)]


def write_simulation_report(
    *,
    output_dir: Path,
    results: Sequence[SimulationResult],
    candidate_limit: int = 20,
) -> SimulationReportPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_md = output_dir / "simulation_summary.md"
    trades_csv = output_dir / "simulation_trades.csv"
    results_csv = output_dir / "simulation_results.csv"
    candidates_json = output_dir / "simulation_candidates.json"

    ordered = rank_simulation_results(results)
    candidates = [
        result for result in ordered if result.simulation_grade is not SimulationGrade.REJECTED
    ][:candidate_limit]
    _write_results_csv(results_csv, ordered)
    _write_trades_csv(trades_csv, [trade for result in ordered for trade in result.trades])
    candidates_json.write_text(
        json.dumps([_json_result(result) for result in candidates], indent=2, sort_keys=True)
        + "\n"
    )
    summary_md.write_text(_render_summary(ordered, candidates))
    return SimulationReportPaths(
        summary_md=summary_md,
        trades_csv=trades_csv,
        results_csv=results_csv,
        candidates_json=candidates_json,
    )


def _candidate_from_robustness(result: RobustnessResult) -> SimulationCandidate:
    corr = (
        result.test_correlation
        if _is_finite(result.test_correlation)
        else result.full_correlation
    )
    return SimulationCandidate(
        asset=result.asset,
        market_id=result.market_id,
        market_slug=result.market_slug,
        token_id=result.token_id,
        question=result.question,
        lag_hours=result.lag_hours,
        signal_correlation=corr,
        robustness_grade=result.grade.value,
    )


def _is_simulatable(result: RobustnessResult) -> bool:
    return result.grade in {CandidateGrade.PROMISING, CandidateGrade.WATCHLIST}


def _load_simulation_observations(
    con: duckdb.DuckDBPyConnection,
    candidate: SimulationCandidate,
) -> list[SimulationObservation]:
    rows = con.execute(
        """
        WITH signals AS (
          SELECT
            open_time_ns,
            poly_price_change,
            crypto_close
          FROM crypto_polymarket_aligned
          WHERE token_id = ?
            AND market_id = ?
            AND poly_price_change IS NOT NULL
            AND crypto_close IS NOT NULL
        ),
        future_returns AS (
          SELECT
            s.open_time_ns,
            s.poly_price_change,
            s.crypto_close,
            ln(exit_bar.close / NULLIF(entry_bar.close, 0)) AS forward_log_return
          FROM signals s
          JOIN crypto_returns entry_bar
            ON entry_bar.symbol = ? || 'USDT'
           AND entry_bar.interval = '1h'
           AND entry_bar.open_time_ns = s.open_time_ns + ?
          JOIN crypto_returns exit_bar
            ON exit_bar.symbol = ? || 'USDT'
           AND exit_bar.interval = '1h'
           AND exit_bar.open_time_ns = s.open_time_ns + ?
        )
        SELECT open_time_ns, poly_price_change, crypto_close, forward_log_return
        FROM future_returns
        WHERE forward_log_return IS NOT NULL
        ORDER BY open_time_ns
        """,
        [
            candidate.token_id,
            candidate.market_id,
            candidate.asset,
            HOUR_NS,
            candidate.asset,
            (candidate.lag_hours + 1) * HOUR_NS,
        ],
    ).fetchall()
    return [
        SimulationObservation(
            open_time_ns=int(row[0]),
            poly_price_change=float(row[1]),
            crypto_close=float(row[2]),
            forward_log_return=float(row[3]),
        )
        for row in rows
    ]


def _result_from_trades(
    candidate: SimulationCandidate,
    trades: Sequence[SimulatedTrade],
    *,
    skipped_tiny_signal: int,
    skipped_exposure_cap: int,
    starting_capital: float,
    max_simultaneous_exposure: float,
) -> SimulationResult:
    if not trades:
        return _empty_result(
            candidate,
            "no_trades",
            skipped_tiny_signal=skipped_tiny_signal,
            skipped_exposure_cap=skipped_exposure_cap,
        )
    gross_returns = [trade.gross_return for trade in trades]
    net_returns = [trade.net_return for trade in trades]
    pnls = [trade.pnl_usd for trade in trades]
    total_pnl = sum(pnls)
    max_drawdown = _max_drawdown(trades, starting_capital=starting_capital)
    exposure_utilization = min(
        1.0,
        max((trade.notional_usd for trade in trades), default=0.0) / max_simultaneous_exposure,
    )
    sharpe = _sharpe_like(net_returns)
    grade = _grade_simulation(
        trade_count=len(trades),
        win_rate=sum(1 for pnl in pnls if pnl > 0) / len(pnls),
        average_net_return=sum(net_returns) / len(net_returns),
        total_pnl=total_pnl,
        max_drawdown=max_drawdown,
        sharpe_like=sharpe,
        starting_capital=starting_capital,
    )
    return SimulationResult(
        rank=0,
        asset=candidate.asset,
        market_id=candidate.market_id,
        market_slug=candidate.market_slug,
        token_id=candidate.token_id,
        question=candidate.question,
        lag_hours=candidate.lag_hours,
        robustness_grade=candidate.robustness_grade,
        simulation_grade=grade,
        trade_count=len(trades),
        win_rate=sum(1 for pnl in pnls if pnl > 0) / len(pnls),
        average_gross_return=sum(gross_returns) / len(gross_returns),
        average_net_return=sum(net_returns) / len(net_returns),
        total_paper_pnl=total_pnl,
        max_drawdown=max_drawdown,
        sharpe_like_hourly=sharpe,
        exposure_utilization=exposure_utilization,
        best_trade_pnl=max(pnls),
        worst_trade_pnl=min(pnls),
        skipped_tiny_signal=skipped_tiny_signal,
        skipped_exposure_cap=skipped_exposure_cap,
        trades=list(trades),
    )


def _empty_result(
    candidate: SimulationCandidate,
    _reason: str,
    *,
    skipped_tiny_signal: int = 0,
    skipped_exposure_cap: int = 0,
) -> SimulationResult:
    return SimulationResult(
        rank=0,
        asset=candidate.asset,
        market_id=candidate.market_id,
        market_slug=candidate.market_slug,
        token_id=candidate.token_id,
        question=candidate.question,
        lag_hours=candidate.lag_hours,
        robustness_grade=candidate.robustness_grade,
        simulation_grade=SimulationGrade.REJECTED,
        trade_count=0,
        win_rate=0.0,
        average_gross_return=0.0,
        average_net_return=0.0,
        total_paper_pnl=0.0,
        max_drawdown=0.0,
        sharpe_like_hourly=0.0,
        exposure_utilization=0.0,
        best_trade_pnl=0.0,
        worst_trade_pnl=0.0,
        skipped_tiny_signal=skipped_tiny_signal,
        skipped_exposure_cap=skipped_exposure_cap,
        trades=[],
    )


def _grade_simulation(
    *,
    trade_count: int,
    win_rate: float,
    average_net_return: float,
    total_pnl: float,
    max_drawdown: float,
    sharpe_like: float,
    starting_capital: float,
) -> SimulationGrade:
    if trade_count < 10 or total_pnl <= 0.0 or average_net_return <= 0.0:
        return SimulationGrade.REJECTED
    drawdown_fraction = max_drawdown / starting_capital if starting_capital else 1.0
    if (
        trade_count >= 20
        and win_rate >= 0.55
        and sharpe_like >= 0.25
        and drawdown_fraction <= 0.10
    ):
        return SimulationGrade.PAPER_READY
    if trade_count >= 10 and win_rate >= 0.50 and drawdown_fraction <= 0.20:
        return SimulationGrade.WATCHLIST
    return SimulationGrade.REJECTED


def _simulation_score(result: SimulationResult) -> float:
    if result.trade_count <= 0:
        return 0.0
    drawdown_penalty = result.max_drawdown / 10.0
    return (
        result.total_paper_pnl
        + result.win_rate
        + max(result.sharpe_like_hourly, 0.0)
        - drawdown_penalty
    )


def _max_drawdown(trades: Sequence[SimulatedTrade], *, starting_capital: float) -> float:
    equity = starting_capital
    peak = starting_capital
    max_dd = 0.0
    for trade in sorted(trades, key=lambda t: (t.exit_time_ns, t.signal_time_ns)):
        equity += trade.pnl_usd
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _sharpe_like(net_returns: Sequence[float]) -> float:
    if len(net_returns) < 3:
        return 0.0
    std = statistics.pstdev(net_returns)
    if std == 0.0:
        return 0.0
    return (sum(net_returns) / len(net_returns)) / std


def _with_rank(result: SimulationResult, rank: int) -> SimulationResult:
    return SimulationResult(
        rank=rank,
        asset=result.asset,
        market_id=result.market_id,
        market_slug=result.market_slug,
        token_id=result.token_id,
        question=result.question,
        lag_hours=result.lag_hours,
        robustness_grade=result.robustness_grade,
        simulation_grade=result.simulation_grade,
        trade_count=result.trade_count,
        win_rate=result.win_rate,
        average_gross_return=result.average_gross_return,
        average_net_return=result.average_net_return,
        total_paper_pnl=result.total_paper_pnl,
        max_drawdown=result.max_drawdown,
        sharpe_like_hourly=result.sharpe_like_hourly,
        exposure_utilization=result.exposure_utilization,
        best_trade_pnl=result.best_trade_pnl,
        worst_trade_pnl=result.worst_trade_pnl,
        skipped_tiny_signal=result.skipped_tiny_signal,
        skipped_exposure_cap=result.skipped_exposure_cap,
        trades=result.trades,
    )


def _write_results_csv(path: Path, results: Sequence[SimulationResult]) -> None:
    fieldnames = list(_json_result(results[0]).keys()) if results else list(_empty_result_record())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow(_json_result(result))


def _write_trades_csv(path: Path, trades: Sequence[SimulatedTrade]) -> None:
    fieldnames = list(asdict(trades[0]).keys()) if trades else list(_empty_trade_record())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for trade in trades:
            writer.writerow(asdict(trade))


def _render_summary(
    results: Sequence[SimulationResult],
    candidates: Sequence[SimulationResult],
) -> str:
    total_pnl = sum(result.total_paper_pnl for result in results)
    total_trades = sum(result.trade_count for result in results)
    counts = {
        grade.value: sum(1 for result in results if result.simulation_grade is grade)
        for grade in SimulationGrade
    }
    lines = [
        "# Simulation Research Summary",
        "",
        "**EXPLORATORY ONLY - NOT TRADEABLE.**",
        "",
        "This paper simulation uses next-bar entries, capped notional exposure, "
        "fixed sizing, and conservative fee/slippage assumptions. PAPER_READY "
        "means extended paper tracking only, not live trading.",
        "",
        "## Coverage",
        "",
        f"- Candidates simulated: {len(results)}",
        f"- Trades generated: {total_trades}",
        f"- Total paper PnL: ${total_pnl:.2f}",
        f"- PAPER_READY: {counts[SimulationGrade.PAPER_READY.value]}",
        f"- WATCHLIST: {counts[SimulationGrade.WATCHLIST.value]}",
        f"- REJECTED: {counts[SimulationGrade.REJECTED.value]}",
        "",
        "## Top Simulated Candidates",
        "",
    ]
    if not candidates:
        lines.extend(
            [
                "No robust candidates were available or survived simulation evidence.",
                "",
                "Practical read: keep collecting paper data before promoting any signal.",
            ]
        )
        return "\n".join(lines) + "\n"
    lines.append("| Rank | Grade | Asset | Lag | Trades | Win | PnL | Max DD | Market |")
    lines.append("| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for result in candidates[:10]:
        market = result.market_slug or result.question or result.market_id
        lines.append(
            f"| {result.rank} | {result.simulation_grade.value} | {result.asset} | "
            f"{result.lag_hours}h | {result.trade_count} | {result.win_rate:.2f} | "
            f"${result.total_paper_pnl:.2f} | ${result.max_drawdown:.2f} | "
            f"{_escape_md(str(market))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- PAPER_READY means run longer paper tracking; it is not live-trade approval.",
            "- This simulator does not place orders and does not use API keys.",
            "- Results are sensitive to stale probabilities, market overlap, costs, "
            "and sparse data.",
        ]
    )
    return "\n".join(lines) + "\n"


def _json_result(result: SimulationResult) -> dict[str, object]:
    record = asdict(result)
    record.pop("trades", None)
    record["simulation_grade"] = result.simulation_grade.value
    return {key: _json_value(value) for key, value in record.items()}


def _empty_result_record() -> dict[str, object]:
    return {
        "rank": "",
        "asset": "",
        "market_id": "",
        "market_slug": "",
        "token_id": "",
        "question": "",
        "lag_hours": "",
        "robustness_grade": "",
        "simulation_grade": "",
        "trade_count": "",
        "win_rate": "",
        "average_gross_return": "",
        "average_net_return": "",
        "total_paper_pnl": "",
        "max_drawdown": "",
        "sharpe_like_hourly": "",
        "exposure_utilization": "",
        "best_trade_pnl": "",
        "worst_trade_pnl": "",
        "skipped_tiny_signal": "",
        "skipped_exposure_cap": "",
    }


def _empty_trade_record() -> dict[str, object]:
    return {
        "asset": "",
        "market_id": "",
        "market_slug": "",
        "token_id": "",
        "lag_hours": "",
        "signal_time_ns": "",
        "entry_time_ns": "",
        "exit_time_ns": "",
        "side": "",
        "notional_usd": "",
        "probability_change": "",
        "gross_return": "",
        "net_return": "",
        "pnl_usd": "",
    }


def _json_value(value: object) -> object:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    return value


def _is_finite(value: float | None) -> bool:
    return value is not None and not math.isnan(value) and not math.isinf(value)


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")
