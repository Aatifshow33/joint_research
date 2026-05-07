# Wallet-flow Disabled Chain Documentation

Status: EXPLORATORY ONLY - NOT TRADEABLE

Codespaces repo path: /workspaces/joint_research
Local Mac repo path reference: /Users/muhammadaatif/joint_research
Current checkpoint: bf3373c phase 4.34: add wallet-flow disabled docs manifest
Primary manifest pointer: docs/wallet_flow_disabled_chain_docs_manifest.md

Wallet-flow artifact guard pointer: Phase 4.55 added the read-only static regression guard `tests/test_wallet_flow_artifact_closeout_guard.py`, and Phase 4.56/4.57 anchored its closeout chain in `docs/wallet_flow_disabled_chain_docs_manifest.md`. Wallet-flow remains EXPLORATORY ONLY - NOT TRADEABLE, and this guard protects against accidental promotion from artifact drift. This pointer does not authorize ingestion, paper trading, live trading, threshold loosening, or candidate promotion.

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
