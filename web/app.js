/* Market Terminal dashboard — vanilla JS, consumes the FastAPI JSON.
   Each view fetches its endpoint independently and renders into its section. */
"use strict";

const ENDPOINTS = {
  macro: "/macro/dashboard",
  watchlist: "/watchlist",
  cot: "/cot/dashboard",
  term: "/term-structure",
  sectors: "/screener/sectors",
  news: "/news?limit=40",
};

// ---- helpers ---------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const num = (v, d = 2) => (v === null || v === undefined || isNaN(v) ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: d }));
const pctCls = (v) => (v > 0 ? "up" : v < 0 ? "down" : "dim");
const pct = (v, d = 2) => (v === null || v === undefined ? '<span class="dim">—</span>' : `<span class="${pctCls(v)}">${v > 0 ? "+" : ""}${num(v, d)}%</span>`);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function fetchJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function panel(title, inner, bad = false) {
  return `<div class="panel ${bad ? "bad" : ""}"><h3>${esc(title)}</h3><div class="body">${inner}</div></div>`;
}
function panelErr(title, msg) {
  return panel(title, `<div class="err">unavailable — ${esc(msg || "no data")}</div>`, true);
}

// ---- renderers -------------------------------------------------------------
function renderMacro(env) {
  const d = env.data || {};
  const out = [];

  // Rates
  const r = d.rates || {};
  if (r.ok) {
    const curve = (r.curve || []).map((p) => `<tr><td>${esc(p.maturity)}</td><td>${num(p.rate_pct, 2)}%</td></tr>`).join("");
    out.push(panel("Rates / Yield Curve", `
      <div class="tiles">
        <div class="tile"><div class="label">2Y</div><div class="value">${num(r.two_year_pct, 2)}%</div></div>
        <div class="tile"><div class="label">10Y</div><div class="value">${num(r.ten_year_pct, 2)}%</div></div>
        <div class="tile"><div class="label">2s10s</div><div class="value ${pctCls(r.spread_2s10s_bps)}">${num(r.spread_2s10s_bps, 1)} bps</div></div>
      </div>
      <table style="margin-top:10px"><thead><tr><th>Maturity</th><th>Rate</th></tr></thead><tbody>${curve}</tbody></table>`));
  } else out.push(panelErr("Rates / Yield Curve", r.error));

  // Dollar & FX
  const fx = d.dollar_fx || {};
  if (fx.ok) {
    const row = (lbl, o) => o ? `<tr><td>${lbl}</td><td>${num(o.value, 4)}</td><td>${pct(o.change_1d_pct)}</td><td>${pct(o.change_1w_pct)}</td><td>${pct(o.change_1m_pct)}</td></tr>` : "";
    out.push(panel("Dollar & FX", `
      <table><thead><tr><th></th><th>Last</th><th>1d</th><th>1w</th><th>1m</th></tr></thead><tbody>
      ${row("Broad USD", fx.dollar_index)}${row("EUR/USD", fx.eurusd)}${row("GBP/USD", fx.gbpusd)}
      </tbody></table>`));
  } else out.push(panelErr("Dollar & FX", fx.error));

  // Macro tiles
  const mt = d.macro_tiles || {};
  if (mt.ok) {
    const tiles = (mt.tiles || []).map((t) => `<div class="tile"><div class="label">${esc(t.label)}</div><div class="value">${num(t.value, 2)}<span style="font-size:12px"> ${esc(t.unit || "")}</span></div><div class="sub">${esc(t.as_of || "")}</div></div>`).join("");
    out.push(panel("Macro Tiles", `<div class="tiles">${tiles}</div>`));
  } else out.push(panelErr("Macro Tiles", mt.error));

  // Indices
  const ix = d.indices || {};
  if (ix.ok) {
    const rows = Object.entries(ix.indices || {}).map(([sym, o]) => `<tr><td>${esc(o.label || sym)}</td><td>${num(o.value, 2)}</td><td>${pct(o.change_1d_pct)}</td><td>${pct(o.change_1w_pct)}</td><td>${pct(o.change_1m_pct)}</td></tr>`).join("");
    out.push(panel("Index Levels", `<table><thead><tr><th></th><th>Last</th><th>1d</th><th>1w</th><th>1m</th></tr></thead><tbody>${rows}</tbody></table>`));
  } else out.push(panelErr("Index Levels", ix.error));

  // Calendar
  const cal = d.calendar || {};
  if (cal.ok) {
    const evs = (cal.events || []).slice(0, 12).map((e) => `<tr><td>${esc(e.date || "")}</td><td>${esc(e.event || "")}</td><td>${esc(e.country || "")}</td></tr>`).join("");
    out.push(panel("Economic Calendar", evs ? `<table><tbody>${evs}</tbody></table>` : '<div class="dim">no events</div>'));
  } else out.push(panelErr("Economic Calendar (needs paid provider)", cal.error));

  return `<div class="grid">${out.join("")}</div>`;
}

function renderWatchlist(env) {
  const d = env.data || {};
  const rows = Object.values(d).map((i) => {
    if (!i.ok) return `<tr><td>${esc(i.code)}</td><td colspan="6" class="err">${esc(i.error)}</td></tr>`;
    const f = i.future || {};
    const p = i.proxy || {};
    const proxy = p.ok === false ? '<span class="dim">—</span>' : `${esc(p.name)}: ${num(p.close, 4)} ${pct(p.change_1d_pct)}`;
    return `<tr>
      <td>${esc(i.code)} <span class="dim">${esc(i.name)}</span></td>
      <td>${num(f.close, 4)}</td><td>${pct(f.change_1d_pct)}</td><td>${pct(f.change_1w_pct)}</td><td>${pct(f.change_1m_pct)}</td>
      <td>${num(i.atr_14, 4)} <span class="dim">(${num(i.atr_14_pct, 2)}%)</span></td>
      <td style="text-align:left">${proxy}</td></tr>`;
  }).join("");
  return panel("Watchlist — futures + spot proxy", `<table><thead><tr><th>Instrument</th><th>Close</th><th>1d</th><th>1w</th><th>1m</th><th>ATR(14)</th><th>Proxy</th></tr></thead><tbody>${rows}</tbody></table>`);
}

function renderCot(env) {
  const d = env.data || {};
  const cards = Object.values(d).map((c) => {
    if (!c.ok) return panelErr(`${c.code || ""} ${c.name || ""}`, c.error);
    const nc = c.non_commercial || {};
    const cm = c.commercial || {};
    const r1y = nc.range_1y || {};
    const pos = r1y.percentile_in_range;
    return panel(`${esc(c.name)} — ${esc(c.contract || "")}`, `
      <div class="tiles">
        <div class="tile"><div class="label">Non-comm net (specs)</div><div class="value ${pctCls(nc.net)}">${num(nc.net, 0)}</div><div class="sub">1w ${nc.net_change_1w > 0 ? "+" : ""}${num(nc.net_change_1w, 0)}</div></div>
        <div class="tile"><div class="label">Commercial net (hedgers)</div><div class="value ${pctCls(cm.net)}">${num(cm.net, 0)}</div><div class="sub">1w ${cm.net_change_1w > 0 ? "+" : ""}${num(cm.net_change_1w, 0)}</div></div>
      </div>
      <div class="sub" style="margin-top:10px">Specs net vs 1y range ${pos === null || pos === undefined ? "" : "(" + num(pos, 0) + "%)"}</div>
      <div class="bar"><span style="left:${Math.max(0, Math.min(100, pos || 0))}%"></span></div>
      <div class="sub" style="margin-top:4px">report ${esc(c.report_date || "")} · ${num(c.history_weeks, 0)} wks</div>`);
  }).join("");
  return `<div class="grid">${cards}</div>`;
}

function renderTerm(env) {
  const d = env.data || {};
  const cards = Object.values(d).map((t) => {
    if (!t.ok) return panelErr(`${t.code || ""} ${t.name || ""}`, t.error);
    const isVix = t.code === "VIX";
    const sig = t.fear_signal ? `<span class="pill ${t.structure === "backwardation" ? "red" : "green"}">${esc(t.fear_signal)}</span>` : "";
    const struct = `<span class="pill ${t.structure === "contango" ? (isVix ? "green" : "amber") : "red"}">${esc(t.structure)}</span>`;
    const curve = (t.curve || []).map((p) => `<tr><td>${esc(p.expiration)}</td><td>${num(p.price, 2)}</td></tr>`).join("");
    return panel(`${esc(t.name)}`, `
      <div>${struct} ${sig}</div>
      <div class="tiles" style="margin-top:10px">
        <div class="tile"><div class="label">Front ${esc(t.front_expiration || "")}</div><div class="value">${num(t.front_price, 2)}</div></div>
        <div class="tile"><div class="label">Back ${esc(t.back_expiration || "")}</div><div class="value">${num(t.back_price, 2)}</div></div>
        <div class="tile"><div class="label">Spread</div><div class="value">${pct(t.front_back_spread_pct)}</div></div>
      </div>
      <table style="margin-top:10px"><tbody>${curve}</tbody></table>`);
  }).join("");
  return `<div class="grid">${cards}</div>`;
}

function renderSectors(env) {
  const d = env.data || {};
  const secs = d.sectors || [];
  const max = Math.max(1, ...secs.map((s) => Math.abs(s.change_1w_pct || 0)));
  const bars = secs.map((s) => {
    const v = s.change_1w_pct || 0;
    const w = (Math.abs(v) / max) * 50; // half-width = 50%
    const color = v >= 0 ? "var(--green)" : "var(--red)";
    const side = v >= 0 ? `left:50%;width:${w}%` : `right:50%;width:${w}%`;
    return `<div class="rot"><div class="name">${esc(s.sector)} <span class="dim">${esc(s.etf)}</span></div>
      <div class="track"><div class="fill" style="${side};background:${color}"></div></div>
      <div class="pct">${pct(v)}</div></div>`;
  }).join("");
  const head = `<div class="sub" style="margin-bottom:8px">Leaders: <span class="up">${(d.leaders || []).map(esc).join(", ")}</span> · Laggards: <span class="down">${(d.laggards || []).map(esc).join(", ")}</span> · ranked by 1-week</div>`;
  return panel("Sector Rotation (1-week)", head + bars);
}

function renderNews(env) {
  const d = env.data || {};
  const items = (d.headlines || []).map((h) => `<div class="news-item">
    <a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a>
    <div class="news-meta"><span>${esc((h.date || "").slice(0, 16))}</span><span>${esc(h.source || "")}</span>${(h.tags || []).map((t) => `<span class="pill">${esc(t)}</span>`).join("")}</div>
  </div>`).join("");
  return panel(`News — ${num(d.count, 0)} headlines`, items || '<div class="dim">no headlines</div>');
}

const RENDERERS = { macro: renderMacro, watchlist: renderWatchlist, cot: renderCot, term: renderTerm, sectors: renderSectors, news: renderNews };

// ---- loading + tabs --------------------------------------------------------
async function loadView(view) {
  const sec = $(`#view-${view}`);
  try {
    const env = await fetchJSON(ENDPOINTS[view]);
    if (env.ok === false) { sec.innerHTML = `<div class="err">${esc(env.error || "request failed")}</div>`; return; }
    sec.innerHTML = RENDERERS[view](env);
    if (env.freshness) $("#freshness").textContent = env.freshness;
  } catch (e) {
    sec.innerHTML = `<div class="err">failed to load: ${esc(e.message)}</div>`;
  }
}

// Execution tab: frames the SEPARATE OpenAlice app (the execution "hand"). The
// terminal stays research-only — it just hosts a window to Alice; no order logic
// lives here. The URL comes from the backend (/health → alice_url).
async function loadExecution() {
  const sec = $("#view-execution");
  let url = "http://localhost:5173";
  try { url = (await fetchJSON("/health")).alice_url || url; } catch (e) { /* keep default */ }
  sec.innerHTML = `
    <div class="exec-bar">
      <span>Execution runs in <b>OpenAlice</b> — a separate app. Research flows out via MCP; orders stay there.</span>
      <a class="btn" href="${esc(url)}" target="_blank" rel="noopener">Open Alice ↗</a>
    </div>
    <iframe class="exec-frame" src="${esc(url)}" title="OpenAlice"></iframe>
    <div class="exec-help dim">Not loading? Make sure OpenAlice is running (<code>pnpm dev</code>) and reachable at
      <a href="${esc(url)}" target="_blank" rel="noopener">${esc(url)}</a>. Some apps block embedding — use the "Open Alice ↗" button.</div>`;
}

// Analysis tab: interpreted signals (regime + COT positioning). Fetches both
// /analysis endpoints and renders the read — research context, not a signal.
function _regimeCls(label) {
  if (!label) return "dim";
  if (label.startsWith("risk-on")) return "up";
  if (label.startsWith("risk-off")) return "down";
  return "dim";
}
function _renderBrief(d) {
  if (!d || d.code === undefined) return '<div class="err">no data</div>';
  const p = d.price || {}, c = d.cot || {}, t = d.term_structure, r = d.regime || {};
  const posCls = c.positioning === "crowded long" ? "red" : c.positioning === "crowded short" ? "green" : "";
  const news = (d.news || []).map((h) =>
    `<div class="news-item"><a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a>
     <div class="news-meta"><span>${esc((h.date || "").slice(0, 16))}</span><span>${esc(h.source || "")}</span></div></div>`).join("");
  return `
    <div style="font-size:14px;margin-bottom:10px"><b>${esc(d.read || "")}</b></div>
    <div class="tiles">
      <div class="tile"><div class="label">Regime</div><div class="value ${_regimeCls(r.regime)}">${esc(r.regime || "—")}</div></div>
      <div class="tile"><div class="label">Close</div><div class="value">${num(p.close, 4)}</div><div class="sub">1w ${pct(p.change_1w_pct)}</div></div>
      <div class="tile"><div class="label">ATR(14)</div><div class="value">${num(p.atr_14_pct, 2)}%</div></div>
      ${c.positioning && c.positioning !== "n/a" ? `<div class="tile"><div class="label">COT</div><div class="value"><span class="pill ${posCls}">${esc(c.positioning)}</span></div><div class="sub">${num(c.percentile_1y, 0)}th pct 1y</div></div>` : ""}
      ${t && t.structure ? `<div class="tile"><div class="label">Curve</div><div class="value">${esc(t.structure)}</div><div class="sub">${pct(t.front_back_spread_pct)}</div></div>` : ""}
    </div>
    ${c.bias ? `<div class="sub" style="margin-top:8px">COT: ${esc(c.bias)}${c.weekly_shift && c.weekly_shift !== "n/a" ? " · " + esc(c.weekly_shift) : ""}</div>` : ""}
    ${news ? `<div style="margin-top:10px">${news}</div>` : '<div class="dim" style="margin-top:10px">no tagged news</div>'}`;
}

async function loadBrief(code) {
  const body = document.getElementById("brief-body");
  if (!body) return;
  body.innerHTML = `<div class="loading">Loading ${esc(code)} brief…</div>`;
  try {
    const env = await fetchJSON("/analysis/brief?instrument=" + encodeURIComponent(code));
    if (env.ok === false) { body.innerHTML = `<div class="err">${esc(env.error || "failed")}</div>`; return; }
    body.innerHTML = _renderBrief(env.data || {});
  } catch (e) {
    body.innerHTML = `<div class="err">failed: ${esc(e.message)}</div>`;
  }
}

async function loadAnalysis() {
  const sec = $("#view-analysis");
  let regime = {}, cot = {};
  try { regime = (await fetchJSON("/analysis/regime")).data || {}; } catch (e) { /* degrade */ }
  try { cot = (await fetchJSON("/analysis/cot")).data || {}; } catch (e) { /* degrade */ }

  const rsig = (regime.signals || []).map((s) =>
    `<tr><td>${esc(s.name)}</td><td>${esc(s.reading)}</td><td class="${_regimeCls(s.leans)}">${esc(s.leans)}</td></tr>`).join("");
  const regimePanel = panel("Macro Regime", `
    <div class="tiles"><div class="tile"><div class="label">Regime</div>
      <div class="value ${_regimeCls(regime.regime)}">${esc(regime.regime || "—")}</div>
      <div class="sub">score ${num(regime.score, 0)}</div></div></div>
    <table style="margin-top:10px"><thead><tr><th>Signal</th><th>Reading</th><th>Leans</th></tr></thead><tbody>${rsig}</tbody></table>
    <div class="exec-help dim">${esc(regime.method || "")}</div>`);

  const rows = Object.entries(cot.signals || {}).map(([code, s]) => {
    if (!s.ok) return `<tr><td>${esc(code)}</td><td colspan="5" class="err">${esc(s.error || "n/a")}</td></tr>`;
    const posCls = s.positioning === "crowded long" ? "down" : s.positioning === "crowded short" ? "up" : "dim";
    return `<tr><td>${esc(code)} <span class="dim">${esc(s.name || "")}</span></td>
      <td>${num(s.non_commercial_net, 0)}</td><td>${num(s.percentile_1y, 0)}%</td>
      <td><span class="pill ${posCls === "down" ? "red" : posCls === "up" ? "green" : ""}">${esc(s.positioning)}</span></td>
      <td style="text-align:left">${esc(s.weekly_shift)}</td>
      <td style="text-align:left">${esc(s.bias)}</td></tr>`;
  }).join("");
  const extremes = (cot.extremes || []).length
    ? `<div class="sub" style="margin-bottom:8px">Extremes: <b class="amber">${(cot.extremes).map(esc).join(", ")}</b></div>` : "";
  const cotPanel = panel("COT Positioning Signals", extremes +
    `<table><thead><tr><th>Instrument</th><th>NC net</th><th>1y %ile</th><th>Positioning</th><th>Weekly shift</th><th>Bias</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="exec-help dim">${esc(cot.method || "")}</div>`);

  const briefPanel = panel("Instrument Brief — what's moving this contract", `
    <select id="brief-pick" class="btn">${["6E", "6B", "GC", "NQ", "YM"].map((k) => `<option${k === "GC" ? " selected" : ""}>${k}</option>`).join("")}</select>
    <div id="brief-body" style="margin-top:10px"></div>`);

  sec.innerHTML = `<div class="grid" style="grid-template-columns:1fr">${briefPanel}${regimePanel}${cotPanel}</div>
    <div class="exec-help dim" style="margin-top:8px">${esc(regime.disclaimer || cot.disclaimer || "")}</div>`;

  const pick = document.getElementById("brief-pick");
  if (pick) pick.addEventListener("change", () => loadBrief(pick.value));
  loadBrief(pick ? pick.value : "GC");
}

// Lazy loading: only fetch the visible tab; fetch others when first opened (by
// then the background pre-cache has usually warmed them, so they appear fast).
const loaded = new Set();
let active = "macro";

function _loadFor(view) {
  if (view === "execution") return loadExecution();
  if (view === "analysis") return loadAnalysis();
  return loadView(view);
}

async function showView(view) {
  active = view;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  if (!loaded.has(view)) {
    loaded.add(view);
    $("#status").textContent = `loading ${view}…`;
    await _loadFor(view);
    $("#status").textContent = "updated " + new Date().toLocaleTimeString();
  }
}

async function refreshActive() {
  $("#status").textContent = "refreshing…";
  await _loadFor(active);
  loaded.add(active);
  $("#status").textContent = "updated " + new Date().toLocaleTimeString();
}

function initTabs() {
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => showView(tab.dataset.view)));
}

function tick() { $("#clock").textContent = new Date().toUTCString().slice(17, 25) + " UTC"; }

initTabs();
$("#refresh").addEventListener("click", refreshActive);
setInterval(tick, 1000); tick();
showView("macro"); // initial load = visible tab only
setInterval(() => loaded.forEach(_loadFor), 10 * 60 * 1000); // refresh opened tabs every 10 min
