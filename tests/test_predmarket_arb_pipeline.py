from __future__ import annotations

import json
from pathlib import Path

from joint_research.predmarket_arb.detector import DetectorConfig, evaluate_market_pair
from joint_research.predmarket_arb.matcher import MatchedMarket
from joint_research.predmarket_arb.pipeline import (
    alerts_from_evaluations,
    append_alerts,
    build_clob_token_map,
    format_alert,
    refine_pair_with_depth,
)
from joint_research.predmarket_arb.types import BinaryMarketQuote


def _kalshi(yes: float, no: float, size: int = 1000) -> BinaryMarketQuote:
    return BinaryMarketQuote("kalshi", "KX-BTC", "Bitcoin above 100k", yes, no, size, size, 1)


def _poly(yes: float, no: float, size: int = 500) -> BinaryMarketQuote:
    return BinaryMarketQuote(
        "polymarket", "0xbtc", "Will Bitcoin be above 100k", yes, no, size, size, 1
    )


def test_build_clob_token_map_parses_string_lists() -> None:
    payloads = [
        {"conditionId": "0xbtc", "clobTokenIds": '["tok_yes", "tok_no"]'},
        {"conditionId": "0xeth", "clobTokenIds": ["e_yes", "e_no"]},
        {"conditionId": "0xbad"},
    ]
    token_map = build_clob_token_map(payloads)
    assert token_map["0xbtc"] == ("tok_yes", "tok_no")
    assert token_map["0xeth"] == ("e_yes", "e_no")
    assert "0xbad" not in token_map


def test_refine_pair_with_depth_replaces_poly_size() -> None:
    match = MatchedMarket(
        market_key="KX-BTC|0xbtc",
        title="Bitcoin above 100k",
        quote_a=_kalshi(0.58, 0.43),
        quote_b=_poly(0.40, 0.60, size=500),
        similarity=1.0,
        match_method="manual_map",
    )
    # Real book only allows 7 contracts on the YES leg, 9 on NO -> caps to 7.
    fills = {("tok_yes", 0.40): 7, ("tok_no", 0.60): 9}

    def fetch(token: str, price: float) -> int:
        return fills[(token, price)]

    ev = refine_pair_with_depth(
        match,
        config=DetectorConfig(bankroll_usd=200.0, min_net_profit_usd=0.25),
        poly_tokens={"0xbtc": ("tok_yes", "tok_no")},
        fetch_fillable=fetch,
    )
    assert ev.contracts == 7


def test_alerts_only_actionable_and_mark_verified() -> None:
    actionable = evaluate_market_pair(
        _kalshi(0.58, 0.43), _poly(0.40, 0.60),
        config=DetectorConfig(bankroll_usd=200.0, min_net_profit_usd=0.25),
        market_key="KX-BTC|0xbtc", title="Bitcoin above 100k",
    )
    rejected = evaluate_market_pair(
        _kalshi(0.60, 0.55), _poly(0.55, 0.60),
        market_key="KX-ETH|0xeth", title="Eth",
    )
    alerts = alerts_from_evaluations(
        [actionable, rejected], verified_keys={"KX-BTC"}
    )
    assert len(alerts) == 1
    assert alerts[0].market_key == "KX-BTC|0xbtc"
    assert alerts[0].verified is True


def test_append_alerts_writes_jsonl(tmp_path: Path) -> None:
    ev = evaluate_market_pair(
        _kalshi(0.58, 0.43), _poly(0.40, 0.60),
        config=DetectorConfig(bankroll_usd=200.0, min_net_profit_usd=0.25),
        market_key="KX-BTC|0xbtc", title="Bitcoin above 100k",
    )
    alerts = alerts_from_evaluations([ev], verified_keys=set())
    log = tmp_path / "alerts.jsonl"
    append_alerts(alerts, path=log)
    append_alerts(alerts, path=log)
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["market_key"] == "KX-BTC|0xbtc"
    assert "UNVERIFIED" in format_alert(alerts[0])
