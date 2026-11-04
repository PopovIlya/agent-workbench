"use strict";
/* Overview, Tickets and Sessions. Every number comes from /api/ctq/*; the page only draws it. */
(function () {
  const L = CTQ.lib, H = CTQ.help, C = CTQ.charts;
  const { el, sum, usd, dur, pct, pS, when, money, help, lbl } = L;
  const P = CTQ.pages = CTQ.pages || {};

  const tUnit = (unit) => (unit === "hour" ? [60, (v) => Math.round(v) + " min"] : [3600, (v) => (Math.round(v * 10) / 10) + " h"]);
  const perWord = (u) => (u === "hour" ? "per hour" : u === "day" ? "per day" : "per week");
  const ticketLink = (t) => el("a", { href: L.href("ticket/" + encodeURIComponent(t)), text: t });

  /* ---------------- Overview ---------------- */
  P.overview = async function () {
    await L.loadMeta();
    const d = await L.get("/api/ctq/overview");
    const k = d.kpis;
    const fr = await L.frame(d, () => {
      const kp = el("div", { cls: "kpis" }, [
        L.kpi("Spend (estimate)", usd(k.spend), `${pct(k.main_share)} in main sessions`, H.spend),
        L.kpi("Agents working", dur(k.working_s), `${k.runs} runs on ${k.tickets} tickets`, H.working),
        L.kpi("Waiting for you", dur(k.waiting_s), k.blocked_s ? `${dur(k.blocked_s)} more blocked` : "", H.waiting),
        L.kpi("Parked", dur(k.parked_s), "a session left open", H.parked),
        L.kpi("Test runs", dur(k.test_s), `${k.test_n} calls · ${k.test_fail} failed · ${k.test_timeouts} timed out`, H.tests),
        L.kpi("Quality score S", k.n_S ? pS(k.S) : "—", k.n_S ? `${k.n_S} scored runs · delivered ${k.delivered ? k.delivered[0] + "/" + k.delivered[1] : "–"}` : (k.n_evaluated ? `too little evidence in ${k.n_too_little} of ${k.n_evaluated} runs` : "no scored runs"), H.S)]);
      return [kp, needsPanel(d.needs_person), el("div", { cls: "grid2" }, [costPanel(d), timePanel(d)]), el("div", { cls: "grid2" }, [spendPanel(d), workPanel(d)]), el("div", { cls: "grid2" }, [qualityPanel(d), tokenPanel(d)])];
    });
    return fr.build();
  };

  let needsAll = false;
  const NEEDS_SHOWN = 15;
  function needsPanel(n) {
    const rows = needsAll ? n.items : n.items.slice(0, NEEDS_SHOWN);
    const body = rows.length ? el("div", { cls: "scroll" }, el("table", null, [
      el("thead", null, el("tr", null, ["Flag", "Role", "Ticket", "When", "Run cost", ""].map((h, i) => el("th", { cls: i === 4 ? "n" : null, text: h })))),
      el("tbody", null, rows.map((x) => el("tr", null, [
        el("td", null, L.flagBadge(x.flag)), el("td", null, el("a", { href: L.href("run/" + encodeURIComponent(x.run_id)), text: L.roleLabel(x.role) })), el("td", null, ticketLink(x.ticket)),
        el("td", { text: when(x.start) }), el("td", { cls: "n", text: usd(x.cost) }),
        el("td", null, x.decidable
          ? [el("button", { cls: "tbtn", text: "Confirm", "data-tip": "Confirm the deception: a hard limit, S = 0 for this run.", onclick: () => decide(x, "confirm") }), " ",
            el("button", { cls: "tbtn", text: "Dismiss", "data-tip": "Dismiss it: the flag was a false alarm.", onclick: () => decide(x, "dismiss") })]
          : el("button", { cls: "tbtn", text: "Mark checked", onclick: async () => { try { await post("/api/flags/check", { run_id: x.run_id, flag: x.flag }); render(true); } catch (e) { /* stays in the list */ } } }))])))]))
      : el("p", { cls: "dim", text: "Nothing flagged in this period." });
    return el("section", { cls: "panel" }, [el("h2", null, ["Needs a person", help(H.needs)]),
      el("div", { cls: "sub", text: `Flagged runs in the period${n.checked ? ` · ${n.checked} already checked` : ""}.` }), body,
      n.items.length > NEEDS_SHOWN ? el("p", { cls: "sub" }, [`Showing ${rows.length} of ${n.total}. `, el("button", { cls: "tbtn", text: needsAll ? `Show ${NEEDS_SHOWN}` : "Show all", onclick: () => { needsAll = !needsAll; render(true); } })]) : null, L.flagsLegend()]);
  }

  async function decide(x, decision) { try { await post("/api/flags/decide", { run_id: x.run_id, flag: x.flag, decision }); render(true); } catch (e) { /* stays in the list */ } }

  function costPanel(d) {
    const rows = d.cost_by_ticket.map((t) => ({ label: t.ticket, go: "ticket/" + encodeURIComponent(t.ticket), parts: [{ v: t.cost_main, cls: "f-main" }, { v: t.cost_sub, cls: "f-sub" }],
      tip: `${t.ticket}\n${usd(t.cost)} total\nmain session ${usd(t.cost_main)} · sub-agents ${usd(t.cost_sub)}\n${t.runs} runs · ${t.roles} roles` }));
    const more = d.cost_by_ticket_more;
    if (more.n) rows.push({ label: `${more.n} more`, parts: [{ v: more.cost_main, cls: "f-main" }, { v: more.cost_sub, cls: "f-sub" }], tip: `${more.n} more tickets\n${usd(more.cost_main + more.cost_sub)}` });
    return L.panel("Cost per ticket", "Estimated spend per ticket. Click a bar to open the ticket.", (w) => C.hbars(w, rows),
      () => L.simpleTable(["Ticket", "Main session", "Sub-agents", "Total", "Runs"], d.cost_by_ticket.map((t) => [t.ticket, usd(t.cost_main), usd(t.cost_sub), usd(t.cost), t.runs]), [1, 2, 3, 4]),
      L.legendOf([["sw-main", "main session (you + coordinator)"], ["sw-sub", "role sub-agents"]]), H.spend + "\n\n" + H.moved);
  }
  function timePanel(d) {
    const rows = d.time_by_ticket.map((t) => ({ label: t.ticket, go: "ticket/" + encodeURIComponent(t.ticket),
      parts: [{ v: Math.max(0, t.working_s - t.test_s) / 3600, cls: "f-work" }, { v: t.test_s / 3600, cls: "f-test" }, { v: t.waiting_s / 3600, cls: "f-wait" }],
      totalLabel: dur(t.working_s + t.waiting_s) + (t.parked_s ? ` · ${dur(t.parked_s)} parked` : ""),
      tip: `${t.ticket}\nagents working ${dur(t.working_s)} (tests ${dur(t.test_s)})\nwaiting for you ${dur(t.waiting_s)}\nparked ${dur(t.parked_s)}\ncalendar span ${dur(t.calendar_s)}` }));
    return L.panel("Time per ticket", "Hours of agent work and of waiting for you. Parked time is not drawn; it is in the table and the tooltip.", (w) => C.hbars(w, rows, { fmt: (v) => (Math.round(v * 10) / 10) + " h" }),
      () => L.simpleTable(["Ticket", "Working", "of it tests", "Waiting for you", "Parked", "Calendar span"], d.time_by_ticket.map((t) => [t.ticket, dur(t.working_s), dur(t.test_s), dur(t.waiting_s), dur(t.parked_s), dur(t.calendar_s)]), [1, 2, 3, 4, 5]),
      L.legendOf([["sw-work", "agents working"], ["sw-test", "test runs"], ["sw-wait", "waiting for you"]]), H.working + "\n\n" + H.waiting + "\n\n" + H.parked);
  }
  function spendPanel(d) {
    const b = d.series.buckets, per = perWord(d.series.unit);
    return L.panel("Spend over time", `Estimated spend ${per}, by the time of each message.`,
      (w) => C.columns(w, b.map((x) => ({ label: x.label, parts: [{ v: x.cost_main, cls: "f-main" }, { v: x.cost_sub, cls: "f-sub" }], tip: `${x.label}\nmain session ${usd(x.cost_main)} · sub-agents ${usd(x.cost_sub)}\ntotal ${usd(x.cost_main + x.cost_sub)}` }))),
      () => L.simpleTable(["Period", "Main session", "Sub-agents", "Total"], b.map((x) => [x.label, usd(x.cost_main), usd(x.cost_sub), usd(x.cost_main + x.cost_sub)]), [1, 2, 3]),
      L.legendOf([["sw-main", "main session"], ["sw-sub", "role sub-agents"]]), H.spend);
  }
  function workPanel(d) {
    const b = d.series.buckets, per = perWord(d.series.unit), [u, fmt] = tUnit(d.series.unit);
    return L.panel("Agent time over time", `Time ${per} of agent work and of waiting for you. Parked time is in the table and the tooltip.`,
      (w) => C.columns(w, b.map((x) => ({ label: x.label, parts: [{ v: x.working_s / u, cls: "f-work" }, { v: x.waiting_s / u, cls: "f-wait" }],
        tip: `${x.label}\nagents working ${dur(x.working_s)}\nwaiting for you ${dur(x.waiting_s)}\nparked ${dur(x.parked_s)}` })), { fmt }),
      () => L.simpleTable(["Period", "Agents working", "Waiting for you", "Parked"], b.map((x) => [x.label, dur(x.working_s), dur(x.waiting_s), dur(x.parked_s)]), [1, 2, 3]),
      L.legendOf([["sw-work", "agents working"], ["sw-wait", "waiting for you"]]), H.working + "\n\n" + H.waiting);
  }
  function qualityPanel(d) {
    const b = d.series.buckets, any = b.some((x) => x.n_S);
    return L.panel("Quality over time", `Average score S of the runs that started ${perWord(d.series.unit)}.`,
      (w) => (any ? C.columns(w, b.map((x) => ({ label: x.label, parts: [{ v: x.S || 0, cls: "f-bar" }], tip: x.n_S ? `${x.label}\nS ${pS(x.S)} from ${x.n_S} scored runs` : `${x.label}\nno scored runs` })), { fmt: pS, max: 1, bar: CTQ.meta.bar })
        : el("p", { cls: "dim", text: "No scored runs in this period." })),
      () => L.simpleTable(["Period", "Average S", "Scored runs"], b.filter((x) => x.n_S).map((x) => [x.label, pS(x.S), x.n_S]), [1, 2]),
      L.legendOf([["sw-bar", "average S"], ["dash", "bar 85%"]]), H.S);
  }
  function tokenPanel(d) {
    const t = d.cost_by_token_type, tot = sum(Object.values(t)) || 1;
    const rows = [["cache_read", "Cache read"], ["cache_write", "Cache write"], ["output", "Output"], ["input", "Input"]];
    return L.panel("What the money buys", "Spend by token type.",
      (w) => C.hbars(w, rows.map(([k, n]) => ({ label: n, parts: [{ v: t[k], cls: "f-bar" }], totalLabel: money(t[k], t[k] / tot), tip: `${n}\n${usd(t[k])} · ${pct(t[k] / tot)} of spend` })), { labelW: 100 }),
      () => L.simpleTable(["Token type", "Cost", "Share"], rows.map(([k, n]) => [n, usd(t[k]), pct(t[k] / tot)]), [1, 2]), null, H.tokens);
  }

  /* ---------------- Tickets ---------------- */
  const ts = { col: "cost", asc: false, limit: 50 };
  P.tickets = async function () {
    await L.loadMeta();
    const d = await L.get("/api/ctq/tickets", undefined, { sort: ts.col, desc: ts.asc ? "false" : "true", limit: ts.limit });
    const fr = await L.frame(d, () => [tablePanel(d)]);
    return fr.build();
  };
  function tablePanel(d) {
    const cols = [["ticket", "Ticket", false], ["cost", "Cost", true, H.spend], ["calendar_s", "Calendar span", true, H.calendar], ["working_s", "Agents working", true, H.working], ["waiting_s", "Waiting for you", true, H.waiting],
      ["parked_s", "Parked", true, H.parked], [null, "Split", false], ["test_s", "Tests", true, H.tests], ["runs", "Runs", true], ["roles", "Roles", true], ["S", "Quality S", true, H.S], ["flags", "Flags", true, H.flags]];
    const head = L.sortHead(cols, ts, (k) => { ts.asc = ts.col === k ? !ts.asc : false; ts.col = k; ts.limit = 50; render(true); });
    const body = d.rows.map((t) => el("tr", { cls: "click", onclick: L.rowClick("ticket/" + encodeURIComponent(t.ticket)) }, [
      el("td", null, [t.ticket, ...badges(t)]),
      el("td", { cls: "n", text: usd(t.cost) }), el("td", { cls: "n", text: dur(t.calendar_s) }), el("td", { cls: "n", text: dur(t.working_s) }), el("td", { cls: "n", text: dur(t.waiting_s) }), el("td", { cls: "n", text: dur(t.parked_s) }),
      el("td", null, split(t)),
      el("td", { cls: "n" }, t.test_n ? [dur(t.test_s), el("span", { cls: "dim", text: ` · ${t.test_n} runs` }), t.test_fail ? el("span", { cls: "err", text: ` · ${t.test_fail} failed` }) : null] : el("span", { cls: "dim", text: "—" })),
      el("td", { cls: "n", text: t.runs }), el("td", { cls: "n", text: t.roles }), el("td", { cls: "n" }, L.qcell(t.S, t.n_S, t.n_eval, t.n_too_little)),
      el("td", { cls: "n" }, t.flags ? el("span", { cls: "err", text: t.flags }) : el("span", { cls: "dim", text: "0" }))]));
    const more = d.total > d.rows.length ? el("p", { cls: "sub" }, [`Showing ${d.rows.length} of ${d.total} tickets. `, el("button", { cls: "tbtn", text: "Show more", onclick: () => { ts.limit += 50; render(true); } })]) : null;
    return el("section", { cls: "panel" }, [el("h2", { text: "Tickets" }), el("div", { cls: "sub", text: "Cost, time and quality per ticket in the period. Click a column to sort, a row to open the ticket." }),
      L.legendOf([["sw-work", "agents working"], ["sw-test", "test runs"], ["sw-wait", "waiting for you"], ["sw-park", "parked"]]),
      el("div", { cls: "scroll" }, el("table", null, [el("thead", null, head), el("tbody", null, body)])), more, L.flagsLegend()]);
  }
  function split(t) {
    const tot = t.working_s + t.waiting_s + t.parked_s;
    return L.stack([[Math.max(0, t.working_s - t.test_s), "sw-work"], [t.test_s, "sw-test"], [t.waiting_s, "sw-wait"], [t.parked_s, "sw-park"]], tot,
      `agents working ${dur(t.working_s)} (tests ${dur(t.test_s)})\nwaiting for you ${dur(t.waiting_s)}\nparked ${dur(t.parked_s)}`);
  }
  function badges(t) {
    const out = [];
    for (const m of t.badges.moved_main) out.push(el("span", { cls: "badge", "data-tip": `Branch says ${m.own_key}; ${m.share_n} of ${m.children} of its sub-agents worked on ${t.ticket}.\n\n${H.moved}`, text: "+ main session" }));
    if (t.badges.tool_waits) out.push(el("span", { cls: "badge warn", "data-tip": `A tool call sat for more than ${CTQ.meta.blocked_after_s / 60} minutes (${dur(t.blocked_s)} in total): probably a permission prompt. Shown as blocked, not as work.`, text: "tool waits?" }));
    if (t.badges.umbrella) out.push(el("span", { cls: "badge warn", "data-tip": "Spans more than a week: probably an umbrella key used for unrelated work.", text: "umbrella?" }));
    return out;
  }
  CTQ.lib.ticketBadges = badges;

  /* ---------------- Sessions ---------------- */
  const ss = { col: "cost", asc: false };
  P.sessions = async function () {
    await L.loadMeta();
    const d = await L.get("/api/ctq/sessions", undefined, { sort: ss.col, desc: ss.asc ? "false" : "true", limit: 200 });
    const red = d.context_red_tokens;
    const fr = await L.frame(d, () => {
      const rows = d.rows;
      const sc = L.panel("Cost of one call against context size", "One dot per main session: context re-read per call against cost per call.",
        (w) => (rows.length ? C.scatter(w, rows.map((r) => ({ x: r.context_per_call / 1000, y: r.cost_per_call, go: "ticket/" + encodeURIComponent(r.ticket),
          tip: `${r.ticket} · ${when(r.start)}\n${r.calls} model calls · ${dur(r.length_s)}\n${usd(r.cost)} · ${usd(r.cost_per_call)} per call\ncontext per call ≈ ${Math.round(r.context_per_call / 1000)}k tokens` })),
          "context re-read per call, thousand tokens", (v) => Math.round(v) + "k", usd, red / 1000) : el("p", { cls: "dim", text: "No main sessions in this period." })),
        () => L.simpleTable(["Ticket", "Start", "Context per call", "Cost per call"], rows.map((r) => [r.ticket, when(r.start), Math.round(r.context_per_call / 1000) + "k", usd(r.cost_per_call)]), [2, 3]), null, H.ctx);
      const cols = [["ticket", "Ticket", false, H.moved], ["start", "Started", false], ["length_s", "Length", true], ["calls", "Model calls", true], ["cost", "Cost", true, H.spend], ["cost_per_call", "$ / call", true, H.cpc],
        ["context_per_call", "Context per call", true, H.ctx], ["relay_share", "Relay share", true, H.relay], ["waiting_s", "Waiting for you", true, H.waiting], ["parked_s", "Parked", true, H.parked], ["sub_agents", "Sub-agents", true]];
      const head = L.sortHead(cols, ss, (k) => { ss.asc = ss.col === k ? !ss.asc : false; ss.col = k; render(true); });
      const body = rows.map((x) => el("tr", { cls: "click", onclick: L.rowClick("ticket/" + encodeURIComponent(x.ticket)) }, [
        el("td", null, [x.ticket, x.moved ? el("span", { cls: "badge", "data-tip": `Branch says ${x.own_ticket}; ${x.moved_note.share_n} of ${x.moved_note.children} of its sub-agents worked on ${x.ticket}.\n\n${H.moved}`, text: "moved" }) : null,
          x.agent_setting ? el("span", { cls: "badge", "data-tip": `Started with --agent ${x.agent_setting}`, text: x.agent_setting }) : null]),
        el("td", { text: when(x.start) }), el("td", { cls: "n", text: dur(x.length_s) }), el("td", { cls: "n", text: Math.round(x.calls).toLocaleString("en-US") }), el("td", { cls: "n", text: usd(x.cost) }), el("td", { cls: "n", text: usd(x.cost_per_call) }),
        el("td", { cls: "n" + (x.context_per_call > red ? " err" : ""), text: Math.round(x.context_per_call / 1000) + "k" }),
        el("td", { cls: "n", "data-tip": x.total_chars ? `relay ${pct(x.relay_share)} · ${L.fmtInt(x.relay_chars)} of ${L.fmtInt(x.total_chars)} characters pass between agents\nhand-backs only ${pct(x.handback_share)} · ${L.fmtInt(x.handback_chars)} characters (the sub-agents' reports coming back)` : "no text counted" }, x.relay_share === null ? "—" : pct(x.relay_share)),
        el("td", { cls: "n", text: dur(x.waiting_s) }), el("td", { cls: "n", text: dur(x.parked_s) }), el("td", { cls: "n", text: x.sub_agents })]));
      const tb = el("section", { cls: "panel" }, [el("h2", { text: "Main sessions" }), el("div", { cls: "sub", text: `Your sessions with the coordinator or a single agent, in the period. Red: more than ${red / 1000}k tokens of context per call.` }),
        el("div", { cls: "scroll" }, el("table", null, [el("thead", null, head), el("tbody", null, body)])), d.total > rows.length ? el("p", { cls: "sub", text: `Showing ${rows.length} of ${d.total} sessions.` }) : null]);
      return [sc, tb];
    });
    return fr.build();
  };
})();
