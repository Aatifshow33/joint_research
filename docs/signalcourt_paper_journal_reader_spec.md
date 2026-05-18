# SignalCourt Paper Journal Reader Spec

Status: DOCS-ONLY / SPEC-ONLY (NON-EXECUTING)

## Purpose

Define a future read-only SignalCourt paper journal reader/reviewer module for local evidence inspection:

- suggested module: `src/joint_research/signalcourt/paper_journal_reader.py`
- purpose: read and review JSONL records produced by the non-executing paper journal writer
- scope: evidence review and safety diagnostics only

This spec does not authorize or implement trading, execution, ingestion, or artifact refresh.

## Input Contract

The future reader must require explicit user-provided input:

- explicit JSONL file path, or
- explicit output directory containing JSONL files

The reader must not silently or implicitly default to real artifacts. Real artifact paths may be read only when explicitly provided by the caller.

## Non-Execution and Safety Constraints

The future reader must remain strictly read-only and non-executing:

- no mutation of journal files
- no file rewrites, no in-place normalization, no journal regeneration
- no artifact refresh
- no ingestion runs
- no broker/exchange/API/LLM calls
- no paper trading or live trading authorization
- no order placement

The reader may summarize evidence but cannot upgrade readiness, override blocked statuses, or authorize execution.

## Expected Output Shape

The future reader output should include, at minimum:

- `record_count`
- `run_ids`
- `lanes_encountered`
- `final_statuses_encountered`
- `blocked_count`
- `no_trade_count` (or equivalent blocked/no-trade count field)
- `missing_safety_field_warnings`
- `malformed_jsonl_line_warnings`
- `containment_path_safety_warnings`

Optional extended fields may be added later, but core safety and blocked/no-trade reporting must remain stable.

## Safety Posture Preservation

The reader must preserve and report current blocked/research-only posture:

- wallet-flow remains `CLOSED_EXPLORATORY_ONLY` / `NO_TRADE_BLOCKED`
- derivatives-regime remains `ACTIVE_RESEARCH_WEAK` / `WATCH_ONLY_BLOCKED` or `NO_TRADE_BLOCKED`

Reader outputs can summarize these states only; they cannot promote lanes, loosen thresholds, or authorize trading decisions.

## Test-Controlled Local Scope

Until explicitly expanded in a later phase, reader usage should remain test-controlled/local-only:

- explicit local/test paths
- deterministic behavior
- no hidden side effects
- no writes outside caller-provided scope

Golden evaluations remain required for the SignalCourt safety chain.
