"""Wallet-flow-conditioned Polymarket -> crypto signal study."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

import duckdb

from joint_research.research.lead_lag import pearson_correlation_with_tstat
from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.views import register_views

HORIZONS: tuple[int, ...] = (1, 4, 24)
COST_BUFFER_RETURN = 0.004
MIN_UNIQUE_FLOW_HOURS = 24
MIN_ACTIVE_WALLET_COVERAGE = 0.50
MIN_NON_ZERO_NET_FLOW_COVERAGE = 0.50
DUPLICATE_SEGMENT_IMPROVEMENT_DELTA = 0.00035
SIMULATION_READY_MIN_TEST_IMPROVEMENT = 0.0008
SIMULATION_READY_MIN_NET_IMPROVEMENT = 0.0002
SIMULATION_READY_MIN_WIN_RATE = 0.58
SIMULATION_READY_MIN_STABILITY = 0.62
SIMULATION_READY_MIN_SAMPLES = 80
SIMULATION_READY_MIN_UNIQUE_HOURS = 48
SIMULATION_READY_MIN_ACTIVE_WALLET_COVERAGE = 0.70
SIMULATION_READY_MIN_NON_ZERO_NET_FLOW_COVERAGE = 0.70
WATCHLIST_MIN_TEST_IMPROVEMENT = 0.0004
WATCHLIST_MIN_WIN_RATE = 0.55
WATCHLIST_MIN_STABILITY = 0.52
WATCHLIST_MIN_SAMPLES = 48
WATCHLIST_MIN_UNIQUE_HOURS = 32
WATCHLIST_MIN_ACTIVE_WALLET_COVERAGE = 0.60
WATCHLIST_MIN_NON_ZERO_NET_FLOW_COVERAGE = 0.60
THIN_COPY_FLOW_MIN_COVERAGE = 0.10


class WalletFlowCandidateGrade(str, Enum):
    REJECTED = "REJECTED"
    WEAK = "WEAK"
    WATCHLIST = "WATCHLIST"
    SIMULATION_READY = "SIMULATION_READY"


@dataclass(frozen=True)
class WalletFlowCoverage:
    wallet_flow_rows: int
    market_flow_hourly_rows: int
    whale_flow_hourly_rows: int
    copy_flow_rows: int


@dataclass(frozen=True)
class WalletFlowStudyDetails:
    results: list[WalletFlowSignalResult]
    raw_results: list[WalletFlowSignalResult]
    segment_rows_before_dedup: int
    segment_rows_after_dedup: int
    coverage: WalletFlowCoverage


@dataclass(frozen=True)
class WalletFlowObservation:
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    open_time_ns: int
    flow_time_ns: int | None
    horizon_hours: int
    poly_price_change: float
    forward_return: float
    buy_volume_usdc: float
    sell_volume_usdc: float
    net_flow_usdc: float
    abs_net_flow_usdc: float
    unique_active_wallets: int
    large_trade_count: int
    whale_flow_score: float
    copy_flow_count: int
    flow_momentum_4h: float | None
    flow_momentum_24h: float | None
    flow_direction: str
    whale_bucket: str
    wallet_activity_bucket: str
    copy_bucket: str


@dataclass(frozen=True)
class WalletFlowSignalResult:
    rank: int
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    horizon_hours: int
    feature_name: str
    segment_type: str
    segment_value: str
    simplicity: float
    sample_count: int
    train_samples: int
    test_samples: int
    learned_direction: int
    train_direction_match_rate: float
    test_direction_match_rate: float
    train_average_forward_return: float
    test_average_forward_return: float
    train_win_rate: float
    test_win_rate: float
    full_correlation: float
    train_correlation: float
    test_correlation: float
    train_test_direction_match: bool
    stability: float
    baseline_test_average_forward_return: float
    test_improvement_over_baseline: float
    net_test_improvement_after_cost: float
    unique_flow_hours: int
    active_wallet_coverage: float
    non_zero_net_flow_coverage: float
    score: float
    grade: WalletFlowCandidateGrade
    filter_reason: str
    warnings: str


@dataclass(frozen=True)
class WalletFlowSignalReportPaths:
    summary_md: Path
    results_csv: Path
    candidates_json: Path
    rejection_diagnostics_csv: Path
    rejection_summary_md: Path


@dataclass(frozen=True)
class WalletFlowRejectionDiagnostic:
    rank: int
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    horizon_hours: int
    feature_name: str
    segment_type: str
    segment_value: str
    final_grade: str
    retained_after_dedup: bool
    rejection_reasons: str
    sample_count: int
    test_samples: int
    unique_flow_hours: int
    active_wallet_coverage: float
    non_zero_net_flow_coverage: float
    test_improvement_over_baseline: float
    net_test_improvement_after_cost: float
    test_win_rate: float
    stability: float


@dataclass(frozen=True)
class WalletFlowNearMiss:
    rank: int
    candidate_rank: int
    candidate_key: str
    final_grade: str
    reasons: str
    gap_to_cost_buffer: float
    gap_to_watchlist_win_rate: float
    gap_to_watchlist_stability: float
    improvement: float
    net_after_cost: float


@dataclass(frozen=True)
class _FeatureSpec:
    name: str
    extractor: Callable[[WalletFlowObservation], float]
    simplicity: float


@dataclass(frozen=True)
class _SplitEvaluation:
    sample_count: int
    train_samples: int
    test_samples: int
    learned_direction: int
    train_direction_match_rate: float
    test_direction_match_rate: float
    train_average_forward_return: float
    test_average_forward_return: float
    train_win_rate: float
    test_win_rate: float
    full_correlation: float
    train_correlation: float
    test_correlation: float
    train_test_direction_match: bool
    stability: float
    filter_reason: str


@dataclass(frozen=True)
class _SegmentContext:
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    horizon_hours: int
    feature_name: str
    segment_type: str
    segment_value: str
    simplicity: float
    baseline_test_average_forward_return: float


FEATURE_SPECS: tuple[_FeatureSpec, ...] = (
    _FeatureSpec("buy_volume_usdc", lambda row: row.buy_volume_usdc, 1.0),
    _FeatureSpec("sell_volume_usdc", lambda row: -row.sell_volume_usdc, 1.0),
    _FeatureSpec("net_flow_usdc", lambda row: row.net_flow_usdc, 1.0),
    _FeatureSpec("abs_net_flow_usdc", lambda row: row.abs_net_flow_usdc, 0.9),
    _FeatureSpec("unique_active_wallets", lambda row: float(row.unique_active_wallets), 0.9),
    _FeatureSpec("large_trade_count", lambda row: float(row.large_trade_count), 0.8),
    _FeatureSpec("whale_flow_score", lambda row: row.whale_flow_score, 0.8),
    _FeatureSpec("copy_flow_count", lambda row: float(row.copy_flow_count), 0.7),
    _FeatureSpec(
        "flow_momentum_4h",
        lambda row: row.flow_momentum_4h if row.flow_momentum_4h is not None else 0.0,
        0.6,
    ),
    _FeatureSpec(
        "flow_momentum_24h",
        lambda row: row.flow_momentum_24h if row.flow_momentum_24h is not None else 0.0,
        0.5,
    ),
)


def run_wallet_flow_signal_study(
    *,
    paths: WarehousePaths,
    min_segment_samples: int = 24,
    min_feature_samples: int = 36,
    train_fraction: float = 0.6,
) -> list[WalletFlowSignalResult]:
    return run_wallet_flow_signal_study_with_details(
        paths=paths,
        min_segment_samples=min_segment_samples,
        min_feature_samples=min_feature_samples,
        train_fraction=train_fraction,
    ).results


def run_wallet_flow_signal_study_with_details(
    *,
    paths: WarehousePaths,
    min_segment_samples: int = 24,
    min_feature_samples: int = 36,
    train_fraction: float = 0.6,
) -> WalletFlowStudyDetails:
    con = duckdb.connect()
    register_views(con, paths)
    observations = load_wallet_flow_observations(con)
    coverage = load_wallet_flow_coverage(con)
    analysis = analyze_wallet_flow_segments_with_details(
        observations,
        min_segment_samples=min_segment_samples,
        min_feature_samples=min_feature_samples,
        train_fraction=train_fraction,
    )
    return WalletFlowStudyDetails(
        results=analysis.results,
        raw_results=analysis.raw_results,
        segment_rows_before_dedup=analysis.segment_rows_before_dedup,
        segment_rows_after_dedup=analysis.segment_rows_after_dedup,
        coverage=coverage,
    )


def load_wallet_flow_coverage(con: duckdb.DuckDBPyConnection) -> WalletFlowCoverage:
    return WalletFlowCoverage(
        wallet_flow_rows=_safe_count(con, "SELECT count(*) FROM polymarket_wallet_flow"),
        market_flow_hourly_rows=_safe_count(con, "SELECT count(*) FROM polymarket_market_flow_hourly"),
        whale_flow_hourly_rows=_safe_count(con, "SELECT count(*) FROM polymarket_whale_flow_hourly"),
        copy_flow_rows=_safe_count(con, "SELECT count(*) FROM polymarket_copy_flow_events"),
    )


def load_wallet_flow_observations(con: duckdb.DuckDBPyConnection) -> list[WalletFlowObservation]:
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
        )
        SELECT
          a.asset,
          a.market_id,
          a.market_slug,
          a.token_id,
          a.question,
          a.open_time_ns,
          a.poly_price_change,
          a.crypto_log_return_next_1h,
          a.crypto_log_return_next_4h,
          a.crypto_log_return_next_24h,
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
        WHERE a.asset IS NOT NULL
          AND a.market_id IS NOT NULL
          AND a.token_id IS NOT NULL
          AND a.poly_price_change IS NOT NULL
        ORDER BY a.asset, a.market_id, a.token_id, a.open_time_ns
        """
    ).fetchall()

    observations: list[WalletFlowObservation] = []
    for row in rows:
        asset = str(row[0]).upper()
        market_id = str(row[1])
        market_slug = row[2]
        token_id = str(row[3])
        question = row[4]
        open_time_ns = int(row[5])
        poly_price_change = float(row[6])
        next_1h = _optional_float(row[7])
        next_4h = _optional_float(row[8])
        next_24h = _optional_float(row[9])

        flow_time_ns = _optional_int(row[10])
        buy_volume = _optional_float(row[11]) or 0.0
        sell_volume = _optional_float(row[12]) or 0.0
        net_flow = _optional_float(row[13]) or 0.0
        abs_net_flow = _optional_float(row[14]) or abs(net_flow)
        unique_wallets = _optional_int(row[15]) or 0
        large_trade_count = _optional_int(row[16]) or 0
        whale_flow_score = _optional_float(row[17]) or 0.0
        copy_flow_count = _optional_int(row[18]) or 0
        flow_momentum_4h = _optional_float(row[19])
        flow_momentum_24h = _optional_float(row[20])
        whale_p75 = _optional_float(row[21]) or 0.0
        wallets_p75 = _optional_float(row[22]) or 0.0

        flow_direction = _flow_direction(net_flow)
        whale_bucket = "high" if abs(whale_flow_score) >= whale_p75 and whale_p75 > 0 else "normal"
        wallet_bucket = "high" if unique_wallets >= wallets_p75 and wallets_p75 > 0 else "normal"
        copy_bucket = "present" if copy_flow_count > 0 else "absent"

        for horizon, forward_return in ((1, next_1h), (4, next_4h), (24, next_24h)):
            if forward_return is None:
                continue
            observations.append(
                WalletFlowObservation(
                    asset=asset,
                    market_id=market_id,
                    market_slug=market_slug,
                    token_id=token_id,
                    question=question,
                    open_time_ns=open_time_ns,
                    flow_time_ns=flow_time_ns,
                    horizon_hours=horizon,
                    poly_price_change=poly_price_change,
                    forward_return=forward_return,
                    buy_volume_usdc=buy_volume,
                    sell_volume_usdc=sell_volume,
                    net_flow_usdc=net_flow,
                    abs_net_flow_usdc=abs_net_flow,
                    unique_active_wallets=unique_wallets,
                    large_trade_count=large_trade_count,
                    whale_flow_score=whale_flow_score,
                    copy_flow_count=copy_flow_count,
                    flow_momentum_4h=flow_momentum_4h,
                    flow_momentum_24h=flow_momentum_24h,
                    flow_direction=flow_direction,
                    whale_bucket=whale_bucket,
                    wallet_activity_bucket=wallet_bucket,
                    copy_bucket=copy_bucket,
                )
            )
    return observations


@dataclass(frozen=True)
class _AnalysisDetails:
    raw_results: list[WalletFlowSignalResult]
    results: list[WalletFlowSignalResult]
    segment_rows_before_dedup: int
    segment_rows_after_dedup: int


def analyze_wallet_flow_segments(
    observations: Sequence[WalletFlowObservation],
    *,
    min_segment_samples: int = 24,
    min_feature_samples: int = 36,
    train_fraction: float = 0.6,
) -> list[WalletFlowSignalResult]:
    return analyze_wallet_flow_segments_with_details(
        observations,
        min_segment_samples=min_segment_samples,
        min_feature_samples=min_feature_samples,
        train_fraction=train_fraction,
    ).results


def analyze_wallet_flow_segments_with_details(
    observations: Sequence[WalletFlowObservation],
    *,
    min_segment_samples: int = 24,
    min_feature_samples: int = 36,
    train_fraction: float = 0.6,
) -> _AnalysisDetails:
    by_market_horizon: dict[tuple[str, str, str, int], list[WalletFlowObservation]] = defaultdict(list)
    for obs in observations:
        key = (obs.asset, obs.market_id, obs.token_id, obs.horizon_hours)
        by_market_horizon[key].append(obs)

    raw_results: list[WalletFlowSignalResult] = []
    for group in by_market_horizon.values():
        if not group:
            continue
        first = group[0]
        baseline_eval = evaluate_segment(group, predictor=lambda row: row.poly_price_change, train_fraction=train_fraction)
        baseline_test_avg = baseline_eval.test_average_forward_return

        segments: dict[tuple[str, str], list[WalletFlowObservation]] = defaultdict(list)
        has_copy_flow = any(item.copy_flow_count > 0 for item in group)
        for obs in group:
            segments[("flow_direction", obs.flow_direction)].append(obs)
            segments[("whale_flow_bucket", obs.whale_bucket)].append(obs)
            segments[("active_wallet_bucket", obs.wallet_activity_bucket)].append(obs)
            if has_copy_flow:
                segments[("copy_flow_bucket", obs.copy_bucket)].append(obs)

        for feature in FEATURE_SPECS:
            feature_obs = [obs for obs in group if _feature_value(obs, feature.name) not in (None, 0.0)]
            if not feature_obs:
                continue
            feature_context = _SegmentContext(
                asset=first.asset,
                market_id=first.market_id,
                market_slug=first.market_slug,
                token_id=first.token_id,
                question=first.question,
                horizon_hours=first.horizon_hours,
                feature_name=feature.name,
                segment_type="all",
                segment_value="all",
                simplicity=feature.simplicity,
                baseline_test_average_forward_return=baseline_test_avg,
            )
            raw_results.append(
                _build_result(
                    context=feature_context,
                    observations=feature_obs,
                    required_samples=min_feature_samples,
                    predictor=feature.extractor,
                    train_fraction=train_fraction,
                )
            )

            for (segment_type, segment_value), seg_obs_all in segments.items():
                seg_obs = [obs for obs in seg_obs_all if _feature_value(obs, feature.name) not in (None, 0.0)]
                if not seg_obs:
                    continue
                context = _SegmentContext(
                    asset=first.asset,
                    market_id=first.market_id,
                    market_slug=first.market_slug,
                    token_id=first.token_id,
                    question=first.question,
                    horizon_hours=first.horizon_hours,
                    feature_name=feature.name,
                    segment_type=segment_type,
                    segment_value=segment_value,
                    simplicity=feature.simplicity * (0.9 if segment_type != "all" else 1.0),
                    baseline_test_average_forward_return=baseline_test_avg,
                )
                raw_results.append(
                    _build_result(
                        context=context,
                        observations=seg_obs,
                        required_samples=min_segment_samples,
                        predictor=feature.extractor,
                        train_fraction=train_fraction,
                    )
                )

    deduped = _dedupe_segment_candidates(raw_results)
    return _AnalysisDetails(
        raw_results=raw_results,
        results=rank_wallet_flow_results(deduped),
        segment_rows_before_dedup=len(raw_results),
        segment_rows_after_dedup=len(deduped),
    )


def evaluate_segment(
    observations: Sequence[WalletFlowObservation],
    *,
    predictor,
    train_fraction: float,
) -> _SplitEvaluation:
    ordered = sorted(observations, key=lambda row: row.open_time_ns)
    n = len(ordered)
    if n < 2:
        return _empty_eval(n)

    split_idx = int(n * train_fraction)
    split_idx = max(1, min(split_idx, n - 1))
    train = ordered[:split_idx]
    test = ordered[split_idx:]

    learned_direction = _learn_direction(train, predictor=predictor)
    train_metrics = _evaluate_signed(train, predictor=predictor, learned_direction=learned_direction)
    test_metrics = _evaluate_signed(test, predictor=predictor, learned_direction=learned_direction)
    full_corr = _correlation(ordered, predictor=predictor)
    train_corr = _correlation(train, predictor=predictor)
    test_corr = _correlation(test, predictor=predictor)

    direction_match = (
        _sign(train_metrics["avg"]) != 0
        and _sign(train_metrics["avg"]) == _sign(test_metrics["avg"])
    )
    stability = _stability_score(
        train_avg=train_metrics["avg"],
        test_avg=test_metrics["avg"],
        train_corr=train_corr,
        test_corr=test_corr,
    )
    filter_reason = "passed" if learned_direction != 0 else "no_train_edge"
    return _SplitEvaluation(
        sample_count=n,
        train_samples=len(train),
        test_samples=len(test),
        learned_direction=learned_direction,
        train_direction_match_rate=train_metrics["direction_match_rate"],
        test_direction_match_rate=test_metrics["direction_match_rate"],
        train_average_forward_return=train_metrics["avg"],
        test_average_forward_return=test_metrics["avg"],
        train_win_rate=train_metrics["win_rate"],
        test_win_rate=test_metrics["win_rate"],
        full_correlation=full_corr,
        train_correlation=train_corr,
        test_correlation=test_corr,
        train_test_direction_match=direction_match,
        stability=stability,
        filter_reason=filter_reason,
    )


def rank_wallet_flow_results(results: Sequence[WalletFlowSignalResult]) -> list[WalletFlowSignalResult]:
    grade_rank = {
        WalletFlowCandidateGrade.SIMULATION_READY: 0,
        WalletFlowCandidateGrade.WATCHLIST: 1,
        WalletFlowCandidateGrade.WEAK: 2,
        WalletFlowCandidateGrade.REJECTED: 3,
    }
    ordered = sorted(
        results,
        key=lambda row: (
            grade_rank[row.grade],
            -row.test_improvement_over_baseline,
            -row.test_samples,
            -row.stability,
            -row.test_win_rate,
            -row.simplicity,
            row.asset,
            row.market_slug or "",
            row.market_id,
            row.token_id,
            row.horizon_hours,
            row.feature_name,
            row.segment_type,
            row.segment_value,
        ),
    )
    return [_with_rank(row, idx + 1) for idx, row in enumerate(ordered)]


def write_wallet_flow_signal_report(
    *,
    output_dir: Path,
    results: Sequence[WalletFlowSignalResult],
    study_details: WalletFlowStudyDetails | None = None,
    candidate_limit: int = 20,
) -> WalletFlowSignalReportPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    ordered = rank_wallet_flow_results(results)
    candidates = [row for row in ordered if row.grade is not WalletFlowCandidateGrade.REJECTED][
        :candidate_limit
    ]

    summary_md = output_dir / "wallet_flow_signal_summary.md"
    results_csv = output_dir / "wallet_flow_signal_results.csv"
    candidates_json = output_dir / "wallet_flow_signal_candidates.json"
    rejection_diagnostics_csv = output_dir / "wallet_flow_rejection_diagnostics.csv"
    rejection_summary_md = output_dir / "wallet_flow_rejection_summary.md"

    _write_results_csv(results_csv, ordered)
    candidates_json.write_text(
        json.dumps([_json_record(row) for row in candidates], indent=2, sort_keys=True) + "\n"
    )
    diagnostics = build_wallet_flow_rejection_diagnostics(
        raw_results=study_details.raw_results if study_details is not None else ordered,
        final_results=ordered,
    )
    _write_rejection_diagnostics_csv(rejection_diagnostics_csv, diagnostics)
    rejection_summary_md.write_text(
        _render_rejection_summary(
            diagnostics=diagnostics,
            final_results=ordered,
            study_details=study_details,
        )
    )
    summary_md.write_text(_render_summary(ordered, candidates, study_details=study_details))
    return WalletFlowSignalReportPaths(
        summary_md=summary_md,
        results_csv=results_csv,
        candidates_json=candidates_json,
        rejection_diagnostics_csv=rejection_diagnostics_csv,
        rejection_summary_md=rejection_summary_md,
    )


def _build_result(
    *,
    context: _SegmentContext,
    observations: Sequence[WalletFlowObservation],
    required_samples: int,
    predictor,
    train_fraction: float,
) -> WalletFlowSignalResult:
    evaluation = evaluate_segment(observations, predictor=predictor, train_fraction=train_fraction)
    improvement = evaluation.test_average_forward_return - context.baseline_test_average_forward_return
    unique_flow_hours = len({obs.flow_time_ns if obs.flow_time_ns is not None else obs.open_time_ns for obs in observations})
    active_wallet_coverage = (
        sum(1 for obs in observations if obs.unique_active_wallets > 0) / len(observations)
        if observations
        else 0.0
    )
    non_zero_net_flow_coverage = (
        sum(1 for obs in observations if abs(obs.net_flow_usdc) > 0.0) / len(observations)
        if observations
        else 0.0
    )
    net_improvement = improvement - COST_BUFFER_RETURN

    grade = grade_wallet_flow_candidate(
        sample_count=evaluation.sample_count,
        required_samples=required_samples,
        train_test_direction_match=evaluation.train_test_direction_match,
        test_improvement=improvement,
        net_test_improvement=net_improvement,
        test_win_rate=evaluation.test_win_rate,
        stability=evaluation.stability,
        test_samples=evaluation.test_samples,
        learned_direction=evaluation.learned_direction,
        unique_flow_hours=unique_flow_hours,
        active_wallet_coverage=active_wallet_coverage,
        non_zero_net_flow_coverage=non_zero_net_flow_coverage,
    )

    filter_reason = evaluation.filter_reason
    if evaluation.sample_count < required_samples:
        filter_reason = "insufficient_samples"
    elif unique_flow_hours < MIN_UNIQUE_FLOW_HOURS:
        filter_reason = "insufficient_unique_flow_hours"
    elif active_wallet_coverage < MIN_ACTIVE_WALLET_COVERAGE:
        filter_reason = "insufficient_active_wallet_coverage"
    elif non_zero_net_flow_coverage < MIN_NON_ZERO_NET_FLOW_COVERAGE:
        filter_reason = "insufficient_non_zero_net_flow_coverage"
    elif not evaluation.train_test_direction_match:
        filter_reason = "train_test_direction_mismatch"
    elif net_improvement <= 0:
        filter_reason = "no_net_improvement_after_cost"

    warnings = _build_warnings(
        evaluation=evaluation,
        required_samples=required_samples,
        observations=observations,
        unique_flow_hours=unique_flow_hours,
        active_wallet_coverage=active_wallet_coverage,
        non_zero_net_flow_coverage=non_zero_net_flow_coverage,
    )

    score = _score_result(
        test_improvement=improvement,
        sample_count=evaluation.sample_count,
        stability=evaluation.stability,
        test_win_rate=evaluation.test_win_rate,
        simplicity=context.simplicity,
        grade=grade,
    )

    return WalletFlowSignalResult(
        rank=0,
        asset=context.asset,
        market_id=context.market_id,
        market_slug=context.market_slug,
        token_id=context.token_id,
        question=context.question,
        horizon_hours=context.horizon_hours,
        feature_name=context.feature_name,
        segment_type=context.segment_type,
        segment_value=context.segment_value,
        simplicity=context.simplicity,
        sample_count=evaluation.sample_count,
        train_samples=evaluation.train_samples,
        test_samples=evaluation.test_samples,
        learned_direction=evaluation.learned_direction,
        train_direction_match_rate=evaluation.train_direction_match_rate,
        test_direction_match_rate=evaluation.test_direction_match_rate,
        train_average_forward_return=evaluation.train_average_forward_return,
        test_average_forward_return=evaluation.test_average_forward_return,
        train_win_rate=evaluation.train_win_rate,
        test_win_rate=evaluation.test_win_rate,
        full_correlation=evaluation.full_correlation,
        train_correlation=evaluation.train_correlation,
        test_correlation=evaluation.test_correlation,
        train_test_direction_match=evaluation.train_test_direction_match,
        stability=evaluation.stability,
        baseline_test_average_forward_return=context.baseline_test_average_forward_return,
        test_improvement_over_baseline=improvement,
        net_test_improvement_after_cost=net_improvement,
        unique_flow_hours=unique_flow_hours,
        active_wallet_coverage=active_wallet_coverage,
        non_zero_net_flow_coverage=non_zero_net_flow_coverage,
        score=score,
        grade=grade,
        filter_reason=filter_reason,
        warnings=";".join(warnings),
    )


def grade_wallet_flow_candidate(
    *,
    sample_count: int,
    required_samples: int,
    train_test_direction_match: bool,
    test_improvement: float,
    net_test_improvement: float,
    test_win_rate: float,
    stability: float,
    test_samples: int,
    learned_direction: int,
    unique_flow_hours: int,
    active_wallet_coverage: float,
    non_zero_net_flow_coverage: float,
) -> WalletFlowCandidateGrade:
    if sample_count < required_samples or learned_direction == 0 or test_samples < 12:
        return WalletFlowCandidateGrade.REJECTED
    if unique_flow_hours < MIN_UNIQUE_FLOW_HOURS:
        return WalletFlowCandidateGrade.REJECTED
    if active_wallet_coverage < MIN_ACTIVE_WALLET_COVERAGE:
        return WalletFlowCandidateGrade.REJECTED
    if non_zero_net_flow_coverage < MIN_NON_ZERO_NET_FLOW_COVERAGE:
        return WalletFlowCandidateGrade.REJECTED
    if net_test_improvement <= 0:
        return WalletFlowCandidateGrade.REJECTED
    if not train_test_direction_match:
        return WalletFlowCandidateGrade.WEAK
    if (
        test_improvement >= SIMULATION_READY_MIN_TEST_IMPROVEMENT
        and net_test_improvement >= SIMULATION_READY_MIN_NET_IMPROVEMENT
        and test_win_rate >= SIMULATION_READY_MIN_WIN_RATE
        and stability >= SIMULATION_READY_MIN_STABILITY
        and sample_count >= max(required_samples, SIMULATION_READY_MIN_SAMPLES)
        and unique_flow_hours >= SIMULATION_READY_MIN_UNIQUE_HOURS
        and active_wallet_coverage >= SIMULATION_READY_MIN_ACTIVE_WALLET_COVERAGE
        and non_zero_net_flow_coverage >= SIMULATION_READY_MIN_NON_ZERO_NET_FLOW_COVERAGE
    ):
        return WalletFlowCandidateGrade.SIMULATION_READY
    if (
        test_improvement >= WATCHLIST_MIN_TEST_IMPROVEMENT
        and net_test_improvement > 0
        and test_win_rate >= WATCHLIST_MIN_WIN_RATE
        and stability >= WATCHLIST_MIN_STABILITY
        and sample_count >= max(required_samples, WATCHLIST_MIN_SAMPLES)
        and unique_flow_hours >= WATCHLIST_MIN_UNIQUE_HOURS
        and active_wallet_coverage >= WATCHLIST_MIN_ACTIVE_WALLET_COVERAGE
        and non_zero_net_flow_coverage >= WATCHLIST_MIN_NON_ZERO_NET_FLOW_COVERAGE
    ):
        return WalletFlowCandidateGrade.WATCHLIST
    if test_improvement > 0 and test_win_rate >= 0.50:
        return WalletFlowCandidateGrade.WEAK
    return WalletFlowCandidateGrade.REJECTED


def _dedupe_segment_candidates(results: Sequence[WalletFlowSignalResult]) -> list[WalletFlowSignalResult]:
    by_key: dict[tuple[str, str, str, int, str], list[WalletFlowSignalResult]] = defaultdict(list)
    for row in results:
        key = (row.asset, row.market_id, row.token_id, row.horizon_hours, row.feature_name)
        by_key[key].append(row)

    deduped: list[WalletFlowSignalResult] = []
    for group in by_key.values():
        ordered_group = sorted(group, key=_dedupe_sort_key)
        best = ordered_group[0]
        for challenger in ordered_group[1:]:
            if _can_override_simple_segment(best=best, challenger=challenger):
                best = challenger

        if len(group) > 1:
            warnings = set(_parse_warnings(best.warnings))
            warnings.add("duplicate_segment_competition")
            best = _replace_warnings(best, warnings)
        deduped.append(best)
    return deduped


def _dedupe_sort_key(row: WalletFlowSignalResult) -> tuple[float, ...]:
    return (
        _segment_priority(row.segment_type),
        -row.test_improvement_over_baseline,
        -row.test_samples,
        -row.stability,
        -row.score,
    )


def _segment_priority(segment_type: str) -> int:
    priorities = {
        "all": 0,
        "active_wallet_bucket": 1,
        "whale_flow_bucket": 2,
        "copy_flow_bucket": 3,
        "flow_direction": 4,
    }
    return priorities.get(segment_type, 5)


def _can_override_simple_segment(*, best: WalletFlowSignalResult, challenger: WalletFlowSignalResult) -> bool:
    if challenger.grade is WalletFlowCandidateGrade.REJECTED:
        return False
    grade_rank = {
        WalletFlowCandidateGrade.SIMULATION_READY: 0,
        WalletFlowCandidateGrade.WATCHLIST: 1,
        WalletFlowCandidateGrade.WEAK: 2,
        WalletFlowCandidateGrade.REJECTED: 3,
    }
    if grade_rank[challenger.grade] > grade_rank[best.grade]:
        return False

    improvement_clear = (
        challenger.test_improvement_over_baseline
        >= best.test_improvement_over_baseline + DUPLICATE_SEGMENT_IMPROVEMENT_DELTA
    )
    sample_clear = (
        challenger.sample_count >= max(MIN_UNIQUE_FLOW_HOURS, int(best.sample_count * 0.5))
        and challenger.test_samples >= max(12, int(best.test_samples * 0.5))
    )
    stable_enough = challenger.stability >= max(0.0, best.stability - 0.05)
    return improvement_clear and sample_clear and stable_enough


def _build_warnings(
    *,
    evaluation: _SplitEvaluation,
    required_samples: int,
    observations: Sequence[WalletFlowObservation],
    unique_flow_hours: int,
    active_wallet_coverage: float,
    non_zero_net_flow_coverage: float,
) -> list[str]:
    warnings: list[str] = []
    if evaluation.sample_count < max(required_samples + 8, 48) or unique_flow_hours < max(MIN_UNIQUE_FLOW_HOURS + 8, 32):
        warnings.append("low_sample_warning")
    copy_present = sum(1 for obs in observations if obs.copy_flow_count > 0)
    if copy_present > 0 and copy_present / max(1, len(observations)) < THIN_COPY_FLOW_MIN_COVERAGE:
        warnings.append("thin_copy_flow_warning")
    if not evaluation.train_test_direction_match or evaluation.stability < 0.45:
        warnings.append("unstable_train_test_warning")
    if active_wallet_coverage < MIN_ACTIVE_WALLET_COVERAGE:
        warnings.append("low_active_wallet_coverage")
    if non_zero_net_flow_coverage < MIN_NON_ZERO_NET_FLOW_COVERAGE:
        warnings.append("low_non_zero_net_flow_coverage")
    return warnings


def _replace_warnings(row: WalletFlowSignalResult, warnings: set[str]) -> WalletFlowSignalResult:
    return WalletFlowSignalResult(
        rank=row.rank,
        asset=row.asset,
        market_id=row.market_id,
        market_slug=row.market_slug,
        token_id=row.token_id,
        question=row.question,
        horizon_hours=row.horizon_hours,
        feature_name=row.feature_name,
        segment_type=row.segment_type,
        segment_value=row.segment_value,
        simplicity=row.simplicity,
        sample_count=row.sample_count,
        train_samples=row.train_samples,
        test_samples=row.test_samples,
        learned_direction=row.learned_direction,
        train_direction_match_rate=row.train_direction_match_rate,
        test_direction_match_rate=row.test_direction_match_rate,
        train_average_forward_return=row.train_average_forward_return,
        test_average_forward_return=row.test_average_forward_return,
        train_win_rate=row.train_win_rate,
        test_win_rate=row.test_win_rate,
        full_correlation=row.full_correlation,
        train_correlation=row.train_correlation,
        test_correlation=row.test_correlation,
        train_test_direction_match=row.train_test_direction_match,
        stability=row.stability,
        baseline_test_average_forward_return=row.baseline_test_average_forward_return,
        test_improvement_over_baseline=row.test_improvement_over_baseline,
        net_test_improvement_after_cost=row.net_test_improvement_after_cost,
        unique_flow_hours=row.unique_flow_hours,
        active_wallet_coverage=row.active_wallet_coverage,
        non_zero_net_flow_coverage=row.non_zero_net_flow_coverage,
        score=row.score,
        grade=row.grade,
        filter_reason=row.filter_reason,
        warnings=";".join(sorted(warnings)),
    )


def _parse_warnings(value: str) -> list[str]:
    if not value:
        return []
    return [item for item in value.split(";") if item]


def build_wallet_flow_rejection_diagnostics(
    *,
    raw_results: Sequence[WalletFlowSignalResult],
    final_results: Sequence[WalletFlowSignalResult],
) -> list[WalletFlowRejectionDiagnostic]:
    final_by_key = {_candidate_identity(row): row for row in final_results}
    diagnostics: list[WalletFlowRejectionDiagnostic] = []
    for row in rank_wallet_flow_results(raw_results):
        key = _candidate_identity(row)
        retained = key in final_by_key
        final_grade = final_by_key[key].grade.value if retained else WalletFlowCandidateGrade.REJECTED.value
        reasons = _diagnostic_reasons(row=row, final_grade=final_grade, retained_after_dedup=retained)
        diagnostics.append(
            WalletFlowRejectionDiagnostic(
                rank=row.rank,
                asset=row.asset,
                market_id=row.market_id,
                market_slug=row.market_slug,
                token_id=row.token_id,
                horizon_hours=row.horizon_hours,
                feature_name=row.feature_name,
                segment_type=row.segment_type,
                segment_value=row.segment_value,
                final_grade=final_grade,
                retained_after_dedup=retained,
                rejection_reasons=";".join(reasons),
                sample_count=row.sample_count,
                test_samples=row.test_samples,
                unique_flow_hours=row.unique_flow_hours,
                active_wallet_coverage=row.active_wallet_coverage,
                non_zero_net_flow_coverage=row.non_zero_net_flow_coverage,
                test_improvement_over_baseline=row.test_improvement_over_baseline,
                net_test_improvement_after_cost=row.net_test_improvement_after_cost,
                test_win_rate=row.test_win_rate,
                stability=row.stability,
            )
        )
    return diagnostics


def rank_wallet_flow_near_misses(
    diagnostics: Sequence[WalletFlowRejectionDiagnostic],
    *,
    limit: int = 10,
) -> list[WalletFlowNearMiss]:
    ranked: list[tuple[float, WalletFlowRejectionDiagnostic]] = []
    for row in diagnostics:
        if not row.retained_after_dedup:
            continue
        if row.final_grade == WalletFlowCandidateGrade.SIMULATION_READY.value:
            continue
        if row.test_improvement_over_baseline <= 0:
            continue
        gap_cost = max(0.0, SIMULATION_READY_MIN_NET_IMPROVEMENT - row.net_test_improvement_after_cost)
        gap_win = max(0.0, SIMULATION_READY_MIN_WIN_RATE - row.test_win_rate)
        gap_stability = max(0.0, SIMULATION_READY_MIN_STABILITY - row.stability)
        gap_samples = max(0.0, SIMULATION_READY_MIN_SAMPLES - row.sample_count) / SIMULATION_READY_MIN_SAMPLES
        gap_unique_hours = max(0.0, SIMULATION_READY_MIN_UNIQUE_HOURS - row.unique_flow_hours) / SIMULATION_READY_MIN_UNIQUE_HOURS
        gap_active_wallet = max(0.0, SIMULATION_READY_MIN_ACTIVE_WALLET_COVERAGE - row.active_wallet_coverage)
        gap_non_zero = max(
            0.0,
            SIMULATION_READY_MIN_NON_ZERO_NET_FLOW_COVERAGE - row.non_zero_net_flow_coverage,
        )
        distance = (
            gap_cost * 1000.0
            + gap_win
            + gap_stability
            + gap_samples
            + gap_unique_hours
            + gap_active_wallet
            + gap_non_zero
        )
        ranked.append((distance, row))

    ordered = sorted(
        ranked,
        key=lambda pair: (
            pair[0],
            -pair[1].test_improvement_over_baseline,
            -pair[1].sample_count,
            pair[1].rank,
            pair[1].market_slug or "",
            pair[1].feature_name,
            pair[1].segment_type,
            pair[1].segment_value,
        ),
    )
    near_misses: list[WalletFlowNearMiss] = []
    for idx, (_distance, row) in enumerate(ordered[:limit], start=1):
        near_misses.append(
            WalletFlowNearMiss(
                rank=idx,
                candidate_rank=row.rank,
                candidate_key=_diagnostic_candidate_key(row),
                final_grade=row.final_grade,
                reasons=row.rejection_reasons,
                gap_to_cost_buffer=max(
                    0.0,
                    SIMULATION_READY_MIN_NET_IMPROVEMENT - row.net_test_improvement_after_cost,
                ),
                gap_to_watchlist_win_rate=max(0.0, WATCHLIST_MIN_WIN_RATE - row.test_win_rate),
                gap_to_watchlist_stability=max(0.0, WATCHLIST_MIN_STABILITY - row.stability),
                improvement=row.test_improvement_over_baseline,
                net_after_cost=row.net_test_improvement_after_cost,
            )
        )
    return near_misses


def _diagnostic_reasons(
    *,
    row: WalletFlowSignalResult,
    final_grade: str,
    retained_after_dedup: bool,
) -> list[str]:
    reasons: set[str] = set()
    if not retained_after_dedup:
        reasons.add("duplicate_segment_competition")

    promoted = final_grade == WalletFlowCandidateGrade.SIMULATION_READY.value
    if not promoted:
        if row.sample_count < SIMULATION_READY_MIN_SAMPLES or row.test_samples < 12 or row.learned_direction == 0:
            reasons.add("low_sample_count")
        if row.unique_flow_hours < SIMULATION_READY_MIN_UNIQUE_HOURS:
            reasons.add("insufficient_unique_flow_hours")
        if row.active_wallet_coverage < SIMULATION_READY_MIN_ACTIVE_WALLET_COVERAGE:
            reasons.add("insufficient_active_wallet_coverage")
        if row.non_zero_net_flow_coverage < SIMULATION_READY_MIN_NON_ZERO_NET_FLOW_COVERAGE:
            reasons.add("insufficient_non_zero_net_flow_coverage")
        if (not row.train_test_direction_match) or row.stability < SIMULATION_READY_MIN_STABILITY:
            reasons.add("unstable_train_test_behavior")
        if row.net_test_improvement_after_cost < SIMULATION_READY_MIN_NET_IMPROVEMENT:
            reasons.add("improvement_below_cost_buffer")
        if row.test_improvement_over_baseline < WATCHLIST_MIN_TEST_IMPROVEMENT:
            reasons.add("weak_or_negative_test_improvement")
        if row.test_win_rate < SIMULATION_READY_MIN_WIN_RATE:
            reasons.add("weak_win_rate")
        if _copy_flow_is_thin(row):
            reasons.add("copy_flow_too_thin")

    return sorted(reasons)


def _copy_flow_is_thin(row: WalletFlowSignalResult) -> bool:
    return "thin_copy_flow_warning" in _parse_warnings(row.warnings)


def _candidate_identity(row: WalletFlowSignalResult) -> tuple[str, str, str, int, str, str, str]:
    return (
        row.asset,
        row.market_id,
        row.token_id,
        row.horizon_hours,
        row.feature_name,
        row.segment_type,
        row.segment_value,
    )


def _diagnostic_candidate_key(row: WalletFlowRejectionDiagnostic) -> str:
    return (
        f"{row.asset}:{row.market_slug or row.market_id}:{row.token_id}:"
        f"{row.horizon_hours}h:{row.feature_name}:{row.segment_type}:{row.segment_value}"
    )


def _score_result(
    *,
    test_improvement: float,
    sample_count: int,
    stability: float,
    test_win_rate: float,
    simplicity: float,
    grade: WalletFlowCandidateGrade,
) -> float:
    grade_bonus = {
        WalletFlowCandidateGrade.SIMULATION_READY: 3.0,
        WalletFlowCandidateGrade.WATCHLIST: 2.0,
        WalletFlowCandidateGrade.WEAK: 1.0,
        WalletFlowCandidateGrade.REJECTED: 0.0,
    }[grade]
    return (
        grade_bonus
        + max(0.0, test_improvement) * 200.0
        + min(sample_count / 100.0, 1.0)
        + stability
        + max(0.0, test_win_rate - 0.5) * 2.0
        + simplicity * 0.2
    )


def _feature_value(row: WalletFlowObservation, feature_name: str) -> float | None:
    value = getattr(row, feature_name, None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flow_direction(net_flow_usdc: float) -> str:
    if net_flow_usdc > 0:
        return "buy_dominant"
    if net_flow_usdc < 0:
        return "sell_dominant"
    return "neutral"


def _learn_direction(rows: Sequence[WalletFlowObservation], *, predictor) -> int:
    score = 0.0
    for row in rows:
        signal = predictor(row)
        if signal is None:
            continue
        score += _sign(float(signal)) * row.forward_return
    return _sign(score)


def _evaluate_signed(
    rows: Sequence[WalletFlowObservation],
    *,
    predictor,
    learned_direction: int,
) -> dict[str, float]:
    if not rows or learned_direction == 0:
        return {"direction_match_rate": 0.0, "avg": 0.0, "win_rate": 0.0}

    signed_values: list[float] = []
    non_zero_signals = 0
    for row in rows:
        signal = predictor(row)
        if signal is None:
            continue
        signal_sign = _sign(float(signal))
        if signal_sign == 0:
            continue
        non_zero_signals += 1
        signed_values.append(learned_direction * signal_sign * row.forward_return)

    if not signed_values:
        return {"direction_match_rate": 0.0, "avg": 0.0, "win_rate": 0.0}

    wins = sum(1 for value in signed_values if value > 0)
    direction_match_rate = wins / non_zero_signals if non_zero_signals else 0.0
    return {
        "direction_match_rate": direction_match_rate,
        "avg": sum(signed_values) / len(signed_values),
        "win_rate": wins / len(signed_values),
    }


def _correlation(rows: Sequence[WalletFlowObservation], *, predictor) -> float:
    xs: list[float] = []
    ys: list[float] = []
    for row in rows:
        signal = predictor(row)
        if signal is None:
            continue
        xs.append(float(signal))
        ys.append(row.forward_return)
    _n, corr, _t, _p = pearson_correlation_with_tstat(xs, ys)
    return corr


def _stability_score(
    *,
    train_avg: float,
    test_avg: float,
    train_corr: float,
    test_corr: float,
) -> float:
    if _sign(train_avg) == 0 or _sign(test_avg) == 0:
        return 0.0
    avg_sign_match = 1.0 if _sign(train_avg) == _sign(test_avg) else 0.0
    corr_sign_match = 1.0 if _sign(train_corr) == _sign(test_corr) and _sign(train_corr) != 0 else 0.0
    corr_magnitude = 0.0
    if _is_finite(train_corr) and _is_finite(test_corr):
        corr_magnitude = min(abs(train_corr), abs(test_corr))
    return 0.5 * avg_sign_match + 0.3 * corr_sign_match + 0.2 * min(corr_magnitude, 1.0)


def _empty_eval(n: int) -> _SplitEvaluation:
    return _SplitEvaluation(
        sample_count=n,
        train_samples=0,
        test_samples=0,
        learned_direction=0,
        train_direction_match_rate=0.0,
        test_direction_match_rate=0.0,
        train_average_forward_return=0.0,
        test_average_forward_return=0.0,
        train_win_rate=0.0,
        test_win_rate=0.0,
        full_correlation=math.nan,
        train_correlation=math.nan,
        test_correlation=math.nan,
        train_test_direction_match=False,
        stability=0.0,
        filter_reason="insufficient_samples",
    )


def _with_rank(row: WalletFlowSignalResult, rank: int) -> WalletFlowSignalResult:
    return WalletFlowSignalResult(
        rank=rank,
        asset=row.asset,
        market_id=row.market_id,
        market_slug=row.market_slug,
        token_id=row.token_id,
        question=row.question,
        horizon_hours=row.horizon_hours,
        feature_name=row.feature_name,
        segment_type=row.segment_type,
        segment_value=row.segment_value,
        simplicity=row.simplicity,
        sample_count=row.sample_count,
        train_samples=row.train_samples,
        test_samples=row.test_samples,
        learned_direction=row.learned_direction,
        train_direction_match_rate=row.train_direction_match_rate,
        test_direction_match_rate=row.test_direction_match_rate,
        train_average_forward_return=row.train_average_forward_return,
        test_average_forward_return=row.test_average_forward_return,
        train_win_rate=row.train_win_rate,
        test_win_rate=row.test_win_rate,
        full_correlation=row.full_correlation,
        train_correlation=row.train_correlation,
        test_correlation=row.test_correlation,
        train_test_direction_match=row.train_test_direction_match,
        stability=row.stability,
        baseline_test_average_forward_return=row.baseline_test_average_forward_return,
        test_improvement_over_baseline=row.test_improvement_over_baseline,
        net_test_improvement_after_cost=row.net_test_improvement_after_cost,
        unique_flow_hours=row.unique_flow_hours,
        active_wallet_coverage=row.active_wallet_coverage,
        non_zero_net_flow_coverage=row.non_zero_net_flow_coverage,
        score=row.score,
        grade=row.grade,
        filter_reason=row.filter_reason,
        warnings=row.warnings,
    )


def _write_results_csv(path: Path, rows: Sequence[WalletFlowSignalResult]) -> None:
    fieldnames = list(_json_record(rows[0]).keys()) if rows else list(_empty_record())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(_json_record(row))


def _write_rejection_diagnostics_csv(
    path: Path,
    rows: Sequence[WalletFlowRejectionDiagnostic],
) -> None:
    fieldnames = list(_rejection_json_record(rows[0]).keys()) if rows else list(_empty_rejection_record())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(_rejection_json_record(row))


def _render_rejection_summary(
    *,
    diagnostics: Sequence[WalletFlowRejectionDiagnostic],
    final_results: Sequence[WalletFlowSignalResult],
    study_details: WalletFlowStudyDetails | None,
) -> str:
    final_grade_counts = {
        grade.value: sum(1 for row in final_results if row.grade is grade)
        for grade in WalletFlowCandidateGrade
    }
    reason_counter: Counter[str] = Counter()
    for row in diagnostics:
        for reason in _parse_warnings(row.rejection_reasons):
            reason_counter[reason] += 1
    top_reasons = reason_counter.most_common(3)
    dropped_duplicate = sum(1 for row in diagnostics if not row.retained_after_dedup)
    near_misses = rank_wallet_flow_near_misses(diagnostics, limit=5)
    lines = [
        "# Wallet Flow Rejection Diagnostics",
        "",
        "**EXPLORATORY ONLY - NOT TRADEABLE.**",
        "",
        "Diagnostics explain why wallet-flow segments were not promoted to SIMULATION_READY.",
        "",
        "## Counts",
        "",
        f"- total_candidates_evaluated={len(diagnostics)}",
        f"- final_simulation_ready={final_grade_counts[WalletFlowCandidateGrade.SIMULATION_READY.value]}",
        f"- final_watchlist={final_grade_counts[WalletFlowCandidateGrade.WATCHLIST.value]}",
        f"- final_weak={final_grade_counts[WalletFlowCandidateGrade.WEAK.value]}",
        f"- final_rejected={final_grade_counts[WalletFlowCandidateGrade.REJECTED.value]}",
        f"- dropped_by_duplicate_competition={dropped_duplicate}",
    ]

    if study_details is not None:
        lines.extend(
            [
                f"- segment_rows_before_dedup={study_details.segment_rows_before_dedup}",
                f"- segment_rows_after_dedup={study_details.segment_rows_after_dedup}",
            ]
        )

    lines.extend(["", "## Rejection Reason Counts", ""])
    if not reason_counter:
        lines.append("- none")
    else:
        for reason, count in sorted(reason_counter.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {reason}: {count}")

    lines.extend(["", "## Top Blockers", ""])
    if not top_reasons:
        lines.append("- none")
    else:
        for reason, count in top_reasons:
            lines.append(f"- {reason}: {count}")

    lines.extend(["", "## Top Near-Miss Candidates", ""])
    if not near_misses:
        lines.append("- none")
    else:
        lines.append("| Rank | Candidate Rank | Final Grade | Candidate | Improvement | Net After Cost | Reasons |")
        lines.append("| ---: | ---: | --- | --- | ---: | ---: | --- |")
        for item in near_misses:
            lines.append(
                f"| {item.rank} | {item.candidate_rank} | {item.final_grade} | "
                f"{_escape_md(item.candidate_key)} | {item.improvement:+.5f} | "
                f"{item.net_after_cost:+.5f} | {_escape_md(item.reasons)} |"
            )

    lines.extend(["", "## Recommended Next Data Action", ""])
    lines.extend(_recommended_data_action_lines(reason_counter))
    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- Exploratory research only.",
            "- Not tradeable.",
            "- No live trading or execution.",
        ]
    )
    return "\n".join(lines) + "\n"


def _recommended_data_action_lines(reason_counter: Counter[str]) -> list[str]:
    if not reason_counter:
        return ["- Continue regular collection and re-run diagnostics."]
    top_reason, _count = reason_counter.most_common(1)[0]
    if top_reason in {"insufficient_unique_flow_hours", "low_sample_count"}:
        return [
            "- Priority: continue hourly wallet-flow backfill until unique-hour continuity and sample depth rise further.",
            "- Focus the next run on markets with the largest missing-hour gaps and sparse hourly coverage.",
        ]
    if top_reason in {"insufficient_active_wallet_coverage", "insufficient_non_zero_net_flow_coverage"}:
        return [
            "- Priority: collect more active flow windows (hours with real wallet participation and non-zero net flow).",
            "- Focus ingestion on markets/assets showing active trade bursts instead of quiet intervals.",
        ]
    if top_reason in {"improvement_below_cost_buffer", "weak_or_negative_test_improvement"}:
        return [
            "- Priority: widen historical coverage before changing thresholds; current edge does not clear the cost buffer.",
            "- Keep filters unchanged and collect more diverse market regimes to retest improvement stability.",
        ]
    if top_reason == "copy_flow_too_thin":
        return [
            "- Priority: increase copy-flow event coverage for the same market-hour windows.",
            "- Keep copy-flow gating unchanged; gather more real copy-flow observations before retesting.",
        ]
    return [
        "- Priority: continue scheduled collection and rerun wallet-flow diagnostics after additional hourly coverage.",
        "- Keep current promotion thresholds unchanged; use diagnostics counts as the blocker map.",
    ]


def _render_summary(
    rows: Sequence[WalletFlowSignalResult],
    candidates: Sequence[WalletFlowSignalResult],
    *,
    study_details: WalletFlowStudyDetails | None,
) -> str:
    counts = {
        grade.value: sum(1 for row in rows if row.grade is grade)
        for grade in WalletFlowCandidateGrade
    }
    reason_counts: dict[str, int] = defaultdict(int)
    warning_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        reason_counts[row.filter_reason] += 1
        for warning in _parse_warnings(row.warnings):
            warning_counts[warning] += 1

    lines = [
        "# Wallet Flow Signal Research Summary",
        "",
        "**EXPLORATORY ONLY - NOT TRADEABLE.**",
        "",
        "This report tests whether Polymarket wallet/trader flow predicts forward crypto returns "
        "better than probability movement alone. SIMULATION_READY means paper simulation only.",
        "",
        "## Coverage",
        "",
        f"- Segment rows tested: {len(rows)}",
        f"- SIMULATION_READY: {counts[WalletFlowCandidateGrade.SIMULATION_READY.value]}",
        f"- WATCHLIST: {counts[WalletFlowCandidateGrade.WATCHLIST.value]}",
        f"- WEAK: {counts[WalletFlowCandidateGrade.WEAK.value]}",
        f"- REJECTED: {counts[WalletFlowCandidateGrade.REJECTED.value]}",
    ]

    if study_details is not None:
        lines.extend(
            [
                f"- Segment rows before de-dup: {study_details.segment_rows_before_dedup}",
                f"- Segment rows after de-dup: {study_details.segment_rows_after_dedup}",
                f"- wallet_flow rows: {study_details.coverage.wallet_flow_rows}",
                f"- market_flow_hourly rows: {study_details.coverage.market_flow_hourly_rows}",
                f"- whale_flow_hourly rows: {study_details.coverage.whale_flow_hourly_rows}",
                f"- copy_flow rows: {study_details.coverage.copy_flow_rows}",
            ]
        )

    lines.extend(["", "## Rejection/Downgrade Reasons", ""])
    if not reason_counts:
        lines.append("No rejection reasons were recorded.")
    else:
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {reason}: {count}")

    lines.extend(["", "## Overfit Warnings", ""])
    if not warning_counts:
        lines.append("No overfit warnings were triggered.")
    else:
        for warning, count in sorted(warning_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {warning}: {count}")

    lines.extend(["", "## Top Wallet-Flow Candidates", ""])

    if not candidates:
        lines.extend(
            [
                "No wallet-flow candidate survived beyond REJECTED.",
                "",
                "Practical read: wallet-flow does not yet show robust uplift over baseline.",
            ]
        )
    else:
        lines.append(
            "| Rank | Grade | Asset | Feature | Segment | Horizon | Test Avg | Baseline Test Avg | Improvement | Net After Cost | Win Rate |"
        )
        lines.append("| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for row in candidates[:10]:
            lines.append(
                f"| {row.rank} | {row.grade.value} | {row.asset} | {row.feature_name} | "
                f"{_escape_md(row.segment_type + ':' + row.segment_value)} | {row.horizon_hours}h | "
                f"{row.test_average_forward_return:+.5f} | {row.baseline_test_average_forward_return:+.5f} | "
                f"{row.test_improvement_over_baseline:+.5f} | {row.net_test_improvement_after_cost:+.5f} | {row.test_win_rate:.2f} |"
            )

    thin_data = False
    if study_details is not None:
        thin_data = (
            study_details.coverage.market_flow_hourly_rows < 2000
            or study_details.coverage.wallet_flow_rows < 3000
            or study_details.coverage.copy_flow_rows < 200
        )
    if thin_data:
        lines.extend(
            [
                "",
                "## Recommended Backfill Plan",
                "",
                "Data coverage is still thin for stable wallet-flow inference. Recommended next run (manual, not automatic):",
                "- `joint-research ingest polymarket-wallet-flow --limit-markets 150 --limit-events 5000`",
                "- `joint-research ingest polymarket-wallet-flow --asset BTC --limit-markets 100 --limit-events 5000`",
                "- `joint-research ingest polymarket-wallet-flow --asset ETH --limit-markets 100 --limit-events 5000`",
            ]
        )

    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- No live trading, no API keys, no execution path.",
            "- Wallet-flow rows align to the same hour or nearest prior flow hour.",
            "- SIMULATION_READY is not tradeable; it only means paper simulation is warranted.",
        ]
    )
    return "\n".join(lines) + "\n"


def _json_record(row: WalletFlowSignalResult) -> dict[str, object]:
    record = asdict(row)
    record["grade"] = row.grade.value
    return record


def _rejection_json_record(row: WalletFlowRejectionDiagnostic) -> dict[str, object]:
    return asdict(row)


def _empty_record() -> dict[str, object]:
    return {
        "rank": "",
        "asset": "",
        "market_id": "",
        "market_slug": "",
        "token_id": "",
        "question": "",
        "horizon_hours": "",
        "feature_name": "",
        "segment_type": "",
        "segment_value": "",
        "simplicity": "",
        "sample_count": "",
        "train_samples": "",
        "test_samples": "",
        "learned_direction": "",
        "train_direction_match_rate": "",
        "test_direction_match_rate": "",
        "train_average_forward_return": "",
        "test_average_forward_return": "",
        "train_win_rate": "",
        "test_win_rate": "",
        "full_correlation": "",
        "train_correlation": "",
        "test_correlation": "",
        "train_test_direction_match": "",
        "stability": "",
        "baseline_test_average_forward_return": "",
        "test_improvement_over_baseline": "",
        "net_test_improvement_after_cost": "",
        "unique_flow_hours": "",
        "active_wallet_coverage": "",
        "non_zero_net_flow_coverage": "",
        "score": "",
        "grade": "",
        "filter_reason": "",
        "warnings": "",
    }


def _empty_rejection_record() -> dict[str, object]:
    return {
        "rank": "",
        "asset": "",
        "market_id": "",
        "market_slug": "",
        "token_id": "",
        "horizon_hours": "",
        "feature_name": "",
        "segment_type": "",
        "segment_value": "",
        "final_grade": "",
        "retained_after_dedup": "",
        "rejection_reasons": "",
        "sample_count": "",
        "test_samples": "",
        "unique_flow_hours": "",
        "active_wallet_coverage": "",
        "non_zero_net_flow_coverage": "",
        "test_improvement_over_baseline": "",
        "net_test_improvement_after_cost": "",
        "test_win_rate": "",
        "stability": "",
    }


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _is_finite(value: float) -> bool:
    return not math.isnan(value) and not math.isinf(value)


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")


def _safe_count(con: duckdb.DuckDBPyConnection, query: str) -> int:
    try:
        value = con.execute(query).fetchone()
    except duckdb.Error:
        return 0
    if not value:
        return 0
    return _optional_int(value[0]) or 0
