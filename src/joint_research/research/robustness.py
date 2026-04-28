"""Robustness checks for exploratory Polymarket -> crypto lead-lag candidates."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import duckdb

from joint_research.research.lead_lag import pearson_correlation_with_tstat
from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.views import register_views

FORWARD_RETURN_COLUMNS: dict[int, str] = {
    1: "crypto_log_return_next_1h",
    4: "crypto_log_return_next_4h",
    24: "crypto_log_return_next_24h",
}


class CandidateGrade(str, Enum):
    REJECTED = "REJECTED"
    WEAK = "WEAK"
    WATCHLIST = "WATCHLIST"
    PROMISING = "PROMISING"


@dataclass(frozen=True)
class RobustnessObservation:
    open_time_ns: int
    poly_price: float
    poly_price_change: float
    crypto_return: float


@dataclass(frozen=True)
class QualityDecision:
    passed: bool
    reason: str
    n_observations: int
    n_nonzero_changes: int
    flat_fraction: float


@dataclass(frozen=True)
class PermutationBaseline:
    real_correlation: float
    empirical_pvalue: float
    shuffled_mean_abs_correlation: float
    n_permutations: int


@dataclass(frozen=True)
class RobustnessResult:
    rank: int
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    lag_hours: int
    n_observations: int
    n_nonzero_changes: int
    train_correlation: float
    test_correlation: float
    full_correlation: float
    empirical_pvalue: float
    rolling_stability: float
    robustness_score: float
    grade: CandidateGrade
    filter_reason: str
    days_to_resolution_at_end: float | None
    volume_bucket: str
    liquidity_bucket: str


@dataclass(frozen=True)
class RobustnessReportPaths:
    summary_md: Path
    results_csv: Path
    candidates_json: Path


@dataclass(frozen=True)
class _MarketMeta:
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    end_date_iso: str | None
    volume_bucket: str
    liquidity_bucket: str


def split_train_test(
    observations: Sequence[RobustnessObservation],
    *,
    train_fraction: float = 0.6,
) -> tuple[list[RobustnessObservation], list[RobustnessObservation]]:
    if not 0.0 < train_fraction < 1.0:
        raise ValueError(f"invalid_train_fraction:{train_fraction}")
    ordered = sorted(observations, key=lambda obs: obs.open_time_ns)
    split_idx = int(len(ordered) * train_fraction)
    split_idx = max(1, min(split_idx, len(ordered) - 1))
    return ordered[:split_idx], ordered[split_idx:]


def permutation_baseline(
    observations: Sequence[RobustnessObservation],
    *,
    n_permutations: int = 200,
    seed: int = 0,
) -> PermutationBaseline:
    xs = [obs.poly_price_change for obs in observations]
    ys = [obs.crypto_return for obs in observations]
    _n, real_corr, _t, _p = pearson_correlation_with_tstat(xs, ys)
    if math.isnan(real_corr):
        return PermutationBaseline(
            real_correlation=math.nan,
            empirical_pvalue=1.0,
            shuffled_mean_abs_correlation=math.nan,
            n_permutations=n_permutations,
        )

    rng = random.Random(seed)
    exceedances = 0
    shuffled_abs: list[float] = []
    for _ in range(n_permutations):
        shuffled_xs = list(xs)
        rng.shuffle(shuffled_xs)
        _n_s, shuffled_corr, _t_s, _p_s = pearson_correlation_with_tstat(
            shuffled_xs, ys
        )
        if math.isnan(shuffled_corr):
            continue
        abs_shuffled = abs(shuffled_corr)
        shuffled_abs.append(abs_shuffled)
        if abs_shuffled >= abs(real_corr):
            exceedances += 1

    empirical_p = (exceedances + 1) / (len(shuffled_abs) + 1) if shuffled_abs else 1.0
    mean_abs = sum(shuffled_abs) / len(shuffled_abs) if shuffled_abs else math.nan
    return PermutationBaseline(
        real_correlation=real_corr,
        empirical_pvalue=empirical_p,
        shuffled_mean_abs_correlation=mean_abs,
        n_permutations=n_permutations,
    )


def apply_quality_filter(
    observations: Sequence[RobustnessObservation],
    *,
    min_observations: int = 60,
    min_nonzero_changes: int = 20,
    max_flat_fraction: float = 0.90,
    days_to_resolution_at_end: float | None = None,
    min_days_to_resolution: float = 3.0,
) -> QualityDecision:
    n_obs = len(observations)
    n_nonzero = sum(1 for obs in observations if abs(obs.poly_price_change) > 1e-12)
    flat_fraction = 1.0 - (n_nonzero / n_obs) if n_obs else 1.0
    if n_obs < min_observations:
        return QualityDecision(False, "insufficient_samples", n_obs, n_nonzero, flat_fraction)
    if flat_fraction > max_flat_fraction:
        return QualityDecision(False, "flat_probability", n_obs, n_nonzero, flat_fraction)
    if n_nonzero < min_nonzero_changes:
        return QualityDecision(
            False,
            "insufficient_nonzero_changes",
            n_obs,
            n_nonzero,
            flat_fraction,
        )
    if (
        days_to_resolution_at_end is not None
        and days_to_resolution_at_end < min_days_to_resolution
    ):
        return QualityDecision(False, "too_close_to_resolution", n_obs, n_nonzero, flat_fraction)
    return QualityDecision(True, "passed", n_obs, n_nonzero, flat_fraction)


def grade_candidate(
    *,
    train_correlation: float,
    test_correlation: float,
    empirical_pvalue: float,
    rolling_stability: float,
    n_observations: int,
) -> CandidateGrade:
    if n_observations < 60 or not _is_finite(train_correlation) or not _is_finite(test_correlation):
        return CandidateGrade.REJECTED
    if _sign(train_correlation) == 0 or _sign(test_correlation) == 0:
        return CandidateGrade.REJECTED
    if _sign(train_correlation) != _sign(test_correlation):
        return CandidateGrade.WEAK
    if (
        empirical_pvalue <= 0.05
        and rolling_stability >= 0.75
        and abs(test_correlation) >= 0.05
        and n_observations >= 120
    ):
        return CandidateGrade.PROMISING
    if (
        empirical_pvalue <= 0.10
        and rolling_stability >= 0.60
        and abs(test_correlation) >= 0.03
        and n_observations >= 90
    ):
        return CandidateGrade.WATCHLIST
    if empirical_pvalue <= 0.25 or rolling_stability >= 0.50:
        return CandidateGrade.WEAK
    return CandidateGrade.REJECTED


def run_robustness_study(
    *,
    paths: WarehousePaths,
    min_observations: int = 60,
    min_nonzero_changes: int = 20,
    max_flat_fraction: float = 0.90,
    min_days_to_resolution: float = 3.0,
    train_fraction: float = 0.6,
    n_permutations: int = 200,
    seed: int = 17,
) -> list[RobustnessResult]:
    con = duckdb.connect()
    register_views(con, paths)
    results: list[RobustnessResult] = []

    meta_rows = con.execute(
        """
        SELECT DISTINCT
          asset,
          market_id,
          market_slug,
          token_id,
          question,
          end_date_iso,
          volume_1mo_usd,
          volume_total_usd,
          liquidity_usd
        FROM crypto_polymarket_aligned
        ORDER BY asset, market_id, token_id
        """
    ).fetchall()

    for row in meta_rows:
        meta = _MarketMeta(
            asset=row[0],
            market_id=row[1],
            market_slug=row[2],
            token_id=row[3],
            question=row[4],
            end_date_iso=row[5],
            volume_bucket=_dollar_bucket_label(_first_present(row[6], row[7])),
            liquidity_bucket=_dollar_bucket_label(row[8]),
        )
        for lag_hours, return_col in FORWARD_RETURN_COLUMNS.items():
            observations = _load_observations(con, meta, return_col)
            days_to_resolution = _days_to_resolution_at_end(
                observations, meta.end_date_iso
            )
            quality = apply_quality_filter(
                observations,
                min_observations=min_observations,
                min_nonzero_changes=min_nonzero_changes,
                max_flat_fraction=max_flat_fraction,
                days_to_resolution_at_end=days_to_resolution,
                min_days_to_resolution=min_days_to_resolution,
            )
            if not quality.passed:
                results.append(
                    _filtered_result(
                        meta=meta,
                        lag_hours=lag_hours,
                        quality=quality,
                        days_to_resolution=days_to_resolution,
                    )
                )
                continue

            train, test = split_train_test(observations, train_fraction=train_fraction)
            train_corr = _correlation(train)
            test_corr = _correlation(test)
            full_corr = _correlation(observations)
            permutation = permutation_baseline(
                observations,
                n_permutations=n_permutations,
                seed=_stable_seed(seed, meta.asset, meta.market_id, meta.token_id, str(lag_hours)),
            )
            stability = rolling_direction_stability(observations, target_correlation=full_corr)
            grade = grade_candidate(
                train_correlation=train_corr,
                test_correlation=test_corr,
                empirical_pvalue=permutation.empirical_pvalue,
                rolling_stability=stability,
                n_observations=len(observations),
            )
            results.append(
                RobustnessResult(
                    rank=0,
                    asset=meta.asset,
                    market_id=meta.market_id,
                    market_slug=meta.market_slug,
                    token_id=meta.token_id,
                    question=meta.question,
                    lag_hours=lag_hours,
                    n_observations=len(observations),
                    n_nonzero_changes=quality.n_nonzero_changes,
                    train_correlation=train_corr,
                    test_correlation=test_corr,
                    full_correlation=full_corr,
                    empirical_pvalue=permutation.empirical_pvalue,
                    rolling_stability=stability,
                    robustness_score=_robustness_score(
                        train_corr,
                        test_corr,
                        permutation.empirical_pvalue,
                        stability,
                        len(observations),
                    ),
                    grade=grade,
                    filter_reason=quality.reason,
                    days_to_resolution_at_end=days_to_resolution,
                    volume_bucket=meta.volume_bucket,
                    liquidity_bucket=meta.liquidity_bucket,
                )
            )
    return _rank_results(results)


def rolling_direction_stability(
    observations: Sequence[RobustnessObservation],
    *,
    target_correlation: float,
    n_windows: int = 4,
    min_window_observations: int = 10,
) -> float:
    target_sign = _sign(target_correlation)
    if target_sign == 0:
        return 0.0
    ordered = sorted(observations, key=lambda obs: obs.open_time_ns)
    windows = _contiguous_windows(ordered, n_windows=n_windows)
    valid = 0
    matches = 0
    for window in windows:
        if len(window) < min_window_observations:
            continue
        corr = _correlation(window)
        corr_sign = _sign(corr)
        if corr_sign == 0:
            continue
        valid += 1
        if corr_sign == target_sign:
            matches += 1
    return matches / valid if valid else 0.0


def write_robustness_report(
    *,
    output_dir: Path,
    results: Sequence[RobustnessResult],
    candidate_limit: int = 20,
) -> RobustnessReportPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_md = output_dir / "robustness_summary.md"
    results_csv = output_dir / "robustness_results.csv"
    candidates_json = output_dir / "robustness_candidates.json"

    ordered = _rank_results(results)
    candidates = [
        r
        for r in ordered
        if r.grade in {CandidateGrade.PROMISING, CandidateGrade.WATCHLIST, CandidateGrade.WEAK}
    ][:candidate_limit]
    _write_results_csv(results_csv, ordered)
    candidates_json.write_text(
        json.dumps([_json_record(r) for r in candidates], indent=2, sort_keys=True) + "\n"
    )
    summary_md.write_text(_render_summary(ordered, candidates))
    return RobustnessReportPaths(
        summary_md=summary_md,
        results_csv=results_csv,
        candidates_json=candidates_json,
    )


def _load_observations(
    con: duckdb.DuckDBPyConnection,
    meta: _MarketMeta,
    return_col: str,
) -> list[RobustnessObservation]:
    rows = con.execute(
        f"""
        SELECT open_time_ns, poly_yes_price, poly_price_change, {return_col}
        FROM crypto_polymarket_aligned
        WHERE token_id = ?
          AND market_id = ?
          AND poly_price_change IS NOT NULL
          AND {return_col} IS NOT NULL
        ORDER BY open_time_ns
        """,
        [meta.token_id, meta.market_id],
    ).fetchall()
    return [
        RobustnessObservation(
            open_time_ns=int(r[0]),
            poly_price=float(r[1]),
            poly_price_change=float(r[2]),
            crypto_return=float(r[3]),
        )
        for r in rows
    ]


def _filtered_result(
    *,
    meta: _MarketMeta,
    lag_hours: int,
    quality: QualityDecision,
    days_to_resolution: float | None,
) -> RobustnessResult:
    return RobustnessResult(
        rank=0,
        asset=meta.asset,
        market_id=meta.market_id,
        market_slug=meta.market_slug,
        token_id=meta.token_id,
        question=meta.question,
        lag_hours=lag_hours,
        n_observations=quality.n_observations,
        n_nonzero_changes=quality.n_nonzero_changes,
        train_correlation=math.nan,
        test_correlation=math.nan,
        full_correlation=math.nan,
        empirical_pvalue=1.0,
        rolling_stability=0.0,
        robustness_score=0.0,
        grade=CandidateGrade.REJECTED,
        filter_reason=quality.reason,
        days_to_resolution_at_end=days_to_resolution,
        volume_bucket=meta.volume_bucket,
        liquidity_bucket=meta.liquidity_bucket,
    )


def _rank_results(results: Sequence[RobustnessResult]) -> list[RobustnessResult]:
    grade_rank = {
        CandidateGrade.PROMISING: 0,
        CandidateGrade.WATCHLIST: 1,
        CandidateGrade.WEAK: 2,
        CandidateGrade.REJECTED: 3,
    }
    ordered = sorted(
        results,
        key=lambda r: (
            grade_rank[r.grade],
            -r.robustness_score,
            r.empirical_pvalue,
            -r.rolling_stability,
            -r.n_observations,
            r.asset,
            r.market_slug or "",
            r.market_id,
            r.token_id,
            r.lag_hours,
        ),
    )
    return [
        RobustnessResult(
            rank=idx,
            asset=r.asset,
            market_id=r.market_id,
            market_slug=r.market_slug,
            token_id=r.token_id,
            question=r.question,
            lag_hours=r.lag_hours,
            n_observations=r.n_observations,
            n_nonzero_changes=r.n_nonzero_changes,
            train_correlation=r.train_correlation,
            test_correlation=r.test_correlation,
            full_correlation=r.full_correlation,
            empirical_pvalue=r.empirical_pvalue,
            rolling_stability=r.rolling_stability,
            robustness_score=r.robustness_score,
            grade=r.grade,
            filter_reason=r.filter_reason,
            days_to_resolution_at_end=r.days_to_resolution_at_end,
            volume_bucket=r.volume_bucket,
            liquidity_bucket=r.liquidity_bucket,
        )
        for idx, r in enumerate(ordered, start=1)
    ]


def _robustness_score(
    train_correlation: float,
    test_correlation: float,
    empirical_pvalue: float,
    rolling_stability: float,
    n_observations: int,
) -> float:
    direction_bonus = 2.0 if _sign(train_correlation) == _sign(test_correlation) != 0 else 0.0
    p_component = max(0.0, 1.0 - min(empirical_pvalue, 1.0)) * 2.0
    test_component = min(abs(test_correlation) * 5.0, 1.0) if _is_finite(test_correlation) else 0.0
    sample_component = min(n_observations / 500.0, 1.0)
    return direction_bonus + p_component + rolling_stability + test_component + sample_component


def _correlation(observations: Sequence[RobustnessObservation]) -> float:
    _n, corr, _t, _p = pearson_correlation_with_tstat(
        [obs.poly_price_change for obs in observations],
        [obs.crypto_return for obs in observations],
    )
    return corr


def _contiguous_windows(
    observations: Sequence[RobustnessObservation],
    *,
    n_windows: int,
) -> list[list[RobustnessObservation]]:
    if not observations:
        return []
    out: list[list[RobustnessObservation]] = []
    n_obs = len(observations)
    for i in range(n_windows):
        start = (i * n_obs) // n_windows
        end = ((i + 1) * n_obs) // n_windows
        out.append(list(observations[start:end]))
    return out


def _days_to_resolution_at_end(
    observations: Sequence[RobustnessObservation],
    end_date_iso: str | None,
) -> float | None:
    if not observations or not end_date_iso:
        return None
    try:
        end_dt = datetime.fromisoformat(end_date_iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    last_ns = max(obs.open_time_ns for obs in observations)
    last_dt = datetime.fromtimestamp(last_ns / 1_000_000_000, tz=timezone.utc)
    return (end_dt - last_dt).total_seconds() / 86400.0


def _write_results_csv(path: Path, results: Sequence[RobustnessResult]) -> None:
    fieldnames = list(_json_record(results[0]).keys()) if results else list(_empty_record().keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for result in results:
            writer.writerow(_json_record(result))


def _render_summary(
    results: Sequence[RobustnessResult],
    candidates: Sequence[RobustnessResult],
) -> str:
    counts = {grade.value: sum(1 for r in results if r.grade is grade) for grade in CandidateGrade}
    lines = [
        "# Robustness Research Summary",
        "",
        "**EXPLORATORY ONLY - NOT TRADEABLE.**",
        "",
        "This report checks whether Polymarket probability-change candidates survive "
        "temporal validation, deterministic permutation baselines, rolling-window "
        "stability checks, and minimum quality filters.",
        "",
        "## Coverage",
        "",
        f"- Hypothesis rows tested: {len(results)}",
        f"- PROMISING: {counts[CandidateGrade.PROMISING.value]}",
        f"- WATCHLIST: {counts[CandidateGrade.WATCHLIST.value]}",
        f"- WEAK: {counts[CandidateGrade.WEAK.value]}",
        f"- REJECTED: {counts[CandidateGrade.REJECTED.value]}",
        "",
        "## Top Robustness Candidates",
        "",
    ]
    if not candidates:
        lines.extend(
            [
                "No candidate survived the robustness filters beyond REJECTED.",
                "",
                "Practical read: collect more history before simulating any signal.",
            ]
        )
        return "\n".join(lines) + "\n"
    lines.append("| Rank | Grade | Asset | Lag | OOS Match | Emp p | Stability | Market |")
    lines.append("| ---: | --- | --- | ---: | --- | ---: | ---: | --- |")
    for result in candidates[:10]:
        oos_match = _sign(result.train_correlation) == _sign(result.test_correlation) != 0
        market = result.market_slug or result.question or result.market_id
        lines.append(
            f"| {result.rank} | {result.grade.value} | {result.asset} | "
            f"{result.lag_hours}h | {str(oos_match)} | "
            f"{result.empirical_pvalue:.4f} | {result.rolling_stability:.2f} | "
            f"{_escape_md(str(market))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- PROMISING means simulation-worthy, not tradeable.",
            "- These checks still do not model fees, slippage, fill uncertainty, position sizing, "
            "or market-impact constraints.",
            "- A robust paper signal must still survive walk-forward simulation before any "
            "execution discussion.",
        ]
    )
    return "\n".join(lines) + "\n"


def _json_record(result: RobustnessResult) -> dict[str, object]:
    record = asdict(result)
    record["grade"] = result.grade.value
    return {k: _json_value(v) for k, v in record.items()}


def _empty_record() -> dict[str, object]:
    return {
        "rank": "",
        "asset": "",
        "market_id": "",
        "market_slug": "",
        "token_id": "",
        "question": "",
        "lag_hours": "",
        "n_observations": "",
        "n_nonzero_changes": "",
        "train_correlation": "",
        "test_correlation": "",
        "full_correlation": "",
        "empirical_pvalue": "",
        "rolling_stability": "",
        "robustness_score": "",
        "grade": "",
        "filter_reason": "",
        "days_to_resolution_at_end": "",
        "volume_bucket": "",
        "liquidity_bucket": "",
    }


def _json_value(value: object) -> object:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    return value


def _stable_seed(seed: int, *parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return seed + int(digest[:12], 16)


def _first_present(*values: float | None) -> float | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, float) and math.isnan(value):
            continue
        return float(value)
    return None


def _dollar_bucket_label(value: float | None) -> str:
    if value is None or math.isnan(value):
        return "unknown"
    if value < 10_000:
        return "<10k"
    if value < 100_000:
        return "10k-100k"
    if value < 1_000_000:
        return "100k-1m"
    return ">=1m"


def _sign(value: float) -> int:
    if not _is_finite(value) or abs(value) < 1e-12:
        return 0
    return 1 if value > 0 else -1


def _is_finite(value: float | None) -> bool:
    return value is not None and not math.isnan(value) and not math.isinf(value)


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")
