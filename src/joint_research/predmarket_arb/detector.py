"""Fee-aware cross-venue arbitrage evaluation.

Given the same event quoted on two venues, holding one YES and one NO
guarantees a $1 payout regardless of outcome. The arb is to acquire that pair
for less than $1 *after fees*. Because exactly one leg pays out, there are two
candidate directions:

* buy YES on venue A and NO on venue B, or
* buy YES on venue B and NO on venue A.

We evaluate both, pick the cheaper, then size the position against the smaller
of (bankroll capacity, quoted liquidity on both legs) and report the realised,
fee-inclusive profit. Near-misses are reported too — the whole point of the
research layer is to measure how often real spreads clear the fee hurdle, not
only to surface the winners.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from joint_research.predmarket_arb.fees import VenueFeeModel, fee_model_for_venue
from joint_research.predmarket_arb.types import BinaryMarketQuote

_CostFn = Callable[[int], float]

# Reason codes (frozen operator-facing contract).
REASON_ACTIONABLE = "actionable"
REASON_NEGATIVE_GROSS_EDGE = "negative_gross_edge"
REASON_ZERO_AVAILABLE_SIZE = "zero_available_size"
REASON_BANKROLL_TOO_SMALL = "bankroll_too_small"
REASON_EDGE_BELOW_THRESHOLD = "edge_below_fee_threshold"
REASON_PROFIT_BELOW_MINIMUM = "profit_below_minimum"

DIRECTION_YES_A_NO_B = "yes_a_no_b"
DIRECTION_YES_B_NO_A = "yes_b_no_a"


@dataclass(frozen=True)
class DetectorConfig:
    """Thresholds that decide whether an evaluation is actionable."""

    bankroll_usd: float = 200.0
    min_net_edge_per_pair: float = 0.02
    min_net_profit_usd: float = 1.0
    max_contracts: int | None = None

    def __post_init__(self) -> None:
        if self.bankroll_usd <= 0:
            raise ValueError(f"bankroll_usd_must_be_positive: {self.bankroll_usd}")
        if not 0.0 <= self.min_net_edge_per_pair < 1.0:
            raise ValueError(f"min_net_edge_out_of_range: {self.min_net_edge_per_pair}")
        if self.min_net_profit_usd < 0:
            raise ValueError(f"min_net_profit_negative: {self.min_net_profit_usd}")
        if self.max_contracts is not None and self.max_contracts <= 0:
            raise ValueError(f"max_contracts_must_be_positive: {self.max_contracts}")


@dataclass(frozen=True)
class ArbEvaluation:
    """The best cross-venue evaluation for one matched market pair."""

    market_key: str
    title: str
    venue_yes: str
    venue_no: str
    direction: str
    yes_ask: float
    no_ask: float
    gross_cost_per_pair: float
    gross_edge_per_pair: float
    fee_per_pair: float
    net_edge_per_pair: float
    contracts: int
    capital_required_usd: float
    net_profit_usd: float
    is_actionable: bool
    reason_code: str


@dataclass(frozen=True)
class _DirectionEconomics:
    direction: str
    venue_yes: str
    venue_no: str
    yes_ask: float
    no_ask: float
    gross_cost_per_pair: float
    gross_edge_per_pair: float


def evaluate_market_pair(
    quote_a: BinaryMarketQuote,
    quote_b: BinaryMarketQuote,
    *,
    config: DetectorConfig | None = None,
    fee_models: dict[str, VenueFeeModel] | None = None,
    market_key: str | None = None,
    title: str | None = None,
) -> ArbEvaluation:
    """Evaluate the best fee-aware arbitrage for a matched pair of quotes."""

    cfg = config or DetectorConfig()
    fees = _resolve_fee_models(quote_a, quote_b, fee_models)

    best = _cheaper_direction(quote_a, quote_b)
    fee_yes = fees[best.venue_yes]
    fee_no = fees[best.venue_no]

    resolved_key = market_key or quote_a.market_key
    resolved_title = title or quote_a.title

    # Liquidity ceiling: the YES leg comes from whichever venue is cheaper for
    # YES, the NO leg from the other. A pair needs one contract on each.
    yes_size = _size_on(quote_a, quote_b, best.venue_yes, "yes")
    no_size = _size_on(quote_a, quote_b, best.venue_no, "no")
    liquidity_cap = min(yes_size, no_size)
    if cfg.max_contracts is not None:
        liquidity_cap = min(liquidity_cap, cfg.max_contracts)

    def total_cost(contracts: int) -> float:
        return (
            best.gross_cost_per_pair * contracts
            + fee_yes.taker_fee(price=best.yes_ask, contracts=contracts)
            + fee_no.taker_fee(price=best.no_ask, contracts=contracts)
        )

    # Bankroll ceiling: both legs *and their fees* must be funded up front, so
    # we search for the largest affordable size rather than dividing by the
    # fee-free cost (which would overstate what a small account can hold).
    affordable_cap = _max_affordable_contracts(
        upper=liquidity_cap,
        bankroll=cfg.bankroll_usd,
        total_cost=total_cost,
    )
    contracts = min(liquidity_cap, affordable_cap)

    if best.gross_edge_per_pair <= 0:
        return _empty_evaluation(
            resolved_key, resolved_title, best, REASON_NEGATIVE_GROSS_EDGE
        )
    if liquidity_cap <= 0:
        return _empty_evaluation(
            resolved_key, resolved_title, best, REASON_ZERO_AVAILABLE_SIZE
        )
    if contracts <= 0:
        return _empty_evaluation(
            resolved_key, resolved_title, best, REASON_BANKROLL_TOO_SMALL
        )

    capital_required = total_cost(contracts)
    fee_total = capital_required - best.gross_cost_per_pair * contracts
    payout = float(contracts)
    net_profit = payout - capital_required
    net_edge_per_pair = net_profit / contracts
    fee_per_pair = fee_total / contracts

    reason = _actionability_reason(
        net_edge_per_pair=net_edge_per_pair,
        net_profit=net_profit,
        cfg=cfg,
    )

    return ArbEvaluation(
        market_key=resolved_key,
        title=resolved_title,
        venue_yes=best.venue_yes,
        venue_no=best.venue_no,
        direction=best.direction,
        yes_ask=best.yes_ask,
        no_ask=best.no_ask,
        gross_cost_per_pair=best.gross_cost_per_pair,
        gross_edge_per_pair=best.gross_edge_per_pair,
        fee_per_pair=fee_per_pair,
        net_edge_per_pair=net_edge_per_pair,
        contracts=contracts,
        capital_required_usd=capital_required,
        net_profit_usd=net_profit,
        is_actionable=reason == REASON_ACTIONABLE,
        reason_code=reason,
    )


def _resolve_fee_models(
    quote_a: BinaryMarketQuote,
    quote_b: BinaryMarketQuote,
    fee_models: dict[str, VenueFeeModel] | None,
) -> dict[str, VenueFeeModel]:
    models = dict(fee_models or {})
    for venue in (quote_a.venue, quote_b.venue):
        if venue not in models:
            models[venue] = fee_model_for_venue(venue)
    return models


def _cheaper_direction(
    quote_a: BinaryMarketQuote, quote_b: BinaryMarketQuote
) -> _DirectionEconomics:
    dir_ab = _DirectionEconomics(
        direction=DIRECTION_YES_A_NO_B,
        venue_yes=quote_a.venue,
        venue_no=quote_b.venue,
        yes_ask=quote_a.yes_ask,
        no_ask=quote_b.no_ask,
        gross_cost_per_pair=quote_a.yes_ask + quote_b.no_ask,
        gross_edge_per_pair=1.0 - (quote_a.yes_ask + quote_b.no_ask),
    )
    dir_ba = _DirectionEconomics(
        direction=DIRECTION_YES_B_NO_A,
        venue_yes=quote_b.venue,
        venue_no=quote_a.venue,
        yes_ask=quote_b.yes_ask,
        no_ask=quote_a.no_ask,
        gross_cost_per_pair=quote_b.yes_ask + quote_a.no_ask,
        gross_edge_per_pair=1.0 - (quote_b.yes_ask + quote_a.no_ask),
    )
    return dir_ab if dir_ab.gross_cost_per_pair <= dir_ba.gross_cost_per_pair else dir_ba


def _size_on(
    quote_a: BinaryMarketQuote,
    quote_b: BinaryMarketQuote,
    venue: str,
    outcome: str,
) -> int:
    quote = quote_a if quote_a.venue == venue else quote_b
    return quote.size_for(outcome)


def _max_affordable_contracts(
    *,
    upper: int,
    bankroll: float,
    total_cost: _CostFn,
) -> int:
    """Largest contract count in [0, upper] whose fee-inclusive cost fits.

    ``total_cost`` is monotonically non-decreasing in contracts, so a binary
    search finds the boundary in O(log upper).
    """
    if upper <= 0:
        return 0
    if total_cost(upper) <= bankroll:
        return upper
    low, high = 0, upper
    while low < high:
        mid = (low + high + 1) // 2
        if total_cost(mid) <= bankroll:
            low = mid
        else:
            high = mid - 1
    return low


def _actionability_reason(
    *,
    net_edge_per_pair: float,
    net_profit: float,
    cfg: DetectorConfig,
) -> str:
    if net_edge_per_pair < cfg.min_net_edge_per_pair:
        return REASON_EDGE_BELOW_THRESHOLD
    if net_profit < cfg.min_net_profit_usd:
        return REASON_PROFIT_BELOW_MINIMUM
    return REASON_ACTIONABLE


def _empty_evaluation(
    market_key: str,
    title: str,
    best: _DirectionEconomics,
    reason: str,
) -> ArbEvaluation:
    return ArbEvaluation(
        market_key=market_key,
        title=title,
        venue_yes=best.venue_yes,
        venue_no=best.venue_no,
        direction=best.direction,
        yes_ask=best.yes_ask,
        no_ask=best.no_ask,
        gross_cost_per_pair=best.gross_cost_per_pair,
        gross_edge_per_pair=best.gross_edge_per_pair,
        fee_per_pair=0.0,
        net_edge_per_pair=0.0,
        contracts=0,
        capital_required_usd=0.0,
        net_profit_usd=0.0,
        is_actionable=False,
        reason_code=reason,
    )
