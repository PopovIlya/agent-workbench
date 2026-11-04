"use strict";
/* Agent console UI. No HTML-string injection anywhere: every value goes through textContent / setAttribute. */

const $app = document.getElementById("app");
const $tip = document.getElementById("tip");
const NS = "http://www.w3.org/2000/svg";

function el(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") e.className = v;
    else if (k === "onclick") e.addEventListener("click", v);
    else if (k === "onchange") e.addEventListener("change", v);
    else if (v !== null && v !== undefined && v !== false) e.setAttribute(k, v);
  }
  add(e, kids);
  return e;
}
function add(e, kids) {
  for (const k of kids.flat()) {
    if (k === null || k === undefined || k === false) continue;
    e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
}
function svg(tag, attrs, ...kids) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  for (const k of kids.flat()) if (k) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}
const fmtInt = (n) => (n === null || n === undefined ? "–" : Math.round(n).toLocaleString("en-US"));
function fmtTok(n) {
  if (n === null || n === undefined) return "–";
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(2) + " B";
  if (a >= 1e6) return (n / 1e6).toFixed(1) + " M";
  if (a >= 1e3) return (n / 1e3).toFixed(1) + " K";
  return String(Math.round(n));
}
function fmtDur(s) {
  if (s === null || s === undefined) return "–";
  if (s < 90) return Math.round(s) + " s";
  if (s < 5400) return Math.round(s / 60) + " min";
  return (s / 3600).toFixed(1) + " h";
}
const fmtTs = (t) => (t ? t.replace("T", " ").slice(0, 16) : "–");
const link = (hash, text) => el("a", { href: hash }, text);
const runLink = (id, text) => link("#/run/" + encodeURIComponent(id), text || id.slice(-8));

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r.json();
}
const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

function tip(e, text) {
  $tip.textContent = text; $tip.hidden = false;
  $tip.style.left = Math.min(e.clientX + 12, innerWidth - 340) + "px"; $tip.style.top = e.clientY + 14 + "px";
}
const hideTip = () => { $tip.hidden = true; };
function hover(node, text) {
  node.addEventListener("mousemove", (e) => tip(e, text));
  node.addEventListener("mouseleave", hideTip);
  return node;
}

function table(cols, rows, empty) {
  if (!rows.length) return el("div", { class: "empty" }, empty || "Nothing to show.");
  return el("table", {}, el("thead", {}, el("tr", {}, cols.map((c) => el("th", { class: c.num ? "num" : "" }, c.h)))),
    el("tbody", {}, rows.map((r) => el("tr", {}, cols.map((c) => el("td", { class: c.num ? "num" : "" }, c.f(r)))))));
}
const costLabel = (a) => (a ? a.cost_label : "cost unknown");
/* ---------- router ---------- */
const SUB = [["overview", "Overview"], ["tickets", "Tickets"], ["roles", "Roles"], ["sessions", "Sessions"]];
async function render(quiet) {
  hideTip();
  if (window.CTQ && CTQ.lib) CTQ.lib.resetTips();
  if (!quiet) api("/api/rescan", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).then(pollStatus, () => {});
  const parts = CTQ.lib.parseHash();
  const name = parts[0] || "overview";
  const tab = "agents";
  document.querySelectorAll("#tabs a").forEach((a) => a.classList.toggle("on", a.dataset.tab === tab));
  const on = (n) => name === n || (n === "tickets" && name === "ticket") || (n === "roles" && name === "role");
  document.getElementById("sub").replaceChildren(...(tab === "agents" ? [...SUB.map(([n, label]) => el("a", { href: CTQ.lib.href(n), class: on(n) ? "on" : "" }, label))] : []));
  try {
    const arg = parts.slice(1).join("/");
    const page = { overview: CTQ.pages.overview, tickets: CTQ.pages.tickets, ticket: () => CTQ.pages.ticket(arg), roles: CTQ.pages.roles, role: () => CTQ.pages.role(arg), sessions: CTQ.pages.sessions,
      run: () => pageRun(arg) }[name];
    const node = await (page || CTQ.pages.overview)();
    $app.replaceChildren(node);
    CTQ.afterMount($app);
  } catch (e) {
    $app.replaceChildren(el("div", { class: "empty" }, "Could not load this page (" + e.message + ")."));
  }
}
let lastScans = null, pollTimer = null;
function paintStatus(st) {
  const box = document.getElementById("status");
  const when = st.last_scan_ok ? new Date(st.last_scan_ok).toLocaleTimeString("en-GB", { hour12: false }) : "never";
  const age = st.age_s === null || st.age_s === undefined ? "" : st.age_s < 90 ? ` (${Math.round(st.age_s)} s ago)` : ` (${Math.round(st.age_s / 60)} min ago)`;
  const sWhen = st.last_score_ok ? new Date(st.last_score_ok).toLocaleTimeString("en-GB", { hour12: false }) : "never";
  const sAge = st.score_age_s === null || st.score_age_s === undefined ? "" : st.score_age_s < 90 ? ` (${Math.round(st.score_age_s)} s ago)` : ` (${Math.round(st.score_age_s / 60)} min ago)`;
  const scoring = ` · last scoring ${sWhen}${sAge}${st.score_error ? " ⚠ " + st.score_error : ""}`;
  const text = (st.state === "indexing" ? `scanning ${st.files_done}/${st.files_total}… · last rescan ${when}${age}` : `last rescan ${when}${age}`) + scoring;
  box.replaceChildren(el("span", { class: st.stale ? "stale" : "" }, (st.stale ? "⚠ STALE · " : "") + text));
  box.title = `Index of ~/.claude/projects. Rescans on every page load and every 30 s. Stale after ${st.stale_after_s} s. Scoring runs by itself after a rescan that found new or changed runs (at most once a minute).`;
}
async function pollStatus() {
  try {
    const st = await api("/api/status");
    paintStatus(st);
    if (lastScans !== null && st.scans !== lastScans && st.state === "idle" && !document.querySelector("pre.text")) { lastScans = st.scans; render(true); }  // never redraw the Data tab under a half-filled form
    lastScans = st.scans;
    clearTimeout(pollTimer);
    pollTimer = setTimeout(pollStatus, st.state === "indexing" ? 1500 : 5000);
  } catch (e) { document.getElementById("status").textContent = "⚠ console not reachable"; pollTimer = setTimeout(pollStatus, 5000); }
}
addEventListener("hashchange", render);
render(); pollStatus();
