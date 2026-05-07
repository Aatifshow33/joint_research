from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


DIAGNOSTICS_PATH = Path(
    "artifacts/research/wallet_flow_signal/wallet_flow_rejection_diagnostics.csv"
)
SUMMARY_PATH = Path("artifacts/research/wallet_flow_signal/wallet_flow_rejection_summary.md")


def _retained_grade_counts(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("retained_after_dedup") == "True":
                counts[row.get("final_grade", "")] += 1
    return counts


def test_wallet_flow_artifact_closeout_guard() -> None:
    assert DIAGNOSTICS_PATH.exists(), "wallet-flow rejection diagnostics CSV must exist"
    assert SUMMARY_PATH.exists(), "wallet-flow rejection summary Markdown must exist"

    summary_text = SUMMARY_PATH.read_text(encoding="utf-8")
    normalized_summary = summary_text.lower().replace("_", " ")

    assert "exploratory only - not tradeable" in normalized_summary

    counts = _retained_grade_counts(DIAGNOSTICS_PATH)
    assert counts.get("SIMULATION_READY", 0) == 0
    assert counts.get("WATCHLIST", 0) == 0
    assert counts.get("WEAK", 0) == 0
    assert counts.get("REJECTED", 0) == 1082

    required_summary_references = [
        "improvement below cost buffer",
        "insufficient unique flow hours",
        "weak win rate",
    ]
    for phrase in required_summary_references:
        assert phrase in normalized_summary
