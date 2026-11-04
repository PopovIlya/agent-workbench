"use strict";
/* Hand-written SVG charts for the cost / time / quality pages. Each takes a width and plain data and returns a node; none keeps state.
   Colours come from CSS classes (f-*, s-*, sw-*), so light and dark come from the stylesheet only. */
(function () {
  const { el, sv, sum, mean, usd, dur, pS, pct, when, DD, TF, niceMax, roleLabel } = CTQ.lib;
  const C = CTQ.charts = {};
  const BAR = () => CTQ.meta.bar;
  const STAGE = (role) => { for (const s of CTQ.meta.stages) if (s.roles.includes(role)) return s.key; return null; };
  C.stageOf = STAGE;
  const ms = (t) => Date.parse(t);

  /* ---------- horizontal stacked bars ---------- */
  C.hbars = function (width, rows, opts) {
    const o = Object.assign({ labelW: 130, rowH: 24, gap: 6, fmt: usd, total: true }, opts || {});
    const W = Math.max(280, width), plotW = Math.max(60, W - o.labelW - 130);
    const max = niceMax(Math.max(...rows.map((r) => sum(r.parts, (p) => p.v)), 0));
    const H = rows.length * (o.rowH + o.gap) + 22;
    const s = sv("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
    const x = (v) => o.labelW + (v / max) * plotW;
    for (let i = 0; i <= 4; i++) {
      const v = (max * i) / 4, gx = x(v);
      s.append(sv("line", { x1: gx, x2: gx, y1: 0, y2: H - 18, cls: i ? "gridl" : "axisl" }));
      s.append(sv("text", { x: gx, y: H - 4, "text-anchor": i === 0 ? "start" : "middle", cls: "tx-m tx-num", text: o.fmt(v) }));
    }
    rows.forEach((r, i) => {
      const y = i * (o.rowH + o.gap) + 2;
      s.append(sv("text", { x: o.labelW - 8, y: y + o.rowH / 2 + 4, "text-anchor": "end", cls: "tx-ink", text: r.label.length > 19 ? r.label.slice(0, 18) + "…" : r.label }));
      let acc = 0;
      const segs = r.parts.filter((p) => p.v > 0);
      segs.forEach((p, j) => {
        const x0 = x(acc), x1 = x(acc + p.v); acc += p.v;
        const w = Math.max(1, x1 - x0 - (j < segs.length - 1 ? 2 : 0));
        const rr = j === segs.length - 1 ? Math.min(4, w) : 0;
        s.append(sv("path", { cls: p.cls, d: `M${x0},${y + 4} h${w - rr} ${rr ? `q${rr},0 ${rr},${rr}` : ""} v${o.rowH - 8 - 2 * rr} ${rr ? `q0,${rr} -${rr},${rr}` : ""} h-${w - rr} z` }));
      });
      if (o.total) s.append(sv("text", { x: x(acc) + 6, y: y + o.rowH / 2 + 4, cls: "tx tx-num", text: (r.totalLabel || o.fmt(acc)) + (r.note || "") }));
      const hit = sv("rect", { x: 0, y, width: W, height: o.rowH, cls: "hit", "data-tip": r.tip });
      if (r.go) hit.addEventListener("click", () => CTQ.lib.go(r.go));
      s.append(hit);
    });
    return s;
  };

  /* ---------- stacked columns (one per bucket) ---------- */
  C.columns = function (width, cols, opts) {
    const o = Object.assign({ fmt: usd, max: null, bar: null, H: 210 }, opts || {});
    const W = Math.max(280, width), H = o.H, L = 50, B = 24, T = 8;
    const max = o.max || niceMax(Math.max(...cols.map((c) => sum(c.parts, (p) => p.v)), 0));
    const s = sv("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
    const y = (v) => T + (H - T - B) * (1 - v / max);
    for (let i = 0; i <= 4; i++) {
      const v = (max * i) / 4;
      s.append(sv("line", { x1: L, x2: W, y1: y(v), y2: y(v), cls: i ? "gridl" : "axisl" }));
      s.append(sv("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end", cls: "tx-m tx-num", text: o.fmt(v) }));
    }
    const bw = (W - L) / Math.max(1, cols.length), cw = Math.max(2, Math.min(36, bw * 0.62));
    const step = Math.max(1, Math.ceil(56 / bw));
    cols.forEach((c, i) => {
      const cx = L + bw * i + bw / 2;
      let acc = 0;
      const segs = c.parts.filter((p) => p.v > 0);
      segs.forEach((p, j) => {
        const y0 = y(acc), y1 = y(acc + p.v); acc += p.v;
        const h = Math.max(1, y0 - y1 - (j < segs.length - 1 ? 2 : 0));
        const rr = j === segs.length - 1 ? Math.min(4, h, cw / 2) : 0;
        s.append(sv("path", { cls: p.cls, d: `M${cx - cw / 2},${y0} v-${h - rr} ${rr ? `q0,-${rr} ${rr},-${rr}` : ""} h${cw - 2 * rr} ${rr ? `q${rr},0 ${rr},${rr}` : ""} v${h - rr} z` }));
      });
      if (i % step === 0) s.append(sv("text", { x: cx, y: H - 6, "text-anchor": "middle", cls: "tx-m", text: c.label }));
      s.append(sv("rect", { x: cx - bw / 2, y: T, width: bw, height: H - T - B, cls: "hit", "data-tip": c.tip }));
    });
    if (o.bar !== null) s.append(sv("line", { x1: L, x2: W, y1: y(o.bar), y2: y(o.bar), cls: "l-bar" }));
    return s;
  };

  /* ---------- scatter ---------- */
  C.scatter = function (width, pts, xl, xfmt, yfmt, redX) {
    const W = Math.max(280, width), H = 260, L = 52, B = 34, T = 10, R = 12;
    const xm = niceMax(Math.max(...pts.map((p) => p.x))), ym = niceMax(Math.max(...pts.map((p) => p.y)));
    const s = sv("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
    const X = (v) => L + ((W - L - R) * v) / xm, Y = (v) => T + (H - T - B) * (1 - v / ym);
    for (let i = 0; i <= 4; i++) {
      s.append(sv("line", { x1: L, x2: W - R, y1: Y((ym * i) / 4), y2: Y((ym * i) / 4), cls: i ? "gridl" : "axisl" }));
      s.append(sv("text", { x: L - 6, y: Y((ym * i) / 4) + 4, "text-anchor": "end", cls: "tx-m tx-num", text: yfmt((ym * i) / 4) }));
      s.append(sv("text", { x: X((xm * i) / 4), y: H - B + 16, "text-anchor": "middle", cls: "tx-m tx-num", text: xfmt((xm * i) / 4) }));
    }
    if (redX && redX < xm) s.append(sv("line", { x1: X(redX), x2: X(redX), y1: T, y2: H - B, cls: "l-bar" }));
    s.append(sv("text", { x: (L + W - R) / 2, y: H - 4, "text-anchor": "middle", cls: "tx", text: xl }));
    for (const p of pts) {
      s.append(sv("circle", { cx: X(p.x), cy: Y(p.y), r: 5, cls: "f-bar", stroke: "var(--surface)", "stroke-width": 2 }));
      const h = sv("circle", { cx: X(p.x), cy: Y(p.y), r: 11, cls: "hit", "data-tip": p.tip });
      if (p.go) h.addEventListener("click", () => CTQ.lib.go(p.go));
      s.append(h);
    }
    return s;
  };

  /* ---------- score history ---------- */
  C.rankMap = function (runs) {          // the server computes it (rank_within_role): the share of the role's other runs that scored lower, ties half
    return new Map(runs.map((r) => [r, r.rank]));
  };
  const CHK = ["first_pass", "outcome", "follows", "grounded"];
  C.history = function (width, runs, opts) {
    const o = Object.assign({ group: false, hl: null, metric: "score", events: [] }, opts || {});
    const rk = o.metric === "rank" ? C.rankMap(runs) : null;
    const val = (r) => (rk ? rk.get(r) : r.S);                 // null for a run whose S is hidden (too little evidence)
    const pos = (r) => { const v = val(r); return v !== null && v !== undefined ? v : (rk ? 0.5 : (r.S_partial ?? 0)); };     // where its dot is drawn
    const has = (r) => { const v = val(r); return v !== null && v !== undefined; };
    const W = Math.max(280, width), H = 230, L = 44, B = 30, T = 10, R = 12;
    const s = sv("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
    const n = runs.length;
    const X = (i) => L + (W - L - R) * (n === 1 ? 0.5 : i / (n - 1)), Y = (v) => T + (H - T - B) * (1 - v);
    for (let i = 0; i <= 4; i++) {
      s.append(sv("line", { x1: L, x2: W - R, y1: Y(i / 4), y2: Y(i / 4), cls: i ? "gridl" : "axisl" }));
      s.append(sv("text", { x: L - 6, y: Y(i / 4) + 4, "text-anchor": "end", cls: "tx-m tx-num", text: pS(i / 4) }));
    }
    if (!rk) s.append(sv("line", { x1: L, x2: W - R, y1: Y(BAR()), y2: Y(BAR()), cls: "l-bar" }));
    const times = runs.map((r) => ms(r.start));
    let lastMk = -1e9;
    for (const ev of o.events) {                 // dotted vertical line between the runs the event falls between; events outside the drawn runs have no place on the axis
      const t = ms(ev.ts);
      if (!n || t < times[0] || t > times[n - 1]) continue;
      const i = Math.max(1, times.findIndex((x) => x >= t));
      const mx = (X(i - 1) + X(i)) / 2;
      s.append(sv("line", { x1: mx, x2: mx, y1: T, y2: H - B, cls: "mk" }));
      if (mx - lastMk > 70) { s.append(sv("text", { x: mx + 3, y: T + 9, cls: "tx-m", text: ev.label })); lastMk = mx; }
      s.append(sv("rect", { x: mx - 5, y: T, width: 10, height: H - B - T, cls: "hit", "data-tip": `${ev.kind} · ${when(ev.ts)}\n${ev.detail}` }));
    }
    const prevOf = new Map(); { const last = {}; runs.forEach((r) => { prevOf.set(r, last[r.role] || null); last[r.role] = r; }); }
    let lastDay = "", lastX = -1e9;
    runs.forEach((r, i) => { const d = DD.format(new Date(r.start)); if (d !== lastDay && X(i) - lastX > 50) { s.append(sv("text", { x: X(i), y: H - 10, "text-anchor": "middle", cls: "tx-m", text: d })); lastX = X(i); } lastDay = d; });
    const rollPts = []; runs.forEach((r, i) => { if (has(r)) rollPts.push([i, mean(runs.slice(Math.max(0, i - 4), i + 1).filter(has).map(val))]); });
    const idx = o.hl ? runs.map((r, i) => (roleLabel(r.role) === o.hl && has(r) ? i : -1)).filter((i) => i >= 0) : null;
    if (idx) {
      const own = idx.map((i, j) => [i, mean(idx.slice(Math.max(0, j - 4), j + 1).map((k) => val(runs[k])))]);
      if (own.length > 1) s.append(sv("path", { cls: "l-hl", d: own.map(([i, v], j) => `${j ? "L" : "M"}${X(i)},${Y(v)}`).join(" ") }));
    } else if (rollPts.length > 1) s.append(sv("path", { cls: "l-ink", d: rollPts.map(([i, v], j) => `${j ? "L" : "M"}${X(i)},${Y(v)}`).join(" ") }));
    runs.forEach((r, i) => {
      const off = o.hl && roleLabel(r.role) !== o.hl;
      const g = o.group ? (STAGE(r.role) || "g3") : "bar", rw = r.rework || (r.round || 1) > 1;
      const tl = !has(r);
      s.append(sv("circle", { cx: X(i), cy: Y(pos(r)), r: off ? 3.5 : 4.5, cls: tl ? "tl" + (off ? " faded" : "") : "f-" + g + (rw ? " rework s-" + g : "") + (off ? " faded" : ""), stroke: rw || tl ? null : "var(--surface)", "stroke-width": 2 }));
      const m = (k) => (r.criteria[k] === null || r.criteria[k] === undefined ? "–" : r.criteria[k] >= 1 ? "✓" : "✗");
      const pv = prevOf.get(r);
      const chg = pv ? CHK.filter((k) => (pv.criteria[k] ?? null) !== (r.criteria[k] ?? null)).map((k) => `${k} ${(pv.criteria[k] ?? null) === null ? "–" : pv.criteria[k] >= 1 ? "✓" : "✗"}→${m(k)}`) : [];
      const h = sv("circle", { cx: X(i), cy: Y(pos(r)), r: 10, cls: "hit", "data-tip":
        `${roleLabel(r.role)} · ${r.ticket} · ${when(r.start)}\n` + (tl ? `S hidden: too little evidence (${pct(r.coverage || 0)} of the weight had data, S shows from 50 %)` + (r.S_partial !== null && r.S_partial !== undefined ? `\nS on the part with data: ${pS(r.S_partial)}${rk ? " (the dot sits at 50 % of the rank axis)" : ""}` : "") : `S ${pS(r.S)}` + (rk ? ` · rank within the role ${pS(rk.get(r))}` : "")) +
        `\nfirst pass ${m("first_pass")}  outcome ${m("outcome")}  follows ${m("follows")}  grounded ${m("grounded")}` + (r.delivered === false ? "\nnot delivered" : "") +
        (r.step ? `\nstep: ${r.step}` : "") + (r.round ? `\nround ${r.round}${r.round > 1 ? " (rework)" : " (first pass)"}` : "") + (r.input_tokens ? ` · input ${Math.round(r.input_tokens / 1000)}k tokens` : "") +
        (rw && !r.round ? "\nrework run: a gate sent the work back" : "") + (!tl && r.coverage !== null && r.coverage !== undefined ? `\nevidence: ${pct(r.coverage)} of the weight had data` : "") +
        (pv ? `\nvs the role's previous run: ${chg.length ? chg.join(", ") : "same checks"}` : "") + (r.flags.length ? `\nflags: ${r.flags.join(", ").replace(/_/g, " ")}` : "") });
      h.addEventListener("click", () => CTQ.lib.go("ticket/" + encodeURIComponent(r.ticket)));
      s.append(h);
    });
    return s;
  };
  C.ticketOrder = function (runs) {
    const last = {}; for (const r of runs) last[r.ticket] = Math.max(last[r.ticket] || 0, ms(r.start));
    return Object.keys(last).sort((a, b) => last[b] - last[a]);
  };
  C.ticketStrip = function (width, runs, opts) {
    const o = Object.assign({ hl: null, metric: "score", limit: 30 }, opts || {});
    const rk = o.metric === "rank" ? C.rankMap(runs) : null;
    const val = (r) => (rk ? rk.get(r) : r.S);
    const has = (r) => { const v = val(r); return v !== null && v !== undefined; };
    const pos = (r) => (has(r) ? val(r) : (rk ? 0.5 : (r.S_partial ?? 0)));
    const keys = C.ticketOrder(runs), show = o.limit ? keys.slice(0, o.limit) : keys;
    const W = Math.max(300, width), L = 130, R = 90, RH = 26, T = 4;
    const H = show.length * RH + T + 22;
    const s = sv("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
    const X = (v) => L + (W - L - R) * v;
    for (let i = 0; i <= 4; i++) {
      s.append(sv("line", { x1: X(i / 4), x2: X(i / 4), y1: T, y2: H - 18, cls: i ? "gridl" : "axisl" }));
      s.append(sv("text", { x: X(i / 4), y: H - 4, "text-anchor": "middle", cls: "tx-m tx-num", text: pS(i / 4) }));
    }
    if (!rk) s.append(sv("line", { x1: X(BAR()), x2: X(BAR()), y1: T, y2: H - 18, cls: "l-bar" }));
    show.forEach((k, ri) => {
      const y = T + ri * RH + RH / 2;
      const rs = runs.filter((r) => r.ticket === k), vis = o.hl ? rs.filter((r) => roleLabel(r.role) === o.hl) : rs;
      s.append(sv("text", { x: L - 8, y: y + 4, "text-anchor": "end", cls: "tx-ink", text: k.length > 17 ? k.slice(0, 16) + "…" : k }));
      const lh = sv("rect", { x: 0, y: y - RH / 2, width: L - 4, height: RH, cls: "hit", "data-tip": `${k}\nopen the ticket` });
      lh.addEventListener("click", () => CTQ.lib.go("ticket/" + encodeURIComponent(k))); s.append(lh);
      rs.forEach((r, j) => {
        const off = o.hl && roleLabel(r.role) !== o.hl, rw = r.rework, g = STAGE(r.role) || "g3";
        const cy = y + ((j % 3) - 1) * 5;
        const tl = !has(r);
        s.append(sv("circle", { cx: X(pos(r)), cy, r: off ? 3 : 4, cls: tl ? "tl" + (off ? " faded" : "") : "f-" + g + (rw ? " rework s-" + g : "") + (off ? " faded" : ""), stroke: rw || tl ? null : "var(--surface)", "stroke-width": 1.5 }));
        s.append(sv("circle", { cx: X(pos(r)), cy, r: 7, cls: "hit", "data-tip": `${roleLabel(r.role)} · ${k} · ${when(r.start)}\n` + (tl ? "S hidden: too little evidence" + (r.coverage !== null && r.coverage !== undefined ? ` (${pct(r.coverage)} of the weight had data)` : "") : `S ${pS(r.S)}`) + (rk && !tl ? ` · rank within the role ${pS(rk.get(r))}` : "") + (rw ? "\nrework run" : "") }));
      });
      if (vis.length) {
        const vs = vis.filter(has);
        const av = vs.length ? mean(vs.map(val)) : null;
        if (av === null) s.append(sv("text", { x: W - R + 8, y: y + 4, cls: "tx-m", text: "S hidden" })); else {
        s.append(sv("line", { x1: X(av), x2: X(av), y1: y - 9, y2: y + 9, cls: "l-hl" }));
        s.append(sv("text", { x: W - R + 8, y: y + 4, cls: "tx tx-num", text: `${pS(av)} · n=${vs.length}` })); }
      } else s.append(sv("text", { x: W - R + 8, y: y + 4, cls: "tx-m", text: "—" }));
    });
    return s;
  };

  /* ---------- handoffs ---------- */
  const ABBR = { "business-analyst": "BA", "system-analyst": "SA", "qa-analyst": "QA-A", "requirements-reviewer": "Req-R", "test-designer": "TD", "lead-qa": "Lead-QA", "automation-engineer": "AE", "test-manager": "TM", "test-runner": "TR", builder: "Build", reviewer: "Rev", "security-engineer": "Sec", "environment-checker": "Env", verifier: "Ver", "independent-auditor": "Aud" };
  C.ABBR = ABBR;
  C.flowDiagram = function (width, steps) {
    const order = []; for (const st of steps) if (!order.includes(st.to_role)) order.push(st.to_role);
    const pos = Object.fromEntries(order.map((r, i) => [r, i]));
    const edges = {};
    for (const st of steps) { if (!st.from_role) continue; const k = st.from_role + ">" + st.to_role; (edges[k] = edges[k] || { a: st.from_role, b: st.to_role, n: 0, back: 0 }).n++; if (st.sent_back) edges[k].back++; }
    const E = Object.values(edges);
    const W = Math.max(320, width), n = order.length, gap = 8, nw = Math.max(46, (W - gap * (n - 1)) / n), nh = 34;
    const cx = (i) => i * (nw + gap) + nw / 2;
    const maxSpan = Math.max(1, ...E.map((e) => Math.abs(pos[e.b] - pos[e.a])));
    const arcH = (d) => 18 + (Math.min(d, 8) / Math.min(maxSpan, 8)) * 70;
    const top = 26 + arcH(maxSpan), H = top + nh + 26 + arcH(maxSpan);
    const s = sv("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
    s.append(sv("defs", null, [
      sv("marker", { id: "ah", viewBox: "0 0 8 8", refX: "7", refY: "4", markerWidth: "8", markerHeight: "8", markerUnits: "userSpaceOnUse", orient: "auto-start-reverse" }, sv("path", { d: "M0,0 L8,4 L0,8 z", cls: "ah" })),
      sv("marker", { id: "ahb", viewBox: "0 0 8 8", refX: "7", refY: "4", markerWidth: "8", markerHeight: "8", markerUnits: "userSpaceOnUse", orient: "auto-start-reverse" }, sv("path", { d: "M0,0 L8,4 L0,8 z", cls: "ahb" }))]));
    const sw = (c) => 1.2 + Math.log2(c) * 1.4;
    for (const e of E) {
      const i = pos[e.a], j = pos[e.b], back = j < i, self = i === j;
      let d, lx, ly;
      if (self) { const x = cx(i); d = `M${x - 8},${top} C${x - 18},${top - 28} ${x + 18},${top - 28} ${x + 8},${top}`; lx = x; ly = top - 26; }
      else if (!back) { const x1 = cx(i) + 6, x2 = cx(j) - 6, h = arcH(j - i); d = `M${x1},${top} C${x1},${top - h} ${x2},${top - h} ${x2},${top}`; lx = (x1 + x2) / 2; ly = top - h * 0.75 - 3; }
      else { const x1 = cx(i) - 6, x2 = cx(j) + 6, y0 = top + nh, h = arcH(i - j); d = `M${x1},${y0} C${x1},${y0 + h} ${x2},${y0 + h} ${x2},${y0}`; lx = (x1 + x2) / 2; ly = y0 + h * 0.75 + 12; }
      const cls = e.back ? "fl-back" : back ? "fl-loop" : "fl-fwd";
      s.append(sv("path", { d, cls, "stroke-width": sw(e.n), opacity: e.n === 1 ? 0.45 : null, "marker-end": `url(#${e.back ? "ahb" : "ah"})` }));
      if (e.n > 1) s.append(sv("text", { x: lx, y: ly, "text-anchor": "middle", cls: "tx tx-num fl-n", text: String(e.n) }));
      s.append(sv("path", { d, cls: "fl-hit", "data-tip": `${e.a} → ${e.b}: ${e.n} time${e.n > 1 ? "s" : ""}` + (e.back ? `\n${e.back} sent back by the gate (rework)` : back ? "\nback to an earlier role" : self ? "\nthe same role ran again" : "") }));
    }
    order.forEach((r, i) => {
      const runs = steps.filter((st) => st.to_role === r), rw = runs.filter((st) => st.rework).length;
      const x = cx(i) - nw / 2, g = STAGE(r) || "g0";
      s.append(sv("rect", { x, y: top, width: nw, height: nh, rx: 6, cls: "fl-node" }));
      s.append(sv("rect", { x, y: top, width: 4, height: nh, rx: 2, cls: "f-" + g }));
      s.append(sv("text", { x: x + nw / 2 + 2, y: top + 15, "text-anchor": "middle", cls: "tx-ink", text: nw > 110 ? r : ABBR[r] || r.slice(0, 6) }));
      s.append(sv("text", { x: x + nw / 2 + 2, y: top + 28, "text-anchor": "middle", cls: "tx-m tx-num", text: `${runs.length}×` + (rw ? ` · ${rw} rework` : "") }));
      s.append(sv("rect", { x, y: top, width: nw, height: nh, cls: "hit", "data-tip": `${r}\n${runs.length} agent${runs.length > 1 ? "s" : ""} started` + (rw ? `, ${rw} of them rework` : "") + `\nfirst at ${when(runs[0].start)}` }));
    });
    return s;
  };
  C.flowSteps = function (width, steps) {
    const order = []; for (const st of steps) if (!order.includes(st.to_role)) order.push(st.to_role);
    const n = steps.length, L = 130, R = 14, LH = 22, T = 22;
    const W = Math.max(320, Math.max(width, L + R + n * 9)), H = T + order.length * LH + 22;
    const s = sv("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
    const X = (i) => L + (W - L - R) * (n === 1 ? 0.5 : i / (n - 1)), Y = (r) => T + order.indexOf(r) * LH + LH / 2;
    order.forEach((r) => {
      s.append(sv("line", { x1: L, x2: W - R, y1: Y(r), y2: Y(r), cls: "gridl" }));
      s.append(sv("text", { x: L - 8, y: Y(r) + 4, "text-anchor": "end", cls: "tx-ink", text: r.length > 19 ? r.slice(0, 18) + "…" : r }));
    });
    let lastDay = "", lastX = -1e9;
    steps.forEach((st, i) => { const t = new Date(st.start), lab = TF.format(t), d = DD.format(t); if (X(i) - lastX > 60) { s.append(sv("text", { x: X(i), y: 12, "text-anchor": "middle", cls: "tx-m tx-num", text: (d !== lastDay ? d + " " : "") + lab })); lastX = X(i); lastDay = d; } });
    steps.forEach((st, i) => {
      if (st.pred_index < 0) return;
      s.append(sv("line", { x1: X(st.pred_index), y1: Y(st.from_role), x2: X(i), y2: Y(st.to_role), cls: st.sent_back ? "fl-back" : "fl-fwd", "stroke-width": st.sent_back ? 1.6 : 1.1, opacity: st.sent_back ? null : 0.55 }));
    });
    steps.forEach((st, i) => {
      const g = STAGE(st.to_role) || "g0", rw = st.rework;
      s.append(sv("circle", { cx: X(i), cy: Y(st.to_role), r: 4.5, cls: "f-" + g + (rw ? " rework s-" + g : ""), stroke: rw ? null : "var(--surface)", "stroke-width": 2 }));
      s.append(sv("circle", { cx: X(i), cy: Y(st.to_role), r: 9, cls: "hit", "data-tip": `#${st.n} ${st.to_role} · ${when(st.start)} · ${dur(st.duration_s)}\nafter: ${st.from_role || "start (coordinator)"}` + (st.sent_back ? "\nsent back by the gate: rework" : st.parallel ? "\nran in parallel with another role" : "") + (st.S !== null && st.S !== undefined ? `\nS ${pS(st.S)}` : "") }));
    });
    return s;
  };

  /* ---------- the ticket timeline ---------- */
  C.gantt = function (width, runs, waits, tests) {
    const W = Math.max(320, width), L = 150, R = 12, BREAK = 30, GAPMIN = CTQ.meta.gap_cut_s * 1000;
    const uni = (iv) => { const a = iv.filter((x) => x[1] > x[0]).sort((x, y) => x[0] - y[0]); const out = []; for (const v of a) { const l = out[out.length - 1]; if (l && v[0] <= l[1]) l[1] = Math.max(l[1], v[1]); else out.push([v[0], v[1]]); } return out; };
    const w = waits.map((x) => ({ a: ms(x.start), b: ms(x.end), kind: x.kind, run: x.run_id }));
    const away = uni(w.filter((x) => ["human", "ask", "parked", "blocked"].includes(x.kind)).map((x) => [x.a, x.b]));
    const act = [];
    for (const r of runs) {
      const a0 = ms(r.start), b0 = ms(r.end);
      if (r.kind !== "main") { act.push([a0, b0]); continue; }
      let cur = a0;
      for (const v of away) { if (v[1] <= cur || v[0] >= b0) continue; if (v[0] > cur) act.push([cur, v[0]]); cur = Math.max(cur, v[1]); }
      if (cur < b0) act.push([cur, b0]);
    }
    const A = uni(act.length ? act : runs.map((r) => [ms(r.start), ms(r.end)]));
    const blocks = [];
    for (const a of A) { const last = blocks[blocks.length - 1]; if (last && a[0] - last[1] <= GAPMIN) last[1] = a[1]; else blocks.push([a[0], a[1]]); }
    if (!blocks.length) blocks.push([Math.min(...runs.map((r) => ms(r.start))), Math.max(...runs.map((r) => ms(r.end)))]);
    const activeMs = sum(blocks, (b) => b[1] - b[0]) || 1;
    const plotW = Math.max(60, W - L - R - BREAK * (blocks.length - 1));
    const segs = []; let px = L;
    for (const b of blocks) { const wd = ((b[1] - b[0]) / activeMs) * plotW; segs.push({ a: b[0], b: b[1], x: px, w: wd }); px += wd + BREAK; }
    const X = (tm) => {
      for (let i = 0; i < segs.length; i++) {
        const g = segs[i];
        if (tm <= g.b || i === segs.length - 1) { if (tm < g.a) return i ? segs[i - 1].x + segs[i - 1].w + BREAK / 2 : g.x; return g.x + Math.min(1, (tm - g.a) / Math.max(1, g.b - g.a)) * g.w; }
      }
      return W - R;
    };
    const laneOrder = []; const lanes = {};
    for (const r of runs) { const k = roleLabel(r.role); if (!lanes[k]) { lanes[k] = []; laneOrder.push(k); } lanes[k].push(r); }
    laneOrder.sort((x, y) => (x === "main session" ? -1 : y === "main session" ? 1 : 0));
    const rowsOut = [], rowOf = new Map();
    for (const k of laneOrder) {
      const rows = [];
      for (const r of lanes[k]) { let i = rows.findIndex((end) => end <= ms(r.start)); if (i < 0) { i = rows.length; rows.push(0); } rows[i] = ms(r.end); rowOf.set(r, i); }
      rowsOut.push({ k, n: rows.length });
    }
    const SUB = 12, PAD = 8;
    let y = 34; const laneY = {};
    for (const l of rowsOut) { laneY[l.k] = y; y += l.n * SUB + PAD * 2; }
    const H = y + 4;
    const s = sv("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img" });
    let lastLbl = -1e9, lastBrk = -1e9;
    segs.forEach((g, i) => {
      s.append(sv("line", { x1: g.x, x2: g.x, y1: 26, y2: H, cls: "gridl" }));
      if (g.x - lastLbl > 92) { lastLbl = g.x; s.append(sv("text", { x: g.x + 2, y: 11, cls: "tx-m tx-num", text: (i === 0 || DD.format(new Date(g.a)) !== DD.format(new Date(segs[i - 1].a)) ? DD.format(new Date(g.a)) + " " : "") + TF.format(new Date(g.a)) })); }
      if (i < segs.length - 1) {
        const gap = segs[i + 1].a - g.b, bx = g.x + g.w + BREAK / 2;
        const inGap = (kinds) => sum(w.filter((v) => kinds.includes(v.kind)), (v) => Math.max(0, Math.min(v.b, segs[i + 1].a) - Math.max(v.a, g.b)));
        const parked = inGap(["parked"]), waiting = inGap(["human", "ask"]), blocked = inGap(["blocked"]);
        const what = parked > gap * 0.5 ? "parked" : waiting > gap * 0.5 ? "waiting" : blocked > gap * 0.5 ? "blocked" : "";
        s.append(sv("line", { x1: bx, x2: bx, y1: 30, y2: H - 6, cls: "axisl", "stroke-dasharray": "2 3" }));
        if (bx - lastBrk > 50) { s.append(sv("text", { x: bx, y: 25, "text-anchor": "middle", cls: "tx-m", text: (what === "parked" ? "parked " : "") + dur(gap / 1000) })); lastBrk = bx; }
        s.append(sv("rect", { x: bx - BREAK / 2, y: 14, width: BREAK, height: H - 14, cls: "hit", "data-tip": `${dur(gap / 1000)} cut out\n${when(new Date(g.b).toISOString())} → ${when(new Date(segs[i + 1].a).toISOString())}\n` +
          (what === "parked" ? `parked: the session was left open (${dur(parked / 1000)})` : what === "waiting" ? `mostly waiting for you (${dur(waiting / 1000)})` : what === "blocked" ? `a tool call sat here (${dur(blocked / 1000)}): probably a permission prompt` : "no agent running") }));
      }
    });
    const testsOf = {}; for (const t of tests) (testsOf[t.run_id] = testsOf[t.run_id] || []).push(t);
    const waitsOf = {}; for (const v of w) (waitsOf[v.run] = waitsOf[v.run] || []).push(v);
    for (const l of rowsOut) {
      const ly = laneY[l.k];
      s.append(sv("text", { x: L - 8, y: ly + PAD + SUB / 2 + 4, "text-anchor": "end", cls: "tx-ink", text: l.k.length > 21 ? l.k.slice(0, 20) + "…" : l.k }));
      s.append(sv("line", { x1: L, x2: W - R, y1: ly + l.n * SUB + PAD * 2 - 1, y2: ly + l.n * SUB + PAD * 2 - 1, cls: "gridl" }));
      for (const r of lanes[l.k]) {
        const by = ly + PAD + rowOf.get(r) * SUB, a0 = ms(r.start), b0 = ms(r.end), x0 = X(a0), x1 = X(b0), isMain = r.kind === "main";
        s.append(sv("rect", { x: x0, y: by + 1, width: Math.max(2, x1 - x0), height: SUB - 3, rx: 2, cls: isMain ? "f-main" : "f-work", opacity: isMain ? 0.35 : 1 }));
        for (const v of waitsOf[r.run_id] || []) {
          if (v.b <= a0 || v.a >= b0) continue;
          const wx0 = X(Math.max(v.a, a0)), wx1 = X(Math.min(v.b, b0));
          if (wx1 - wx0 < 1) continue;
          const cls = v.kind === "human" || v.kind === "ask" ? "f-wait" : v.kind === "parked" ? "f-park" : v.kind === "blocked" ? "f-block" : null;
          if (cls) s.append(sv("rect", { x: wx0, y: by + 1, width: wx1 - wx0, height: SUB - 3, cls, opacity: v.kind === "blocked" ? 0.6 : null }));
        }
        for (const t of testsOf[r.run_id] || []) {
          const tx = X(ms(t.start)), tw = Math.max(2, X(ms(t.start) + t.duration_s * 1000) - tx);
          s.append(sv("rect", { x: tx - 1, y: by + SUB - 1, width: tw, height: 3, cls: t.is_error ? "f-crit" : "f-test" }));
          if (t.timed_out) s.append(sv("path", { d: `M${tx - 3},${by - 2} l3,5 l3,-5 z`, cls: "f-crit" }));
          s.append(sv("rect", { x: tx - 2, y: by + SUB - 3, width: tw + 3, height: 7, cls: "hit", "data-tip": `${t.class} · ${dur(t.duration_s)}${t.is_error ? " · failed" : ""}${t.timed_out ? " · timed out: a timeout or a permission prompt, not test time" : ""}\n${when(t.start)}` }));
        }
        const tl = testsOf[r.run_id] || [];
        const tipTxt = `${roleLabel(r.role)}${isMain ? "" : " (sub-agent)"}\n${when(r.start)} · ${dur(r.duration_s)}\n${usd(r.cost)} · ${r.rounds} model calls` +
          (tl.length ? `\n${tl.length} test runs · ${dur(sum(tl.filter((t) => !t.timed_out), (t) => t.duration_s))}${tl.some((t) => t.is_error) ? " · " + tl.filter((t) => t.is_error).length + " failed" : ""}` : "") +
          (r.S !== null && r.S !== undefined ? `\nS ${pS(r.S)}` : "") + (r.flags.length ? `\nflags: ${r.flags.join(", ").replace(/_/g, " ")}` : "") +
          (isMain ? `\nwaiting for you ${dur(sum((waitsOf[r.run_id] || []).filter((v) => v.kind === "human" || v.kind === "ask"), (v) => (v.b - v.a) / 1000))}` : "");
        const hit = sv("rect", { x: x0 - 2, y: by, width: Math.max(6, x1 - x0 + 4), height: SUB - 4, cls: "hit", "data-tip": tipTxt });
        hit.addEventListener("click", () => CTQ.lib.go("run/" + encodeURIComponent(r.run_id)));
        s.append(hit);
      }
    }
    return s;
  };

  /* ---------- a stacked split bar with a legend line, used on the Run page ---------- */
  C.splitBar = function (parts, total) {
    const box = el("div", { cls: "stack", "data-tip": parts.map((p) => `${p.label} ${dur(p.v)}`).join("\n") });
    for (const p of parts) if (p.v > 0) { const sp = el("span", { cls: p.cls }); sp.style.width = (p.v / (total || 1) * 100) + "%"; box.append(sp); }
    return box;
  };
})();
