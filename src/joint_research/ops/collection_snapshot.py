"""Parse collection-loop logs and write timestamped ops snapshots."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SnapshotStep:
    name: str
    command: str
    exit_code: int
    output: str


@dataclass(frozen=True)
class SnapshotMetrics:
    simulation_ready: int
    paper_ready: int
    wallet_flow_rows_before: int | None
    wallet_flow_rows_after: int | None
    market_flow_rows_before: int | None
    market_flow_rows_after: int | None
    whale_flow_rows_before: int | None
    whale_flow_rows_after: int | None


def classify_status(*, simulation_ready: int, paper_ready: int, any_failures: bool) -> str:
    if paper_ready > 0:
        return "PAPER_TRACKING_READY"
    if simulation_ready > 0:
        return "MORE_DATA_NEEDED"
    if any_failures:
        return "NOT_TRADEABLE"
    return "MORE_DATA_NEEDED"


def parse_steps(log_text: str) -> list[SnapshotStep]:
    marker = ">>> STEP_START "
    lines = log_text.splitlines()
    steps: list[SnapshotStep] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith(marker):
            i += 1
            continue

        name = line[len(marker) :].strip()
        command = ""
        output_lines: list[str] = []
        exit_code: int | None = None
        i += 1
        while i < len(lines):
            current = lines[i]
            if current.startswith(">>> COMMAND "):
                command = current[len(">>> COMMAND ") :].strip()
            elif current.startswith(">>> EXIT_CODE "):
                code = current[len(">>> EXIT_CODE ") :].strip()
                try:
                    exit_code = int(code)
                except ValueError:
                    exit_code = 1
            elif current.startswith(">>> STEP_END"):
                break
            else:
                output_lines.append(current)
            i += 1
        steps.append(
            SnapshotStep(
                name=name,
                command=command,
                exit_code=exit_code if exit_code is not None else 1,
                output="\n".join(output_lines).strip(),
            )
        )
        i += 1
    return steps


def parse_metrics(steps: list[SnapshotStep]) -> SnapshotMetrics:
    simulation_ready = 0
    paper_ready = 0
    coverage_before = _find_last_kv(steps, "wallet_flow_rows", from_prefix="coverage_before")
    coverage_after = _find_last_kv(steps, "wallet_flow_rows", from_prefix="coverage_after")
    market_before = _find_last_kv(steps, "market_flow_hourly_rows", from_prefix="coverage_before")
    market_after = _find_last_kv(steps, "market_flow_hourly_rows", from_prefix="coverage_after")
    whale_before = _find_last_kv(steps, "whale_flow_hourly_rows", from_prefix="coverage_before")
    whale_after = _find_last_kv(steps, "whale_flow_hourly_rows", from_prefix="coverage_after")

    for step in steps:
        kvs = parse_key_values(step.output)
        if "simulation_ready" in kvs:
            simulation_ready = max(simulation_ready, _to_int(kvs.get("simulation_ready")))
        if "paper_ready" in kvs:
            paper_ready = max(paper_ready, _to_int(kvs.get("paper_ready")))

    return SnapshotMetrics(
        simulation_ready=simulation_ready,
        paper_ready=paper_ready,
        wallet_flow_rows_before=coverage_before,
        wallet_flow_rows_after=coverage_after,
        market_flow_rows_before=market_before,
        market_flow_rows_after=market_after,
        whale_flow_rows_before=whale_before,
        whale_flow_rows_after=whale_after,
    )


def parse_key_values(text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for line in text.splitlines():
        for key, value in re.findall(r"([A-Za-z0-9_]+)=([^\s]+)", line):
            pairs[key] = value
    return pairs


def write_summary(
    *,
    summary_path: Path,
    steps: list[SnapshotStep],
    warnings: list[str],
    metrics: SnapshotMetrics,
    status: str,
    wallet_flow_top_rejection_reasons: list[tuple[str, int]] | None = None,
) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Daily Research Snapshot",
        "",
        "**EXPLORATORY ONLY - NOT TRADEABLE.**",
        "",
        f"- status={status}",
        f"- simulation_ready={metrics.simulation_ready}",
        f"- paper_ready={metrics.paper_ready}",
        "",
        "## Wallet-Flow Coverage",
        "",
        f"- before_wallet_flow_rows={_fmt(metrics.wallet_flow_rows_before)}",
        f"- after_wallet_flow_rows={_fmt(metrics.wallet_flow_rows_after)}",
        f"- before_market_flow_hourly_rows={_fmt(metrics.market_flow_rows_before)}",
        f"- after_market_flow_hourly_rows={_fmt(metrics.market_flow_rows_after)}",
        f"- before_whale_flow_hourly_rows={_fmt(metrics.whale_flow_rows_before)}",
        f"- after_whale_flow_hourly_rows={_fmt(metrics.whale_flow_rows_after)}",
        "",
        "## Commands Run",
        "",
    ]

    for idx, step in enumerate(steps, start=1):
        lines.append(f"{idx}. `{step.command}`")
        lines.append(f"   - step={step.name} exit_code={step.exit_code}")
        extracted = _extract_row_counts(step.output)
        if extracted:
            lines.append(f"   - extracted={extracted}")

    lines.extend(["", "## Warnings", ""])
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    lines.extend(["", "## Wallet-Flow Rejection Diagnostics", ""])
    if not wallet_flow_top_rejection_reasons:
        lines.append("- top_rejection_reasons=unknown (diagnostics artifact missing)")
    else:
        for reason, count in wallet_flow_top_rejection_reasons[:3]:
            lines.append(f"- {reason}: {count}")

    lines.extend(
        [
            "",
            "## Scope Guardrails",
            "",
            "- No live execution.",
            "- No trades placed.",
            "- No API keys used.",
            "",
            "## Honest Status",
            "",
            _status_explanation(status),
        ]
    )

    summary_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a markdown summary from collection-loop logs.")
    parser.add_argument("--log-file", type=Path, required=True)
    parser.add_argument("--summary-path", type=Path, required=True)
    parser.add_argument("--warnings-file", type=Path, required=False)
    parser.add_argument(
        "--wallet-flow-rejection-csv",
        type=Path,
        required=False,
        default=Path("artifacts/research/wallet_flow_signal/wallet_flow_rejection_diagnostics.csv"),
    )
    args = parser.parse_args()

    log_text = args.log_file.read_text() if args.log_file.exists() else ""
    steps = parse_steps(log_text)
    metrics = parse_metrics(steps)
    warnings: list[str] = []
    for step in steps:
        if step.exit_code != 0:
            warnings.append(f"step_failed:{step.name}:exit_code={step.exit_code}")
        for line in step.output.splitlines():
            if "warning=" in line:
                warnings.append(line.strip())
    if args.warnings_file is not None and args.warnings_file.exists():
        for line in args.warnings_file.read_text().splitlines():
            stripped = line.strip()
            if stripped:
                warnings.append(stripped)

    status = classify_status(
        simulation_ready=metrics.simulation_ready,
        paper_ready=metrics.paper_ready,
        any_failures=any(step.exit_code != 0 for step in steps),
    )
    top_rejection_reasons = load_wallet_flow_top_rejection_reasons(
        args.wallet_flow_rejection_csv,
        limit=3,
    )
    write_summary(
        summary_path=args.summary_path,
        steps=steps,
        warnings=warnings,
        metrics=metrics,
        status=status,
        wallet_flow_top_rejection_reasons=top_rejection_reasons,
    )


def _find_last_kv(steps: list[SnapshotStep], key: str, *, from_prefix: str) -> int | None:
    for step in reversed(steps):
        for line in reversed(step.output.splitlines()):
            if not line.strip().startswith(from_prefix):
                continue
            kv = parse_key_values(line)
            if key in kv:
                return _to_int(kv[key])
    return None


def _to_int(value: str | None) -> int:
    if value is None:
        return 0
    cleaned = value.strip().replace("$", "")
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def _fmt(value: int | None) -> str:
    return str(value) if value is not None else "unknown"


def _extract_row_counts(text: str) -> str:
    keys = ("rows_written", "trade_rows", "copy_rows", "simulation_ready", "paper_ready")
    kvs = parse_key_values(text)
    parts = [f"{k}={kvs[k]}" for k in keys if k in kvs]
    return " ".join(parts)


def load_wallet_flow_top_rejection_reasons(
    path: Path,
    *,
    limit: int = 3,
) -> list[tuple[str, int]]:
    if not path.exists():
        return []
    counts: Counter[str] = Counter()
    try:
        with path.open(newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw = (row.get("rejection_reasons") or "").strip()
                if not raw:
                    continue
                for reason in raw.split(";"):
                    if reason:
                        counts[reason] += 1
    except (OSError, csv.Error):
        return []
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _status_explanation(status: str) -> str:
    if status == "PAPER_TRACKING_READY":
        return "PAPER_TRACKING_READY: at least one PAPER_READY candidate exists for ongoing paper monitoring only."
    if status == "MORE_DATA_NEEDED":
        return "MORE_DATA_NEEDED: pipeline ran, but evidence is still insufficient for paper-tracking promotion."
    return "NOT_TRADEABLE: one or more collection/research steps failed or were unavailable; do not act on signals."


if __name__ == "__main__":
    main()
