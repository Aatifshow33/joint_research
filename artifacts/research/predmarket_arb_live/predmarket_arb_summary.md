# Cross-Venue Prediction-Market Arbitrage Scan

> Research / detection artifact. No orders are placed. Edges are net of
> modeled venue fees; near-misses are retained on purpose.

- generated_at: `2026-06-18T23:46:51.693497+00:00`
- venue A quotes: 32078
- venue B quotes: 798
- matched markets: 35
- **actionable opportunities: 2**
- total actionable net profit (modeled): $7.40

## Outcome reason codes

| reason_code | count |
| --- | ---: |
| actionable | 2 |
| edge_below_fee_threshold | 7 |
| negative_gross_edge | 24 |
| profit_below_minimum | 2 |

> ⚠️ **Do not trade `token_overlap` (unverified) matches blind.** A high
> title similarity does not guarantee the two venues resolve the question
> by the same criteria, source, and date — a mismatch turns a "risk-free"
> pair into directional risk. Confirm resolution rules per market and move
> it into the trusted `--manual-map` before risking capital.

## Top opportunities by net edge per pair

| market | match | net_edge/pair | contracts | capital | net_profit | reason |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Will Luiz Inácio Lula da Silva win the first rou | UNVERIFIED | 0.5130 | 1 | $0.49 | $0.51 | actionable |
| Will ChatGPT be Time Person of the Year in 2026? | UNVERIFIED | 0.0348 | 198 | $191.11 | $6.89 | actionable |
| Will Putin and Zelenskyy meet next in Russia? | UNVERIFIED | 0.0210 | 1 | $0.98 | $0.02 | profit_below_minimum |
| Will Alexandru Nazare be the next Prime Minister | UNVERIFIED | 0.0200 | 1 | $0.98 | $0.02 | profit_below_minimum |
| Will Michael Mebruer be the Republican nominee f | UNVERIFIED | 0.0197 | 204 | $199.99 | $4.01 | edge_below_fee_threshold |
| Will James Talarico be Time Person of the Year i | UNVERIFIED | 0.0137 | 202 | $199.24 | $2.76 | edge_below_fee_threshold |
| Will Taylor Swift be Time Person of the Year in  | UNVERIFIED | 0.0116 | 202 | $199.65 | $2.35 | edge_below_fee_threshold |
| Will Bad Bunny be Time Person of the Year in 202 | UNVERIFIED | 0.0098 | 201 | $199.03 | $1.98 | edge_below_fee_threshold |
| Will John Larson be the Democratic nominee for C | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| Will Catalina Lauf be the Republican nominee for | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| Will Marine Le Pen win the 2027 French president | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| Will Byron Donalds be the Republican nominee for | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| Will Yossi Cohen be the next Prime Minister of I | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| Will Hollie Noveletsky be the Republican nominee | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| U.S. Open: Will Keegan Bradley finish top 10? | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| U.S. Open: Will Matt Fitzpatrick finish top 10? | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| U.S. Open: Will Sam Stevens finish top 10? | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| U.S. Open: Will Collin Morikawa finish top 20? | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| Will Michael Soetaert be the Democratic nominee  | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
| Will Este Haim attend Taylor Swift and Travis Ke | UNVERIFIED | 0.0000 | 0 | $0.00 | $0.00 | negative_gross_edge |
