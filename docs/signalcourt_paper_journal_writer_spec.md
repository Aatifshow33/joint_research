# SignalCourt Paper Journal Writer Spec

Status: DOCS-ONLY / SPEC-ONLY (NON-EXECUTING)

## 1. Purpose

Define the contract for a future SignalCourt paper journal writer that persists
paper-journal records for operator review and auditability.

This future writer is intended to:

- persist deterministic SignalCourt paper journal entries for later review
- improve auditability and paper-validation workflows
- remain non-executing and never place trades

This phase does not implement any writer behavior.

## 2. Proposed Future Output Path

Proposed base path for future writer output:

- `artifacts/signalcourt/paper_journal/`

Future file and run-directory naming must be deterministic, collision-safe, and
easy to audit.

No file writes happen in this phase.

## 3. Required Future Writer Inputs

Minimum required future inputs:

- `PaperJournalEntry`
- `SignalCourtTrace`
- `SignalCourtPipelineSnapshot` or equivalent dashboard lane context
- run metadata:
  - deterministic run id
  - generated timestamp (UTC)
  - lane and signal identifiers
  - source commit/version metadata when available

## 4. Required Future Output Formats

First implementation phase should support:

- JSONL for machine-readable decision and audit logs
- Markdown operator summary as optional later output
- no database writes in first writer phase

## 5. Required Safety Constraints

Future writer must never:

- place trades
- call exchange or broker APIs
- mutate research artifacts
- refresh ingestion or rerun research
- alter wallet-flow or derivatives-regime artifacts
- mark any lane/candidate as tradeable

Future writer must always:

- preserve non-authorization notices from upstream SignalCourt objects
- preserve blocked/no-trade statuses exactly as produced upstream

## 6. Required Validation Gates Before Implementation

Before implementing the writer, the following gates must pass:

- `tests/test_signalcourt_golden_evaluations.py`
- `tests/test_signalcourt_dashboard_cli.py`
- `tests/test_signalcourt_trace.py`

Future writer tests must also prove:

- no unrelated artifacts are modified
- blocked lanes remain blocked
- no execution permission surfaces are introduced

## 7. Future Acceptance Criteria

Writer implementation is acceptable only if it provides:

- deterministic output content and ordering
- atomic/safe write behavior
- append-only behavior or explicitly versioned immutable run directories
- no execution permissions or execution side effects
- explicit blocked/no-trade status in every written entry

## 8. Explicit Non-Authorization Statement

This spec does not authorize paper trading, live trading, order placement,
ingestion, candidate promotion, or execution.
