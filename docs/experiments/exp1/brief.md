**EXP1: Ticket comparison report in the console**

Business need: to compare two tickets (or two runs of one ticket) side by side by cost, time and outcome, without adding numbers up by hand.

What it does:
1. A page `/compare?a=<KEY>&b=<KEY>` and a CLI `python -m agent_console compare <KEY> <KEY> [--json]`.
2. For each ticket, including its main sessions:
   - role runs: total, failed, and how many were repeat rounds;
   - tokens split into input, output, cache write and cache read, per model;
   - cost per model and in total, from `pricing.yaml`;
   - wall time from the first to the last event; active role time; time spent waiting on a person (gaps between a stop and the next human message);
   - the main session's cost as a share of the sub-agents' cost.
3. A third column with the difference (b minus a, and b divided by a).
4. An unknown key gives a clear error on the page and exit code 2 in the CLI; a ticket with no main session shows "no main session" in that row, not zero.
5. The JSON output is stable (sorted keys, fixed field names) so a script can read it.

Out of scope: charts, more than two tickets, editing data.

Decisions made in advance (so neither arm has to ask):
- Wait time = the gap between an assistant message that ends with a stop for the person and the next user message. Gaps under 60 s count as zero.
- Cost uses the prices in `pricing.yaml` as they are on the base commit.
- A session belongs to a ticket by the console's existing key rules.
- Numbers on the page are rounded: tokens to thousands, dollars to cents, time to minutes. JSON keeps raw values.
- No new dependencies.
