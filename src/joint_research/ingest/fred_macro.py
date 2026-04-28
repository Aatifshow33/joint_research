"""Ingest macro time series from FRED.

FRED's public CSV endpoint is the simplest and most reliable surface — no
API key required, no rate limiting on reasonable use:

    https://fred.stlouisfed.org/graph/fredgraph.csv?id=<series_id>

The CSV shape is two columns: ``DATE``, ``<series_id>``. Missing values
appear as a literal ``.`` in the value column. Dates are calendar days
(daily series at most; FRED interpolates monthly/quarterly to date stamps).
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import httpx

from joint_research.warehouse.schema import MACRO_SERIES

FRED_SOURCE = "fred"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


@dataclass(frozen=True)
class MacroSeriesRow:
    source_system: str
    series_id: str
    event_time_ns: int
    value: float | None
    units: str | None
    frequency: str | None
    payload_hash: str
    payload_json: str

    def to_warehouse_row(self) -> dict[str, object]:
        return {
            "event_time_ns": self.event_time_ns,
            "source": f"{self.source_system}.{self.series_id}",
            "payload_hash": self.payload_hash,
            "payload_json": self.payload_json,
            "source_system": self.source_system,
            "series_id": self.series_id,
            "value": self.value,
            "units": self.units,
            "frequency": self.frequency,
        }


def project_fred_csv(
    csv_text: str,
    *,
    series_id: str,
    units: str | None = None,
    frequency: str | None = None,
) -> list[MacroSeriesRow]:
    rows: list[MacroSeriesRow] = []
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader, None)
    if not header or len(header) < 2:
        return rows
    # FRED's date column is "DATE" or "observation_date" depending on era;
    # the value column matches the series id (case-insensitive).
    for raw in reader:
        if not raw or len(raw) < 2:
            continue
        date_str = raw[0].strip()
        value_str = raw[1].strip()
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        # FRED uses "." for missing observations.
        value: float | None
        if value_str in ("", "."):
            value = None
        else:
            try:
                value = float(value_str)
            except ValueError:
                value = None

        event_time_ns = int(dt.timestamp() * 1_000_000_000)
        payload_json = (
            '{"series_id":"' + series_id +
            '","date":"' + date_str +
            '","value":' + (("null") if value is None else str(value)) +
            '}'
        )
        payload_hash = hashlib.sha256(
            f"{FRED_SOURCE}|{series_id}|{event_time_ns}|{payload_json}".encode("utf-8")
        ).hexdigest()
        rows.append(
            MacroSeriesRow(
                source_system=FRED_SOURCE,
                series_id=series_id.upper(),
                event_time_ns=event_time_ns,
                value=value,
                units=units,
                frequency=frequency,
                payload_hash=payload_hash,
                payload_json=payload_json,
            )
        )
    return rows


def fetch_fred_csv(
    *,
    series_id: str,
    client: httpx.Client | None = None,
) -> str:
    owns_client = client is None
    http = client if client is not None else httpx.Client(timeout=30.0)
    try:
        response = http.get(FRED_CSV_URL, params={"id": series_id})
        response.raise_for_status()
        return response.text
    finally:
        if owns_client:
            http.close()


TABLE = MACRO_SERIES
