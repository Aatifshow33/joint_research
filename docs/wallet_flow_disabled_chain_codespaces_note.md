# Wallet-flow Disabled Chain Codespaces Operator Note

Status: EXPLORATORY ONLY - NOT TRADEABLE

This note is specific to Codespaces operator workflows and documents the safe disabled-chain validation posture without enabling any live wallet-flow execution.

## Repo paths

- Codespaces repo path: `/workspaces/joint_research`
- Local Mac repo path reference only: `/Users/muhammadaatif/joint_research`

Codespaces paths are different from local Mac paths. Operators must verify they are running in the Codespaces environment and not on a local Mac path.

## Operator safety checks

Operators must run:

- `git status -sb`

before every phase.

Unexpected dirty files must stop the phase.

Accidental `poetry.lock` should not be committed unless intentionally approved.

## Disabled policy state

Wallet-flow remains disabled by policy.

Current checkpoint:

- `c8b0865 phase 4.32: add wallet-flow disabled chain audit pack`

## Related documents

- `docs/wallet_flow_disabled_chain_operator_readme.md`
- `docs/wallet_flow_disabled_chain_release_notes.md`
- `docs/wallet_flow_disabled_chain_index.md`
- `docs/wallet_flow_disabled_chain_audit_pack.md`

## Expected safe statuses

- `adapter_status=DISABLED_BY_POLICY`
- `run_status=DISABLED_BY_POLICY_CONFIRMED`
- `chain_status=DISABLED_CHAIN_CONFIRMED`
- `guard_status=POLICY_GUARD_PASS`

`POLICY_GUARD_PASS` means disabled-policy validation only, not approval to trade.

## Do not do this in Codespaces

- Do not run ingestion.
- Do not enable adapters.
- Do not execute manifests.
- Do not place orders.
- Do not change thresholds.
- Do not promote candidates.
- Do not commit accidental environment files.

## Final safety statement

This Codespaces note helps operators keep the disabled wallet-flow chain safe in Codespaces; it does not make wallet-flow tradeable.
