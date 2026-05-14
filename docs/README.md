# Wallet-flow Disabled Chain Documentation

Status: EXPLORATORY ONLY - NOT TRADEABLE

Codespaces repo path: /workspaces/joint_research
Local Mac repo path reference: /Users/muhammadaatif/joint_research
Current checkpoint: bf3373c phase 4.34: add wallet-flow disabled docs manifest
Primary manifest pointer: docs/wallet_flow_disabled_chain_docs_manifest.md

Wallet-flow artifact guard pointer: Phase 4.55 added the read-only static regression guard `tests/test_wallet_flow_artifact_closeout_guard.py`, and Phase 4.56/4.57 anchored its closeout chain in `docs/wallet_flow_disabled_chain_docs_manifest.md`. Wallet-flow remains EXPLORATORY ONLY - NOT TRADEABLE, and this guard protects against accidental promotion from artifact drift. This pointer does not authorize ingestion, paper trading, live trading, threshold loosening, or candidate promotion.

Derivatives-regime triage guard pointer: With wallet-flow closed as EXPLORATORY ONLY - NOT TRADEABLE, derivatives-regime is the next research lane. Phase 4.60 added the read-only static triage guard `tests/test_derivatives_regime_artifact_triage_guard.py`, which checks committed derivatives-regime artifacts and counts/reviews grades without promoting candidates. This guard does not authorize ingestion, artifact refresh, paper trading, live trading, threshold loosening, or candidate promotion.

Phase 4.62 closeout note: Phase 4.60 added the read-only static triage guard, and Phase 4.61 linked it from `docs/README.md`. Derivatives-regime is the active next research lane after wallet-flow was closed exploratory-only. The guard checks committed derivatives-regime artifacts and reviews/counts grades without promotion. This closeout chain does not authorize ingestion, artifact refresh, paper trading, live trading, threshold loosening, or candidate promotion.

Derivatives-regime evidence plan pointer: Phase 4.64 added `docs/derivatives_regime_evidence_strengthening_plan.md` as a docs-only, diagnostics-only follow-on to the Phase 4.63 artifact review. This plan targets sample sufficiency gaps, train/test direction mismatch, and insufficient strength/stability for promotion. It does not authorize ingestion, artifact refresh, paper trading, live trading, threshold loosening, or candidate promotion.

Derivatives-regime diagnostics spec pointer: Phase 4.66 added `docs/derivatives_regime_diagnostics_spec.md` as a docs-only, non-executing specification for a future read-only diagnostics implementation. It follows the Phase 4.64 evidence-strengthening plan and defines diagnostics coverage plus schema contracts for future outputs. This spec does not authorize ingestion, artifact refresh, rerunning research, paper trading, live trading, threshold loosening, or candidate promotion.

Phase 4.68 closeout note: Phase 4.66 added the diagnostics spec, and Phase 4.67 linked it from `docs/README.md`. This chain is docs-only and non-executing, and it prepares future read-only diagnostics only. It does not authorize ingestion, artifact refresh, rerunning research, paper trading, live trading, threshold loosening, or candidate promotion.

Derivatives-regime diagnostics implementation plan pointer: Phase 4.69 added `docs/derivatives_regime_diagnostics_implementation_plan.md` as a docs-only/planning-only step. It follows the Phase 4.66 diagnostics spec and Phase 4.68 closeout, and prepares a future read-only implementation only. It does not authorize ingestion, artifact refresh, rerunning research, diagnostics artifact creation in this phase, paper/live trading, threshold loosening, or candidate promotion.

Phase 4.71 closeout note: Phase 4.69 added the diagnostics implementation plan, and Phase 4.70 linked it from `docs/README.md`. This chain is docs-only/planning-only and prepares future read-only diagnostics implementation only. It does not authorize ingestion, artifact refresh, rerunning research, diagnostics artifact creation in this phase, paper trading, live trading, threshold loosening, or candidate promotion.

Supporting docs:
- docs/wallet_flow_disabled_chain_index.md
- docs/wallet_flow_disabled_chain_operator_readme.md
- docs/wallet_flow_disabled_chain_release_notes.md
- docs/wallet_flow_disabled_chain_audit_pack.md
- docs/wallet_flow_disabled_chain_codespaces_note.md

Phase 4.49 schema contract: `src/joint_research/wallet_flow_coverage_schema_contract.py` (static documentation/supporting code only, `CoverageArtifactSchema`, `COVERAGE_ARTIFACT_SCHEMAS`). See `docs/wallet_flow_static_coverage_schema_validation_tests.md` and `docs/wallet_flow_static_coverage_diagnostic_artifact_spec.md`. Does not write artifacts, run ingestion, rerun research, promote candidates, or make wallet-flow tradeable. **EXPLORATORY ONLY - NOT TRADEABLE**

`POLICY_GUARD_PASS` means disabled-policy validation only, not approval to trade.

This root pointer does not approve ingestion.
This root pointer does not approve execution.
This root pointer does not approve live trading.
This root pointer does not promote wallet-flow candidates.
This root pointer does not change thresholds.
This root pointer does not enable adapters.
This root pointer does not allow orders.

Codespaces hygiene:
- Run `git status -sb` before every phase.
- Stop on unexpected dirty files.
- Do not commit accidental `poetry.lock`.
- Do not commit accidental environment files.

This root pointer helps operators find the disabled wallet-flow documentation chain; it does not make wallet-flow tradeable.

## SignalCourt Dashboard Summary CLI Pointer (Phase 4.85)

Use the local preview command:

`.venv/bin/joint-research signalcourt dashboard-summary`

This command is stdout-only and prints the in-memory SignalCourt dashboard summary. It shows the wallet-flow and derivatives-regime lanes and currently reports a research-only/blocked posture:

- `Any Order Allowed: false`
- `Paper Orders Allowed Count: 0`
- `Live Orders Allowed Count: 0`

This preview does not authorize ingestion, candidate promotion, paper trading, live trading, or execution.

Phase 4.86 closeout note: Phase 4.84 added the local `signalcourt dashboard-summary` CLI, and Phase 4.85 documented `.venv/bin/joint-research signalcourt dashboard-summary` in this README. This chain is preview-only and stdout-only, does not write artifacts or journals, and does not authorize ingestion, candidate promotion, paper trading, live trading, or execution. Current wallet-flow and derivatives-regime lanes remain blocked and research-only.

## SignalCourt Trace Schema Pointer (Phase 4.88)

Phase 4.87 added the in-memory SignalCourt trace schema:

- `SignalCourtTraceStep`
- `SignalCourtTrace`
- `build_trace_from_pipeline_result(...)`
- `trace_allows_order(...)`

The trace captures current pipeline stages for future observability/audit review:
`readiness`, `passport`, `verdict`, `trade_decision`, `paper_decision`, `risk_gate`, and `paper_journal`.

This layer is read-only and in-memory only. It does not write trace files, journals, or artifacts, and it does not authorize ingestion, candidate promotion, paper trading, live trading, or execution. Current wallet-flow and derivatives-regime lanes remain blocked and research-only.

Phase 4.89 closeout note: Phase 4.87 added the in-memory SignalCourt trace schema, and Phase 4.88 documented that schema in `docs/README.md`. This chain supports future observability/audit review while remaining read-only and in-memory only. It does not write trace files, journals, or artifacts, and it does not authorize ingestion, candidate promotion, paper trading, live trading, or execution. Current wallet-flow and derivatives-regime lanes remain blocked and research-only.

## SignalCourt Golden Evaluations Pointer (Phase 4.91)

Phase 4.90 added golden evaluation regression tests in `tests/test_signalcourt_golden_evaluations.py`. These tests protect against accidental promotion of weak/research-only lanes by asserting the current wallet-flow and derivatives-regime lanes remain blocked, no executable paper/live actions (`PAPER_ENTER`, `PAPER_EXIT`, `LIVE_REVIEW_REQUIRED`, `LIVE_ENTER`) are emitted, and no lane allows order execution. The suite also locks in blocked dashboard posture (`Any Order Allowed: false` with zero paper/live order counts) and preserves non-authorization boundaries.

This regression layer supports future changes to journal writers, connectors, equity lanes, and broker adapters while keeping current safety behavior deterministic. It does not authorize ingestion, candidate promotion, paper trading, live trading, or execution.

Phase 4.92 closeout note: Phase 4.90 added golden evaluation regression tests, and Phase 4.91 documented that suite in `docs/README.md`. This chain protects against accidental promotion/execution regressions while supporting future journal writers, connectors, equity lanes, broker adapters, and paper/live execution work. It does not authorize ingestion, candidate promotion, paper trading, live trading, or execution. Current wallet-flow and derivatives-regime lanes remain blocked and research-only.

## SignalCourt Paper Journal Writer Spec Pointer (Phase 4.94)

Phase 4.93 added the docs-only paper journal writer spec:
`docs/signalcourt_paper_journal_writer_spec.md`.

The spec defines the future persistence contract for SignalCourt paper journal entries, including JSONL output and optional Markdown summaries in a later implementation phase, with safe/atomic deterministic write requirements.

No journal writer is implemented in the current phase, and no files are written by this pointer/spec phase. This chain does not authorize ingestion, candidate promotion, paper trading, live trading, order placement, or execution. Golden evaluations must remain passing before any writer implementation work begins.

Phase 4.95 closeout note: Phase 4.93 added the docs-only SignalCourt paper journal writer spec, and Phase 4.94 documented the spec pointer in `docs/README.md`. This chain prepares future journal persistence without implementing file writing today. Future writer implementation must preserve deterministic, safe, atomic/append-only behavior, and golden evaluations must remain passing before implementation. This chain does not authorize ingestion, candidate promotion, paper trading, live trading, order placement, or execution. Current wallet-flow and derivatives-regime lanes remain blocked and research-only.

## SignalCourt Paper Journal Writer Test Plan Pointer (Phase 4.97)

Phase 4.96 added the docs-only paper journal writer test plan:
`docs/signalcourt_paper_journal_writer_test_plan.md`.

The plan defines required validation before any writer implementation, including golden evaluations as a precondition, writer tests that prove no unrelated artifacts are modified, and writer tests that prove blocked lanes remain blocked.

This pointer does not authorize ingestion, candidate promotion, paper trading, live trading, order placement, or execution.

Phase 4.98 closeout note: Phase 4.96 added the docs-only paper journal writer test plan, and Phase 4.97 documented that pointer in `docs/README.md`. This chain prepares future writer implementation without implementing file writing today. Future writer work must preserve golden evaluations, protected artifact safety, deterministic output, and blocked-lane behavior. This chain does not authorize ingestion, candidate promotion, paper trading, live trading, order placement, or execution. Current wallet-flow and derivatives-regime lanes remain blocked and research-only.

## SignalCourt Paper Journal Writer Skeleton Pointer (Phase 5.00)

Phase 4.99 added the non-executing SignalCourt paper journal writer skeleton:
`src/joint_research/signalcourt/paper_journal_writer.py`.

The writer requires an explicit `output_dir` and is test-controlled/isolated by design. It writes deterministic JSONL output only under the provided output directory and does not write to real artifacts by default.

This writer skeleton does not execute trades, does not call brokers, exchanges, LLMs, or external APIs, and does not mutate research artifacts. It does not authorize paper trading, live trading, or order placement.

Current safety posture remains unchanged:

- wallet-flow remains `CLOSED_EXPLORATORY_ONLY` / `NO_TRADE_BLOCKED`
- derivatives-regime remains `ACTIVE_RESEARCH_WEAK` / `WATCH_ONLY_BLOCKED` or `NO_TRADE_BLOCKED`

Golden evaluations must remain passing for this chain.

Phase 5.01 closeout note: Phase 5.00 added the `docs/README.md` pointer for the non-executing SignalCourt paper journal writer skeleton (`e960e80`), and the closeout note for that docs-pointer chain is recorded in `docs/signalcourt_paper_journal_writer_docs_pointer_closeout.md`. This chain remains docs-only/non-executing and does not authorize ingestion, candidate promotion, paper trading, live trading, order placement, or execution. Current wallet-flow and derivatives-regime lanes remain blocked and research-only, and golden evaluations remain required.

Phase 5.03 closeout note: Phase 5.02 (`53fd96b`) added the writer isolation regression guard `tests/test_signalcourt_paper_journal_writer_isolation.py`, and this closeout note is recorded in `docs/signalcourt_paper_journal_writer_isolation_guard_closeout.md`. The guard verifies no default pipeline/CLI wiring to the writer, no default SignalCourt paper journal artifact writes, explicit `output_dir` enforcement, blocked/research-only wallet-flow and derivatives-regime posture, and no executable paper/live permissions or actions. Current safety posture remains unchanged, and golden evaluations remain required.
