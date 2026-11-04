"use strict";
/* The Ticket page: timeline, handoffs, agents per role, quality by role, cost and time by role. */
(function () {
  const L = CTQ.lib, H = CTQ.help, C = CTQ.charts;
  const { el, sum, mean, usd, dur, pct, pS, when, help, lbl, roleLabel } = L;
  const P = CTQ.pages = CTQ.pages || {};
  let flowView = "steps";                       // "steps" | "summary"

  P.ticket = async function (key) {
    await L.loadMeta();
    const d = await L.get("/api/ctq/tickets/" + encodeURIComponent(key), L.apiParams(false));
    const crumbs = el("div", { cls: "crumbs" }, [el("a", { href: L.href("tickets"), text: "← Tickets" }), "  /  " + key]);
    const bar = await L.periodBar(d.period, { filters: false });
    if (d.empty) return L.root([crumbs, bar, L.emptyPanel("No runs in this period", "This ticket has no runs in the chosen period. Pick a longer one above.")]);
    const build = () => L.root([crumbs, bar, ...body(d, key)]);
    ticketRebuild = () => L.swap(build);
    return build();
  };
  let ticketRebuild = null;

  function body(d, key) {
    const t = d.row, runs = d.runs;
    const sc = runs.filter((r) => r.S !== null && r.S !== undefined);
    const kp = el("div", { cls: "kpis" }, [
      L.kpi("Cost (estimate)", usd(t.cost), `main session ${usd(t.cost_main)} · sub-agents ${usd(t.cost_sub)}`, H.spend),
      L.kpi("Calendar span", dur(t.calendar_s), `${when(t.first)} → ${when(t.last)}`, H.calendar),
      L.kpi("Agents working", dur(t.working_s), `${t.runs} runs · ${t.roles} roles`, H.working),
      L.kpi("Waiting for you", dur(t.waiting_s), t.parked_s || t.blocked_s ? [t.parked_s ? `${dur(t.parked_s)} parked` : "", t.blocked_s ? `${dur(t.blocked_s)} blocked` : ""].filter(Boolean).join(" · ") : (t.main_sessions ? "in the main session" : "no main session on this ticket"), H.waiting),
      L.kpi("Test runs", dur(t.test_s), `${t.test_n} calls · ${t.test_fail} failed · ${t.test_timeouts} timed out`, H.tests),
      L.kpi("Quality S", t.S === null ? "—" : pS(t.S), t.n_S ? `${t.n_S} scored runs · ${t.flags} flags` : (t.n_eval ? `too little evidence in ${t.n_too_little} of ${t.n_eval} runs` : "no scored runs"), H.S)]);
    return [kp, L.findings(d.findings), verdictPanel(d, key), timeline(d), handoffs(d), agents(d), quality(d, sc), byRole(d), defectPanel(d, key)];
  }

  function timeline(d) {
    return L.panel("Timeline", "Runs by role, at their real length.", (w) => C.gantt(w, d.runs, d.waits, d.tests),
      () => L.simpleTable(["Role", "Start", "Duration", "Cost", "S", "Flags"], d.runs.map((r) => [roleLabel(r.role), when(r.start), dur(r.duration_s), usd(r.cost), pS(r.S), r.flags.join(", ").replace(/_/g, " ") || "—"]), [2, 3]),
      L.legendOf([["sw-main", "main session open"], ["sw-wait", "waiting for you"], ["sw-park", "parked"], ["sw-block", "blocked"], ["sw-work", "sub-agent run"], ["sw-test", "test run (red = failed, ▼ = timed out)"]]), H.timeline);
  }

  function handoffs(d) {
    const steps = d.handoffs;
    if (!steps.length) return null;
    const btns = el("span", { cls: "seg" }, [["steps", "Step by step"], ["summary", "Summary"]].map(([k, l]) => el("button", { cls: flowView === k ? "on" : "", text: l, onclick: () => { flowView = k; ticketRebuild(); } })));
    const p = L.panel("Handoffs", flowView === "steps"
      ? "Each dot is a role run in the order it started; a line joins it to the run it followed."
      : "Which role ran after which, added up. Arrows above go forward, arrows below go back to an earlier role.",
    (w) => (flowView === "steps" ? C.flowSteps(w, steps) : C.flowDiagram(w, steps)),
    () => L.simpleTable(["#", "Started", "From", "To", "How"], steps.map((s) => [s.n, when(s.start), s.from_role || "coordinator (start)", s.to_role, s.how]), [0]),
    L.legendOf([["lf", "next role"], ["ll", "back to an earlier role"], ["lb", "sent back by a gate (rework)"], ["hol", "rework run"], ...CTQ.meta.stages.map((s) => ["sw-" + s.key, s.name])]), H.handoffs);
    const tb = p._head.lastChild;
    p._head.append(el("span", { cls: "range" }, [btns, tb]));
    return p;
  }

  function agents(d) {
    const ag = d.agents_by_role;
    if (!ag.length) return null;
    const nSess = new Set(d.runs.filter((r) => r.kind === "sub").map((r) => r.session_id)).size;
    return el("section", { cls: "panel" }, [el("h2", null, ["Agents per role", help(H.agents)]),
      el("div", { cls: "sub", text: `${sum(ag, (x) => x.agents)} agents from ${nSess} session${nSess === 1 ? "" : "s"} on this ticket.` }),
      el("div", { cls: "scroll" }, L.simpleTable(["Role", "Agents", "Sessions", "In a shared session", "Rework agents", "Most at once", "Cost", "Run time", "S (n)"],
        ag.map((x) => [x.role, x.agents, x.sessions, `${x.shared} of ${x.agents}`, x.rework || "—", x.max_parallel, usd(x.cost), dur(x.run_time_s), x.n_S ? L.qcell(x.S, x.n_S) : el("span", { cls: "dim", text: "not scored" })]), [1, 2, 4, 5, 6, 7, 8]))]);
  }

  function quality(d, sc) {
    const groups = d.by_role.filter((x) => x.n_S || x.n_eval || Object.keys(x.flags).length);
    const cols = L.checkCols();
    const flagsOf = (f) => { const e = Object.entries(f); return e.length ? e.map(([k, n]) => [L.flagBadge(k), n > 1 ? ` ×${n}` : ""]) : "—"; };
    const runsQ = d.runs.filter((r) => r.S !== null && r.S !== undefined || r.flags.length);
    return el("section", { cls: "panel" }, [el("h2", null, ["Quality by role", help(H.S)]),
      el("div", { cls: "sub", text: "Score, the gate and each check, per role on this ticket. A row opens the role. A dash: the check has no data yet." }),
      groups.length ? el("div", { cls: "scroll" }, el("table", null, [
        el("thead", null, el("tr", null, [el("th", { text: "Role" }), el("th", { cls: "n" }, lbl("S", H.S)), ...cols.map(([k, label]) => el("th", { cls: "n" }, lbl(label, H[k]))), el("th", null, lbl("Flags", H.flags))])),
        el("tbody", null, groups.map((x) => el("tr", { cls: "click", onclick: L.rowClick("role/" + encodeURIComponent(x.role)) }, [el("td", { text: roleLabel(x.role) }), el("td", { cls: "n" }, L.qcell(x.S, x.n_S, x.n_eval, x.n_eval - x.n_S)),
          ...cols.map((c) => el("td", { cls: "n" }, L.checkCell(x, c))), el("td", null, flagsOf(x.flags))])))])) : el("p", { cls: "dim", text: "No scored or flagged runs." }),
      el("details", null, [el("summary", { text: `All ${runsQ.length} scored or flagged runs` }),
        el("div", { cls: "scroll" }, L.simpleTable(["Role", "Start", "Step", "Round", "S", "first pass", "outcome", "follows", "grounded", "Flags"], runsQ.map((r) => [
          el("a", { href: L.href("run/" + encodeURIComponent(r.run_id)), text: roleLabel(r.role) }), when(r.start), (r.step || "—") + (r.log_deleted ? " · log deleted" : ""), r.round || "—", r.S === null || r.S === undefined ? (r.too_little ? "too little evidence" : "—") : pS(r.S), L.mark(r.criteria.first_pass), L.mark(r.criteria.outcome), L.mark(r.criteria.follows), L.mark(r.criteria.grounded),
          r.flags.length ? r.flags.map((f) => L.flagBadge(f)) : "—"]), [4]))]),
      L.flagsLegend()]);
  }

  /* ---- your verdict and the defects found after done (the gold label for S) ---- */
  const VERDICTS = [["accepted", "Accepted"], ["accepted_after_rework", "Accepted after rework"], ["rejected", "Rejected"]];
  const form = { verdict: null, note: "", roles: new Set() };
  function roleChips(d, set, onChange) {
    const roles = [...new Set(d.runs.filter((r) => r.kind === "sub").map((r) => r.role))];
    return el("div", { cls: "chips" }, roles.map((r) => el("button", { cls: "chip" + (set.has(r) ? " on" : ""), type: "button", text: r, onclick: (e) => { set.has(r) ? set.delete(r) : set.add(r); e.target.classList.toggle("on", set.has(r)); onChange && onChange(); } })));
  }
  function verdictPanel(d, key) {
    const cur = d.verdict;
    const note = el("input", { type: "text", maxlength: "200", placeholder: "Note (up to 200 characters)", size: 50, "aria-label": "Note", value: form.note, oninput: (e) => { form.note = e.target.value; } });
    const msg = el("span", { cls: "dim" });
    const btns = el("span", { cls: "seg" }, VERDICTS.map(([v, label]) => el("button", { cls: form.verdict === v ? "on" : "", type: "button", text: label, onclick: (e) => { form.verdict = v; [...e.target.parentNode.children].forEach((b) => b.classList.toggle("on", b === e.target)); } })));
    const save = el("button", { cls: "tbtn", text: "Save verdict", onclick: async () => {
      if (!form.verdict) { msg.textContent = "Pick a verdict first."; return; }
      try { await post("/api/verdict", { ticket: key, verdict: form.verdict, note: form.note.trim(), roles: [...form.roles] }); form.note = ""; form.roles = new Set(); form.verdict = null; render(true); } catch (e) { msg.textContent = "Not saved (" + e.message + ")."; }
    } });
    return el("section", { cls: "panel" }, [el("h2", null, ["Your verdict", help(H.verdict)]),
      el("div", { cls: "sub", text: cur ? `Latest: ${cur.verdict.replace(/_/g, " ")} · ${when(cur.ts)}${cur.note ? " · " + cur.note : ""}${cur.roles && cur.roles.length ? " · fell short: " + cur.roles.join(", ") : ""}` : "No verdict yet. It is the gold label S is compared with." }),
      el("div", { cls: "controls" }, [btns, note, save, msg]), el("div", { cls: "sub", text: "Which roles fell short (optional):" }), roleChips(d, form.roles)]);
  }
  const dform = { date: new Date().toISOString().slice(0, 10), note: "", roles: new Set() };
  function defectPanel(d, key) {
    const date = el("input", { type: "date", value: dform.date, "aria-label": "Date", onchange: (e) => { dform.date = e.target.value; } });
    const note = el("input", { type: "text", maxlength: "200", placeholder: "What was found (up to 200 characters)", size: 50, "aria-label": "Defect note", value: dform.note, oninput: (e) => { dform.note = e.target.value; } });
    const msg = el("span", { cls: "dim" });
    const send = el("button", { cls: "tbtn", text: "Report defect", onclick: async () => {
      if (!dform.roles.size) { msg.textContent = "Pick the roles that fell short."; return; }
      try { await post("/api/defect", { ticket: key, date: dform.date, roles: [...dform.roles], note: dform.note.trim() }); dform.note = ""; dform.roles = new Set(); render(true); } catch (e) { msg.textContent = "Not saved (" + e.message + ")."; }
    } });
    return el("section", { cls: "panel" }, [el("h2", null, ["Report a defect found after done", help(H.defect)]),
      el("div", { cls: "sub", text: d.defects.length ? `${d.defects.length} reported: ` + d.defects.map((x) => `${x.date} (${x.roles.join(", ")})`).join(" · ") : "None reported for this ticket." }),
      el("div", { cls: "controls" }, [date, note, send, msg]), roleChips(d, dform.roles)]);
  }

  function byRole(d) {
    const rr = d.by_role;
    return L.panel("Cost and time by role", "Sum over the role's runs on this ticket.",
      (w) => C.hbars(w, rr.map((x) => ({ label: roleLabel(x.role), parts: [{ v: x.cost, cls: x.role === "main" ? "f-main" : "f-sub" }], note: ` · ${x.runs} run${x.runs > 1 ? "s" : ""} · ${dur(x.run_time_s)}`,
        tip: `${roleLabel(x.role)}\n${usd(x.cost)} · ${x.runs} runs · ${dur(x.run_time_s)} run time` + (x.n_S ? `\nS ${pS(x.S)} (n=${x.n_S})` : "") })), { labelW: 150 }),
      () => L.simpleTable(["Role", "Runs", "Cost", "Run time", "S (n)"], rr.map((x) => [roleLabel(x.role), x.runs, usd(x.cost), dur(x.run_time_s), x.n_S ? `${pS(x.S)} (${x.n_S})` : "—"]), [1, 2, 3]), null, H.spend);
  }
})();
