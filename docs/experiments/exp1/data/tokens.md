# Tokens, cost and time per arm (raw logs, one script: ~/exp1-private/count_tokens.py)

## kit

files 22, deduplicated messages 270, first 2026-11-05T13:54:18.345000, last 2026-11-05T16:59:09.315000
role runs 21 (repeat rounds 15): {'kit-builder': 6, 'kit-analyst': 3, 'kit-test-designer': 3, 'kit-security': 4, 'kit-reviewer': 4, 'kit-verifier': 1}
tokens: input 598, output 246502, cache_w5m 1003046, cache_w1h 0, cache_read 13503150
cost USD: total 7.67, main 3.05, sub-agents 4.63, main share of sub 0.66
wall 185 min, active role time 46 min, wait on a person 130 min (1 gaps, over 2 h: 130 min; by kind {'human': '130 min', 'ops': '0 min'})

| model | msgs | input | output | cache write 5m | cache write 1h | cache read | cost |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | 270 | 598 | 246502 | 1003046 | 0 | 13503150 | 7.67 |

| role | msgs | input | output | cache write | cache read | cost |
|---|---|---|---|---|---|---|
| kit-analyst | 33 | 66 | 33169 | 144604 | 940404 | 0.88 |
| kit-builder | 50 | 100 | 61136 | 200851 | 1450919 | 1.40 |
| kit-reviewer | 31 | 62 | 18050 | 92482 | 468821 | 0.51 |
| kit-security | 12 | 24 | 5655 | 58166 | 92350 | 0.22 |
| kit-test-designer | 42 | 84 | 69755 | 165017 | 2045412 | 1.52 |
| kit-verifier | 5 | 10 | 5040 | 14108 | 54868 | 0.10 |
| main | 97 | 252 | 53697 | 327818 | 8450376 | 3.05 |

## r22

files 148, deduplicated messages 2277, first 2026-11-05T13:54:47.265000, last 2026-11-05T19:08:57.811000
role runs 147 (repeat rounds 133): {'test-designer': 17, 'business-analyst': 27, 'lead-qa': 5, 'requirements-reviewer': 15, 'reviewer': 8, 'qa-analyst': 8, 'system-analyst': 17, 'automation-engineer': 26, 'security-engineer': 3, 'builder': 11, 'verifier': 2, 'test-runner': 2, 'environment-checker': 3, 'hostile-verifier': 3}
tokens: input 4933, output 1989697, cache_w5m 10154470, cache_w1h 0, cache_read 199887331
cost USD: total 117.42, main 51.97, sub-agents 65.45, main share of sub 0.79
wall 314 min, active role time 373 min, wait on a person 1 min (1 gaps, over 2 h: 0 min; by kind {'human': '0 min', 'ops': '1 min'})

| model | msgs | input | output | cache write 5m | cache write 1h | cache read | cost |
|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | 1662 | 3644 | 1287994 | 7728136 | 0 | 173821632 | 99.18 |
| claude-sonnet-5-5 | 600 | 1200 | 697889 | 2404425 | 0 | 25948052 | 18.18 |
| anthropic.claude-haiku-4-5-20251001-v1:0 | 15 | 89 | 3814 | 21909 | 0 | 117647 | 0.06 |

| role | msgs | input | output | cache write | cache read | cost |
|---|---|---|---|---|---|---|
| automation-engineer | 272 | 544 | 297790 | 923396 | 10820726 | 7.45 |
| builder | 111 | 222 | 101338 | 439994 | 6100754 | 3.33 |
| business-analyst | 279 | 558 | 226918 | 762311 | 6449314 | 9.64 |
| environment-checker | 10 | 20 | 3372 | 18777 | 55540 | 0.09 |
| hostile-verifier | 108 | 216 | 77540 | 195929 | 4636589 | 3.46 |
| lead-qa | 83 | 166 | 41900 | 256909 | 3377862 | 2.80 |
| main | 384 | 1088 | 295489 | 4277224 | 123329414 | 51.97 |
| qa-analyst | 60 | 120 | 87662 | 267806 | 1738703 | 3.44 |
| requirements-reviewer | 104 | 208 | 77108 | 365108 | 1541646 | 3.68 |
| reviewer | 279 | 558 | 184272 | 721617 | 19895963 | 11.27 |
| security-engineer | 84 | 168 | 70963 | 179587 | 3252726 | 2.97 |
| system-analyst | 281 | 562 | 226142 | 701645 | 9599415 | 9.95 |
| test-designer | 159 | 318 | 263711 | 922883 | 7404904 | 6.43 |
| test-runner | 15 | 89 | 3814 | 21909 | 117647 | 0.06 |
| verifier | 48 | 96 | 31678 | 99375 | 1566128 | 0.88 |
