"use strict";
/* The Roles page (score history, role runs by ticket, shared or own session, the table) and the Role page. */
(function () {
  const L = CTQ.lib, H = CTQ.help, C = CTQ.charts;
  const { el, sum, mean, usd, dur, pct, pS, when, help, lbl, roleLabel } = L;
  const P = CTQ.pages = CTQ.pages || {};
  const view = { hl: null, hm: "score", hv: "time", showAll: false, sort: { col: "cost", asc: false } };

  /* ---------------- Roles ---------------- */
  P.roles = async function () {
    await L.loadMeta();
    const d = await L.get("/api/ctq/roles", undefined, { matrix_limit: view.showAll ? 0 : 30 });
    const bar = await L.periodBar(d.period);
    if (d.period.runs === 0) return L.root([bar, L.emptyPanel("No runs in this period", "Pick a longer period or clear the filters above.")]);
    return L.root([bar, L.findings(d.findings), ...nodes(d)]);
  };

  function nodes(d) {
    const pipeline = d.rows.filter((r) => r.pipeline_role);
    const hist = d.history;
    const roleList = pipeline.filter((r) => r.n_S).sort((a, b) => b.n_S - a.n_S);
    if (view.hl && !roleList.some((r) => r.role === view.hl)) view.hl = null;
    const chips = el("div", { cls: "chips" });
    const openLink = el("a", { cls: "tbtn" });
    const more = el("button", { cls: "tbtn" });
    let pHist;
    const nT = C.ticketOrder(hist).length;
    pHist = L.panel("Score history, all roles", view.hv === "time" ? "Every scored run in time order, coloured by pipeline stage." : "Scored runs grouped by ticket, newest activity first.",
      (w) => (!hist.length ? el("p", { cls: "dim", text: "No evaluated runs in this period." }) : view.hv === "time" ? C.history(w, hist, { group: true, hl: view.hl, metric: view.hm }) : C.ticketStrip(w, hist, { hl: view.hl, metric: view.hm, limit: view.showAll ? 0 : 30 })),
      null,
      el("div", null, [
        el("div", { cls: "controls" }, [
          el("span", { cls: "seg" }, [["score", "Score %"], ["rank", "Rank within the role"]].map(([k, l]) => el("button", { cls: view.hm === k ? "on" : "", text: l, onclick: () => { view.hm = k; L.swap(() => rebuildRoles(d)); } }))),
          help(view.hm === "rank" ? H.rank : H.S + "\n\n" + H.rank),
          el("span", { cls: "seg" }, [["time", "By time"], ["ticket", "By ticket"]].map(([k, l]) => el("button", { cls: view.hv === k ? "on" : "", text: l, onclick: () => { view.hv = k; L.swap(() => rebuildRoles(d)); } }))),
          help(view.hv === "ticket" ? H.byTicket : H.history)]),
        L.legendOf([...CTQ.meta.stages.map((s) => ["sw-" + s.key, s.name]), ["hol", "rework run"], ["tl", "S hidden: too little evidence"], ["ln", view.hv === "ticket" ? "average per ticket" : view.hl ? "average of the last 5 runs of the role" : "average of the last 5 runs"], ...(view.hm === "score" ? [["dash", "bar 85%"]] : [])]),
        chips,
        view.hv === "ticket" && nT > 30 ? el("div", { cls: "sub" }, [view.showAll ? `All ${nT} tickets. ` : `Showing the 30 most recent of ${nT} tickets. `, more]) : null]),
      view.hv === "ticket" ? H.byTicket : H.history);
    more.textContent = view.showAll ? "Show 30" : "Show all";
    more.addEventListener("click", () => { view.showAll = !view.showAll; render(true); });
    function drawChips() {
      chips.textContent = "";
      chips.append(el("button", { cls: "chip" + (view.hl ? "" : " on"), text: "All roles", onclick: () => { view.hl = null; drawChips(); pHist._draw(); } }));
      for (const r of roleList) chips.append(el("button", { cls: "chip" + (view.hl === r.role ? " on" : ""), onclick: () => { view.hl = view.hl === r.role ? null : r.role; drawChips(); pHist._draw(); } },
        [el("i", { cls: "sw-" + (r.stage || "g3") }), r.role, el("span", { cls: "cn", text: String(r.n_S) })]));
      openLink.textContent = view.hl ? `Open ${view.hl} →` : "";
      openLink.classList.toggle("hidden", !view.hl);
      if (view.hl) openLink.setAttribute("href", L.href("role/" + encodeURIComponent(view.hl)));
    }
    pHist._head.append(openLink);
    drawChips();
    return [pHist, matrixPanel(d), modePanel(d), verdictPanel(d), tablePanel(d)];
  }
  function rebuildRoles(d) {
    return L.root([document.querySelector("#app .ctq .periodbar"), L.findings(d.findings), ...nodes(d)]);
  }

  function matrixPanel(d) {
    const m = d.matrix;
    const bin = (n) => (n >= 10 ? 5 : n >= 5 ? 4 : n >= 3 ? 3 : n >= 2 ? 2 : 1);
    const shown = m.rows.length;
    const table = el("table", { cls: "mx" }, [
      el("thead", null, el("tr", null, [el("th", { text: "Ticket" }), ...m.columns.map((c) => el("th", { cls: "n", "data-tip": c === "other" ? "Generic and built-in agents (general-purpose, Explore, fork…)" : c }, [el("i", { cls: "dot sw-" + (C.stageOf(c) || "g0") }), C.ABBR[c] || c])), el("th", { cls: "n", text: "All" })])),
      el("tbody", null, m.rows.map((r) => el("tr", null, [el("td", null, el("a", { href: L.href("ticket/" + encodeURIComponent(r.ticket)), text: r.ticket })), ...m.columns.map((c) => {
        const cell = r.cells[c];
        if (!cell) return el("td", { cls: "n mxc" });
        return el("td", { cls: "n mxc" }, el("span", { cls: "q q" + bin(cell.n), "data-tip": `${r.ticket} · ${c}\n${cell.n} run${cell.n > 1 ? "s" : ""}${cell.rework ? `, ${cell.rework} rework` : ""}` + (cell.n_S ? `\naverage S ${pS(cell.S)} (n=${cell.n_S})` : "\nnot scored") }, String(cell.n)));
      }), el("td", { cls: "n", text: String(r.total) })])))]);
    return el("section", { cls: "panel" }, [el("h2", null, ["Role runs by ticket", help(H.matrix)]),
      el("div", { cls: "sub" }, [`Runs of each role per ticket in the period${m.total_tickets > shown ? `, the ${shown} most recent of ${m.total_tickets} tickets` : ""}. `, m.total_tickets > 30 ? el("button", { cls: "tbtn", text: view.showAll ? "Show 30" : "Show all", onclick: () => { view.showAll = !view.showAll; render(true); } }) : null]),
      m.rows.length ? el("div", { cls: "scroll" }, table) : el("p", { cls: "dim", text: "No role runs in this period." })]);
  }

  function modePanel(d) {
    const cell = (o) => (o.runs ? [o.runs, o.n_S ? L.qcell(o.S, o.n_S) : el("span", { cls: "dim", text: "—" }), usd(o.median_cost), dur(o.median_time_s)] : [el("span", { cls: "dim", text: "0" }), "", "", ""]);
    const verdict = (m) => (m.verdict ? `${m.verdict.better} better by ${m.verdict.points} points` : "too few runs to compare");
    return el("section", { cls: "panel" }, [el("h2", null, ["Same session or separate sessions", help(H.mode)]),
      el("div", { cls: "sub", text: "Per role: runs in a shared coordinator session against runs in their own session. Score, median cost and median time per run." }),
      d.session_mode.length ? el("div", { cls: "scroll" }, el("table", null, [
        el("thead", null, [el("tr", null, [el("th"), el("th", { cls: "n", colspan: 4, text: "Shared session" }), el("th", { cls: "n", colspan: 4, text: "Own session" }), el("th")]),
          el("tr", null, ["Role", "Runs", "S", "Cost / run", "Time / run", "Runs", "S", "Cost / run", "Time / run", "Comparison"].map((h, i) => el("th", { cls: i && i < 9 ? "n" : null, text: h })))]),
        el("tbody", null, d.session_mode.map((m) => el("tr", null, [el("td", { text: m.role }), ...cell(m.shared).map((c) => el("td", { cls: "n" }, c)), ...cell(m.own).map((c) => el("td", { cls: "n" }, c)), el("td", { cls: "dim", text: verdict(m) })])))])) : el("p", { cls: "dim", text: "No pipeline runs in this period." })]);
  }

  const SKIP_LABEL = { probe: "probe", api_error: "ended by API error", spawn_failure: "spawn failure" };

  function tablePanel(d) {
    const checks = L.checkCols();
    const cols = [["role", "Role", false], ["runs", "Runs", true, H.roleRuns], ["cost", "Total cost", true, H.spend], ["median_cost_per_run", "Cost / run", true, H.medCost], ["median_run_time_s", "Time / run", true, H.medTime],
      ["test_s", "Tests", true, H.tests], ["S", "Quality S", true, H.S], ...checks.map(([k, label]) => [k, label, true, H[k]]), ["flags_per_run", "Flags / run", true, H.flags]];
    const sc = view.sort, maxCost = Math.max(...d.rows.map((r) => r.cost), 0.0001);
    const val = (r, c) => (c === "delivered" ? (r.delivered && r.delivered[1] ? r.delivered[0] / r.delivered[1] : null) : (["first_pass", "outcome", "follows", "grounded", "judge"].includes(c) ? r.mean[c] : r[c]));
    const rows = d.rows.slice().sort((a, b) => { const x = val(a, sc.col), y = val(b, sc.col); const r = typeof x === "string" ? x.localeCompare(y) : (x ?? -1) - (y ?? -1); return sc.asc ? r : -r; });
    const head = L.sortHead(cols, sc, (k) => { view.sort = { col: k, asc: sc.col === k ? !sc.asc : false }; L.swap(() => rebuildRoles(d)); });
    const body = rows.map((r) => { const b = el("span", { cls: "ibar" }); b.style.width = Math.max(2, (r.cost / maxCost) * 70) + "px"; return el("tr", { cls: "click", onclick: L.rowClick("role/" + encodeURIComponent(r.role)) }, [
      el("td", null, [roleLabel(r.role), r.pipeline_role ? null : el("span", { cls: "badge", "data-tip": "A built-in or generic agent, not one of the pipeline roles: it has no criteria file, so it is not scored.", text: "not a pipeline role" })]),
      el("td", { cls: "n" }, [String(r.runs), r.n_skipped ? el("span", { cls: "dim", "data-tip": "Runs not scored, kept in the count: " + Object.entries(r.skipped).map(([k, n]) => `${n} ${SKIP_LABEL[k] || k}`).join(", ") + ". Open the role to see them.", text: ` · ${r.n_skipped} skipped` }) : null]), el("td", { cls: "n" }, [b, usd(r.cost)]), el("td", { cls: "n", text: usd(r.median_cost_per_run) }), el("td", { cls: "n", text: dur(r.median_run_time_s) }),
      el("td", { cls: "n", text: r.test_n ? `${dur(r.test_s)} · ${r.test_n} runs` : "—" }), el("td", { cls: "n" }, L.qcell(r.S, r.n_S, r.n_eval, r.n_too_little)),
      ...checks.map((c) => el("td", { cls: "n" }, L.checkCell(r, c))),
      el("td", { cls: "n" }, r.flags ? el("span", { cls: "err", text: r.flags_per_run.toFixed(2) }) : el("span", { cls: "dim", text: "0" }))]); });
    return el("section", { cls: "panel" }, [el("h2", { text: "Roles" }), el("div", { cls: "sub", text: "Cost, time and quality per role in the period. The columns after S show the gate (delivered) and each check; a dash means the check has no data yet." }),
      el("div", { cls: "scroll" }, el("table", null, [el("thead", null, head), el("tbody", null, body)])), L.flagsLegend()]);
  }

  function verdictPanel(d) {
    const v = d.verdict_panel;
    if (!v.shown) return el("section", { cls: "panel" }, [el("h2", null, ["Score vs your verdict", help(H.verdictPanel)]),
      el("p", { cls: "dim", text: `${v.n} of ${v.needed} tickets have both a verdict and a score. Give a verdict on the Ticket page; the comparison appears at ${v.needed}.` })]);
    const g = (k) => (v.mean_S[k] === null || v.mean_S[k] === undefined ? "—" : `${pS(v.mean_S[k])} · n=${v.count[k]}`);
    return el("section", { cls: "panel" }, [el("h2", null, ["Score vs your verdict", help(H.verdictPanel)]),
      el("div", { cls: "sub", text: `${v.n} tickets have both a verdict and a score.` }),
      L.simpleTable(["Your verdict", "Mean S of the ticket's runs"], [["accepted", g("accepted")], ["accepted after rework", g("accepted_after_rework")], ["rejected", g("rejected")]]),
      el("p", null, [`S ≥ ${pS(CTQ.meta.bar)} matches "accepted" on `, el("strong", { text: v.agree_share === null ? "—" : pct(v.agree_share) }), " of the tickets."])]);
  }

  /* ---------------- Role ---------------- */
  const rc = { first: false, ticket: "" };
  P.role = async function (role) {
    await L.loadMeta();
    const extra = {};
    if (rc.first) extra.first_only = "true";
    if (rc.ticket) extra.ticket = rc.ticket;
    const d = await L.get("/api/ctq/roles/" + encodeURIComponent(role), undefined, extra);
    const bar = await L.periodBar(d.period);
    const crumbs = el("div", { cls: "crumbs" }, [el("a", { href: L.href("roles"), text: "← Roles" }), "  /  " + roleLabel(role)]);
    if (d.empty) return L.root([crumbs, bar, L.emptyPanel("No runs of this role in this period", "Pick a longer period or clear the filters above.")]);
    const r = d.row, hist = d.history;
    const kp = el("div", { cls: "kpis" }, [
      L.kpi("Runs", String(r.runs), `on ${r.tickets} ticket${r.tickets > 1 ? "s" : ""}`, H.roleRuns),
      L.kpi("Cost", usd(r.cost), `${usd(r.median_cost_per_run)} per run (median)`, H.spend),
      L.kpi("Time per run", dur(r.median_run_time_s), "median", H.medTime),
      L.kpi("Quality S", r.S === null ? (r.n_eval ? "—" : "—") : pS(r.S), r.n_S ? `${r.n_S} scored runs${r.n_S < CTQ.meta.min_scored ? " · too few to judge" : ""}` : (r.n_eval ? `too little evidence in ${r.n_too_little} of ${r.n_eval} runs` : "not scored"), H.S),
      r.n_skipped ? L.kpi("Skipped runs", String(r.n_skipped), Object.entries(r.skipped).map(([k, n]) => `${n} ${SKIP_LABEL[k] || k}`).join(" · "), H.skipped) : null,
      L.kpi("Flags per run", r.flags_per_run.toFixed(2), `${r.flags} flag${r.flags === 1 ? "" : "s"}, model downgrade not counted`, H.flags)]);
    const back = el("a", { cls: "tbtn", href: L.href("roles"), text: "← All roles" });
    const ctl = d.controls;
    const tsel = el("select", { "aria-label": "Ticket", onchange: (e) => { rc.ticket = e.target.value; render(true); } },
      [el("option", { value: "", text: "All tickets" }), ...ctl.tickets.map((t) => el("option", { value: t, text: t }))]);
    tsel.value = rc.ticket;
    const controls = el("div", { cls: "controls" }, [
      el("span", { cls: "seg" }, [[false, "All rounds"], [true, "First passes only"]].map(([k, l]) => el("button", { cls: rc.first === k ? "on" : "", text: l, onclick: () => { rc.first = k; render(true); } }))),
      el("span", { cls: "seg" }, [[false, "All tickets"], [true, "Same ticket"]].map(([k, l]) => el("button", { cls: (!!rc.ticket) === k ? "on" : "", text: l, onclick: () => { rc.ticket = k ? (rc.ticket || ctl.tickets[ctl.tickets.length - 1] || "") : ""; render(true); } }))),
      rc.ticket ? tsel : null, help(H.controls), el("span", { cls: "dim", text: `${ctl.n_shown} of ${ctl.n_all} runs shown` })]);
    const pH = L.panel("Score history", "One dot per scored run of this role, in time order. Click a dot to open its ticket.",
      (w) => (hist.length ? C.history(w, hist, { events: d.events }) : el("p", { cls: "dim", text: "No scored runs for this selection." })),
      () => L.simpleTable(["When", "Ticket", "Step", "Round", "S", "first pass", "outcome", "follows", "grounded", "Flags"], hist.map((x) => [when(x.start), x.ticket, x.step || "—", x.round || "—", pS(x.S), L.mark(x.criteria.first_pass), L.mark(x.criteria.outcome), L.mark(x.criteria.follows), L.mark(x.criteria.grounded), x.flags.join(", ").replace(/_/g, " ") || "—"]), [3, 4]),
      L.legendOf([["sw-bar", "one run"], ["hol", "rework run (round 2 or later)"], ["tl", "S hidden: too little evidence"], ["ln", "average of the last 5 runs"], ["dash", "bar 85%"], ["mkl", "event: new ticket, role file, skills, shared rules, lesson, scorer version, model, benchmark"]]), H.history);
    pH._head.append(back);
    pH.insertBefore(controls, pH.children[1]);
    const b = d.series.buckets;
    const pB = L.panel(`Average score ${d.series.unit === "hour" ? "per hour" : d.series.unit === "day" ? "per day" : "per week"}`, "Mean S of the runs that started in each period.",
      (w) => (hist.length ? C.columns(w, b.map((x) => ({ label: x.label, parts: [{ v: x.S || 0, cls: "f-bar" }], tip: x.n_S ? `${x.label}\nS ${pS(x.S)} from ${x.n_S} runs` : `${x.label}\nno scored runs` })), { fmt: pS, max: 1, bar: CTQ.meta.bar }) : el("p", { cls: "dim", text: "No scored runs for this selection." })),
      () => L.simpleTable(["Period", "Average S", "Runs"], b.filter((x) => x.n_S).map((x) => [x.label, pS(x.S), x.n_S]), [1, 2]), L.legendOf([["sw-bar", "average S"], ["dash", "bar 85%"]]), H.S);
    const W = d.weights;
    const checks = el("section", { cls: "panel" }, [el("h2", null, ["Gate and checks", help(H.S)]), el("div", { cls: "sub", text: "The gate (delivered) and how each weighted check did for this role. A dash: no data yet." }),
      L.simpleTable(["Check", "Result", "Weight in S"], [["delivered", L.critCell(r.delivered), "gate: S = 0 if not"],
        ...["first_pass", "outcome", "judge", "follows", "grounded"].map((k) => [k.replace("_", " "), L.checkCell(r, [k, k, ["first_pass", "follows"].includes(k) ? "pass" : "mean"]), pct(W[k])])].map(([k, c, w]) => [lbl(k, H[k.replace(" ", "_")]), c, w]), [1, 2]), L.flagsLegend()]);
    const skippedPanel = d.skipped_runs.length ? el("section", { cls: "panel" }, [el("h2", null, ["Skipped runs", help(H.skipped)]),
      el("div", { cls: "sub", text: "Runs of this role that were not scored, and why. They stay in the run count and cost; they have no S." }),
      L.simpleTable(["When", "Ticket", "Why skipped", "Reason", "Run"], d.skipped_runs.map((x) => [when(x.start), x.ticket, x.label, x.reason, el("a", { href: L.href("run/" + encodeURIComponent(x.run_id)), text: "open" })]))]) : null;
    return L.root([crumbs, bar, kp, L.findings(d.findings), pH, skippedPanel, el("div", { cls: "grid2" }, [pB, checks])]);
  };
})();
