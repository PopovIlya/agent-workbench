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

## old:EXP1-CHECK

files 1, deduplicated messages 48, first 2026-11-05T22:23:40.691000, last 2026-11-05T22:39:31.775000
role runs 0 (repeat rounds 0): {}
tokens: input 96, output 40910, cache_w5m 130021, cache_w1h 0, cache_read 3983635
cost USD: total 1.53, main 1.53, sub-agents 0.00, main share of sub no sub-agents
wall 16 min, active role time 0 min, wait on a person 0 min (0 gaps, over 2 h: 0 min; by kind {'human': '0 min', 'ops': '0 min'})

| model | msgs | input | output | cache write 5m | cache write 1h | cache read | cost |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | 48 | 96 | 40910 | 130021 | 0 | 3983635 | 1.53 |

| role | msgs | input | output | cache write | cache read | cost |
|---|---|---|---|---|---|---|
| main | 48 | 96 | 40910 | 130021 | 3983635 | 1.53 |

## old:EXP1-KIT

files 12, deduplicated messages 139, first 2026-11-05T12:31:24.393000, last 2026-11-05T13:32:35.331000
role runs 11 (repeat rounds 6): {'kit-builder': 3, 'kit-security': 2, 'kit-reviewer': 2, 'kit-analyst': 3, 'kit-test-designer': 1}
tokens: input 304, output 126181, cache_w5m 657391, cache_w1h 0, cache_read 5523909
cost USD: total 4.01, main 1.36, sub-agents 2.65, main share of sub 0.51
wall 61 min, active role time 36 min, wait on a person 25 min (2 gaps, over 2 h: 0 min; by kind {'human': '25 min', 'ops': '0 min'})

| model | msgs | input | output | cache write 5m | cache write 1h | cache read | cost |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | 139 | 304 | 126181 | 657391 | 0 | 5523909 | 4.01 |

| role | msgs | input | output | cache write | cache read | cost |
|---|---|---|---|---|---|---|
| kit-analyst | 22 | 44 | 24100 | 124842 | 798719 | 0.71 |
| kit-builder | 26 | 52 | 36439 | 134524 | 868755 | 0.87 |
| kit-reviewer | 13 | 26 | 10730 | 54742 | 216728 | 0.29 |
| kit-security | 9 | 18 | 4174 | 39886 | 84280 | 0.16 |
| kit-test-designer | 20 | 40 | 28471 | 65485 | 849716 | 0.62 |
| main | 49 | 124 | 22267 | 237912 | 2705711 | 1.36 |

## old:EXP1-KITB

files 3, deduplicated messages 30, first 2026-11-05T13:37:36.197000, last 2026-11-05T13:42:03.101000
role runs 2 (repeat rounds 1): {'kit-analyst': 2}
tokens: input 66, output 21344, cache_w5m 117142, cache_w1h 0, cache_read 1008932
cost USD: total 0.71, main 0.24, sub-agents 0.47, main share of sub 0.51
wall 4 min, active role time 2 min, wait on a person 0 min (0 gaps, over 2 h: 0 min; by kind {'human': '0 min', 'ops': '0 min'})

| model | msgs | input | output | cache write 5m | cache write 1h | cache read | cost |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | 30 | 66 | 21344 | 117142 | 0 | 1008932 | 0.71 |

| role | msgs | input | output | cache write | cache read | cost |
|---|---|---|---|---|---|---|
| kit-analyst | 15 | 30 | 15738 | 86042 | 485520 | 0.47 |
| main | 15 | 36 | 5606 | 31100 | 523412 | 0.24 |

## old:EXP1-R22

files 11, deduplicated messages 172, first 2026-11-05T12:31:32.185000, last 2026-11-05T13:37:31.040000
role runs 10 (repeat rounds 7): {'business-analyst': 5, 'requirements-reviewer': 2, 'system-analyst': 3}
tokens: input 368, output 149582, cache_w5m 657923, cache_w1h 0, cache_read 6642816
cost USD: total 6.81, main 1.07, sub-agents 5.73, main share of sub 0.19
wall 66 min, active role time 29 min, wait on a person 35 min (3 gaps, over 2 h: 0 min; by kind {'human': '35 min', 'ops': '0 min'})

| model | msgs | input | output | cache write 5m | cache write 1h | cache read | cost |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | 29 | 82 | 15684 | 259154 | 0 | 1339407 | 1.07 |
| claude-opus-5-5 | 143 | 286 | 133898 | 398769 | 0 | 5303409 | 5.73 |

| role | msgs | input | output | cache write | cache read | cost |
|---|---|---|---|---|---|---|
| business-analyst | 49 | 98 | 49220 | 117939 | 739672 | 1.72 |
| main | 29 | 82 | 15684 | 259154 | 1339407 | 1.07 |
| requirements-reviewer | 13 | 26 | 16093 | 52733 | 158900 | 0.62 |
| system-analyst | 81 | 162 | 68585 | 228097 | 4404837 | 3.39 |

## old:EXP1-R22B

files 3, deduplicated messages 23, first 2026-11-05T13:37:36.864000, last 2026-11-05T13:41:51.934000
role runs 2 (repeat rounds 0): {'business-analyst': 1, 'requirements-reviewer': 1}
tokens: input 52, output 21112, cache_w5m 92933, cache_w1h 0, cache_read 574552
cost USD: total 0.56, main 0.22, sub-agents 0.34, main share of sub 0.66
wall 4 min, active role time 2 min, wait on a person 0 min (0 gaps, over 2 h: 0 min; by kind {'human': '0 min', 'ops': '0 min'})

| model | msgs | input | output | cache write 5m | cache write 1h | cache read | cost |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | 23 | 52 | 21112 | 92933 | 0 | 574552 | 0.56 |

| role | msgs | input | output | cache write | cache read | cost |
|---|---|---|---|---|---|---|
| business-analyst | 7 | 14 | 10287 | 36871 | 126903 | 0.22 |
| main | 11 | 26 | 5544 | 34470 | 396897 | 0.22 |
| requirements-reviewer | 5 | 12 | 5281 | 21592 | 50752 | 0.12 |
