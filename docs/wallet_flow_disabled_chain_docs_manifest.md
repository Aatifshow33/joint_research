# Wallet-flow Disabled Chain Docs Manifest

Status: EXPLORATORY ONLY - NOT TRADEABLE

Codespaces repo path: `/workspaces/joint_research`

Local Mac repo path reference: `/Users/muhammadaatif/joint_research`

Current checkpoint: `eeea51e phase 4.33: add wallet-flow Codespaces operator note`

## Purpose

This manifest is a navigation map for the disabled-chain documentation artifacts only. It lists every wallet-flow disabled-chain doc, its purpose, when operators should use it, and the safe boundaries that apply. This manifest does not enable trading, approve execution, or override the disabled policy.

## Manifest entries

### docs/wallet_flow_disabled_chain_index.md

Purpose: Concise checkpoint summary of what Phases 4.25 through 4.31 added.

Use when: Starting disabled-chain validation work; read this first to understand release scope and guard outcomes.

Safety note: Index documents safety posture and checkpoints; it does not enable adapters or execution.

### docs/wallet_flow_disabled_chain_operator_readme.md

Purpose: Primary operator runbook for validating the full disabled wallet-flow approval chain.

Use when: Ready to perform end-to-end validation; this doc lists the full non-executing command chain and expected success outcomes.

Safety note: Runbook validation is non-executing and does not authorize trading or execution.

### docs/wallet_flow_disabled_chain_release_notes.md

Purpose: Detailed breakdown of what each phase added and the safety boundaries that apply.

Use when: Understanding the incremental scope and release-level safety decisions.

Safety note: Release notes document safety posture; they do not enable execution or override disabled policy.

### docs/wallet_flow_disabled_chain_audit_pack.md

Purpose: Compact checklist for reviewers verifying disabled-chain docs are complete and guarded.

Use when: reviewing disabled-chain work for consistency and non-execution posture.

Safety note: Audit pack is a review aid only; it does not authorize ingestion or execution.

### docs/wallet_flow_disabled_chain_codespaces_note.md

Purpose: Codespaces-specific operator hygiene and safety checks.

Use when: Running disabled-chain validation in Codespaces; this doc clarifies Codespaces paths vs. local Mac paths.

Safety note: Codespaces note is a path and hygiene guide only; it does not make wallet-flow tradeable.

## Required read order

1. docs/wallet_flow_disabled_chain_index.md
2. docs/wallet_flow_disabled_chain_operator_readme.md
3. docs/wallet_flow_disabled_chain_release_notes.md
4. docs/wallet_flow_disabled_chain_audit_pack.md
5. docs/wallet_flow_disabled_chain_codespaces_note.md

## Expected safe statuses

These statuses confirm disabled-chain validation passed and no execution was enabled:

- `adapter_status=DISABLED_BY_POLICY`
- `run_status=DISABLED_BY_POLICY_CONFIRMED`
- `chain_status=DISABLED_CHAIN_CONFIRMED`
- `guard_status=POLICY_GUARD_PASS`

`POLICY_GUARD_PASS` means disabled-policy validation only, not approval to trade.

## Manifest boundaries

This manifest does not approve ingestion.

This manifest does not approve execution.

This manifest does not approve live trading.

This manifest does not promote wallet-flow candidates.

This manifest does not change thresholds.

This manifest does not enable adapters.

This manifest does not allow orders.

## Codespaces hygiene

Run `git status -sb` before every phase.

Stop on unexpected dirty files.

Do not commit accidental `poetry.lock`.

Do not commit accidental environment files.

## Final safety statement

This docs manifest helps operators navigate the disabled wallet-flow documentation chain; it does not make wallet-flow tradeable.
