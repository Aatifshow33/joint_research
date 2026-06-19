from __future__ import annotations

import json
from pathlib import Path

from joint_research.predmarket_arb.cli import app
from joint_research.predmarket_arb.detector import (
    REASON_ACTIONABLE,
    REASON_NEGATIVE_GROSS_EDGE,
)
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests/fixtures/predmarket_arb"

runner = CliRunner()


def test_scan_over_fixtures_writes_artifacts(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "scan",
            "--fixtures-dir",
            str(FIXTURES),
            "--artifact-dir",
            str(artifact_dir),
            "--bankroll",
            "200",
        ],
    )
    assert result.exit_code == 0, result.output

    json_path = artifact_dir / "predmarket_arb_scan.json"
    csv_path = artifact_dir / "predmarket_arb_scan.csv"
    md_path = artifact_dir / "predmarket_arb_summary.md"
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    # BTC and ETH match across venues; the Fed market has no Polymarket twin.
    assert payload["matched_count"] == 2
    assert payload["actionable_count"] == 1
    assert payload["reason_counts"].get(REASON_ACTIONABLE) == 1
    assert payload["reason_counts"].get(REASON_NEGATIVE_GROSS_EDGE) == 1
    assert payload["total_actionable_profit_usd"] > 0

    rows = payload["rows"]
    top = rows[0]
    assert top["is_actionable"] is True
    assert top["venue_yes"] == "polymarket"
    assert top["venue_no"] == "kalshi"
    assert top["capital_required_usd"] <= 200.0 + 1e-9


def test_scan_requires_an_input_mode() -> None:
    result = runner.invoke(app, ["scan"])
    assert result.exit_code != 0


def test_scan_rejects_both_modes(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["scan", "--live", "--fixtures-dir", str(FIXTURES)],
    )
    assert result.exit_code != 0
