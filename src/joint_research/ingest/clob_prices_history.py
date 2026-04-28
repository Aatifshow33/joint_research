"""Ingest Polymarket CLOB ``/prices-history`` for a list of token IDs.

Endpoint shape:
    GET https://clob.polymarket.com/prices-history
        ?market=<token_id>&interval=<1h|6h|1d|1w|1m|max>&fidelity=<minutes>

Response: ``{"history": [{"t": <unix_seconds>, "p": <prob 0..1>}, ...]}``

The endpoint demands exactly one of ``interval`` or ``startTs/endTs``. We use
``interval`` for incremental polling and ``startTs/endTs`` for explicit
backfills of a known window.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

from joint_research.warehouse.schema import POLYMARKET_PRICE_HISTORY

CLOB_PRICES_HISTORY_URL = "https://clob.polymarket.com/prices-history"
CLOB_SOURCE_PREFIX = "clob.prices_history"


@dataclass(frozen=True)
class PriceHistoryRow:
    token_id: str
    market_id: str | None
    outcome: str | None
    event_time_ns: int
    price: float
    interval_label: str | None
    fidelity_minutes: int | None
    payload_hash: str
    payload_json: str

    def to_warehouse_row(self) -> dict[str, object]:
        source = (
            f"{CLOB_SOURCE_PREFIX}.{self.interval_label}"
            if self.interval_label
            else CLOB_SOURCE_PREFIX
        )
        return {
            "event_time_ns": self.event_time_ns,
            "source": source,
            "payload_hash": self.payload_hash,
            "payload_json": self.payload_json,
            "token_id": self.token_id,
            "market_id": self.market_id,
            "outcome": self.outcome,
            "price": self.price,
            "interval_label": self.interval_label,
            "fidelity_minutes": self.fidelity_minutes,
        }


def project_history_samples(
    samples: Iterable[dict[str, Any]],
    *,
    token_id: str,
    market_id: str | None = None,
    outcome: str | None = None,
    interval_label: str | None = None,
    fidelity_minutes: int | None = None,
) -> list[PriceHistoryRow]:
    rows: list[PriceHistoryRow] = []
    for sample in samples:
        if not isinstance(sample, dict):
            continue
        t = sample.get("t")
        p = sample.get("p")
        if not isinstance(t, (int, float)) or not isinstance(p, (int, float)):
            continue
        event_time_ns = int(t) * 1_000_000_000
        price = float(p)
        # Hash on (token, t, p) for natural dedup. Two samples at the same t
        # with the same p don't collide with samples on other tokens.
        digest = hashlib.sha256(
            f"{token_id}|{event_time_ns}|{price:.10f}".encode("utf-8")
        ).hexdigest()
        rows.append(
            PriceHistoryRow(
                token_id=token_id,
                market_id=market_id,
                outcome=outcome,
                event_time_ns=event_time_ns,
                price=price,
                interval_label=interval_label,
                fidelity_minutes=fidelity_minutes,
                payload_hash=digest,
                payload_json=f'{{"t":{int(t)},"p":{price}}}',
            )
        )
    return rows


async def fetch_prices_history(
    *,
    token_id: str,
    interval: str | None = "1m",
    fidelity_minutes: int = 60,
    start_ts: int | None = None,
    end_ts: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch price history for one token. Pass ``interval`` OR ``start_ts/end_ts``, not both."""

    if interval is None and (start_ts is None or end_ts is None):
        raise ValueError("must_pass_interval_or_start_end_ts")
    if interval is not None and (start_ts is not None or end_ts is not None):
        raise ValueError("interval_and_start_end_are_mutually_exclusive")

    params: dict[str, Any] = {"market": token_id, "fidelity": fidelity_minutes}
    if interval is not None:
        params["interval"] = interval
    else:
        params["startTs"] = start_ts
        params["endTs"] = end_ts

    owns_client = client is None
    http = client if client is not None else httpx.AsyncClient(timeout=30.0)
    try:
        response = await http.get(CLOB_PRICES_HISTORY_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            await http.aclose()

    if not isinstance(payload, dict):
        raise TypeError(f"prices_history_unexpected_payload:{type(payload)!r}")
    history = payload.get("history", [])
    if not isinstance(history, list):
        raise TypeError(f"prices_history_history_not_list:{type(history)!r}")
    return [s for s in history if isinstance(s, dict)]


TABLE = POLYMARKET_PRICE_HISTORY
