from __future__ import annotations

from joint_research.funding_arb.scanner import scan_funding_opportunities
from joint_research.funding_arb.types import HOURS_PER_YEAR, FundingQuote
from joint_research.funding_arb.venues import project_dydx, project_hyperliquid


def _q(venue: str, base: str, funding: float) -> FundingQuote:
    return FundingQuote(
        venue=venue, base=base, symbol=base, funding_hourly=funding, mark_price=100.0
    )


def test_shorts_high_funding_longs_low_funding() -> None:
    quotes = [_q("hyperliquid", "BTC", 0.00002), _q("dydx", "BTC", 0.00010)]
    opps = scan_funding_opportunities(quotes, haircut=0.0, min_realistic_apr=0.0)
    assert len(opps) == 1
    o = opps[0]
    assert o.short_venue == "dydx"
    assert o.long_venue == "hyperliquid"
    assert o.spread_hourly == 0.00008
    assert o.gross_apr == 0.00008 * HOURS_PER_YEAR


def test_haircut_discounts_realistic_apr() -> None:
    quotes = [_q("hyperliquid", "ETH", 0.0), _q("dydx", "ETH", 0.0001)]
    opps = scan_funding_opportunities(quotes, haircut=0.5, min_realistic_apr=0.0)
    assert opps[0].realistic_apr == opps[0].gross_apr * 0.5


def test_major_only_filters_alts() -> None:
    quotes = [_q("hyperliquid", "PEPE", 0.0), _q("dydx", "PEPE", 0.001)]
    assert scan_funding_opportunities(quotes, major_only=True) == []
    assert scan_funding_opportunities(quotes, major_only=False, min_realistic_apr=0.0)


def test_min_realistic_apr_threshold() -> None:
    quotes = [_q("hyperliquid", "BTC", 0.0), _q("dydx", "BTC", 0.000001)]
    # Tiny spread -> realistic APR below 5% default -> filtered out.
    assert scan_funding_opportunities(quotes) == []


def test_single_venue_base_is_skipped() -> None:
    quotes = [_q("hyperliquid", "BTC", 0.0005)]
    assert scan_funding_opportunities(quotes, min_realistic_apr=0.0) == []


def test_breakeven_hours_reflects_fees() -> None:
    quotes = [_q("hyperliquid", "BTC", 0.0), _q("dydx", "BTC", 0.0001)]
    opps = scan_funding_opportunities(quotes, taker_fee=0.0005, haircut=0.0, min_realistic_apr=0.0)
    # round trip = 4 * 0.0005 = 0.002; breakeven = 0.002 / 0.0001 = 20 hours.
    assert opps[0].breakeven_hours == 20.0


def test_project_hyperliquid_and_dydx_shapes() -> None:
    hl = [
        {"universe": [{"name": "BTC"}, {"name": "ETH"}]},
        [{"funding": "0.00005", "markPx": "60000"}, {"funding": "-0.00002", "markPx": "3000"}],
    ]
    hq = project_hyperliquid(hl)
    assert [q.base for q in hq] == ["BTC", "ETH"]
    assert hq[0].funding_hourly == 0.00005

    dy = {
        "markets": {
            "BTC-USD": {"status": "ACTIVE", "nextFundingRate": "0.0001", "oraclePrice": "61000"}
        }
    }
    dq = project_dydx(dy)
    assert dq[0].base == "BTC"
    assert dq[0].venue == "dydx"
