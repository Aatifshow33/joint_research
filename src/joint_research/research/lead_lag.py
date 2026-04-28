"""Lead-lag study: do Polymarket Δprob shifts predict future crypto returns?

Approach:

1. For each YES token in ``polymarket_token_returns_aligned``, compute the
   Pearson correlation of ``poly_price_change`` against forward crypto
   log-returns at lags {0, +1h, +4h, +24h}. Also compute the reverse
   (lagged poly vs current crypto) so we can tell which side leads.
2. Compute a t-statistic ``t = r * sqrt((n-2)/(1-r^2))`` and a two-sided
   p-value from the t-distribution survival function.
3. Bucket each token by days-to-resolution (``<7d``, ``7-30d``, ``30-90d``,
   ``>90d``, ``unknown``) so we can separate time-decay-dominated tail
   markets from active-pricing markets.
4. Aggregate per (asset, days_bucket): pooled correlation across tokens
   weighted by sample size, plus Benjamini-Hochberg adjusted significance
   over the full table of tested hypotheses.

The output is two structured tables:
- ``LeadLagTokenResult`` rows — one per token × lag pair tested.
- ``LeadLagBucketResult`` rows — one per (asset, days_bucket, lag) cell.

Both can be written to ``pattern_catalog.parquet`` for downstream selection.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

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
    aligned_view="polymarket_token_returns_aligned",
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
    question: str | None
    days_bucket: str
    lag_hours: int
    direction: str  # "poly_leads_crypto" | "crypto_leads_poly" | "contemporaneous"
    n: int
    correlation: float
    tstat: float
    pvalue_two_sided: float
    volume_1mo_usd: float | None


@dataclass(frozen=True)
class LeadLagBucketResult:
    asset: str
    days_bucket: str
    lag_hours: int
    direction: str
    n_tokens: int
    n_observations: int
    pooled_correlation: float
    pooled_tstat: float
    pooled_pvalue: float
    bh_significant_at_0_05: bool


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
    for x, y in zip(xs, ys):
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
          asset, token_id, market_id, question, end_date_iso, volume_1mo_usd
        FROM {cfg.aligned_view}
        ORDER BY asset, token_id
        """
    ).fetchall()

    return_select = ", ".join(
        cfg.return_columns[lag] for lag in cfg.lag_horizons
    )

    token_results: list[LeadLagTokenResult] = []
    for (asset, token_id, market_id, question, end_iso, vol) in tokens_meta:
        rows = con.execute(
            f"""
            SELECT poly_price_change, {return_select}
            FROM {cfg.aligned_view}
            WHERE token_id = ?
              AND poly_price_change IS NOT NULL
            ORDER BY open_time_ns
            """,
            [token_id],
        ).fetchall()
        if len(rows) < min_observations_per_token:
            continue
        delta = [r[0] for r in rows]
        crypto_lag_map = {
            lag: [r[i + 1] for r in rows]
            for i, lag in enumerate(cfg.lag_horizons)
        }
        days_bucket = _days_bucket_label(end_iso, as_of=as_of)

        for lag in cfg.lag_horizons:
            n, r_corr, t, p = pearson_correlation_with_tstat(delta, crypto_lag_map[lag])
            direction = "contemporaneous" if lag == 0 else "poly_leads_crypto"
            token_results.append(
                LeadLagTokenResult(
                    asset=asset,
                    token_id=token_id,
                    market_id=market_id,
                    question=question,
                    days_bucket=days_bucket,
                    lag_hours=lag if cfg.lag_unit == "h" else lag * 24,
                    direction=direction,
                    n=n,
                    correlation=r_corr,
                    tstat=t,
                    pvalue_two_sided=p,
                    volume_1mo_usd=vol,
                )
            )

    bucket_results = _aggregate_buckets(token_results)
    return token_results, bucket_results


def _aggregate_buckets(
    token_results: Iterable[LeadLagTokenResult],
) -> list[LeadLagBucketResult]:
    grouped: dict[tuple[str, str, int, str], list[LeadLagTokenResult]] = {}
    for tr in token_results:
        key = (tr.asset, tr.days_bucket, tr.lag_hours, tr.direction)
        grouped.setdefault(key, []).append(tr)

    raw: list[tuple[tuple[str, str, int, str], int, int, float, float, float]] = []
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
        z_mean = sum(z * w for z, w in zip(z_values, weights)) / sum(weights)
        z_se = 1.0 / math.sqrt(sum(weights))
        z_t = z_mean / z_se if z_se > 0 else math.nan
        pooled_r = _inverse_fisher_z(z_mean)
        pooled_p = _t_two_sided_pvalue(abs(z_t), df=max(1, sum(weights)))
        raw.append((key, len(valid), n_obs, pooled_r, z_t, pooled_p))

    pvalues = [item[5] for item in raw]
    bh = benjamini_hochberg_significant(pvalues, alpha=0.05)
    out: list[LeadLagBucketResult] = []
    for (key, n_tokens, n_obs, pooled_r, z_t, pooled_p), survives in zip(raw, bh):
        asset, days_bucket, lag_hours, direction = key
        out.append(
            LeadLagBucketResult(
                asset=asset,
                days_bucket=days_bucket,
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
    out.sort(key=lambda b: (b.asset, b.days_bucket, b.lag_hours))
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
