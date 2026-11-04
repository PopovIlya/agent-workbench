"use strict";
/* Shared pieces of the cost / time / quality pages: DOM builders, number formats, the URL state (period + filters), tooltips and "?" tips,
   panels with a Table toggle, and the small tables. No HTML strings anywhere: values go through textContent / setAttribute only. */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const L = CTQ.lib = {};

  /* ---------- DOM ---------- */
  function el(tag, attrs, kids) {
    const e = document.createElement(tag);
    if (attrs) for (const k in attrs) {
      const v = attrs[k];
      if (v === null || v === undefined || v === false) continue;
      if (k === "text") e.textContent = v;
      else if (k === "cls") e.className = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
    if (kids !== undefined && kids !== null) for (const c of [].concat(kids).flat(Infinity)) if (c !== null && c !== undefined && c !== false) e.append(c.nodeType ? c : document.createTextNode(String(c)));
    return e;
  }
  function sv(tag, attrs, kids) {
    const e = document.createElementNS(NS, tag);
    if (attrs) for (const k in attrs) { const v = attrs[k]; if (v === null || v === undefined) continue; if (k === "text") e.textContent = v; else if (k === "cls") e.setAttribute("class", v); else e.setAttribute(k, v); }
    if (kids) for (const c of [].concat(kids)) if (c) e.append(c);
    return e;
  }
  Object.assign(L, { el, sv });

  /* ---------- numbers ---------- */
  const sum = (a, f) => a.reduce((s, x) => s + (f ? f(x) : x), 0);
  const mean = (a) => (a.length ? sum(a) / a.length : null);
  function median(a) { if (!a.length) return null; const s = a.slice().sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
  function usd(v) {
    if (v === null || v === undefined) return "—";
    if (v === 0) return "$0";
    if (v < 0.995) return "$" + v.toFixed(2);
    if (v < 99.5) return "$" + v.toFixed(1);
    return "$" + Math.round(v).toLocaleString("en-US");
  }
  function dur(s) {
    if (s === null || s === undefined) return "—";
    if (s < 1) return "0 s";
    if (s < 60) return Math.round(s) + " s";
    if (s < 3600) return Math.round(s / 60) + " min";
    if (s < 100 * 3600) return (s / 3600).toFixed(s < 10 * 3600 ? 1 : 0) + " h";
    return (s / 86400).toFixed(1) + " d";
  }
  const pct = (v) => Math.round(v * 100) + "%";
  const pS = (v) => (v === null || v === undefined ? "—" : Math.round(v * 100) + "%");
  const ms = (t) => Date.parse(t);
  const DF = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  const DD = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
  const TF = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" });
  const when = (t) => (t ? DF.format(new Date(t)) : "—");
  const fmtInt = (n) => (n === null || n === undefined ? "–" : Math.round(n).toLocaleString("en-US"));
  function niceMax(v) { if (v <= 0) return 1; const p = Math.pow(10, Math.floor(Math.log10(v))); const f = v / p; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p; }
  const roleLabel = (r) => (r === "main" ? "main session" : r);
  const money = (usdV, share) => usd(usdV) + " · " + pct(share);      // a money amount next to a percentage is always separated by " · "
  Object.assign(L, { sum, mean, median, usd, dur, pct, pS, ms, DF, DD, TF, when, fmtInt, niceMax, roleLabel, money });

  /* ---------- URL state: period + filters live in the hash, never in storage ---------- */
  const PRESETS = [["1h", "Last hour", 3600e3], ["24h", "Last 24 h", 86400e3], ["7d", "Last 7 days", 7 * 86400e3], ["30d", "Last 30 days", 30 * 86400e3], ["all", "All", null]];
  const S = L.state = { p: "7d", from: null, to: null, proj: "", q: "" };
  L.PRESETS = PRESETS;
  L.parseHash = function () {
    const raw = (location.hash || "#/overview").replace(/^#\/?/, "");
    const [path, query] = raw.split("?");
    const q = new URLSearchParams(query || "");
    if (q.get("from") && q.get("to")) { S.p = "custom"; S.from = q.get("from"); S.to = q.get("to"); }
    else { S.p = PRESETS.some((x) => x[0] === q.get("p")) ? q.get("p") : "7d"; S.from = S.to = null; }
    S.proj = q.get("proj") || ""; S.q = q.get("q") || "";
    return path.split("/").map(decodeURIComponent);
  };
  L.qs = function (extra) {
    const q = new URLSearchParams();
    if (S.p === "custom") { q.set("from", S.from); q.set("to", S.to); } else if (S.p !== "7d") q.set("p", S.p);
    if (S.proj) q.set("proj", S.proj);
    if (S.q) q.set("q", S.q);
    for (const k in extra || {}) q.set(k, extra[k]);
    const t = q.toString();
    return t ? "?" + t : "";
  };
  L.href = (path, extra) => "#/" + path + L.qs(extra);
  L.go = (path) => { location.hash = L.href(path); };
  L.apiParams = function (withFilters) {
    const p = {};
    if (S.p === "custom") { p.from = S.from; p.to = S.to; }
    else { const pr = PRESETS.find((x) => x[0] === S.p); if (pr && pr[2]) { const to = new Date(); p.from = new Date(to.getTime() - pr[2]).toISOString(); p.to = to.toISOString(); } }
    if (withFilters !== false) { if (S.proj) p.proj = S.proj; if (S.q) p.q = S.q; }
    return p;
  };
  L.get = async function (path, params, extra) {
    const q = new URLSearchParams(Object.assign({}, params === undefined ? L.apiParams() : params, extra || {}));
    return api(path + (q.toString() ? "?" + q.toString() : ""));
  };

  /* ---------- tooltips and "?" tips (one #tip element, shared with the rest of the console) ---------- */
  let pinned = null;
  function showTip(text, x, y) {
    $tip.textContent = text; $tip.hidden = false;
    const w = $tip.offsetWidth, h = $tip.offsetHeight;
    let px = x + 14, py = y + 14;
    if (px + w > innerWidth - 8) px = x - w - 14;
    if (py + h > innerHeight - 8) py = y - h - 14;
    $tip.style.left = Math.max(8, px) + "px"; $tip.style.top = Math.max(8, py) + "px";
  }
  document.addEventListener("mousemove", (e) => {
    if (pinned) return;
    const t = e.target.closest && e.target.closest("[data-tip]");
    if (!t) { if (!$tip.hidden && !e.target.closest("#tip")) $tip.hidden = true; return; }
    showTip(t.getAttribute("data-tip"), e.clientX, e.clientY);
  });
  document.addEventListener("click", (e) => {
    const h = e.target.closest && e.target.closest(".help");
    const was = pinned;
    if (pinned) { pinned.classList.remove("pinned"); pinned = null; $tip.hidden = true; }
    if (h) { e.stopPropagation(); e.preventDefault(); if (h !== was) { pinned = h; h.classList.add("pinned"); const r = h.getBoundingClientRect(); showTip(h.getAttribute("data-tip"), r.right, r.bottom); } }
  }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && pinned) { pinned.classList.remove("pinned"); pinned = null; $tip.hidden = true; } });
  document.addEventListener("scroll", () => { if (!pinned) $tip.hidden = true; }, true);
  L.resetTips = () => { pinned = null; $tip.hidden = true; };

  const help = (text) => el("button", { cls: "help", type: "button", "aria-label": "Explain", "data-tip": text, text: "?" });
  const lbl = (text, tipText) => el("span", { cls: "hl" }, [text, tipText ? help(tipText) : null]);
  Object.assign(L, { help, lbl });

  /* ---------- panels with a Table toggle, drawn after they are attached (they need their width) ---------- */
  let panels = [];
  L.panel = function (title, sub, chartFn, tableFn, legend, titleHelp) {
    const body = el("div", { cls: "scroll" });
    const tbl = el("div", { cls: "hidden scroll" });
    const btn = tableFn ? el("button", { cls: "tbtn", text: "Table", onclick: () => {
      const show = tbl.classList.contains("hidden");
      tbl.classList.toggle("hidden", !show); body.classList.toggle("hidden", show);
      btn.textContent = show ? "Chart" : "Table";
      tbl.textContent = ""; if (show) tbl.append(tableFn());
    } }) : null;
    const head = el("div", { cls: "phead" }, [el("div", null, [el("h2", null, [title, titleHelp ? help(titleHelp) : null]), sub ? el("div", { cls: "sub", text: sub }) : null]), btn]);
    const p = el("section", { cls: "panel" }, [head, legend || null, body, tbl]);
    p._head = head;
    p._draw = () => { body.textContent = ""; body.append(chartFn(body.clientWidth || p.clientWidth - 32 || 600)); };
    return p;
  };
  L.collect = function (root) {
    panels = [];
    (function walk(n) { if (n._draw) panels.push(n); for (const c of n.children || []) walk(c); })(root);
  };
  L.redraw = () => { for (const p of panels) p._draw(); };
  let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(L.redraw, 120); });
  CTQ.afterMount = function (root) { L.collect(root); L.redraw(); };

  L.emptyPanel = (title, text) => el("section", { cls: "panel" }, [el("h2", { text: title }), el("p", { cls: "dim", text })]);
  L.legendOf = (items) => el("div", { cls: "legend" }, items.map(([cls, label]) => el("span", null, [el("i", { cls }), label])));
  L.simpleTable = (head, rows, numCols) => el("table", null, [
    el("thead", null, el("tr", null, head.map((h, i) => el("th", { cls: numCols && numCols.includes(i) ? "n" : null }, h)))),
    el("tbody", null, rows.map((r) => el("tr", null, r.map((c, i) => el("td", { cls: numCols && numCols.includes(i) ? "n" : null }, c)))))]);
  L.findings = (items) => {
    items = (items || []).filter(Boolean);
    return items.length ? el("section", { cls: "findings" }, [el("div", { cls: "fh", text: "What stands out" }), el("ul", null, items.map((x) => el("li", null, x)))]) : null;
  };
  L.flagsLegend = () => el("details", null, [el("summary", { text: `What each flag means (${CTQ.FLAGS.length} types)` }),
    el("div", { cls: "scroll" }, L.simpleTable(["Flag", "Meaning"], CTQ.FLAGS.map((f) => [flagBadge(f[0]), f[2]])))]);
  function flagBadge(f) {
    const meaning = (CTQ.FLAGS.find((x) => x[0] === f) || [])[2] || f;
    return el("span", { cls: "badge " + (CTQ.FLAG_LEVEL[f] || ""), "data-tip": meaning, text: f.replace(/_/g, " ") });
  }
  L.flagBadge = flagBadge;
  L.kpi = (label, value, sub, tipText) => el("div", { cls: "kpi" }, [el("div", { cls: "l" }, [label, tipText ? help(tipText) : null]), el("div", { cls: "v", text: value }), sub ? el("div", { cls: "s", text: sub }) : null]);

  /* quality cells */
  L.qcell = (S_, n, nEval, nTooLittle) => {
    if (S_ === null || S_ === undefined) {
      if (nEval) return el("span", { cls: "dim", "data-tip": `${nEval} run${nEval > 1 ? "s" : ""} evaluated, but the checks that have data carry less than half of the weight (${nTooLittle || nEval} without enough evidence). S is not shown rather than guessed.` }, "too little evidence");
      return el("span", { cls: "dim", text: "not scored" });
    }
    const few = n < CTQ.meta.min_scored;
    return el("span", null, [el("span", { cls: S_ >= CTQ.meta.bar ? "ok" : "", text: pS(S_) }),
      el("span", { cls: "badge" + (few ? " warn" : ""), "data-tip": few ? `Fewer than ${CTQ.meta.min_scored} scored runs: too few to judge.` : `Average of ${n} scored runs.`, text: "n=" + n })]);
  };
  L.critCell = (v) => {
    if (!v || !v[1]) return el("span", { cls: "dim", "data-tip": "This check does not apply to the role, or there are no scored runs.", text: "–" });
    const r = v[0] / v[1];
    return el("span", { "data-tip": `Passed in ${v[0]} of ${v[1]} scored runs` }, [el("span", { cls: "pc " + (r >= CTQ.meta.bar ? "ok" : r < 0.5 ? "err" : ""), text: pct(r) }), el("span", { cls: "dim", text: ` · ${v[0]}/${v[1]}` })]);
  };
  L.meanCell = (m, n, emptyShare) => {
    if (m === null || m === undefined) return el("span", { cls: "dim", "data-tip": emptyShare === null || emptyShare === undefined ? "No data yet." : `Empty in ${pct(emptyShare)} of the runs: no data yet.`, text: "–" });
    return el("span", { "data-tip": `Mean over ${n} run${n === 1 ? "" : "s"} that have this check` + (emptyShare ? `; empty in ${pct(emptyShare)} of all runs` : "") }, [el("span", { cls: "pc " + (m >= CTQ.meta.bar ? "ok" : m < 0.5 ? "err" : ""), text: pct(m) }), el("span", { cls: "dim", text: ` · n=${n}` })]);
  };
  /* the gate and the weighted checks, as columns: [key, label, kind] ; the judge column appears only when it carries weight */
  L.checkCols = () => [["delivered", "delivered", "gate"], ["first_pass", "first pass", "pass"], ["outcome", "outcome", "mean"], ["follows", "follows", "pass"], ["grounded", "grounded", "mean"],
    ...(CTQ.meta.judge && CTQ.meta.judge.weight_active ? [["judge", "judge", "mean"]] : [])];
  L.checkCell = (row, [k, , kind]) => {
    if (kind === "gate") return L.critCell(row.delivered);
    if (kind === "pass") return L.critCell(row.pass[k]);
    return L.meanCell(row.mean ? row.mean[k] : null, row.pass && row.pass[k] ? row.pass[k][1] : 0, row.empty_share ? row.empty_share[k] : null);
  };
  L.mark = (v) => (v === null || v === undefined ? el("span", { cls: "dim", text: "–" }) : v >= 1 ? el("span", { cls: "ok", text: "✓" }) : el("span", { cls: "err", text: "✗" }));
  L.sortHead = (cols, sc, onSort) => el("tr", null, cols.map(([k, h, n, tipText]) => el("th", {
    cls: [k ? "sort" : "", n ? "n" : "", sc.col === k ? "sorted" : "", sc.col === k && sc.asc ? "asc" : ""].join(" "),
    onclick: k ? ((e) => { if (e.target.closest(".help")) return; onSort(k); }) : null }, lbl(h, tipText))));
  L.rowClick = (path) => (e) => { if (!e.target.closest(".help") && !e.target.closest("a")) L.go(path); };
  L.stack = (parts, total, tipText) => {         // a horizontal split bar; widths set from JS (CSSOM), never from markup
    const box = el("div", { cls: "mini", "data-tip": tipText });
    for (const [v, cls] of parts) if (v > 0) { const s = el("span", { cls }); s.style.width = (v / (total || 1) * 100) + "%"; box.append(s); }
    return box;
  };

  /* ---------- the period bar and the filters ---------- */
  let filtersCache = null;
  async function filtersFor(params) {
    const key = JSON.stringify([params.from, params.to, S.proj]);
    if (filtersCache && filtersCache.key === key && Date.now() - filtersCache.at < 30000) return filtersCache.data;
    const data = await L.get("/api/ctq/filters", L.apiParams(false), S.proj ? { proj: S.proj } : {});
    filtersCache = { key, at: Date.now(), data };
    return data;
  }
  L.periodBar = async function (period, opts) {
    opts = opts || {};
    const navigate = () => { location.hash = "#/" + (location.hash.replace(/^#\/?/, "").split("?")[0] || "overview") + L.qs(); };
    const seg = el("span", { cls: "seg" }, PRESETS.map(([k, label]) => el("button", { cls: S.p === k ? "on" : "", text: label, onclick: () => { S.p = k; S.from = S.to = null; navigate(); } })));
    const day = (iso) => (iso || "").slice(0, 10);
    const from = el("input", { type: "date", value: S.from ? day(S.from) : day(period && period.from), "aria-label": "From" });
    const to = el("input", { type: "date", value: S.to ? day(S.to) : day(period && period.to), "aria-label": "To" });
    const apply = el("button", { cls: "tbtn" + (S.p === "custom" ? " on" : ""), text: "Apply dates", onclick: () => { if (from.value && to.value) { S.p = "custom"; S.from = from.value; S.to = to.value; navigate(); } } });
    const bar = el("div", { cls: "periodbar" }, [el("span", { text: "Period" }), seg, el("span", { cls: "range" }, ["from", from, "to", to, apply]),
      el("span", { cls: "when", text: period ? `${when(period.from)} – ${when(period.to)}` : "" }),
      period && period.incomplete ? el("span", { cls: "badge warn", text: "still indexing: the numbers are incomplete" }) : null]);
    if (opts.filters !== false) {
      let f = { projects: [], keys: [] };
      try { f = await filtersFor(L.apiParams(false)); } catch (e) { /* the page still works without the filter lists */ }
      const proj = el("select", { "aria-label": "Project", onchange: (e) => { S.proj = e.target.value; S.q = ""; navigate(); } },
        [el("option", { value: "", text: "All projects" }), ...f.projects.map((p) => el("option", { value: p.name, text: `${p.name} (${p.runs} runs)` }))]);
      proj.value = S.proj;
      const dl = el("datalist", { id: "tk-list" }, f.keys.map((k) => el("option", { value: k })));
      const q = el("input", { type: "search", list: "tk-list", placeholder: "Ticket key or part of it", value: S.q, "aria-label": "Ticket", size: 22, onchange: (e) => { S.q = e.target.value.trim(); navigate(); } });
      bar.append(el("span", { cls: "range" }, ["Project", proj, "Ticket", q, dl, (S.proj || S.q) ? el("button", { cls: "tbtn", text: "Clear filters", onclick: () => { S.proj = ""; S.q = ""; navigate(); } }) : null]));
    }
    return bar;
  };
  L.root = (nodes) => el("div", { cls: "ctq" }, nodes.filter(Boolean));
  L.loadMeta = async function () {
    if (!CTQ.meta) {
      CTQ.meta = await api("/api/ctq/meta");
      const j = CTQ.meta.judge || {};       // the judge's state belongs in the tooltip of S
      CTQ.help.S += "\n\nJudge: " + (!j.on ? "off" : "on") + (j.n ? `; calibration n=${j.n}, kappa ${j.kappa === null || j.kappa === undefined ? "–" : j.kappa}` : "; not calibrated yet")
        + ` (it needs n ≥ ${j.needs_n} and kappa ≥ ${j.needs_kappa} to carry weight${j.weight_active ? "; it does now" : "; it does not yet"}).`;
    }
    return CTQ.meta;
  };
})();

/* Rebuild a page from data it already holds (a switch or a chip), without fetching again. */
CTQ.lib.swap = function (build) {
  const old = document.querySelector("#app .ctq");
  const fresh = build();
  if (old) old.replaceWith(fresh); else document.getElementById("app").replaceChildren(fresh);
  CTQ.afterMount(fresh);
};
/* The common frame of a page: period bar, findings, panels. Empty period -> a sentence, never an empty chart. */
CTQ.lib.frame = async function (data, nodes, opts) {
  const bar = await CTQ.lib.periodBar(data.period, opts);
  return { bar, build: (extra) => CTQ.lib.root([bar, ...(data.period.runs === 0 ? [CTQ.lib.emptyPanel("No runs in this period", "Pick a longer period or clear the filters above.")] : [CTQ.lib.findings(data.findings), ...nodes(extra)])]) };
};
