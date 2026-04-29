"""Derivatives-regime-aware Polymarket -> crypto signal study."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

import duckdb

from joint_research.research.lead_lag import pearson_correlation_with_tstat
from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.views import register_views

HORIZONS: tuple[int, ...] = (1, 4, 24)
FORWARD_RETURN_BY_HORIZON: dict[int, str] = {
    1: "crypto_log_return_next_1h",
    4: "crypto_log_return_next_4h",
    24: "crypto_log_return_next_24h",
}


class RegimeCandidateGrade(str, Enum):
    REJECTED = "REJECTED"
    WEAK = "WEAK"
    WATCHLIST = "WATCHLIST"
    SIMULATION_READY = "SIMULATION_READY"


@dataclass(frozen=True)
class RegimeObservation:
    asset: str
    symbol: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    open_time_ns: int
    regime_time_ns: int | None
    horizon_hours: int
    poly_price_change: float
    forward_return: float
    funding_rate: float | None
    basis_pct: float | None
    funding_direction: str
    funding_intensity: str
    basis_side: str
    combined_regime: str


@dataclass(frozen=True)
class RegimeSegmentResult:
    rank: int
    asset: str
    symbol: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    horizon_hours: int
    segment_type: str
    segment_value: str
    combined_regime: str | None
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
    score: float
    grade: RegimeCandidateGrade
    filter_reason: str


@dataclass(frozen=True)
class DerivativesRegimeReportPaths:
    summary_md: Path
    results_csv: Path
    candidates_json: Path


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
    symbol: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    horizon_hours: int
    segment_type: str
    segment_value: str
    combined_regime: str | None
    simplicity: float
    baseline_test_average_forward_return: float


def run_derivatives_regime_study(
    *,
    paths: WarehousePaths,
    min_segment_samples: int = 24,
    min_combined_samples: int = 36,
    train_fraction: float = 0.6,
) -> list[RegimeSegmentResult]:
    con = duckdb.connect()
    register_views(con, paths)
    observations = load_regime_observations(con)
    return analyze_regime_segments(
        observations,
        min_segment_samples=min_segment_samples,
        min_combined_samples=min_combined_samples,
        train_fraction=train_fraction,
    )


def load_regime_observations(con: duckdb.DuckDBPyConnection) -> list[RegimeObservation]:
    rows = con.execute(
        """
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
          d.event_time_ns,
          d.funding_rate,
          d.basis_pct
        FROM crypto_polymarket_aligned a
        LEFT JOIN LATERAL (
          SELECT
            event_time_ns,
            funding_rate,
            basis_pct
          FROM crypto_derivatives_regime d
          WHERE d.symbol = upper(a.asset || 'USDT')
            AND d.event_time_ns <= a.open_time_ns
          ORDER BY d.event_time_ns DESC
          LIMIT 1
        ) d ON TRUE
        WHERE a.asset IS NOT NULL
          AND a.token_id IS NOT NULL
          AND a.market_id IS NOT NULL
          AND a.poly_price_change IS NOT NULL
        ORDER BY a.asset, a.market_id, a.token_id, a.open_time_ns
        """
    ).fetchall()
    observations: list[RegimeObservation] = []
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
        regime_time_ns = _optional_int(row[10])
        funding_rate = _optional_float(row[11])
        basis_pct = _optional_float(row[12])

        direction = funding_direction_from_rate(funding_rate)
        intensity = funding_intensity_bucket(funding_rate)
        basis_side = basis_side_from_pct(basis_pct)
        combined = combined_regime_label(direction, intensity, basis_side)
        symbol = asset_to_symbol(asset)

        for horizon, forward_return in ((1, next_1h), (4, next_4h), (24, next_24h)):
            if forward_return is None:
                continue
            observations.append(
                RegimeObservation(
                    asset=asset,
                    symbol=symbol,
                    market_id=market_id,
                    market_slug=market_slug,
                    token_id=token_id,
                    question=question,
                    open_time_ns=open_time_ns,
                    regime_time_ns=regime_time_ns,
                    horizon_hours=horizon,
                    poly_price_change=poly_price_change,
                    forward_return=forward_return,
                    funding_rate=funding_rate,
                    basis_pct=basis_pct,
                    funding_direction=direction,
                    funding_intensity=intensity,
                    basis_side=basis_side,
                    combined_regime=combined,
                )
            )
    return observations


def analyze_regime_segments(
    observations: Sequence[RegimeObservation],
    *,
    min_segment_samples: int = 24,
    min_combined_samples: int = 36,
    train_fraction: float = 0.6,
) -> list[RegimeSegmentResult]:
    by_market_horizon: dict[tuple[str, str, str, int], list[RegimeObservation]] = defaultdict(list)
    for obs in observations:
        key = (obs.asset, obs.market_id, obs.token_id, obs.horizon_hours)
        by_market_horizon[key].append(obs)

    out: list[RegimeSegmentResult] = []
    for key, group in by_market_horizon.items():
        del key
        if not group:
            continue
        baseline_eval = evaluate_segment(group, train_fraction=train_fraction)
        baseline_test_avg = baseline_eval.test_average_forward_return

        segments: dict[tuple[str, str], list[RegimeObservation]] = defaultdict(list)
        for obs in group:
            if obs.funding_direction in {"positive", "negative"}:
                segments[("funding_direction", obs.funding_direction)].append(obs)
            if obs.funding_intensity in {"high", "normal", "low"}:
                segments[("funding_intensity", obs.funding_intensity)].append(obs)
            if obs.basis_side in {"premium", "discount"}:
                segments[("basis_side", obs.basis_side)].append(obs)
            if obs.combined_regime != "unknown":
                segments[("combined_regime", obs.combined_regime)].append(obs)

        first = group[0]
        for (segment_type, segment_value), segment_obs in segments.items():
            required_samples = (
                min_combined_samples if segment_type == "combined_regime" else min_segment_samples
            )
            context = _SegmentContext(
                asset=first.asset,
                symbol=first.symbol,
                market_id=first.market_id,
                market_slug=first.market_slug,
                token_id=first.token_id,
                question=first.question,
                horizon_hours=first.horizon_hours,
                segment_type=segment_type,
                segment_value=segment_value,
                combined_regime=segment_value if segment_type == "combined_regime" else None,
                simplicity=_segment_simplicity(segment_type),
                baseline_test_average_forward_return=baseline_test_avg,
            )
            out.append(
                _build_segment_result(
                    context=context,
                    observations=segment_obs,
                    required_samples=required_samples,
                    train_fraction=train_fraction,
                )
            )

    return rank_regime_results(out)


def evaluate_segment(
    observations: Sequence[RegimeObservation],
    *,
    train_fraction: float,
) -> _SplitEvaluation:
    ordered = sorted(observations, key=lambda row: row.open_time_ns)
    n = len(ordered)
    if n < 2:
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
    split_idx = int(n * train_fraction)
    split_idx = max(1, min(split_idx, n - 1))
    train = ordered[:split_idx]
    test = ordered[split_idx:]

    learned_direction = _learn_direction(train)
    train_metrics = _evaluate_signed(train, learned_direction=learned_direction)
    test_metrics = _evaluate_signed(test, learned_direction=learned_direction)
    full_corr = _correlation(ordered)
    train_corr = _correlation(train)
    test_corr = _correlation(test)
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
    filter_reason = "passed"
    if learned_direction == 0:
        filter_reason = "no_train_edge"
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


def rank_regime_results(results: Sequence[RegimeSegmentResult]) -> list[RegimeSegmentResult]:
    grade_rank = {
        RegimeCandidateGrade.SIMULATION_READY: 0,
        RegimeCandidateGrade.WATCHLIST: 1,
        RegimeCandidateGrade.WEAK: 2,
        RegimeCandidateGrade.REJECTED: 3,
    }
    ordered = sorted(
        results,
        key=lambda row: (
            grade_rank[row.grade],
            -row.test_improvement_over_baseline,
            -int(row.train_test_direction_match),
            -row.sample_count,
            -row.stability,
            -row.test_win_rate,
            -row.simplicity,
            row.asset,
            row.market_slug or "",
            row.market_id,
            row.token_id,
            row.horizon_hours,
            row.segment_type,
            row.segment_value,
        ),
    )
    return [_with_rank(row, idx + 1) for idx, row in enumerate(ordered)]


def write_derivatives_regime_report(
    *,
    output_dir: Path,
    results: Sequence[RegimeSegmentResult],
    candidate_limit: int = 20,
) -> DerivativesRegimeReportPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    ordered = rank_regime_results(results)
    candidates = [row for row in ordered if row.grade is not RegimeCandidateGrade.REJECTED][
        :candidate_limit
    ]

    summary_md = output_dir / "derivatives_regime_summary.md"
    results_csv = output_dir / "derivatives_regime_results.csv"
    candidates_json = output_dir / "derivatives_regime_candidates.json"

    _write_results_csv(results_csv, ordered)
    candidates_json.write_text(
        json.dumps([_json_record(row) for row in candidates], indent=2, sort_keys=True) + "\n"
    )
    summary_md.write_text(_render_summary(ordered, candidates))
    return DerivativesRegimeReportPaths(
        summary_md=summary_md,
        results_csv=results_csv,
        candidates_json=candidates_json,
    )


def asset_to_symbol(asset: str) -> str:
    return f"{asset.upper()}USDT"


def funding_direction_from_rate(rate: float | None) -> str:
    if rate is None:
        return "unknown"
    if rate > 0:
        return "positive"
    if rate < 0:
        return "negative"
    return "neutral"


def funding_intensity_bucket(rate: float | None) -> str:
    if rate is None:
        return "unknown"
    absolute = abs(rate)
    if absolute >= 0.0001:
        return "high"
    if absolute >= 0.00003:
        return "normal"
    return "low"


def basis_side_from_pct(basis_pct: float | None) -> str:
    if basis_pct is None:
        return "unknown"
    if basis_pct > 0:
        return "premium"
    if basis_pct < 0:
        return "discount"
    return "flat"


def combined_regime_label(direction: str, intensity: str, basis_side: str) -> str:
    if direction not in {"positive", "negative"}:
        return "unknown"
    if intensity not in {"high", "normal", "low"}:
        return "unknown"
    if basis_side not in {"premium", "discount"}:
        return "unknown"
    return f"{direction}|{intensity}|{basis_side}"


def _build_segment_result(
    *,
    context: _SegmentContext,
    observations: Sequence[RegimeObservation],
    required_samples: int,
    train_fraction: float,
) -> RegimeSegmentResult:
    evaluation = evaluate_segment(observations, train_fraction=train_fraction)
    improvement = (
        evaluation.test_average_forward_return - context.baseline_test_average_forward_return
    )
    grade = grade_regime_candidate(
        sample_count=evaluation.sample_count,
        required_samples=required_samples,
        train_test_direction_match=evaluation.train_test_direction_match,
        test_improvement=improvement,
        test_win_rate=evaluation.test_win_rate,
        stability=evaluation.stability,
        test_samples=evaluation.test_samples,
        learned_direction=evaluation.learned_direction,
    )
    filter_reason = evaluation.filter_reason
    if evaluation.sample_count < required_samples:
        filter_reason = "insufficient_samples"
    elif not evaluation.train_test_direction_match:
        filter_reason = "train_test_direction_mismatch"
    elif improvement <= 0:
        filter_reason = "no_improvement_over_baseline"
    score = _score_result(
        test_improvement=improvement,
        direction_match=evaluation.train_test_direction_match,
        sample_count=evaluation.sample_count,
        stability=evaluation.stability,
        test_win_rate=evaluation.test_win_rate,
        simplicity=context.simplicity,
        grade=grade,
    )
    return RegimeSegmentResult(
        rank=0,
        asset=context.asset,
        symbol=context.symbol,
        market_id=context.market_id,
        market_slug=context.market_slug,
        token_id=context.token_id,
        question=context.question,
        horizon_hours=context.horizon_hours,
        segment_type=context.segment_type,
        segment_value=context.segment_value,
        combined_regime=context.combined_regime,
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
        score=score,
        grade=grade,
        filter_reason=filter_reason,
    )


def grade_regime_candidate(
    *,
    sample_count: int,
    required_samples: int,
    train_test_direction_match: bool,
    test_improvement: float,
    test_win_rate: float,
    stability: float,
    test_samples: int,
    learned_direction: int,
) -> RegimeCandidateGrade:
    if sample_count < required_samples or learned_direction == 0 or test_samples < 10:
        return RegimeCandidateGrade.REJECTED
    if not train_test_direction_match:
        return RegimeCandidateGrade.WEAK
    if test_improvement <= 0:
        return RegimeCandidateGrade.REJECTED
    if (
        test_improvement >= 0.0006
        and test_win_rate >= 0.57
        and stability >= 0.60
        and sample_count >= max(required_samples, 48)
    ):
        return RegimeCandidateGrade.SIMULATION_READY
    if (
        test_improvement >= 0.00025
        and test_win_rate >= 0.54
        and stability >= 0.50
        and sample_count >= max(required_samples, 32)
    ):
        return RegimeCandidateGrade.WATCHLIST
    if test_improvement > 0 and test_win_rate >= 0.50:
        return RegimeCandidateGrade.WEAK
    return RegimeCandidateGrade.REJECTED


def _score_result(
    *,
    test_improvement: float,
    direction_match: bool,
    sample_count: int,
    stability: float,
    test_win_rate: float,
    simplicity: float,
    grade: RegimeCandidateGrade,
) -> float:
    grade_bonus = {
        RegimeCandidateGrade.SIMULATION_READY: 3.0,
        RegimeCandidateGrade.WATCHLIST: 2.0,
        RegimeCandidateGrade.WEAK: 1.0,
        RegimeCandidateGrade.REJECTED: 0.0,
    }[grade]
    return (
        grade_bonus
        + max(0.0, test_improvement) * 200.0
        + (0.5 if direction_match else 0.0)
        + min(sample_count / 100.0, 1.0)
        + stability
        + max(0.0, test_win_rate - 0.5) * 2.0
        + simplicity * 0.2
    )


def _write_results_csv(path: Path, rows: Sequence[RegimeSegmentResult]) -> None:
    fieldnames = list(_json_record(rows[0]).keys()) if rows else list(_empty_record())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(_json_record(row))


def _render_summary(
    rows: Sequence[RegimeSegmentResult],
    candidates: Sequence[RegimeSegmentResult],
) -> str:
    counts = {
        grade.value: sum(1 for row in rows if row.grade is grade)
        for grade in RegimeCandidateGrade
    }
    lines = [
        "# Derivatives Regime Research Summary",
        "",
        "**EXPLORATORY ONLY - NOT TRADEABLE.**",
        "",
        "This report tests whether Polymarket -> crypto signal behavior improves when "
        "conditioned on funding/perp-basis regimes. SIMULATION_READY means paper simulation only.",
        "",
        "## Coverage",
        "",
        f"- Segment rows tested: {len(rows)}",
        f"- SIMULATION_READY: {counts[RegimeCandidateGrade.SIMULATION_READY.value]}",
        f"- WATCHLIST: {counts[RegimeCandidateGrade.WATCHLIST.value]}",
        f"- WEAK: {counts[RegimeCandidateGrade.WEAK.value]}",
        f"- REJECTED: {counts[RegimeCandidateGrade.REJECTED.value]}",
        "",
        "## Top Regime Candidates",
        "",
    ]
    if not candidates:
        lines.extend(
            [
                "No regime-conditioned candidate survived beyond REJECTED.",
                "",
                "Practical read: current derivatives regimes did not produce a robust, actionable uplift.",
            ]
        )
        return "\n".join(lines) + "\n"

    lines.append(
        "| Rank | Grade | Asset | Segment | Horizon | Test Avg | Baseline Test Avg | Improvement | Win Rate |"
    )
    lines.append("| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for row in candidates[:10]:
        lines.append(
            f"| {row.rank} | {row.grade.value} | {row.asset} | "
            f"{_escape_md(row.segment_type + ':' + row.segment_value)} | "
            f"{row.horizon_hours}h | {row.test_average_forward_return:+.5f} | "
            f"{row.baseline_test_average_forward_return:+.5f} | "
            f"{row.test_improvement_over_baseline:+.5f} | {row.test_win_rate:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- No live trading, no API keys, no execution path.",
            "- Regime alignment uses nearest prior derivatives regime hour per asset symbol.",
            "- SIMULATION_READY is not tradeable; it only means paper simulation is warranted.",
        ]
    )
    return "\n".join(lines) + "\n"


def _json_record(row: RegimeSegmentResult) -> dict[str, object]:
    record = asdict(row)
    record["grade"] = row.grade.value
    return record


def _empty_record() -> dict[str, object]:
    return {
        "rank": "",
        "asset": "",
        "symbol": "",
        "market_id": "",
        "market_slug": "",
        "token_id": "",
        "question": "",
        "horizon_hours": "",
        "segment_type": "",
        "segment_value": "",
        "combined_regime": "",
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
        "score": "",
        "grade": "",
        "filter_reason": "",
    }


def _segment_simplicity(segment_type: str) -> float:
    if segment_type == "combined_regime":
        return 0.6
    return 1.0


def _learn_direction(rows: Sequence[RegimeObservation]) -> int:
    score = 0.0
    for row in rows:
        score += _sign(row.poly_price_change) * row.forward_return
    return _sign(score)


def _evaluate_signed(
    rows: Sequence[RegimeObservation],
    *,
    learned_direction: int,
) -> dict[str, float]:
    if not rows or learned_direction == 0:
        return {"direction_match_rate": 0.0, "avg": 0.0, "win_rate": 0.0}
    signed_values = [
        learned_direction * _sign(row.poly_price_change) * row.forward_return for row in rows
    ]
    if not signed_values:
        return {"direction_match_rate": 0.0, "avg": 0.0, "win_rate": 0.0}
    matches = sum(1 for value in signed_values if value > 0)
    non_zero_direction = sum(1 for row in rows if _sign(row.poly_price_change) != 0)
    direction_match_rate = matches / non_zero_direction if non_zero_direction else 0.0
    return {
        "direction_match_rate": direction_match_rate,
        "avg": sum(signed_values) / len(signed_values),
        "win_rate": matches / len(signed_values),
    }


def _correlation(rows: Sequence[RegimeObservation]) -> float:
    xs = [row.poly_price_change for row in rows]
    ys = [row.forward_return for row in rows]
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


def _with_rank(row: RegimeSegmentResult, rank: int) -> RegimeSegmentResult:
    return RegimeSegmentResult(
        rank=rank,
        asset=row.asset,
        symbol=row.symbol,
        market_id=row.market_id,
        market_slug=row.market_slug,
        token_id=row.token_id,
        question=row.question,
        horizon_hours=row.horizon_hours,
        segment_type=row.segment_type,
        segment_value=row.segment_value,
        combined_regime=row.combined_regime,
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
        score=row.score,
        grade=row.grade,
        filter_reason=row.filter_reason,
    )


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _is_finite(value: float) -> bool:
    return not math.isnan(value) and not math.isinf(value)


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


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")
