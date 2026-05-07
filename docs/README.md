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
