"""Deterministic feature engine for paper Polymarket/crypto research."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

HOUR_NS = 3_600_000_000_000


@dataclass(frozen=True)
class FeatureInput:
    open_time_ns: int
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    end_date_iso: str | None
    poly_yes_price: float
    crypto_close: float
    crypto_volume_quote: float | None
    forward_return_1h: float | None
    forward_return_4h: float | None
    forward_return_24h: float | None
    funding_rate: float | None = None
    basis_pct: float | None = None
    funding_regime: str | None = None
    funding_intensity: str | None = None
    basis_regime: str | None = None


@dataclass(frozen=True)
class FeatureRow:
    open_time_ns: int
    asset: str
    market_id: str
    market_slug: str | None
    token_id: str
    question: str | None
    poly_yes_price: float
    crypto_close: float
    prob_change_1h: float
    prob_change_4h: float
    prob_change_24h: float
    probability_momentum: float
    probability_reversal: float
    probability_volatility: float
    probability_level_bucket: str
    large_probability_move: bool
    market_nearing_expiry: bool
    crypto_return_1h: float
    crypto_return_4h: float
    crypto_return_24h: float
    realized_volatility: float
    momentum_regime: str
    reversal_regime: str
    large_crypto_move: bool
    volume_spike: bool
    funding_rate: float | None
    basis_pct: float | None
    funding_regime: str
    funding_intensity: str
    basis_regime: str
    probability_crypto_divergence: float
    probability_confirms_crypto_momentum: bool
    probability_opposes_crypto_momentum: bool
    lagged_probability_predictor: float
    forward_return_1h: float | None
    forward_return_4h: float | None
    forward_return_24h: float | None


def build_feature_rows(
    inputs: Sequence[FeatureInput],
    *,
    large_probability_move_threshold: float = 0.05,
    large_crypto_move_threshold: float = 0.02,
    volatility_window: int = 24,
    nearing_expiry_hours: int = 72,
) -> list[FeatureRow]:
    ordered = sorted(inputs, key=lambda row: row.open_time_ns)
    out: list[FeatureRow] = []
    for idx, row in enumerate(ordered):
        prob_change_1h = _price_change(ordered, idx, 1)
        prob_change_4h = _price_change(ordered, idx, 4)
        prob_change_24h = _price_change(ordered, idx, 24)
        crypto_return_1h = _log_return(ordered, idx, 1)
        crypto_return_4h = _log_return(ordered, idx, 4)
        crypto_return_24h = _log_return(ordered, idx, 24)
        recent_prob_changes = [
            _price_change(ordered, j, 1)
            for j in range(max(0, idx - volatility_window + 1), idx + 1)
        ]
        recent_crypto_returns = [
            _log_return(ordered, j, 1)
            for j in range(max(0, idx - volatility_window + 1), idx + 1)
        ]
        probability_momentum = _round(prob_change_1h + 0.5 * prob_change_4h)
        probability_reversal = _round(-probability_momentum)
        momentum_regime = _regime(crypto_return_4h, threshold=0.005)
        reversal_regime = _regime(-crypto_return_4h, threshold=0.005)
        divergence = _round(prob_change_1h - crypto_return_1h)
        confirms = _same_nonzero_sign(prob_change_1h, crypto_return_1h)
        opposes = _opposite_nonzero_sign(prob_change_1h, crypto_return_1h)
        out.append(
            FeatureRow(
                open_time_ns=row.open_time_ns,
                asset=row.asset,
                market_id=row.market_id,
                market_slug=row.market_slug,
                token_id=row.token_id,
                question=row.question,
                poly_yes_price=row.poly_yes_price,
                crypto_close=row.crypto_close,
                prob_change_1h=prob_change_1h,
                prob_change_4h=prob_change_4h,
                prob_change_24h=prob_change_24h,
                probability_momentum=probability_momentum,
                probability_reversal=probability_reversal,
                probability_volatility=_stdev(recent_prob_changes),
                probability_level_bucket=_probability_level_bucket(row.poly_yes_price),
                large_probability_move=abs(prob_change_1h) >= large_probability_move_threshold,
                market_nearing_expiry=_is_nearing_expiry(
                    row.open_time_ns,
                    row.end_date_iso,
                    nearing_expiry_hours=nearing_expiry_hours,
                ),
                crypto_return_1h=crypto_return_1h,
                crypto_return_4h=crypto_return_4h,
                crypto_return_24h=crypto_return_24h,
                realized_volatility=_stdev(recent_crypto_returns),
                momentum_regime=momentum_regime,
                reversal_regime=reversal_regime,
                large_crypto_move=abs(crypto_return_1h) >= large_crypto_move_threshold,
                volume_spike=_volume_spike(ordered, idx),
                funding_rate=row.funding_rate,
                basis_pct=row.basis_pct,
                funding_regime=row.funding_regime or "unknown_funding",
                funding_intensity=row.funding_intensity or "unknown_funding",
                basis_regime=row.basis_regime or "unknown_basis",
                probability_crypto_divergence=divergence,
                probability_confirms_crypto_momentum=confirms,
                probability_opposes_crypto_momentum=opposes,
                lagged_probability_predictor=prob_change_1h,
                forward_return_1h=row.forward_return_1h,
                forward_return_4h=row.forward_return_4h,
                forward_return_24h=row.forward_return_24h,
            )
        )
    return out


def split_feature_train_test(
    rows: Sequence[FeatureRow],
    *,
    train_fraction: float = 0.6,
) -> tuple[list[FeatureRow], list[FeatureRow]]:
    if not 0.0 < train_fraction < 1.0:
        raise ValueError(f"invalid_train_fraction:{train_fraction}")
    ordered = sorted(rows, key=lambda row: row.open_time_ns)
    split_idx = int(len(ordered) * train_fraction)
    split_idx = max(1, min(split_idx, len(ordered) - 1))
    return ordered[:split_idx], ordered[split_idx:]


def is_flat_market(
    rows: Sequence[FeatureRow],
    *,
    max_flat_fraction: float = 0.90,
    tiny_move_threshold: float = 1e-12,
) -> bool:
    if not rows:
        return True
    flat = sum(1 for row in rows if abs(row.prob_change_1h) <= tiny_move_threshold)
    return flat / len(rows) > max_flat_fraction


def _price_change(rows: Sequence[FeatureInput], idx: int, lookback: int) -> float:
    if idx <= 0:
        return 0.0
    ref_idx = max(0, idx - lookback)
    return _round(rows[idx].poly_yes_price - rows[ref_idx].poly_yes_price)


def _log_return(rows: Sequence[FeatureInput], idx: int, lookback: int) -> float:
    if idx <= 0:
        return 0.0
    ref_idx = max(0, idx - lookback)
    prior = rows[ref_idx].crypto_close
    current = rows[idx].crypto_close
    if prior <= 0 or current <= 0:
        return 0.0
    return math.log(current / prior)


def _probability_level_bucket(price: float) -> str:
    if price < 0.25:
        return "low"
    if price < 0.60:
        return "mid"
    if price < 0.85:
        return "high"
    return "very_high"


def _volume_spike(rows: Sequence[FeatureInput], idx: int, *, lookback: int = 24) -> bool:
    current = rows[idx].crypto_volume_quote
    if current is None or idx == 0:
        return False
    prior = [
        row.crypto_volume_quote
        for row in rows[max(0, idx - lookback):idx]
        if row.crypto_volume_quote is not None
    ]
    if not prior:
        return False
    return current >= 2.0 * (sum(prior) / len(prior))


def _is_nearing_expiry(
    open_time_ns: int,
    end_date_iso: str | None,
    *,
    nearing_expiry_hours: int,
) -> bool:
    if not end_date_iso:
        return False
    try:
        end_dt = datetime.fromisoformat(end_date_iso.replace("Z", "+00:00"))
    except ValueError:
        return False
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    open_dt = datetime.fromtimestamp(open_time_ns / 1_000_000_000, tz=timezone.utc)
    hours = (end_dt - open_dt).total_seconds() / 3600.0
    return 0 <= hours <= nearing_expiry_hours


def _regime(value: float, *, threshold: float) -> str:
    if value > threshold:
        return "up"
    if value < -threshold:
        return "down"
    return "flat"


def _same_nonzero_sign(a: float, b: float) -> bool:
    return a * b > 0


def _opposite_nonzero_sign(a: float, b: float) -> bool:
    return a * b < 0


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def _round(value: float) -> float:
    return round(value, 12)
