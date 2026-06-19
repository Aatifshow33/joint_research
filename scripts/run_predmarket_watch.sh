#!/bin/bash
# Continuous cross-venue arbitrage watch — one pass per invocation.
#
# Runs the predmarket-arb watch CLI against live Kalshi + Polymarket using the
# verified watchlist, appends opportunities to the alert log, records a run-line
# summary, and fires a macOS notification when a VERIFIED actionable arb appears.
#
# Scheduled by ~/Library/LaunchAgents/com.joint-research.predmarket-watch.plist.

set -uo pipefail

REPO="/Users/muhammadaatif/joint_research"
PY="$REPO/.venv/bin/python"
ART="$REPO/artifacts/research/predmarket_arb"
RUN_LOG="$ART/watch_runs.log"
ALERTS="$ART/alerts.jsonl"

cd "$REPO" || exit 1
mkdir -p "$ART"

OUT="$("$PY" -m joint_research.predmarket_arb.cli watch \
  --watchlist "$REPO/config/predmarket_arb_watchlist.json" \
  --bankroll 200 --min-profit 0.25 --refine-top-n 8 \
  --alert-log "$ALERTS" --iterations 1 2>&1)"

STAMP="$(date '+%Y-%m-%d %H:%M:%S')"
SUMMARY="$(printf '%s\n' "$OUT" | grep -E 'pass 1/1' | head -1)"
printf '%s | %s\n' "$STAMP" "${SUMMARY:-no-summary}" >> "$RUN_LOG"

# Notify only on VERIFIED (trusted-resolution) actionable opportunities.
# Exclude UNVERIFIED first — it contains the substring "VERIFIED".
VERIFIED_LINES="$(printf '%s\n' "$OUT" | grep 'VERIFIED' | grep -v 'UNVERIFIED' || true)"
if [ -n "$VERIFIED_LINES" ]; then
  MSG="$(printf '%s\n' "$VERIFIED_LINES" | head -1 | cut -c1-180)"
  /usr/bin/osascript -e "display notification \"${MSG//\"/}\" with title \"Arb opportunity (verified)\" sound name \"Glass\"" 2>/dev/null || true
  printf '%s | ALERT | %s\n' "$STAMP" "$MSG" >> "$RUN_LOG"
fi
