"""Lead-lag study: do Polymarket probability shifts predict crypto returns?

The hourly study reads ``crypto_polymarket_aligned`` after DuckDB view
registration, scans every aligned crypto YES token, and computes Pearson
correlations between ``poly_price_change`` and same-hour/+1h/+4h/+24h crypto
log returns.

Outputs are intentionally paper-only:
- ``LeadLagTokenResult`` rows, one per market/token/horizon.
- ``LeadLagBucketResult`` rows segmented by asset, time-to-resolution,
  volume, liquidity, and horizon.
- Markdown/CSV/JSON artifacts labeled exploratory and not tradeable.
"""

from __future__ import annotations

import csv
import json
import math
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from joint_research.warehouse.paths import WarehousePaths
from joint_research.warehouse.views import register_views

# Lag horizons we test (in the unit of the chosen frequency).
LAG_HORIZONS_HOURLY: tuple[int, ...] = (0, 1, 4, 24)
LAG_HORIZONS_DAILY: tuple[int, ...] = (0, 1, 3, 7, 14)


@dataclass(frozen=True)
class _FrequencyConfig:
    label: str
    aligned_view: str
    lag_horizons: tuple[int, ...]
    lag_unit: str  # "h" or "d"
    return_columns: dict[int, str]  # lag -> column name in view


_HOURLY_CFG = _FrequencyConfig(
    label="hourly",
    aligned_view="crypto_polymarket_aligned",
    lag_horizons=LAG_HORIZONS_HOURLY,
    lag_unit="h",
    return_columns={
        0: "crypto_log_return",
        1: "crypto_log_return_next_1h",
        4: "crypto_log_return_next_4h",
        24: "crypto_log_return_next_24h",
    },
)
_DAILY_CFG = _FrequencyConfig(
    label="daily",
    aligned_view="polymarket_token_returns_aligned_daily",
    lag_horizons=LAG_HORIZONS_DAILY,
    lag_unit="d",
    return_columns={
        0: "crypto_log_return",
        1: "crypto_log_return_next_1d",
        3: "crypto_log_return_next_3d",
        7: "crypto_log_return_next_7d",
        14: "crypto_log_return_next_14d",
    },
)
_FREQUENCIES: dict[str, _FrequencyConfig] = {"hourly": _HOURLY_CFG, "daily": _DAILY_CFG}

DAYS_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("<7d", 0.0, 7.0),
    ("7-30d", 7.0, 30.0),
    ("30-90d", 30.0, 90.0),
    (">90d", 90.0, math.inf),
)
UNKNOWN_BUCKET = "unknown"


@dataclass(frozen=True)
class LeadLagTokenResult:
    asset: str
    token_id: str
    market_id: str
    market_slug: str | None
    question: str | None
    days_bucket: str
    volume_bucket: str
    liquidity_bucket: str
    lag_hours: int
    direction: str  # "poly_leads_crypto" | "crypto_leads_poly" | "contemporaneous"
    n: int
    correlation: float
    tstat: float
    pvalue_two_sided: float
    volume_1mo_usd: float | None
    volume_total_usd: float | None
    liquidity_usd: float | None


@dataclass(frozen=True)
class LeadLagBucketResult:
    asset: str
    days_bucket: str
    volume_bucket: str
    liquidity_bucket: str
    lag_hours: int
    direction: str
    n_tokens: int
    n_observations: int
    pooled_correlation: float
    pooled_tstat: float
    pooled_pvalue: float
    bh_significant_at_0_05: bool


@dataclass(frozen=True)
class LeadLagCandidate:
    rank: int
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    lag_hours: int
    n: int
    correlation: float
    tstat: float
    pvalue_two_sided: float
    candidate_score: float
    days_bucket: str
    volume_bucket: str
    liquidity_bucket: str
    volume_1mo_usd: float | None
    volume_total_usd: float | None
    liquidity_usd: float | None
    exploratory_label: str = "EXPLORATORY ONLY - NOT TRADEABLE"


@dataclass(frozen=True)
class LeadLagReportPaths:
    summary_md: Path
    results_csv: Path
    candidates_json: Path


# ---------------------------------------------------------------------------
# Statistical primitives
# ---------------------------------------------------------------------------


def pearson_correlation_with_tstat(
    xs: Sequence[float],
    ys: Sequence[float],
) -> tuple[int, float, float, float]:
    """Return (n, correlation, tstat, two_sided_pvalue).

    Uses pure-Python statistics so the package stays pyarrow+duckdb only.
    Pairs containing NaN/None are filtered. If n<3 or variance is zero on
    either side, returns (n, nan, nan, 1.0).
    """

    paired: list[tuple[float, float]] = []
    for x, y in zip(xs, ys, strict=False):
        if x is None or y is None:
            continue
        if isinstance(x, float) and math.isnan(x):
            continue
        if isinstance(y, float) and math.isnan(y):
            continue
        paired.append((float(x), float(y)))
    n = len(paired)
    if n < 3:
        return n, math.nan, math.nan, 1.0
    xs_, ys_ = zip(*paired)
    if statistics.pstdev(xs_) == 0 or statistics.pstdev(ys_) == 0:
        return n, math.nan, math.nan, 1.0
    r = statistics.correlation(xs_, ys_)
    if abs(r) >= 1.0:
        return n, r, math.inf if r > 0 else -math.inf, 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    p = _t_two_sided_pvalue(abs(t), df=n - 2)
    return n, r, t, p


def _t_two_sided_pvalue(t_abs: float, df: int) -> float:
    """Two-sided p-value for Student's t.

    Uses the relation ``P(|T| > t) = I_x(df/2, 1/2)`` where ``x = df/(df+t^2)``
    and ``I_x`` is the regularized incomplete beta function.
    """

    if df <= 0 or math.isinf(t_abs):
        return 0.0
    if t_abs == 0.0:
        return 1.0
    x = df / (df + t_abs * t_abs)
    p = _regularized_incomplete_beta(x, df / 2.0, 0.5)
    if p < 0.0:
        return 0.0
    if p > 1.0:
        return 1.0
    return p


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta I_x(a, b).

    Implementation follows Numerical Recipes 3rd ed.: the symmetry
    ``I_x(a,b) = 1 - I_{1-x}(b,a)`` lets us always evaluate on the side
    where the continued fraction converges fastest.
    """

    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_bt = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    bt = math.exp(log_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _betacf(a: float, b: float, x: float, *, max_iter: int = 500, eps: float = 1e-12) -> float:
    """Continued-fraction expansion for the incomplete beta (Lentz's method)."""

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    fpmin = 1e-300
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        # Even step: a_{2m+1} = m*(b-m)*x / ((qam+m2)*(a+m2))
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        # Odd step: a_{2m+2} = -(a+m)*(qab+m)*x / ((a+m2)*(qap+m2))
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def benjamini_hochberg_significant(
    pvalues: Sequence[float],
    *,
    alpha: float = 0.05,
) -> list[bool]:
    """Return a same-length list marking which pvalues survive BH at ``alpha``."""

    m = len(pvalues)
    if m == 0:
        return []
    indexed = sorted(enumerate(pvalues), key=lambda kv: kv[1])
    survivors: set[int] = set()
    threshold_rank = -1
    for rank, (orig_idx, p) in enumerate(indexed, start=1):
        if p <= (rank / m) * alpha:
            threshold_rank = rank
    if threshold_rank > 0:
        for rank, (orig_idx, _p) in enumerate(indexed, start=1):
            if rank <= threshold_rank:
                survivors.add(orig_idx)
    return [i in survivors for i in range(m)]


# ---------------------------------------------------------------------------
# Study runner
# ---------------------------------------------------------------------------


def run_lead_lag_study(
    *,
    paths: WarehousePaths,
    min_observations_per_token: int = 30,
    as_of: datetime | None = None,
    frequency: str = "hourly",
) -> tuple[list[LeadLagTokenResult], list[LeadLagBucketResult]]:
    """Run the full lead-lag study against the warehouse and return results.

    ``frequency`` selects the aligned view and the lag horizons. ``hourly``
    tests {0, +1h, +4h, +24h}; ``daily`` tests {0, +1d, +3d, +7d, +14d}.
    """

    cfg = _FREQUENCIES.get(frequency)
    if cfg is None:
        raise ValueError(f"unsupported_frequency:{frequency}")

    as_of = as_of or datetime.now(tz=timezone.utc)
    con = duckdb.connect()
    register_views(con, paths)

    tokens_meta = con.execute(
        f"""
        SELECT DISTINCT
          asset,
          token_id,
          market_id,
          market_slug,
          question,
          end_date_iso,
          volume_1mo_usd,
          volume_total_usd,
          liquidity_usd
        FROM {cfg.aligned_view}
        ORDER BY asset, token_id
        """
    ).fetchall()

    return_select = ", ".join(
        cfg.return_columns[lag] for lag in cfg.lag_horizons
    )

    token_results: list[LeadLagTokenResult] = []
    for (
        asset,
        token_id,
        market_id,
        market_slug,
        question,
        end_iso,
        volume_1mo,
        volume_total,
        liquidity,
    ) in tokens_meta:
        rows = con.execute(
            f"""
            SELECT poly_price_change, {return_select}
            FROM {cfg.aligned_view}
            WHERE token_id = ?
              AND market_id = ?
              AND poly_price_change IS NOT NULL
            ORDER BY open_time_ns
            """,
            [token_id, market_id],
        ).fetchall()
        if len(rows) < min_observations_per_token:
            continue
        delta = [r[0] for r in rows]
        crypto_lag_map = {
            lag: [r[i + 1] for r in rows]
            for i, lag in enumerate(cfg.lag_horizons)
        }
        days_bucket = _days_bucket_label(end_iso, as_of=as_of)
        volume_bucket = _dollar_bucket_label(_first_present(volume_1mo, volume_total))
        liquidity_bucket = _dollar_bucket_label(liquidity)

        for lag in cfg.lag_horizons:
            n, r_corr, t, p = pearson_correlation_with_tstat(delta, crypto_lag_map[lag])
            direction = "contemporaneous" if lag == 0 else "poly_leads_crypto"
            token_results.append(
                LeadLagTokenResult(
                    asset=asset,
                    token_id=token_id,
                    market_id=market_id,
                    market_slug=market_slug,
                    question=question,
                    days_bucket=days_bucket,
                    volume_bucket=volume_bucket,
                    liquidity_bucket=liquidity_bucket,
                    lag_hours=lag if cfg.lag_unit == "h" else lag * 24,
                    direction=direction,
                    n=n,
                    correlation=r_corr,
                    tstat=t,
                    pvalue_two_sided=p,
                    volume_1mo_usd=volume_1mo,
                    volume_total_usd=volume_total,
                    liquidity_usd=liquidity,
                )
            )

    bucket_results = _aggregate_buckets(token_results)
    return token_results, bucket_results


def _aggregate_buckets(
    token_results: Iterable[LeadLagTokenResult],
) -> list[LeadLagBucketResult]:
    grouped: dict[tuple[str, str, str, str, int, str], list[LeadLagTokenResult]] = {}
    for tr in token_results:
        key = (
            tr.asset,
            tr.days_bucket,
            tr.volume_bucket,
            tr.liquidity_bucket,
            tr.lag_hours,
            tr.direction,
        )
        grouped.setdefault(key, []).append(tr)

    raw: list[
        tuple[tuple[str, str, str, str, int, str], int, int, float, float, float]
    ] = []
    for key, items in grouped.items():
        valid = [
            it for it in items
            if not math.isnan(it.correlation) and not math.isnan(it.tstat)
        ]
        if not valid:
            continue
        n_obs = sum(it.n for it in valid)
        if n_obs < 3:
            continue
        # Sample-size-weighted Fisher-z mean as a pooled-correlation estimate.
        z_values = [_fisher_z(it.correlation) for it in valid]
        weights = [it.n - 3 for it in valid]
        if sum(weights) <= 0:
            continue
        z_mean = sum(
            z * w for z, w in zip(z_values, weights, strict=False)
        ) / sum(weights)
        z_se = 1.0 / math.sqrt(sum(weights))
        z_t = z_mean / z_se if z_se > 0 else math.nan
        pooled_r = _inverse_fisher_z(z_mean)
        pooled_p = _t_two_sided_pvalue(abs(z_t), df=max(1, sum(weights)))
        raw.append((key, len(valid), n_obs, pooled_r, z_t, pooled_p))

    pvalues = [item[5] for item in raw]
    bh = benjamini_hochberg_significant(pvalues, alpha=0.05)
    out: list[LeadLagBucketResult] = []
    for (key, n_tokens, n_obs, pooled_r, z_t, pooled_p), survives in zip(
        raw, bh, strict=False
    ):
        asset, days_bucket, volume_bucket, liquidity_bucket, lag_hours, direction = key
        out.append(
            LeadLagBucketResult(
                asset=asset,
                days_bucket=days_bucket,
                volume_bucket=volume_bucket,
                liquidity_bucket=liquidity_bucket,
                lag_hours=lag_hours,
                direction=direction,
                n_tokens=n_tokens,
                n_observations=n_obs,
                pooled_correlation=pooled_r,
                pooled_tstat=z_t,
                pooled_pvalue=pooled_p,
                bh_significant_at_0_05=survives,
            )
        )
    out.sort(
        key=lambda b: (
            b.asset,
            b.days_bucket,
            b.volume_bucket,
            b.liquidity_bucket,
            b.lag_hours,
        )
    )
    return out


def _fisher_z(r: float) -> float:
    if r >= 1.0:
        return math.inf
    if r <= -1.0:
        return -math.inf
    return 0.5 * math.log((1.0 + r) / (1.0 - r))


def _inverse_fisher_z(z: float) -> float:
    if math.isinf(z):
        return 1.0 if z > 0 else -1.0
    e = math.exp(2.0 * z)
    return (e - 1.0) / (e + 1.0)


def _days_bucket_label(end_date_iso: str | None, *, as_of: datetime) -> str:
    if not end_date_iso:
        return UNKNOWN_BUCKET
    try:
        cleaned = end_date_iso.replace("Z", "+00:00")
        end_dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return UNKNOWN_BUCKET
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    delta_days = (end_dt - as_of).total_seconds() / 86400.0
    if delta_days < 0:
        return "<7d"  # already past — treat as expiring imminently
    for label, lo, hi in DAYS_BUCKETS:
        if lo <= delta_days < hi:
            return label
    return UNKNOWN_BUCKET


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


# ---------------------------------------------------------------------------
# Phase 2.1 report output
# ---------------------------------------------------------------------------


def rank_signal_candidates(
    token_results: Sequence[LeadLagTokenResult],
    *,
    limit: int | None = 20,
    min_observations: int = 30,
) -> list[LeadLagCandidate]:
    """Rank exploratory Polymarket-leading candidates deterministically."""

    eligible = [
        row
        for row in token_results
        if row.direction == "poly_leads_crypto"
        and row.n >= min_observations
        and _is_finite(row.correlation)
        and _is_finite(row.tstat)
    ]
    ordered = sorted(
        eligible,
        key=lambda row: (
            -_candidate_score(row),
            -abs(row.correlation),
            -row.n,
            row.asset,
            row.market_slug or "",
            row.market_id,
            row.token_id,
            row.lag_hours,
        ),
    )
    if limit is not None:
        ordered = ordered[:limit]
    return [
        LeadLagCandidate(
            rank=rank,
            asset=row.asset,
            market_id=row.market_id,
            market_slug=row.market_slug,
            token_id=row.token_id,
            question=row.question,
            lag_hours=row.lag_hours,
            n=row.n,
            correlation=row.correlation,
            tstat=row.tstat,
            pvalue_two_sided=row.pvalue_two_sided,
            candidate_score=_candidate_score(row),
            days_bucket=row.days_bucket,
            volume_bucket=row.volume_bucket,
            liquidity_bucket=row.liquidity_bucket,
            volume_1mo_usd=row.volume_1mo_usd,
            volume_total_usd=row.volume_total_usd,
            liquidity_usd=row.liquidity_usd,
        )
        for rank, row in enumerate(ordered, start=1)
    ]


def write_lead_lag_report(
    *,
    output_dir: Path,
    token_results: Sequence[LeadLagTokenResult],
    bucket_results: Sequence[LeadLagBucketResult],
    candidate_limit: int = 20,
) -> LeadLagReportPaths:
    """Write the deterministic Phase 2.1 lead-lag report artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_md = output_dir / "lead_lag_summary.md"
    results_csv = output_dir / "lead_lag_results.csv"
    candidates_json = output_dir / "lead_lag_candidates.json"

    candidates = rank_signal_candidates(token_results, limit=candidate_limit)
    _write_results_csv(results_csv, token_results)
    candidates_json.write_text(
        json.dumps([asdict(c) for c in candidates], indent=2, sort_keys=True) + "\n"
    )
    summary_md.write_text(_render_summary_md(token_results, bucket_results, candidates))

    return LeadLagReportPaths(
        summary_md=summary_md,
        results_csv=results_csv,
        candidates_json=candidates_json,
    )


def _write_results_csv(path: Path, token_results: Sequence[LeadLagTokenResult]) -> None:
    fieldnames = [
        "asset",
        "market_id",
        "market_slug",
        "token_id",
        "question",
        "lag_hours",
        "direction",
        "n",
        "correlation",
        "tstat",
        "pvalue_two_sided",
        "candidate_score",
        "days_bucket",
        "volume_bucket",
        "liquidity_bucket",
        "volume_1mo_usd",
        "volume_total_usd",
        "liquidity_usd",
        "exploratory_label",
    ]
    ordered = sorted(
        token_results,
        key=lambda row: (
            -_candidate_score(row) if row.direction == "poly_leads_crypto" else math.inf,
            row.asset,
            row.market_slug or "",
            row.market_id,
            row.token_id,
            row.lag_hours,
        ),
    )
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in ordered:
            writer.writerow(
                {
                    "asset": row.asset,
                    "market_id": row.market_id,
                    "market_slug": row.market_slug,
                    "token_id": row.token_id,
                    "question": row.question,
                    "lag_hours": row.lag_hours,
                    "direction": row.direction,
                    "n": row.n,
                    "correlation": _float_or_blank(row.correlation),
                    "tstat": _float_or_blank(row.tstat),
                    "pvalue_two_sided": _float_or_blank(row.pvalue_two_sided),
                    "candidate_score": _float_or_blank(_candidate_score(row)),
                    "days_bucket": row.days_bucket,
                    "volume_bucket": row.volume_bucket,
                    "liquidity_bucket": row.liquidity_bucket,
                    "volume_1mo_usd": _float_or_blank(row.volume_1mo_usd),
                    "volume_total_usd": _float_or_blank(row.volume_total_usd),
                    "liquidity_usd": _float_or_blank(row.liquidity_usd),
                    "exploratory_label": "EXPLORATORY ONLY - NOT TRADEABLE",
                }
            )


def _render_summary_md(
    token_results: Sequence[LeadLagTokenResult],
    bucket_results: Sequence[LeadLagBucketResult],
    candidates: Sequence[LeadLagCandidate],
) -> str:
    markets = {(r.asset, r.market_id, r.token_id) for r in token_results}
    lines = [
        "# Lead-Lag Research Summary",
        "",
        "**EXPLORATORY ONLY - NOT TRADEABLE.**",
        "",
        "This report scans aligned Polymarket YES probability changes against same-hour "
        "and forward crypto returns. It is a research screen, not a trading signal.",
        "",
        "## Coverage",
        "",
        f"- Markets/tokens tested: {len(markets)}",
        f"- Hypothesis rows: {len(token_results)}",
        f"- Segmented bucket rows: {len(bucket_results)}",
        "- Horizons: same-hour, +1h, +4h, +24h",
        "- Segments: asset, market/question/slug, time-to-resolution bucket, "
        "volume bucket, liquidity bucket",
        "",
        "## Top Candidates",
        "",
    ]
    if not candidates:
        lines.extend(
            [
                "No eligible aligned samples met the candidate threshold.",
                "",
                "Practical read: collect more history before interpreting lead-lag behavior.",
            ]
        )
        return "\n".join(lines) + "\n"

    lines.append("| Rank | Asset | Lag | N | Corr | t-stat | p-value | Market |")
    lines.append("| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for c in candidates[:10]:
        market = c.market_slug or c.question or c.market_id
        lines.append(
            f"| {c.rank} | {c.asset} | {c.lag_hours}h | {c.n} | "
            f"{c.correlation:+.4f} | {c.tstat:+.2f} | {c.pvalue_two_sided:.4g} | "
            f"{_escape_md(str(market))} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- These are univariate exploratory correlations, not causal evidence.",
            "- Multiple testing, thin samples, overlapping markets, and stale Polymarket pricing "
            "can create false positives.",
            "- A candidate is not tradeable until it survives out-of-sample testing, cost/slippage "
            "modeling, execution simulation, and risk controls.",
        ]
    )
    return "\n".join(lines) + "\n"


def _candidate_score(row: LeadLagTokenResult) -> float:
    if _is_finite(row.tstat):
        return abs(row.tstat)
    if _is_finite(row.correlation):
        return abs(row.correlation) * math.sqrt(max(row.n - 2, 1))
    return 0.0


def _is_finite(value: float | None) -> bool:
    return value is not None and not math.isnan(value) and not math.isinf(value)


def _float_or_blank(value: float | None) -> float | str:
    if value is None:
        return ""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    return value


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|")


# ---------------------------------------------------------------------------
# Pattern catalog Parquet output
# ---------------------------------------------------------------------------


def write_pattern_catalog(
    *,
    out_path: Path,
    token_results: Sequence[LeadLagTokenResult],
    bucket_results: Sequence[LeadLagBucketResult],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _to_table(rows: Sequence, cls) -> pa.Table:
        if not rows:
            # Build an empty table with the right shape from the dataclass.
            sample = cls(**{f: None for f in cls.__dataclass_fields__})  # type: ignore[arg-type]
            cols = list(asdict(sample).keys())
            return pa.table({c: [] for c in cols})
        records = [asdict(r) for r in rows]
        cols = list(records[0].keys())
        return pa.table({c: [rec[c] for rec in records] for c in cols})

    token_table = _to_table(token_results, LeadLagTokenResult)
    bucket_table = _to_table(bucket_results, LeadLagBucketResult)
    pq.write_table(token_table, out_path.with_suffix(".tokens.parquet"))
    pq.write_table(bucket_table, out_path.with_suffix(".buckets.parquet"))
