"""Composite deterministic signal scanner for paper research."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

import duckdb

from joint_research.research.features import (
    FeatureInput,
    FeatureRow,
    build_feature_rows,
    is_flat_market,
    split_feature_train_test,
)
from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.views import register_views


class CompositeCandidateGrade(str, Enum):
    REJECTED = "REJECTED"
    WEAK = "WEAK"
    WATCHLIST = "WATCHLIST"
    SIMULATION_READY = "SIMULATION_READY"


@dataclass(frozen=True)
class CompositeSignalResult:
    rank: int
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    rule_family: str
    horizon_hours: int
    learned_direction: int
    train_accuracy: float
    test_accuracy: float
    train_average_forward_return: float
    test_average_forward_return: float
    stability: float
    train_samples: int
    test_samples: int
    simplicity: float
    score: float
    grade: CompositeCandidateGrade
    filter_reason: str


@dataclass(frozen=True)
class CompositeSignalReportPaths:
    summary_md: Path
    results_csv: Path
    candidates_json: Path


@dataclass(frozen=True)
class _RuleFamily:
    name: str
    signal: Callable[[FeatureRow], float]
    simplicity: float


RULE_FAMILIES: tuple[_RuleFamily, ...] = (
    _RuleFamily("probability_momentum_continuation", lambda row: row.probability_momentum, 1.0),
    _RuleFamily("probability_reversal", lambda row: row.probability_reversal, 1.0),
    _RuleFamily(
        "polymarket_leads_crypto_momentum",
        lambda row: row.lagged_probability_predictor,
        0.9,
    ),
    _RuleFamily("divergence_mean_reversion", lambda row: -row.probability_crypto_divergence, 0.8),
    _RuleFamily(
        "high_confidence_probability_move",
        lambda row: row.prob_change_1h if row.large_probability_move else 0.0,
        0.7,
    ),
)


def scan_feature_group(
    rows: Sequence[FeatureRow],
    *,
    train_fraction: float = 0.6,
    min_train_samples: int = 30,
    min_test_samples: int = 20,
    max_flat_fraction: float = 0.90,
) -> list[CompositeSignalResult]:
    if not rows:
        return []
    ordered = sorted(rows, key=lambda row: row.open_time_ns)
    first = ordered[0]
    if is_flat_market(ordered, max_flat_fraction=max_flat_fraction):
        return [
            _rejected_result(
                first,
                rule_family=rule.name,
                horizon_hours=horizon,
                reason="flat_market",
            )
            for rule in RULE_FAMILIES
            for horizon in (1, 4, 24)
        ]
    train, test = split_feature_train_test(ordered, train_fraction=train_fraction)
    out: list[CompositeSignalResult] = []
    for rule in RULE_FAMILIES:
        for horizon in (1, 4, 24):
            train_pairs = _rule_pairs(train, rule, horizon)
            test_pairs = _rule_pairs(test, rule, horizon)
            if len(train_pairs) < min_train_samples or len(test_pairs) < min_test_samples:
                out.append(
                    _rejected_result(
                        first,
                        rule_family=rule.name,
                        horizon_hours=horizon,
                        reason="insufficient_samples",
                    )
                )
                continue
            direction = _learn_direction(train_pairs)
            if direction == 0:
                out.append(
                    _rejected_result(
                        first,
                        rule_family=rule.name,
                        horizon_hours=horizon,
                        reason="no_train_edge",
                    )
                )
                continue
            train_stats = _evaluate_pairs(train_pairs, learned_direction=direction)
            test_stats = _evaluate_pairs(test_pairs, learned_direction=direction)
            stability = 1.0 if train_stats["avg"] * test_stats["avg"] > 0 else 0.0
            grade = _grade(
                train_accuracy=train_stats["accuracy"],
                test_accuracy=test_stats["accuracy"],
                train_average=train_stats["avg"],
                test_average=test_stats["avg"],
                stability=stability,
                test_samples=len(test_pairs),
            )
            score = _score(
                test_accuracy=test_stats["accuracy"],
                test_average=test_stats["avg"],
                stability=stability,
                test_samples=len(test_pairs),
                simplicity=rule.simplicity,
                grade=grade,
            )
            out.append(
                CompositeSignalResult(
                    rank=0,
                    asset=first.asset,
                    market_id=first.market_id,
                    market_slug=first.market_slug,
                    token_id=first.token_id,
                    question=first.question,
                    rule_family=rule.name,
                    horizon_hours=horizon,
                    learned_direction=direction,
                    train_accuracy=train_stats["accuracy"],
                    test_accuracy=test_stats["accuracy"],
                    train_average_forward_return=train_stats["avg"],
                    test_average_forward_return=test_stats["avg"],
                    stability=stability,
                    train_samples=len(train_pairs),
                    test_samples=len(test_pairs),
                    simplicity=rule.simplicity,
                    score=score,
                    grade=grade,
                    filter_reason="passed",
                )
            )
    return rank_composite_results(out)


def run_composite_signal_study(
    *,
    paths: WarehousePaths,
    min_train_samples: int = 30,
    min_test_samples: int = 20,
) -> list[CompositeSignalResult]:
    con = duckdb.connect()
    register_views(con, paths)
    meta_rows = con.execute(
        """
        SELECT DISTINCT asset, market_id, token_id
        FROM crypto_polymarket_aligned
        ORDER BY asset, market_id, token_id
        """
    ).fetchall()
    all_results: list[CompositeSignalResult] = []
    for asset, market_id, token_id in meta_rows:
        inputs = _load_feature_inputs(con, asset=asset, market_id=market_id, token_id=token_id)
        rows = build_feature_rows(inputs)
        all_results.extend(
            scan_feature_group(
                rows,
                min_train_samples=min_train_samples,
                min_test_samples=min_test_samples,
            )
        )
    return rank_composite_results(all_results)


def rank_composite_results(
    results: Sequence[CompositeSignalResult],
) -> list[CompositeSignalResult]:
    grade_rank = {
        CompositeCandidateGrade.SIMULATION_READY: 0,
        CompositeCandidateGrade.WATCHLIST: 1,
        CompositeCandidateGrade.WEAK: 2,
        CompositeCandidateGrade.REJECTED: 3,
    }
    ordered = sorted(
        results,
        key=lambda row: (
            grade_rank[row.grade],
            -row.score,
            -row.test_accuracy,
            -row.test_average_forward_return,
            -row.test_samples,
            row.asset,
            row.market_slug or "",
            row.market_id,
            row.token_id,
            row.rule_family,
            row.horizon_hours,
        ),
    )
    return [_with_rank(row, rank) for rank, row in enumerate(ordered, start=1)]


def write_composite_signal_report(
    *,
    output_dir: Path,
    results: Sequence[CompositeSignalResult],
    candidate_limit: int = 20,
) -> CompositeSignalReportPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_md = output_dir / "composite_signal_summary.md"
    results_csv = output_dir / "composite_signal_results.csv"
    candidates_json = output_dir / "composite_signal_candidates.json"
    ordered = rank_composite_results(results)
    candidates = [
        row for row in ordered if row.grade is not CompositeCandidateGrade.REJECTED
    ][:candidate_limit]
    _write_results_csv(results_csv, ordered)
    candidates_json.write_text(
        json.dumps([_json_record(row) for row in candidates], indent=2, sort_keys=True)
        + "\n"
    )
    summary_md.write_text(_render_summary(ordered, candidates))
    return CompositeSignalReportPaths(
        summary_md=summary_md,
        results_csv=results_csv,
        candidates_json=candidates_json,
    )


def _load_feature_inputs(
    con: duckdb.DuckDBPyConnection,
    *,
    asset: str,
    market_id: str,
    token_id: str,
) -> list[FeatureInput]:
    rows = con.execute(
        """
        SELECT
          a.open_time_ns,
          a.asset,
          a.market_id,
          a.market_slug,
          a.token_id,
          a.question,
          a.end_date_iso,
          a.poly_yes_price,
          a.crypto_close,
          r.volume_quote,
          a.crypto_log_return_next_1h,
          a.crypto_log_return_next_4h,
          a.crypto_log_return_next_24h
        FROM crypto_polymarket_aligned a
        LEFT JOIN crypto_returns r
          ON r.symbol = a.asset || 'USDT'
         AND r.interval = '1h'
         AND r.open_time_ns = a.open_time_ns
        WHERE a.asset = ?
          AND a.market_id = ?
          AND a.token_id = ?
          AND a.poly_yes_price IS NOT NULL
          AND a.crypto_close IS NOT NULL
        ORDER BY a.open_time_ns
        """,
        [asset, market_id, token_id],
    ).fetchall()
    return [
        FeatureInput(
            open_time_ns=int(row[0]),
            asset=row[1],
            market_id=row[2],
            market_slug=row[3],
            token_id=row[4],
            question=row[5],
            end_date_iso=row[6],
            poly_yes_price=float(row[7]),
            crypto_close=float(row[8]),
            crypto_volume_quote=float(row[9]) if row[9] is not None else None,
            forward_return_1h=float(row[10]) if row[10] is not None else None,
            forward_return_4h=float(row[11]) if row[11] is not None else None,
            forward_return_24h=float(row[12]) if row[12] is not None else None,
        )
        for row in rows
    ]


def _rule_pairs(
    rows: Sequence[FeatureRow],
    rule: _RuleFamily,
    horizon: int,
) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for row in rows:
        target = _target(row, horizon)
        if target is None or math.isnan(target):
            continue
        signal = rule.signal(row)
        if signal == 0.0 or math.isnan(signal):
            continue
        pairs.append((signal, target))
    return pairs


def _target(row: FeatureRow, horizon: int) -> float | None:
    if horizon == 1:
        return row.forward_return_1h
    if horizon == 4:
        return row.forward_return_4h
    if horizon == 24:
        return row.forward_return_24h
    raise ValueError(f"unsupported_horizon:{horizon}")


def _learn_direction(pairs: Sequence[tuple[float, float]]) -> int:
    score = sum(_sign(signal) * target for signal, target in pairs)
    return _sign(score)


def _evaluate_pairs(
    pairs: Sequence[tuple[float, float]],
    *,
    learned_direction: int,
) -> dict[str, float]:
    signed_returns = [learned_direction * _sign(signal) * target for signal, target in pairs]
    if not signed_returns:
        return {"accuracy": 0.0, "avg": 0.0}
    wins = sum(1 for value in signed_returns if value > 0)
    return {
        "accuracy": wins / len(signed_returns),
        "avg": sum(signed_returns) / len(signed_returns),
    }


def _grade(
    *,
    train_accuracy: float,
    test_accuracy: float,
    train_average: float,
    test_average: float,
    stability: float,
    test_samples: int,
) -> CompositeCandidateGrade:
    if test_samples < 20 or test_average <= 0 or stability <= 0:
        return CompositeCandidateGrade.REJECTED
    if train_average <= 0:
        return CompositeCandidateGrade.WEAK
    if test_accuracy >= 0.58 and test_samples >= 50 and test_average > 0.001:
        return CompositeCandidateGrade.SIMULATION_READY
    if test_accuracy >= 0.54 and test_samples >= 30:
        return CompositeCandidateGrade.WATCHLIST
    if test_accuracy >= 0.50:
        return CompositeCandidateGrade.WEAK
    return CompositeCandidateGrade.REJECTED


def _score(
    *,
    test_accuracy: float,
    test_average: float,
    stability: float,
    test_samples: int,
    simplicity: float,
    grade: CompositeCandidateGrade,
) -> float:
    grade_bonus = {
        CompositeCandidateGrade.SIMULATION_READY: 3.0,
        CompositeCandidateGrade.WATCHLIST: 2.0,
        CompositeCandidateGrade.WEAK: 1.0,
        CompositeCandidateGrade.REJECTED: 0.0,
    }[grade]
    sample_component = min(test_samples / 100.0, 1.0)
    return (
        grade_bonus
        + max(0.0, test_accuracy - 0.5) * 4.0
        + max(0.0, test_average) * 100.0
        + stability
        + sample_component
        + simplicity * 0.25
    )


def _rejected_result(
    row: FeatureRow,
    *,
    rule_family: str,
    horizon_hours: int,
    reason: str,
) -> CompositeSignalResult:
    return CompositeSignalResult(
        rank=0,
        asset=row.asset,
        market_id=row.market_id,
        market_slug=row.market_slug,
        token_id=row.token_id,
        question=row.question,
        rule_family=rule_family,
        horizon_hours=horizon_hours,
        learned_direction=0,
        train_accuracy=0.0,
        test_accuracy=0.0,
        train_average_forward_return=0.0,
        test_average_forward_return=0.0,
        stability=0.0,
        train_samples=0,
        test_samples=0,
        simplicity=0.0,
        score=0.0,
        grade=CompositeCandidateGrade.REJECTED,
        filter_reason=reason,
    )


def _with_rank(row: CompositeSignalResult, rank: int) -> CompositeSignalResult:
    return CompositeSignalResult(
        rank=rank,
        asset=row.asset,
        market_id=row.market_id,
        market_slug=row.market_slug,
        token_id=row.token_id,
        question=row.question,
        rule_family=row.rule_family,
        horizon_hours=row.horizon_hours,
        learned_direction=row.learned_direction,
        train_accuracy=row.train_accuracy,
        test_accuracy=row.test_accuracy,
        train_average_forward_return=row.train_average_forward_return,
        test_average_forward_return=row.test_average_forward_return,
        stability=row.stability,
        train_samples=row.train_samples,
        test_samples=row.test_samples,
        simplicity=row.simplicity,
        score=row.score,
        grade=row.grade,
        filter_reason=row.filter_reason,
    )


def _write_results_csv(path: Path, rows: Sequence[CompositeSignalResult]) -> None:
    fieldnames = list(_json_record(rows[0]).keys()) if rows else list(_empty_record())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(_json_record(row))


def _render_summary(
    rows: Sequence[CompositeSignalResult],
    candidates: Sequence[CompositeSignalResult],
) -> str:
    counts = {
        grade.value: sum(1 for row in rows if row.grade is grade)
        for grade in CompositeCandidateGrade
    }
    lines = [
        "# Composite Signal Research Summary",
        "",
        "**EXPLORATORY ONLY - NOT TRADEABLE.**",
        "",
        "This report scans deterministic, train-learned composite rule families. "
        "SIMULATION_READY means send to paper simulation only.",
        "",
        "## Coverage",
        "",
        f"- Rule rows tested: {len(rows)}",
        f"- SIMULATION_READY: {counts[CompositeCandidateGrade.SIMULATION_READY.value]}",
        f"- WATCHLIST: {counts[CompositeCandidateGrade.WATCHLIST.value]}",
        f"- WEAK: {counts[CompositeCandidateGrade.WEAK.value]}",
        f"- REJECTED: {counts[CompositeCandidateGrade.REJECTED.value]}",
        "",
        "## Top Composite Candidates",
        "",
    ]
    if not candidates:
        lines.extend(
            [
                "No composite candidates survived beyond REJECTED.",
                "",
                "Practical read: do not promote any composite rule to simulation yet.",
            ]
        )
        return "\n".join(lines) + "\n"
    lines.append("| Rank | Grade | Asset | Rule | Horizon | Test Acc | Test Avg | Market |")
    lines.append("| ---: | --- | --- | --- | ---: | ---: | ---: | --- |")
    for row in candidates[:10]:
        market = row.market_slug or row.question or row.market_id
        lines.append(
            f"| {row.rank} | {row.grade.value} | {row.asset} | {row.rule_family} | "
            f"{row.horizon_hours}h | {row.test_accuracy:.2f} | "
            f"{row.test_average_forward_return:.5f} | {_escape_md(str(market))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- No live trading, no API keys, no execution path.",
            "- Rule directions are learned on train only and validated on test.",
            "- SIMULATION_READY is not tradeable; it only means paper simulation is warranted.",
        ]
    )
    return "\n".join(lines) + "\n"


def _json_record(row: CompositeSignalResult) -> dict[str, object]:
    record = asdict(row)
    record["grade"] = row.grade.value
    return record


def _empty_record() -> dict[str, object]:
    return {
        "rank": "",
        "asset": "",
        "market_id": "",
        "market_slug": "",
        "token_id": "",
        "question": "",
        "rule_family": "",
        "horizon_hours": "",
        "learned_direction": "",
        "train_accuracy": "",
        "test_accuracy": "",
        "train_average_forward_return": "",
        "test_average_forward_return": "",
        "stability": "",
        "train_samples": "",
        "test_samples": "",
        "simplicity": "",
        "score": "",
        "grade": "",
        "filter_reason": "",
    }


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")
