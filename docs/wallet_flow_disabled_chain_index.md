# Wallet-flow Disabled Chain Docs Index

Status: EXPLORATORY ONLY - NOT TRADEABLE

Repo path: `/Users/muhammadaatif/joint_research`

## Read order

1. `docs/wallet_flow_disabled_chain_operator_readme.md`
- Purpose: primary operator runbook for validating the full disabled wallet-flow approval chain.
- When to use it: first, before running any wallet-flow disabled-chain validation commands.
- Safety note: runbook validation is non-executing and does not authorize trading or execution.

2. `docs/wallet_flow_disabled_chain_release_notes.md`
- Purpose: concise checkpoint summary of what Phases 4.25 through 4.30 added.
- When to use it: after the operator README, to understand release-level scope and guard outcomes.
- Safety note: release notes document safety posture; they do not enable adapters or execution.

## Current disabled chain checkpoint

- Phase 4.25 disabled adapter interface
- Phase 4.26 disabled adapter run receipt
- Phase 4.27 disabled chain summary
- Phase 4.28 disabled policy guard
- Phase 4.29 operator README
- Phase 4.30 release notes

## Do not interpret this index as approval

- The index does not approve ingestion.
- The index does not approve execution.
- The index does not approve live trading.
- The index does not promote wallet-flow candidates.
- The index does not change thresholds.
- The index does not enable an adapter.
- The index does not allow orders.

## Expected safe statuses

- `adapter_status=DISABLED_BY_POLICY`
- `run_status=DISABLED_BY_POLICY_CONFIRMED`
- `chain_status=DISABLED_CHAIN_CONFIRMED`
- `guard_status=POLICY_GUARD_PASS`

`POLICY_GUARD_PASS` only confirms the disabled policy guard passed.

Warning: avoid accidental nested repo paths such as `/Users/muhammadaatif/joint_research/joint_research`.

This docs index helps operators find the disabled wallet-flow chain documentation; it does not make wallet-flow tradeable.
