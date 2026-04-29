#!/usr/bin/env bash

set -u -o pipefail

DRY_RUN=0
STAGE="stage_1_quick"
LIMIT_MARKETS="75"
LIMIT_EVENTS="2000"
MIN_VOLUME="0"
START_WINDOW="-7d"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --stage)
      STAGE="${2:-}"
      shift 2
      ;;
    --limit-markets)
      LIMIT_MARKETS="${2:-}"
      shift 2
      ;;
    --limit-events)
      LIMIT_EVENTS="${2:-}"
      shift 2
      ;;
    --min-volume)
      MIN_VOLUME="${2:-}"
      shift 2
      ;;
    --start-window)
      START_WINDOW="${2:-}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ ! -d ".venv" ]]; then
  echo "missing .venv. run: python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]" >&2
  exit 2
fi

source .venv/bin/activate

TIMESTAMP_UTC="$(date -u +"%Y-%m-%dT%H%M%SZ")"
SNAPSHOT_DIR="artifacts/ops/snapshots"
SUMMARY_PATH="${SNAPSHOT_DIR}/${TIMESTAMP_UTC}_summary.md"
LOG_PATH="${SNAPSHOT_DIR}/${TIMESTAMP_UTC}_commands.log"
WARNINGS_PATH="${SNAPSHOT_DIR}/${TIMESTAMP_UTC}_warnings.log"
mkdir -p "${SNAPSHOT_DIR}"
: > "${LOG_PATH}"
: > "${WARNINGS_PATH}"

append_warning() {
  local msg="$1"
  echo "$msg" | tee -a "${WARNINGS_PATH}" >/dev/null
}

run_step() {
  local step_name="$1"
  shift
  local cmd="$*"

  {
    echo ">>> STEP_START ${step_name}"
    echo ">>> COMMAND ${cmd}"
  } >> "${LOG_PATH}"

  echo "[step:${step_name}] ${cmd}"

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    echo "DRY_RUN_SKIPPED" | tee -a "${LOG_PATH}" >/dev/null
    echo ">>> EXIT_CODE 0" >> "${LOG_PATH}"
    echo ">>> STEP_END" >> "${LOG_PATH}"
    return 0
  fi

  local output
  output="$($cmd 2>&1)"
  local code=$?

  if [[ -n "${output}" ]]; then
    echo "${output}" | tee -a "${LOG_PATH}" >/dev/null
  fi
  echo ">>> EXIT_CODE ${code}" >> "${LOG_PATH}"
  echo ">>> STEP_END" >> "${LOG_PATH}"

  if [[ ${code} -ne 0 ]]; then
    append_warning "step_failed:${step_name}:exit_code=${code}"
    echo "[warning] ${step_name} failed with exit code ${code}" >&2
  fi
  return 0
}

run_step "crypto_ohlcv_btc" "joint-research ingest crypto-ohlcv --symbol BTCUSDT --interval 1h --start ${START_WINDOW}"
run_step "crypto_ohlcv_eth" "joint-research ingest crypto-ohlcv --symbol ETHUSDT --interval 1h --start ${START_WINDOW}"
run_step "crypto_ohlcv_sol" "joint-research ingest crypto-ohlcv --symbol SOLUSDT --interval 1h --start ${START_WINDOW}"
run_step "crypto_ohlcv_xrp" "joint-research ingest crypto-ohlcv --symbol XRPUSDT --interval 1h --start ${START_WINDOW}"
run_step "polymarket_crypto_markets" "joint-research ingest gamma-crypto-markets --limit 500"
run_step "polymarket_prices" "joint-research ingest polymarket-prices --top-n 150 --interval 1m --fidelity-minutes 60 --include-closed"
run_step "crypto_derivatives" "joint-research ingest crypto-derivatives --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT --limit 24"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  run_step "wallet_flow_backfill_plan" "joint-research ingest wallet-flow-backfill-plan --stage ${STAGE} --dry-run --limit-markets ${LIMIT_MARKETS} --limit-events ${LIMIT_EVENTS} --min-volume ${MIN_VOLUME}"
else
  run_step "wallet_flow_backfill_plan" "joint-research ingest wallet-flow-backfill-plan --stage ${STAGE} --execute --limit-markets ${LIMIT_MARKETS} --limit-events ${LIMIT_EVENTS} --min-volume ${MIN_VOLUME}"
fi

run_step "research_wallet_flow_signal" "joint-research research wallet-flow-signal"
run_step "research_simulate_wallet_flow" "joint-research research simulate --candidate-source wallet-flow-signal"

python -m joint_research.ops.collection_snapshot \
  --log-file "${LOG_PATH}" \
  --summary-path "${SUMMARY_PATH}" \
  --warnings-file "${WARNINGS_PATH}"

echo "snapshot_summary=${SUMMARY_PATH}"
echo "snapshot_log=${LOG_PATH}"
echo "snapshot_warnings=${WARNINGS_PATH}"
