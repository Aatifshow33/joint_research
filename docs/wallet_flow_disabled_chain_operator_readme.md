# Wallet-flow Disabled Chain Operator README

Status: EXPLORATORY ONLY - NOT TRADEABLE

This README defines the human review path for wallet-flow approval artifacts and the disabled adapter chain. It documents a non-executing verification workflow only, so operators can validate consistency and policy boundaries without enabling ingestion, execution, trading, orders, or any live adapter behavior.

## Hard boundaries

- No candidates promoted.
- No threshold changes.
- No live trading changes.
- No ingestion executed by these approval artifacts.
- No manifest commands executed.
- No live execution adapter enabled.
- No orders placed.
- Adapter remains disabled by policy.

## Artifact chain overview

| Artifact | Purpose | Input(s) | Output(s) | Success status | Safety boundary |
|---|---|---|---|---|---|
| wallet_flow_backfill_execution_manifest | Build review-only backfill manifest rows. | Backfill planning outputs and CLI options. | `wallet_flow_backfill_execution_manifest.md/.csv/.json` | `dry_run=True` with manifest rows generated. | Manifest is review-oriented only; no ingestion execution is performed. |
| wallet_flow_manifest_review_gate | Enforce manifest policy gate before any approval artifacts. | `wallet_flow_backfill_execution_manifest.json` | `wallet_flow_manifest_review_gate.md` | `gate_status=PASS` | Gate checks formatting/policy only; does not execute any manifest command. |
| wallet_flow_approved_manifest_packet | Export deterministic approved packet after gate review. | Manifest JSON + review gate report. | `wallet_flow_approved_manifest_packet.md/.json` | `export_status=PASS` | Packet creation is metadata export only; no execution side effects. |
| wallet_flow_manifest_audit_index | Index report presence/hash and summarize review chain inputs. | Coverage/priority/batch/manifest/review/approved reports and JSONs (if present). | `wallet_flow_manifest_audit_index.md/.json` | `audit_status=READY` | Read-only inventory and checksums only. |
| wallet_flow_dry_run_execution_plan | Render preview-only planned rows from approved artifacts. | Manifest JSON + approved packet JSON + audit index JSON. | `wallet_flow_dry_run_execution_plan.md/.json` | `plan_status=READY` | Dry-run preview only; no commands are run. |
| wallet_flow_guarded_operator_handoff | Create manual approval boundary for operator review. | Dry-run plan JSON + approved packet JSON + audit index JSON. | `wallet_flow_guarded_operator_handoff.md/.json` | `handoff_status=READY_FOR_MANUAL_APPROVAL` | Manual-review artifact only; no execution path is enabled. |
| wallet_flow_operator_approval_ledger | Record manual operator decision locally. | Guarded handoff JSON + decision metadata. | `wallet_flow_operator_approval_ledger.md/.json` | `ledger_status=APPROVED` or `PENDING_MANUAL_REVIEW` | Decision logging only; no execution authorization implied. |
| wallet_flow_approval_execution_contract | Define future adapter contract requirements without execution. | Approval ledger JSON + handoff JSON + dry-run plan JSON. | `wallet_flow_approval_execution_contract.md/.json` | `contract_status=CONTRACT_READY` | Contract artifact only; no live adapter code or command execution. |
| wallet_flow_contract_audit_receipt | Verify contract consistency against upstream artifacts. | Contract JSON + ledger/handoff/plan/packet/audit JSONs. | `wallet_flow_contract_audit_receipt.md/.json` | `receipt_status=RECEIPT_READY` | Consistency receipt only; no ingestion/execution behavior. |
| wallet_flow_disabled_adapter_interface | Return deterministic disabled adapter response surface. | Contract audit receipt JSON. | `wallet_flow_disabled_adapter_interface.md/.json` | `adapter_status=DISABLED_BY_POLICY` | Adapter remains hard-disabled; execution/network/order methods forbidden. |
| wallet_flow_disabled_adapter_run_receipt | Prove disabled adapter invocation stayed non-executing. | Disabled adapter interface JSON. | `wallet_flow_disabled_adapter_run_receipt.md/.json` | `run_status=DISABLED_BY_POLICY_CONFIRMED` | Confirms disabled result only; no commands executed. |
| wallet_flow_disabled_chain_summary | Summarize full disabled chain and consistency checks. | Contract JSON + receipt JSON + disabled interface JSON + disabled run receipt JSON. | `wallet_flow_disabled_chain_summary.md/.json` | `chain_status=DISABLED_CHAIN_CONFIRMED` | Consolidated read-only summary; chain remains non-executing. |
| wallet_flow_disabled_policy_guard | Regression guard to confirm disabled policy cannot drift executable. | Disabled chain summary JSON. | `wallet_flow_disabled_policy_guard.md/.json` | `guard_status=POLICY_GUARD_PASS` | Policy verification only; execution remains impossible by policy. |

## Non-executing validation command chain

Run from the exact repo path: `/Users/muhammadaatif/joint_research`

```bash
.venv/bin/joint-research research wallet-flow-backfill-manifest --command-template-preset review_echo
.venv/bin/joint-research research wallet-flow-manifest-review-gate
.venv/bin/joint-research research wallet-flow-approved-manifest-packet
.venv/bin/joint-research research wallet-flow-manifest-audit-index
.venv/bin/joint-research research wallet-flow-dry-run-execution-planner
.venv/bin/joint-research research wallet-flow-guarded-operator-handoff
.venv/bin/joint-research research wallet-flow-operator-approval-ledger --decision approve --reviewer "manual-operator" --review-note "Operator README disabled chain validation only"
.venv/bin/joint-research research wallet-flow-approval-execution-contract
.venv/bin/joint-research research wallet-flow-contract-audit-receipt
.venv/bin/joint-research research wallet-flow-disabled-adapter-interface
.venv/bin/joint-research research wallet-flow-disabled-adapter-run-receipt
.venv/bin/joint-research research wallet-flow-disabled-chain-summary
.venv/bin/joint-research research wallet-flow-disabled-policy-guard
```

## Expected success lines

- `ledger_status=APPROVED`
- `contract_status=CONTRACT_READY`
- `receipt_status=RECEIPT_READY`
- `adapter_status=DISABLED_BY_POLICY`
- `run_status=DISABLED_BY_POLICY_CONFIRMED`
- `chain_status=DISABLED_CHAIN_CONFIRMED`
- `guard_status=POLICY_GUARD_PASS`
- `adapter_enabled=false`
- `execution_enabled=false`
- `network_enabled=false`
- `ingestion_enabled=false`
- `shell_enabled=false`
- `order_placement_enabled=false`
- `database_mutation_enabled=false`

## Cleanup command

```bash
rm -f \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_backfill_execution_manifest.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_backfill_execution_manifest.csv \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_backfill_execution_manifest.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_manifest_review_gate.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approved_manifest_packet.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approved_manifest_packet.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_manifest_audit_index.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_manifest_audit_index.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_dry_run_execution_plan.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_dry_run_execution_plan.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_guarded_operator_handoff.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_guarded_operator_handoff.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_operator_approval_ledger.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_operator_approval_ledger.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approval_execution_contract.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_approval_execution_contract.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_contract_audit_receipt.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_contract_audit_receipt.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_adapter_interface.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_adapter_interface.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_adapter_run_receipt.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_adapter_run_receipt.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_chain_summary.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_chain_summary.json \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_policy_guard.md \
  artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_disabled_policy_guard.json
```

## Operator decision matrix

- `PENDING_MANUAL_REVIEW` or `AWAITING_APPROVAL`: stop.
- `REJECTED`: stop.
- `BLOCKED`: stop and inspect `warnings` / `block_reasons`.
- `POLICY_GUARD_PASS`: disabled chain validation passed only; it does not authorize execution.

## Common mistakes

- Treating approved ledger as permission to trade.
- Treating dry-run plan commands as executable.
- Committing generated artifacts.
- Running from the wrong repo path.
- Using nested accidental repo paths such as `/Users/muhammadaatif/joint_research/joint_research`.

## Recovery checklist

- Check repo path with `pwd`.
- Check branch with `git status -sb`.
- Remove accidental nested `joint_research/` directory only after verifying it is accidental.
- Clean generated artifacts.
- Rerun tests.

This chain proves the wallet-flow path remains disabled by policy; it does not make wallet-flow tradeable.
