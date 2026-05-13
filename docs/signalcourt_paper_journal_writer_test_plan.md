# SignalCourt Paper Journal Writer Test Plan

Status: DOCS-ONLY / TEST-PLAN-ONLY (NON-EXECUTING)

## 1. Golden Safety Precondition

Before any writer implementation begins, this gate must pass:

- `tests/test_signalcourt_golden_evaluations.py`

Writer work is blocked until this precondition remains green.

## 2. Writer Output Behavior

Future implementation tests must enforce:

- writer output is restricted to `artifacts/signalcourt/paper_journal/`
- JSONL decision logs are deterministic in content and ordering
- optional Markdown operator summary is deterministic when enabled
- no writes occur outside the allowed output directory

## 3. No-Execution Guarantees

Future implementation tests must prove the writer:

- does not place trades
- does not call broker or exchange APIs
- does not mutate readiness/passport/verdict/decision/risk objects
- does not convert blocked lanes into allowed/executable lanes

## 4. Artifact Safety

Future implementation tests must prove the writer:

- does not modify wallet-flow artifacts
- does not modify derivatives-regime artifacts
- does not refresh ingestion
- does not rerun research

Tests should snapshot protected paths before and after writer runs.

## 5. Atomic/Safe Writes

Future implementation tests should validate:

- temp-file writes followed by atomic replace semantics
- repeated writes are deterministic or versioned safely
- partial/interrupted writes do not leave corrupted journal records

## 6. Expected Current-Lane Entries

Given current committed posture, future writer tests must assert:

- wallet-flow final status remains `NO_TRADE_BLOCKED`
- derivatives-regime final status remains `WATCH_ONLY_BLOCKED` or `NO_TRADE_BLOCKED`
- `paper_order_allowed` remains `false`
- `live_order_allowed` remains `false`
- non-authorization notice is present in every written entry

## 7. Validation Commands for Future Implementation

At minimum, future writer implementation work should validate:

- writer unit tests (new writer-specific test module)
- `tests/test_signalcourt_golden_evaluations.py`
- `tests/test_signalcourt_dashboard_cli.py`
- `tests/test_signalcourt_trace.py`

## 8. Explicit Non-Authorization Statement

This test plan does not authorize paper trading, live trading, order placement,
ingestion, candidate promotion, or execution.
