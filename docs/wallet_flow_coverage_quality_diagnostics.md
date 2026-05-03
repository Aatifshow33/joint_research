# Wallet-flow Coverage Quality Diagnostics

Status: EXPLORATORY ONLY - NOT TRADEABLE

Codespaces repo path:
/workspaces/joint_research

Local Mac repo path reference:
/Users/muhammadaatif/joint_research

Current checkpoint:
65efd05 phase 4.38: add wallet-flow final freeze checklist

This document defines coverage-quality diagnostics needed before any future wallet-flow threshold or promotion review. It establishes what evidence strength is required to trust wallet-flow research results.

This diagnostic plan does not promote wallet-flow candidates.

This diagnostic plan does not change thresholds.

This diagnostic plan does not approve ingestion, execution, live trading, adapters, manifests, orders, or database mutation.

## Why coverage quality comes next

- The disabled-chain documentation package is frozen enough for now.
- Wallet-flow research usefulness is still unproven.
- The latest known result had zero candidates beyond rejected.
- insufficient_unique_flow_hours was one of the largest rejection bottlenecks.
- Coverage quality must be measured before debating thresholds.

## Latest known outcome snapshot

- SIMULATION_READY: 0
- WATCHLIST: 0
- WEAK: 0
- REJECTED: 1049
- No wallet-flow candidate survived beyond REJECTED.

## Coverage-related bottleneck context

- insufficient_unique_flow_hours: 4993
- insufficient_unique_flow_hours means the flow sample is too thin, repetitive, or sparse to trust.
- Fixing coverage does not automatically make a signal valid.
- Better coverage only makes later rejection analysis more reliable.

## Coverage quality dimensions

| Dimension | Diagnostic question | Why it matters |
|-----------|---------------------|----------------|
| Market coverage | Do enough markets have wallet-flow history across the tested horizon? | Thin market coverage can make results look worse or better than reality. |
| Wallet coverage | Are enough distinct wallets represented without one wallet dominating? | Concentrated wallets can create fragile or misleading signals. |
| Time coverage | Are there enough unique flow hours across each horizon? | Repeated or sparse hours reduce trust in forward outcome comparisons. |
| Horizon coverage | Do 1h, 4h, and 24h horizons each have enough observations? | A signal may only be testable at some horizons. |
| Class coverage | Are whale, market, and copy-flow classes represented clearly? | Different wallet-flow classes may behave differently. |
| Missingness | Which markets, wallets, classes, or horizons have missing data? | Missingness can explain candidate rejection and prevent false conclusions. |
| Recency | Is coverage recent enough for current market behavior? | Old coverage may not reflect present wallet behavior. |
| Duplication | Are repeated events or duplicate flow hours inflating counts? | Duplicate-heavy coverage can overstate evidence strength. |

## Minimum diagnostic outputs

- Coverage by market.
- Coverage by wallet class.
- Coverage by horizon.
- Unique flow hours by market and horizon.
- Candidate rejection counts by coverage bucket.
- Missingness table by market, class, and horizon.
- Concentration table showing top-wallet share.
- Recency table showing how much coverage is stale.
- Duplication check for repeated flow hours.

## Diagnostic interpretation rules

- If unique flow hours are low, do not loosen thresholds.
- If one wallet dominates a market, mark the signal fragile.
- If coverage is stale, do not treat old performance as current evidence.
- If rejection improves only after removing costs, treat it as weak evidence.
- If coverage improves but win rate remains weak, do not promote.
- If coverage is strong and rejection remains high, wallet-flow may be a weak standalone signal.
- If coverage is weak but some markets look promising, treat them as diagnostic-only watch areas.

## Stop / continue criteria

| Finding | Decision |
|---------|----------|
| Coverage is thin across most markets and horizons | Continue diagnostics; do not promote. |
| Coverage is dominated by a few wallets | Continue diagnostics; mark fragile. |
| Coverage is stale | Refresh coverage plan before interpreting results. |
| Coverage is broad but win rate remains weak | Treat wallet-flow as likely weak standalone signal. |
| Coverage is broad and rejection bottlenecks improve | Continue to rejection-bottleneck breakdown phase. |
| Any candidate appears strong only after loosening thresholds | Stop; do not promote. |

## Recommended next phase

- The next phase should be wallet-flow rejection-bottleneck breakdowns by market, wallet class, and horizon.
- Coverage diagnostics should come before any threshold review.
- All outputs must remain exploratory and non-tradeable.

## Operator checklist

- [ ] Run git status -sb before the phase.
- [ ] Confirm the repo path is /workspaces/joint_research in Codespaces.
- [ ] Confirm no accidental poetry.lock, __pycache__, egg-info, or environment files are staged.
- [ ] Confirm no thresholds are changed.
- [ ] Confirm no candidates are promoted.
- [ ] Confirm no ingestion, execution, adapters, manifests, orders, or database mutation are approved.

This coverage quality diagnostic plan helps decide what wallet-flow evidence is trustworthy; it does not make wallet-flow tradeable.