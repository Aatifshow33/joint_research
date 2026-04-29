"""Walk-forward paper simulation for Polymarket -> crypto candidates."""

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
CANDIDATE_SOURCES = {
    "robustness",
    "composite-signal",
    "derivatives-regime",
    "wallet-flow-signal",
}


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
    candidate_source: str = "robustness"
    feature_name: str | None = None
    segment_type: str | None = None
    segment_value: str | None = None
    learned_direction: int | None = None


@dataclass(frozen=True)
class SimulationObservation:
    open_time_ns: int
    poly_price_change: float
    crypto_close: float
    forward_log_return: float
    buy_volume_usdc: float | None = None
    sell_volume_usdc: float | None = None
    net_flow_usdc: float | None = None
    abs_net_flow_usdc: float | None = None
    unique_active_wallets: int | None = None
    large_trade_count: int | None = None
    whale_flow_score: float | None = None
    copy_flow_count: int | None = None
    flow_momentum_4h: float | None = None
    flow_momentum_24h: float | None = None
    flow_direction: str | None = None
    whale_flow_bucket: str | None = None
    active_wallet_bucket: str | None = None
    copy_flow_bucket: str | None = None


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

        side = _candidate_side(candidate, obs)
        if side == 0:
            skipped_tiny += 1
            continue

        if candidate.candidate_source == "robustness" and abs(obs.poly_price_change) < min_probability_move:
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
    candidate_source: str = "robustness",
    starting_capital: float = 200.0,
    fixed_notional: float = 10.0,
    max_simultaneous_exposure: float = 50.0,
    fee_bps: float = 10.0,
    slippage_bps: float = 10.0,
    min_samples: int = 20,
    min_probability_move: float = 0.001,
) -> list[SimulationResult]:
    if candidate_source not in CANDIDATE_SOURCES:
        raise ValueError(f"unsupported_candidate_source:{candidate_source}")

    con = duckdb.connect()
    register_views(con, paths)
    candidates = _load_candidates(paths=paths, source=candidate_source)
    if candidate_source == "wallet-flow-signal":
        candidates = _dedupe_wallet_candidates(candidates)

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
    file_prefix: str = "simulation",
) -> SimulationReportPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_md = output_dir / f"{file_prefix}_summary.md"
    trades_csv = output_dir / f"{file_prefix}_trades.csv"
    results_csv = output_dir / f"{file_prefix}_results.csv"
    candidates_json = output_dir / f"{file_prefix}_candidates.json"

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


def _load_candidates(*, paths: WarehousePaths, source: str) -> list[SimulationCandidate]:
    if source == "robustness":
        robust_results = run_robustness_study(paths=paths)
        return [_candidate_from_robustness(r) for r in robust_results if _is_simulatable(r)]

    if source == "composite-signal":
        records = _load_json_records(
            _artifact_path(
                paths,
                "artifacts",
                "research",
                "composite_signal",
                "composite_signal_candidates.json",
            )
        )
        return [_candidate_from_composite(record) for record in records if record.get("grade") in {"SIMULATION_READY", "WATCHLIST"}]

    if source == "derivatives-regime":
        records = _load_json_records(
            _artifact_path(
                paths,
                "artifacts",
                "research",
                "derivatives_regime",
                "derivatives_regime_candidates.json",
            )
        )
        return [_candidate_from_derivatives(record) for record in records if record.get("grade") in {"SIMULATION_READY", "WATCHLIST"}]

    records = _load_json_records(
        _artifact_path(
            paths,
            "artifacts",
            "research",
            "wallet_flow_signal",
            "wallet_flow_signal_candidates.json",
        )
    )
    return [_candidate_from_wallet_flow(record) for record in records if record.get("grade") in {"SIMULATION_READY", "WATCHLIST"}]


def _artifact_path(paths: WarehousePaths, *parts: str) -> Path:
    return paths.root.resolve().parent.parent.joinpath(*parts)


def _load_json_records(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


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
        candidate_source="robustness",
    )


def _candidate_from_composite(record: dict[str, object]) -> SimulationCandidate:
    return SimulationCandidate(
        asset=str(record.get("asset") or ""),
        market_id=str(record.get("market_id") or ""),
        market_slug=_optional_str(record.get("market_slug")),
        token_id=str(record.get("token_id") or ""),
        question=_optional_str(record.get("question")),
        lag_hours=_optional_int(record.get("horizon_hours")) or 1,
        signal_correlation=float(_optional_int(record.get("learned_direction")) or 0),
        robustness_grade=str(record.get("grade") or "WATCHLIST"),
        candidate_source="composite-signal",
        learned_direction=_optional_int(record.get("learned_direction")),
    )


def _candidate_from_derivatives(record: dict[str, object]) -> SimulationCandidate:
    return SimulationCandidate(
        asset=str(record.get("asset") or ""),
        market_id=str(record.get("market_id") or ""),
        market_slug=_optional_str(record.get("market_slug")),
        token_id=str(record.get("token_id") or ""),
        question=_optional_str(record.get("question")),
        lag_hours=_optional_int(record.get("horizon_hours")) or 1,
        signal_correlation=float(_optional_int(record.get("learned_direction")) or 0),
        robustness_grade=str(record.get("grade") or "WATCHLIST"),
        candidate_source="derivatives-regime",
        learned_direction=_optional_int(record.get("learned_direction")),
    )


def _candidate_from_wallet_flow(record: dict[str, object]) -> SimulationCandidate:
    return SimulationCandidate(
        asset=str(record.get("asset") or ""),
        market_id=str(record.get("market_id") or ""),
        market_slug=_optional_str(record.get("market_slug")),
        token_id=str(record.get("token_id") or ""),
        question=_optional_str(record.get("question")),
        lag_hours=_optional_int(record.get("horizon_hours")) or 1,
        signal_correlation=float(_optional_int(record.get("learned_direction")) or 0),
        robustness_grade=str(record.get("grade") or "WATCHLIST"),
        candidate_source="wallet-flow-signal",
        feature_name=_optional_str(record.get("feature_name")),
        segment_type=_optional_str(record.get("segment_type")),
        segment_value=_optional_str(record.get("segment_value")),
        learned_direction=_optional_int(record.get("learned_direction")),
    )


def _is_simulatable(result: RobustnessResult) -> bool:
    return result.grade in {CandidateGrade.PROMISING, CandidateGrade.WATCHLIST}


def _dedupe_wallet_candidates(candidates: Sequence[SimulationCandidate]) -> list[SimulationCandidate]:
    # 1) remove exact duplicates by source dimensions
    by_exact: dict[tuple[object, ...], SimulationCandidate] = {}
    for candidate in candidates:
        key = (
            candidate.asset,
            candidate.market_id,
            candidate.lag_hours,
            candidate.feature_name,
            candidate.segment_type,
            candidate.segment_value,
        )
        if key not in by_exact:
            by_exact[key] = candidate

    # 2) prefer the first/highest-ranked entry per asset/market/horizon to avoid overlap
    by_bucket: dict[tuple[str, str, int], SimulationCandidate] = {}
    for candidate in by_exact.values():
        bucket = (candidate.asset, candidate.market_id, candidate.lag_hours)
        if bucket not in by_bucket:
            by_bucket[bucket] = candidate
    return list(by_bucket.values())


def _load_simulation_observations(
    con: duckdb.DuckDBPyConnection,
    candidate: SimulationCandidate,
) -> list[SimulationObservation]:
    if candidate.candidate_source == "wallet-flow-signal":
        return _load_wallet_flow_observations(con, candidate)

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


def _load_wallet_flow_observations(
    con: duckdb.DuckDBPyConnection,
    candidate: SimulationCandidate,
) -> list[SimulationObservation]:
    rows = con.execute(
        """
        WITH copy_hourly AS (
          SELECT
            market_id,
            asset,
            event_time_ns - (event_time_ns % 3600000000000) AS flow_hour_ns,
            count(*) AS copy_flow_count
          FROM polymarket_copy_flow_events
          GROUP BY market_id, asset, flow_hour_ns
        ),
        flow_base AS (
          SELECT
            f.market_id,
            f.asset,
            f.open_time_ns,
            f.buy_volume_usdc,
            f.sell_volume_usdc,
            f.net_flow_usdc,
            abs(f.net_flow_usdc) AS abs_net_flow_usdc,
            f.unique_active_wallets,
            f.large_trade_count,
            f.whale_flow_score,
            coalesce(c.copy_flow_count, 0) AS copy_flow_count,
            f.net_flow_usdc - lag(f.net_flow_usdc, 4) OVER (
              PARTITION BY f.market_id, f.asset ORDER BY f.open_time_ns
            ) AS flow_momentum_4h,
            f.net_flow_usdc - lag(f.net_flow_usdc, 24) OVER (
              PARTITION BY f.market_id, f.asset ORDER BY f.open_time_ns
            ) AS flow_momentum_24h
          FROM polymarket_market_flow_hourly f
          LEFT JOIN copy_hourly c
            ON c.market_id = f.market_id
           AND c.asset = f.asset
           AND c.flow_hour_ns = f.open_time_ns
        ),
        flow_quantiles AS (
          SELECT
            percentile_cont(0.75) WITHIN GROUP (ORDER BY abs(whale_flow_score)) AS whale_p75,
            percentile_cont(0.75) WITHIN GROUP (ORDER BY unique_active_wallets) AS wallets_p75
          FROM flow_base
          WHERE market_id = ?
            AND asset = ?
        ),
        signals AS (
          SELECT
            a.open_time_ns,
            a.poly_price_change,
            a.crypto_close,
            ln(exit_bar.close / NULLIF(entry_bar.close, 0)) AS forward_log_return,
            f.open_time_ns AS flow_time_ns,
            f.buy_volume_usdc,
            f.sell_volume_usdc,
            f.net_flow_usdc,
            f.abs_net_flow_usdc,
            f.unique_active_wallets,
            f.large_trade_count,
            f.whale_flow_score,
            f.copy_flow_count,
            f.flow_momentum_4h,
            f.flow_momentum_24h,
            q.whale_p75,
            q.wallets_p75
          FROM crypto_polymarket_aligned a
          CROSS JOIN flow_quantiles q
          LEFT JOIN LATERAL (
            SELECT *
            FROM flow_base f
            WHERE f.market_id = a.market_id
              AND f.asset = upper(a.asset)
              AND f.open_time_ns <= a.open_time_ns
            ORDER BY f.open_time_ns DESC
            LIMIT 1
          ) f ON TRUE
          JOIN crypto_returns entry_bar
            ON entry_bar.symbol = ? || 'USDT'
           AND entry_bar.interval = '1h'
           AND entry_bar.open_time_ns = a.open_time_ns + ?
          JOIN crypto_returns exit_bar
            ON exit_bar.symbol = ? || 'USDT'
           AND exit_bar.interval = '1h'
           AND exit_bar.open_time_ns = a.open_time_ns + ?
          WHERE a.token_id = ?
            AND a.market_id = ?
            AND a.poly_price_change IS NOT NULL
            AND a.crypto_close IS NOT NULL
        )
        SELECT *
        FROM signals
        ORDER BY open_time_ns
        """,
        [
            candidate.market_id,
            candidate.asset,
            candidate.asset,
            HOUR_NS,
            candidate.asset,
            (candidate.lag_hours + 1) * HOUR_NS,
            candidate.token_id,
            candidate.market_id,
        ],
    ).fetchall()

    observations: list[SimulationObservation] = []
    for row in rows:
        (
            open_time_ns,
            poly_price_change,
            crypto_close,
            forward_log_return,
            _flow_time_ns,
            buy_volume_usdc,
            sell_volume_usdc,
            net_flow_usdc,
            abs_net_flow_usdc,
            unique_active_wallets,
            large_trade_count,
            whale_flow_score,
            copy_flow_count,
            flow_momentum_4h,
            flow_momentum_24h,
            whale_p75,
            wallets_p75,
        ) = row

        whale_bucket = _bucket_whale(_optional_float(whale_flow_score) or 0.0, _optional_float(whale_p75) or 0.0)
        active_bucket = _bucket_active_wallets(_optional_int(unique_active_wallets) or 0, _optional_float(wallets_p75) or 0.0)
        copy_count = _optional_int(copy_flow_count) or 0
        copy_bucket = "present" if copy_count > 0 else "absent"
        flow_direction = _flow_direction(_optional_float(net_flow_usdc) or 0.0)
        obs = SimulationObservation(
            open_time_ns=int(open_time_ns),
            poly_price_change=float(poly_price_change),
            crypto_close=float(crypto_close),
            forward_log_return=float(forward_log_return),
            buy_volume_usdc=_optional_float(buy_volume_usdc),
            sell_volume_usdc=_optional_float(sell_volume_usdc),
            net_flow_usdc=_optional_float(net_flow_usdc),
            abs_net_flow_usdc=_optional_float(abs_net_flow_usdc),
            unique_active_wallets=_optional_int(unique_active_wallets),
            large_trade_count=_optional_int(large_trade_count),
            whale_flow_score=_optional_float(whale_flow_score),
            copy_flow_count=copy_count,
            flow_momentum_4h=_optional_float(flow_momentum_4h),
            flow_momentum_24h=_optional_float(flow_momentum_24h),
            flow_direction=flow_direction,
            whale_flow_bucket=whale_bucket,
            active_wallet_bucket=active_bucket,
            copy_flow_bucket=copy_bucket,
        )
        if _wallet_segment_match(candidate, obs):
            observations.append(obs)
    return observations


def _wallet_segment_match(candidate: SimulationCandidate, observation: SimulationObservation) -> bool:
    if candidate.segment_type in (None, "", "all"):
        return True
    if candidate.segment_type == "flow_direction":
        return observation.flow_direction == candidate.segment_value
    if candidate.segment_type == "whale_flow_bucket":
        return observation.whale_flow_bucket == candidate.segment_value
    if candidate.segment_type == "active_wallet_bucket":
        return observation.active_wallet_bucket == candidate.segment_value
    if candidate.segment_type == "copy_flow_bucket":
        return observation.copy_flow_bucket == candidate.segment_value
    return True


def _candidate_side(candidate: SimulationCandidate, observation: SimulationObservation) -> int:
    if candidate.candidate_source == "wallet-flow-signal":
        signal_value = _wallet_feature_signal_value(observation, candidate.feature_name)
        return _wallet_feature_side(signal_value=signal_value, learned_direction=candidate.learned_direction)

    if candidate.learned_direction is not None and candidate.candidate_source in {
        "composite-signal",
        "derivatives-regime",
    }:
        return _directional_side(
            learned_direction=candidate.learned_direction,
            signal_value=observation.poly_price_change,
        )

    return determine_side(
        signal_correlation=candidate.signal_correlation,
        probability_change=observation.poly_price_change,
    )


def _wallet_feature_signal_value(
    observation: SimulationObservation,
    feature_name: str | None,
) -> float:
    if feature_name == "buy_volume_usdc":
        return observation.buy_volume_usdc or 0.0
    if feature_name == "sell_volume_usdc":
        return observation.sell_volume_usdc or 0.0
    if feature_name == "net_flow_usdc":
        return observation.net_flow_usdc or 0.0
    if feature_name == "abs_net_flow_usdc":
        return observation.abs_net_flow_usdc or 0.0
    if feature_name == "unique_active_wallets":
        return float(observation.unique_active_wallets or 0)
    if feature_name == "large_trade_count":
        return float(observation.large_trade_count or 0)
    if feature_name == "whale_flow_score":
        return observation.whale_flow_score or 0.0
    if feature_name == "copy_flow_count":
        return float(observation.copy_flow_count or 0)
    if feature_name == "flow_momentum_4h":
        return observation.flow_momentum_4h or 0.0
    if feature_name == "flow_momentum_24h":
        return observation.flow_momentum_24h or 0.0
    return 0.0


def _wallet_feature_side(*, signal_value: float, learned_direction: int | None) -> int:
    if learned_direction is None or learned_direction == 0:
        return 0
    signal_sign = _sign(signal_value)
    if signal_sign == 0:
        return 0
    return learned_direction * signal_sign


def _directional_side(*, learned_direction: int, signal_value: float) -> int:
    signal_sign = _sign(signal_value)
    if learned_direction == 0 or signal_sign == 0:
        return 0
    return learned_direction * signal_sign


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


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bucket_whale(whale_flow_score: float, whale_p75: float) -> str:
    if whale_p75 > 0 and abs(whale_flow_score) >= whale_p75:
        return "high"
    return "normal"


def _bucket_active_wallets(unique_active_wallets: int, wallets_p75: float) -> str:
    if wallets_p75 > 0 and unique_active_wallets >= wallets_p75:
        return "high"
    return "normal"


def _flow_direction(net_flow_usdc: float) -> str:
    if net_flow_usdc > 0:
        return "buy_dominant"
    if net_flow_usdc < 0:
        return "sell_dominant"
    return "neutral"
