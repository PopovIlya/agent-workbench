"use strict";
/* The Run page: one run, why it has this score and these flags, where its time went. Keeps the old page; adds the time split on top. */
/* ---------- shared bits ---------- */
function evidenceText(f) {
  const e = f.evidence;
  if (f.flag === "out_of_scope_edit") return `${e.count} path(s): ` + e.items.slice(0, 3).map((i) => `${i.path} (${i.why})`).join("; ");
  if (f.flag === "overthinking") return Object.entries(e).map(([k, v]) => `${k} ${typeof v === "number" ? fmtInt(v) : v}`).join(" · ");
  if (f.flag === "spawn_failure") return "errors: " + (e.categories.join(", ") || "other");
  if (f.flag === "model_downgraded") return `expected ${e.expected_tier}, served ${e.served_tiers.join("+")}`;
  if (f.flag === "stalled") return `${e.count} silent gap(s) of more than 20 min, longest ${fmtDur(e.longest_s)}, ${fmtDur(e.total_s)} in total`;
  if (f.flag === "returned") return `round ${e.round} of ${e.role} (derived from spawn order)`;
  if (f.flag === "deception") return "suspected (heuristic): " + (e.reasons || []).map((r) => `${r.rule.replace(/_/g, " ")}: ${r.detail}`).join("; ");
  if (f.flag === "secrets_file_edited") return `${e.count} secrets file(s): ` + (e.paths || []).join(", ") + " (path only, content not read)";
  if (f.flag === "secret_suspected") return `${(e.rules || []).join(", ")} in ${(e.where || []).join(", ")}: ${e.note || ""}`;
  return JSON.stringify(e);
}
function flagTable(flags, onChange) {
  return table([
    { h: CTQ.lib.lbl("Flag", CTQ.help.flags), f: (f) => CTQ.lib.flagBadge(f.flag) }, { h: "Role", f: (f) => link("#/role/" + encodeURIComponent(f.role), f.role) },
    { h: "Ticket", f: (f) => (f.ticket ? link("#/ticket/" + encodeURIComponent(f.ticket), f.ticket) : "unknown") },
    { h: "Started", f: (f) => fmtTs(f.start_ts) }, { h: "Evidence", f: (f) => evidenceText(f) },
    { h: "Run", f: (f) => runLink(f.run_id) },
    { h: "", f: (f) => (f.status === "open" ? el("button", { onclick: async () => { await post("/api/flags/check", { run_id: f.run_id, flag: f.flag }); onChange(); } }, "Mark checked") : el("span", { class: "muted" }, "checked")) },
  ], flags, "No open flags.");
}
function modelsText(m) { return Object.entries(m).map(([k, v]) => `${k} ×${v}`).join(", ") || "–"; }
const kpi = (l, v, n) => el("div", { class: "kpi" }, el("div", { class: "l" }, l), el("div", { class: "v" }, v), el("div", { class: "n" }, n || " "));
const CRIT_NAMES = { first_pass: "First pass (25 %)", outcome: "Outcome (30 %)", judge: "Judge (25 %)", follows: "Follows instructions (10 %)", grounded: "Grounded in requirements (10 %)",
  done: "1 Task done", accepted: "4 Accepted downstream", budget: "5 Within budget" };   // the last three belong to scorer v1 lines
function scoreView(sc) {
  const box = el("div", {});
  const v2 = sc.scorer_version === 2;
  const head = sc.S === null ? (sc.too_little_evidence ? "too little evidence" : (sc.skipped || "not scored")) : `S = ${Math.round(sc.S * 100)}%`;
  box.append(el("div", { class: "kpis" }, kpi("Score" + (v2 ? " (scorer v2)" : " (scorer v1)"), head, sc.hard_limit ? "hard limit: " + sc.hard_limit.limit : (v2 && sc.coverage !== undefined ? `evidence: ${Math.round(sc.coverage * 100)}% of the weight had data` : " ")),
    kpi("Judge needed", sc.judge_needed ? "yes" : "no", sc.returns >= 2 ? "returned twice" : " "), kpi("Revision", String(sc.rev), (sc.ts || "").replace("T", " ").slice(0, 16))));
  if (sc.skipped && sc.skip_kind) box.append(el("div", { class: "banner warn" }, `Skipped (${({ probe: "probe", api_error: "ended by API error", spawn_failure: "spawn failure" })[sc.skip_kind] || sc.skip_kind}): ${sc.skipped}. No S for this run.`));
  if (v2 && sc.gate) box.append(el("div", { class: "banner" + (sc.gate.delivered ? "" : " warn") }, sc.gate.delivered ? `Delivered (found in: ${(sc.gate.found_in || []).join(", ") || "n/a"}).` : sc.gate.reason));
  if (sc.hard_limit) box.append(el("div", { class: "banner warn" }, `Hard limit ${sc.hard_limit.limit}: ${sc.hard_limit.detail}`));
  if (sc.note) box.append(el("div", { class: "note" }, "Note: " + sc.note));
  const keys = (v2 ? ["first_pass", "outcome", "judge", "follows", "grounded"] : ["done", "follows", "grounded", "accepted", "budget"]).filter((k) => k in (sc.criteria || {}));
  if (keys.length) box.append(table([{ h: "Check", f: (k) => CRIT_NAMES[k] || k }, { h: "Weight", num: 1, f: (k) => sc.criteria[k].w },
    { h: "c", num: 1, f: (k) => (sc.criteria[k].c === null ? (sc.criteria[k].pending ? "pending" : "empty") : sc.criteria[k].c) },
    { h: "Reason", f: (k) => sc.criteria[k].c === null ? sc.criteria[k].omitted : (sc.criteria[k].provisional ? "provisional: " : "") + (sc.criteria[k].reason || "") }], keys));
  if (keys.length) box.append(el("div", { class: "note" }, "A check with no data is left empty and the other weights are re-scaled; nothing is guessed. Round " + (sc.round || "–") + (sc.step ? " · step: " + sc.step : "") + "."));
  return box;
}

async function pageRun(id) {
  const r = await api("/api/runs/" + encodeURIComponent(id));
  const root = el("div", {}, el("h1", {}, `${r.role} · ${r.run_id.slice(-12)}`), el("div", { class: "sub" }, `${r.kind === "main" ? "Main session" : "Subagent run"} · started ${fmtTs(r.start_ts)} · span ${fmtDur(r.duration_s)}`));
  root.append(CTQ.lib.findings(r.findings) || "", timeStrip(r));
  root.append(el("div", { class: "kv" },
    el("div", {}, "Ticket"), el("div", {}, r.ticket_eff ? [link("#/ticket/" + encodeURIComponent(r.ticket_eff), r.ticket_eff), el("mark", { class: "src" }, r.ticket_eff_via === "children" && r.ticket_eff !== r.ticket
      ? `  filed here because ${r.eff_share_n} of ${r.eff_children} of its sub-agents worked on it (its own key: ${r.ticket || "none"}, source: ${r.ticket_src})`
      : "  source: " + r.ticket_src + (r.ticket_via ? " (" + r.ticket_via + " in force at spawn time)" : ""))] : "unknown"),
    el("div", {}, "Model(s) that answered"), el("div", {}, modelsText(r.models)),
    el("div", {}, "Model(s) requested"), el("div", {}, modelsText(r.requested_models)),
    el("div", {}, "Rounds / tool calls"), el("div", {}, `${r.rounds} / ${r.tool_count} (${r.tool_errors} tool error(s))`),
    el("div", {}, "Tokens"), el("div", {}, `in ${fmtTok(r.input)} · out ${fmtTok(r.output)} · cache write ${fmtTok(r.cache_w5m + r.cache_w1h)} · cache read ${fmtTok(r.cache_read)}`),
    el("div", {}, "Cost"), el("div", {}, costLabel(r.cost) + (r.cli_cost_usd !== null && r.cli_cost_usd !== undefined ? ` · CLI-reported for the whole session: $${r.cli_cost_usd.toFixed(2)}` : "")),
    el("div", {}, "API errors"), el("div", {}, Object.entries(r.errors).map(([k, v]) => `${k} ×${v}`).join(", ") || "none"),
    el("div", {}, "Working dir / branch"), el("div", {}, `${r.cwd || "–"} / ${r.branch || "–"}`),
    el("div", {}, "Scope"), el("div", {}, `${r.scope} (${r.scope_reason})`),
    r.parent_run_id ? [el("div", {}, "Spawned by"), el("div", {}, runLink(r.parent_run_id, r.parent_run_id.slice(-12)))] : null));
  root.append(el("h2", {}, "Flags", CTQ.lib.help(CTQ.help.flags)), r.flags.length ? flagTable(r.flags.map((f) => ({ ...f, role: r.role, ticket: r.ticket })), () => render()) : el("div", { class: "empty" }, "No flags."));
  root.append(el("div", { class: "ctq" }, CTQ.lib.flagsLegend()));
  root.append(el("h2", {}, "Score"), r.scores.length ? scoreView(r.scores[r.scores.length - 1]) : el("div", { class: "empty" }, "no score for this run yet."));
  root.append(el("h2", {}, "Files touched"), el("div", { class: "note" }, `${r.files_read_count} file(s) read; edits and writes below. “from Bash command” = best-effort match of > / tee / sed -i.`),
    table([{ h: "Path", f: (f) => f.path }, { h: "Tool", f: (f) => f.tool + (f.from_bash_command ? " (from Bash command)" : "") }, { h: "Times", num: 1, f: (f) => f.count }], r.files_edited, "No edits or writes."));
  root.append(el("h2", {}, "Tool calls"), table([{ h: "Tool", f: (x) => x[0] }, { h: "Count", num: 1, f: (x) => x[1] }], Object.entries(r.tool_counts).sort((a, b) => b[1] - a[1])));
  if (r.children.length) root.append(el("h2", {}, "Spawned runs"), table([{ h: "Role", f: (c) => c.role }, { h: "Run", f: (c) => runLink(c.run_id) }, { h: "Started", f: (c) => fmtTs(c.start_ts) }, { h: "Tokens", num: 1, f: (c) => fmtTok(c.total_tokens) }], r.children));
  root.append(el("h2", {}, "Text (on request, redacted)"), el("div", { class: "note" }, "Prompt and reply text is not stored in the index. It is read from the log on request and passed through the repo's gitleaks rules plus a built-in subset; not every secret format is covered."));
  const out = el("div");
  root.append(el("div", {}, r.text_parts.map((p) => el("button", { onclick: async () => {
    out.replaceChildren(el("div", { class: "note" }, "Loading…"));
    const t = await post("/api/show/" + encodeURIComponent(r.run_id), { part: p });
    out.replaceChildren(el("div", { class: "note" }, `${p}: ${t.redactions} redaction(s)${t.truncated ? " · truncated" : ""}`), el("pre", { class: "text" }, t.text));
  } }, "Show " + p))), out);
  return root;
}


/* Where the run's time went: one stacked bar and its test calls. All numbers come from the index (runs.* time columns, tool_calls). */
function timeStrip(r) {
  const parts = [
    { label: "model", v: r.model_s, cls: "sw-model" }, { label: "tools", v: r.tool_s, cls: "sw-tool" }, { label: "tests", v: r.test_s, cls: "sw-test" },
    { label: "waiting for you", v: r.human_wait_s, cls: "sw-wait" }, { label: "parked", v: r.parked_s, cls: "sw-park" }, { label: "blocked", v: r.blocked_s, cls: "sw-block" }, { label: "stalled", v: r.stalled_s, cls: "sw-stall" },
    { label: "notification waits", v: r.notif_wait_s, cls: "sw-unk" }, { label: "unattributed", v: r.unattributed_s, cls: "sw-unk" }];
  const wall = r.duration_s || 0;
  const box = el("div", { class: "ctq" });
  if (!wall) return box;
  const L = CTQ.lib, H = CTQ.help;
  const legend = L.legendOf(parts.filter((p) => p.v > 0).map((p) => [p.cls, `${p.label} ${L.dur(p.v)}`]));
  const tests = r.tests || [];
  box.append(el("section", { class: "panel" }, el("h2", {}, "Where the time went", L.help(H.split)),
    el("div", { class: "sub" }, `${L.dur(wall)} from the first to the last record of this run.`), CTQ.charts.splitBar(parts, wall), legend,
    tests.length ? el("div", { class: "callrow" }, [`${tests.length} test call${tests.length > 1 ? "s" : ""}: `, ...tests.map((t) => el("span", { class: "badge" + (t.timed_out ? " crit" : t.is_error ? " warn" : ""),
      "data-tip": `${t.class} · ${L.when(t.start)}${t.timed_out ? "\ntimed out: a timeout or a permission prompt, not test time" : t.is_error ? "\nfailed" : ""}` }, `${t.class} ${L.dur(t.dur_s)}`))]) : null));
  return box;
}
